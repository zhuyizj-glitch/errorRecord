"""薄弱点聚合与真题推荐（v2.0）

匹配策略：知识点归一化后精确匹配。
导入真题时已把库内词汇表注入提示词（build_exam_prompt），
让 AI 尽量复用标签，从源头提高匹配率。
"""

import re
from typing import Optional


def normalize_kp(text: str) -> str:
    """知识点标签归一化：去首尾空白、合并连续空白。

    不做同义词扩展——「方程」这类宽泛词会过度匹配，
    宁缺毋滥，匹配不上的薄弱点显式暴露给家长。
    """
    return re.sub(r"\s+", " ", (text or "").strip())


def collect_weak_points(questions: list[dict]) -> list[dict]:
    """聚合孩子的薄弱知识点。

    只统计未掌握的错题（mastery_status != mastered）；
    每个知识点的薄弱度权重 = Σ(1 − mastery_score/100)，
    错得越多、掌握度越低，权重越大。
    """
    agg: dict[str, dict] = {}
    for q in questions:
        if q.get("mastery_status") == "mastered":
            continue
        weight = 1.0 - min(100, max(0, int(q.get("mastery_score", 0)))) / 100.0
        for raw in q.get("knowledge_points") or []:
            kp = normalize_kp(raw)
            if not kp:
                continue
            entry = agg.setdefault(kp, {
                "knowledge_point": kp, "weight": 0.0,
                "question_count": 0, "mastery_sum": 0,
            })
            entry["weight"] += weight
            entry["question_count"] += 1
            entry["mastery_sum"] += int(q.get("mastery_score", 0))

    result = []
    for entry in agg.values():
        count = entry["question_count"]
        result.append({
            "knowledge_point": entry["knowledge_point"],
            "weight": round(entry["weight"], 2),
            "question_count": count,
            "avg_mastery": round(entry["mastery_sum"] / count, 1) if count else 0,
        })
    result.sort(key=lambda x: (-x["weight"], -x["question_count"], x["knowledge_point"]))
    return result


def knowledge_vocab(questions: list[dict], zhenti: list[dict]) -> list[str]:
    """库内已有知识点词汇表（去重、归一化），供导入提示词注入。

    错题标签优先（它们是薄弱点匹配的目标），真题标签补充。
    """
    seen: dict[str, None] = {}
    for source in (questions, zhenti):
        for item in source:
            for raw in item.get("knowledge_points") or []:
                kp = normalize_kp(raw)
                if kp:
                    seen.setdefault(kp, None)
    return list(seen.keys())


def child_practice_count(zhenti_item: dict, child_id: str) -> int:
    """某个孩子对这道真题的练习次数（练习历史按孩子记录）"""
    return sum(
        1 for record in zhenti_item.get("practice_history") or []
        if record.get("child_id") == child_id
    )


def recommend(
    weak_points: list[dict],
    zhenti: list[dict],
    child_id: str,
    *,
    subject: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """按薄弱点权重给真题打分排序。

    得分 = 命中薄弱点的权重和；
    同分：该孩子练得少的优先，再按年份新的优先。
    零分（完全不匹配）的真题不推荐。
    """
    weight_by_kp = {w["knowledge_point"]: w["weight"] for w in weak_points}
    scored = []
    for item in zhenti:
        if subject and item.get("subject") != subject:
            continue
        matched = []
        score = 0.0
        for raw in item.get("knowledge_points") or []:
            kp = normalize_kp(raw)
            if kp in weight_by_kp:
                matched.append(kp)
                score += weight_by_kp[kp]
        if score <= 0:
            continue
        scored.append({
            **{k: v for k, v in item.items() if not k.startswith("_")},
            "match_score": round(score, 2),
            "matched_points": matched,
            "child_practice_count": child_practice_count(item, child_id),
        })

    def sort_key(item: dict):
        year = str(item.get("year") or "")
        year_rank = -int(year) if year.isdigit() else 0
        return (-item["match_score"], item["child_practice_count"], year_rank)

    scored.sort(key=sort_key)
    return scored[:limit]
