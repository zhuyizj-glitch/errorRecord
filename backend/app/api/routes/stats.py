"""统计分析路由"""

from datetime import date, timedelta
from collections import defaultdict
from fastapi import APIRouter, Query, Path
from typing import Optional

from app.services import file_ops

router = APIRouter()


@router.get("/stats/overview")
async def get_overview(child: str = Query(...)):
    """获取总览统计"""
    questions = file_ops.list_questions(child)

    total = len(questions)
    if total == 0:
        return {
            "total": 0,
            "by_subject": {},
            "by_mastery_level": {"low": 0, "medium": 0, "high": 0},
            "by_error_type": {},
            "recent_trend": [],
            "due_for_review": 0,
            "avg_mastery_score": 0,
        }

    # 按学科统计
    by_subject = defaultdict(int)
    for q in questions:
        by_subject[q.get("subject", "其他")] += 1

    # 按掌握度统计
    by_mastery = {"low": 0, "medium": 0, "high": 0}
    total_score = 0
    for q in questions:
        level = q.get("mastery_level", "medium")
        by_mastery[level] = by_mastery.get(level, 0) + 1
        total_score += q.get("mastery_score", 0)

    # 按错误类型统计
    by_error_type = defaultdict(int)
    for q in questions:
        et = q.get("error_type")
        if et:
            by_error_type[et] += 1

    # 最近 7 天趋势
    today = date.today()
    recent_trend = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        count = sum(1 for q in questions if q.get("created_at") == d.isoformat())
        recent_trend.append({"date": d.isoformat(), "count": count})

    # 待复习数量
    due_for_review = sum(
        1 for q in questions
        if q.get("next_review_date") and q.get("next_review_date") <= today.isoformat()
    )

    return {
        "total": total,
        "by_subject": dict(by_subject),
        "by_mastery_level": by_mastery,
        "by_error_type": dict(by_error_type),
        "recent_trend": recent_trend,
        "due_for_review": due_for_review,
        "avg_mastery_score": round(total_score / total, 1) if total > 0 else 0,
    }


@router.get("/stats/subject/{subject}")
async def get_subject_stats(
    subject: str = Path(...),
    child: str = Query(...),
):
    """获取某学科详细统计"""
    questions = file_ops.list_questions(child, subject)

    # 知识点掌握度
    kp_stats = defaultdict(lambda: {"total": 0, "mastered": 0, "avg_score": 0, "scores": []})
    for q in questions:
        for kp in q.get("knowledge_points", []):
            kp_stats[kp]["total"] += 1
            score = q.get("mastery_score", 0)
            kp_stats[kp]["scores"].append(score)
            if q.get("mastery_level") == "high":
                kp_stats[kp]["mastered"] += 1

    # 计算平均分
    for kp, data in kp_stats.items():
        if data["scores"]:
            data["avg_score"] = round(sum(data["scores"]) / len(data["scores"]), 1)
        del data["scores"]  # 不返回原始分数列表

    # 错误类型分布
    error_types = defaultdict(int)
    for q in questions:
        et = q.get("error_type")
        if et:
            error_types[et] += 1

    # 重复犯错统计
    repeat_count = sum(1 for q in questions if q.get("repeat_pattern"))

    return {
        "subject": subject,
        "total": len(questions),
        "knowledge_points": dict(kp_stats),
        "error_types": dict(error_types),
        "repeat_error_count": repeat_count,
    }


@router.get("/stats/weak-points")
async def get_weak_points(
    child: str = Query(...),
    limit: int = Query(default=10),
):
    """获取薄弱知识点 TOP N"""
    questions = file_ops.list_questions(child)

    kp_scores = defaultdict(list)
    for q in questions:
        for kp in q.get("knowledge_points", []):
            kp_scores[kp].append(q.get("mastery_score", 0))

    # 计算每个知识点的平均掌握度
    kp_avg = []
    for kp, scores in kp_scores.items():
        avg = sum(scores) / len(scores) if scores else 0
        kp_avg.append({
            "knowledge_point": kp,
            "avg_score": round(avg, 1),
            "question_count": len(scores),
        })

    # 按平均分升序排列（最薄弱的在前）
    kp_avg.sort(key=lambda x: x["avg_score"])
    return {"weak_points": kp_avg[:limit]}
