"""薄弱点聚合与真题推荐（v2.0 · 三形态 + 时代/主题轴）

匹配策略：
- 独立小题与材料组/语篇的子题：知识点归一化精确匹配（子题可独立调用）
- 历史按 era（朝代/时期）、政治按 module（主题）支持专项切片
- 语篇整题（passage）按「题型 + 评级梯度」推荐，不做顶层知识点匹配
"""

import re
from typing import Optional


def normalize_kp(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def collect_weak_points(questions: list[dict]) -> list[dict]:
    """聚合孩子未掌握错题的薄弱知识点（权重 = Σ(1−掌握度/100)）"""
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
    """库内已有知识点词汇表（含子题标签），供导入提示词注入"""
    seen: dict[str, None] = {}
    for item in questions:
        for raw in item.get("knowledge_points") or []:
            kp = normalize_kp(raw)
            if kp:
                seen.setdefault(kp, None)
    for item in zhenti:
        for raw in item.get("knowledge_points") or []:
            kp = normalize_kp(raw)
            if kp:
                seen.setdefault(kp, None)
        for sub in item.get("sub_questions") or []:
            for raw in sub.get("knowledge_points") or []:
                kp = normalize_kp(raw)
                if kp:
                    seen.setdefault(kp, None)
    return list(seen.keys())


def child_practice_count(zhenti_item: dict, child_id: str) -> int:
    return sum(
        1 for r in zhenti_item.get("practice_history") or []
        if r.get("child_id") == child_id
    )


def matchable_units(item: dict) -> list[dict]:
    """把一道真题展开为可匹配单元。

    independent → 顶层自身；material_group/passage → 各子题（带父题引用）。
    每个单元含 knowledge_points / era / module，供知识点与维度匹配。
    """
    form = item.get("question_form", "independent")
    if form == "independent" or not item.get("sub_questions"):
        return [{
            "kp": item.get("knowledge_points") or [],
            "era": item.get("era"),
            "module": item.get("module"),
            "sub_number": None,
        }]
    return [{
        "kp": sub.get("knowledge_points") or [],
        "era": sub.get("era") or item.get("era"),
        "module": sub.get("module") or item.get("module"),
        "sub_number": sub.get("number"),
    } for sub in item["sub_questions"]]


def recommend(
    weak_points: list[dict],
    zhenti: list[dict],
    child_id: str,
    *,
    subject: Optional[str] = None,
    era: Optional[str] = None,
    module: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """按薄弱点权重给真题打分（子题级匹配）。

    得分 = 命中薄弱点的权重和（跨子题累加）；
    同分：该孩子练得少优先，再按年份新优先。零分不推荐。
    era/module 为专项切片过滤（历史按朝代、政治按主题）。
    """
    weight_by_kp = {w["knowledge_point"]: w["weight"] for w in weak_points}
    scored = []
    for item in zhenti:
        if subject and item.get("subject") != subject:
            continue
        matched: list[str] = []
        matched_subs: list[str] = []
        score = 0.0
        for unit in matchable_units(item):
            if era and unit["era"] != era:
                continue
            if module and unit["module"] != module:
                continue
            hit = False
            for raw in unit["kp"]:
                kp = normalize_kp(raw)
                if kp in weight_by_kp:
                    if kp not in matched:
                        matched.append(kp)
                    score += weight_by_kp[kp]
                    hit = True
            if hit and unit["sub_number"]:
                matched_subs.append(str(unit["sub_number"]))
        if score <= 0:
            continue
        scored.append({
            **{k: v for k, v in item.items() if not k.startswith("_")},
            "match_score": round(score, 2),
            "matched_points": matched,
            "matched_sub_numbers": matched_subs,
            "child_practice_count": child_practice_count(item, child_id),
        })

    def sort_key(x):
        year = str(x.get("year") or "")
        return (-x["match_score"], x["child_practice_count"], -int(year) if year.isdigit() else 0)

    scored.sort(key=sort_key)
    return scored[:limit]


def list_passages(
    zhenti: list[dict],
    *,
    subject: Optional[str] = None,
    question_type: Optional[str] = None,
) -> list[dict]:
    """语篇整题按「题型 + 评级梯度」列出（语文英语整篇练习用）。

    评级排序：简单→中等→较难（难度递进）；同评级年份新优先。
    """
    order = {"简单": 0, "中等": 1, "较难": 2}
    items = [
        {k: v for k, v in i.items() if not k.startswith("_")}
        for i in zhenti
        if i.get("question_form") == "passage"
        and (not subject or i.get("subject") == subject)
        and (not question_type or i.get("question_type") == question_type)
    ]
    items.sort(key=lambda x: (order.get(x.get("rating") or "中等", 1),
                              -int(str(x.get("year") or 0)) if str(x.get("year") or "").isdigit() else 0))
    return items
