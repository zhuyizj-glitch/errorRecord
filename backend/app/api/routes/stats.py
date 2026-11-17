"""统计分析路由"""

from datetime import date, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Optional

from app.core import timeutil
from app.services import file_ops
from app.api.deps import get_active_account, get_auth_service
from app.models.auth import Account
from app.services.auth_service import AuthService

router = APIRouter()


def _require_child(auth: AuthService, account_id: str, child_id: str):
    with auth.db.connect() as connection:
        child = connection.execute(
            "SELECT 1 FROM children WHERE id = ? AND account_id = ?",
            (child_id, account_id),
        ).fetchone()
    if not child:
        raise HTTPException(status_code=404, detail="孩子不存在")


def _num(value, default=None):
    """把可能被 IMA 改写成字符串的数值转回来。

    IMA 会改写笔记内容，YAML 里的数字有可能回来是 "42" 这样的字符串；
    直接拿去做算术会 TypeError，所以统一在这里收口。
    """
    if isinstance(value, bool) or value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _attempt_count(q: dict) -> int:
    """这道题被重做过几次。

    ⚠️ 用它来区分「没做过」和「做错了」—— 两者的 mastery_score 都是 0，光看分
    数分不出来：
      · 刚录入、从没重做过的题 → 0 分，但它不代表薄弱，只代表「还没有数据」
      · 重做全错的题           → 也是 0 分，这是真的薄弱

    统计里把这两者混在一起，就会出现「一个新录入、一次还没练过的知识点
    霸占最薄弱榜首」——这正是本次要修的问题。

    redo_count 与 total_reviews 历史上有过分叉，取较大值更稳。
    """
    return int(max(_num(q.get("redo_count"), 0), _num(q.get("total_reviews"), 0)))


@router.get("/stats/overview")
async def get_overview(
    child_id: str = Query(...),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """获取总览统计"""
    _require_child(auth, account.id, child_id)
    questions = file_ops.list_questions(account.id, child_id)

    # 已摸底（重做过至少一次）与从未重做过的，分开统计。
    # 新题的 mastery_score 恒为 0，混进平均分会把「平均掌握度」拉低 ——
    # 而它其实只是「还没测」，不是「掌握得差」。
    attempted = [q for q in questions if _attempt_count(q) > 0]

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
            "attempted_total": 0,
            "untested_total": 0,
        }

    # 按学科统计
    by_subject = defaultdict(int)
    for q in questions:
        by_subject[q.get("subject", "其他")] += 1

    # 按掌握度统计
    by_mastery = {"low": 0, "medium": 0, "high": 0}
    for q in questions:
        level = q.get("mastery_level", "medium")
        by_mastery[level] = by_mastery.get(level, 0) + 1

    # 按错误类型统计
    by_error_type = defaultdict(int)
    for q in questions:
        et = q.get("error_type")
        if et:
            by_error_type[et] += 1

    # 最近 7 天趋势
    today = timeutil.today()
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
        # ⚠️ 语义变化：只对**已摸底**的题求平均。前端若拿它和 total 相除要注意口径。
        "avg_mastery_score": round(
            sum(_num(q.get("mastery_score"), 0) for q in attempted) / len(attempted), 1
        ) if attempted else 0,
        "attempted_total": len(attempted),
        "untested_total": total - len(attempted),
    }


@router.get("/stats/subject/{subject}")
async def get_subject_stats(
    subject: str = Path(...),
    child_id: str = Query(...),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """获取某学科详细统计"""
    _require_child(auth, account.id, child_id)
    questions = file_ops.list_questions(account.id, child_id, subject)

    # 知识点掌握度
    #
    # 与 /stats/weak-points 保持同一口径：均分只统计**已摸底**的题。
    # 否则同一个知识点在这两个接口上会给出不同的分数，家长会以为是 bug。
    kp_stats = defaultdict(
        lambda: {"total": 0, "mastered": 0, "rated_count": 0, "untested_count": 0, "scores": []}
    )
    for q in questions:
        kps = q.get("knowledge_points") or []
        if isinstance(kps, str):  # IMA 改写可能把列表写成字符串
            kps = [kps]
        for kp in kps:
            if not (isinstance(kp, str) and kp.strip()):
                continue
            key = kp.strip()
            kp_stats[key]["total"] += 1
            if _attempt_count(q) > 0:
                kp_stats[key]["rated_count"] += 1
                kp_stats[key]["scores"].append(_num(q.get("mastery_score"), 0))
                if q.get("mastery_level") == "high":
                    kp_stats[key]["mastered"] += 1
            else:
                kp_stats[key]["untested_count"] += 1

    # 计算平均分（该知识点还没有任何已摸底的题时为 None）
    for data in kp_stats.values():
        scores = data.pop("scores")  # 不返回原始分数列表
        data["avg_score"] = round(sum(scores) / len(scores), 1) if scores else None

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
    child_id: str = Query(...),
    limit: int = Query(default=10, ge=1, le=50),
    min_rated: int = Query(default=1, ge=0, description="参与均分所需的最少重做次数"),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """获取薄弱知识点 TOP N

    ⚠️ 只统计**已摸底**的题（重做过至少 min_rated 次）。

    原实现把所有题（含从未重做的题）一起平均，而那些题的 mastery_score 恒为 0
    （新题与全错题在分数上不可区分），结果是「刚录入一批新题的知识点」均分被
    打到个位数、霸占最薄弱榜首 —— 而它其实只是「还没有数据」。

    现在把「未知」与「薄弱」拆开：前者进 untested_points，**不参与排名**，
    并以 avg_score=None 表示（用 0 会重现"没练过显示成最薄弱"的老问题）。
    """
    _require_child(auth, account.id, child_id)
    questions = file_ops.list_questions(account.id, child_id)

    buckets: dict[str, list[dict]] = defaultdict(list)
    for q in questions:
        kps = q.get("knowledge_points") or []
        if isinstance(kps, str):  # IMA 改写可能把列表写成字符串
            kps = [kps]
        for kp in kps:
            if isinstance(kp, str) and kp.strip():
                buckets[kp.strip()].append(q)

    rated_rows: list[dict] = []
    untested_rows: list[dict] = []

    for kp, qs in buckets.items():
        graded = [q for q in qs if _attempt_count(q) >= min_rated]
        row = {
            "knowledge_point": kp,
            "question_count": len(qs),
            "rated_count": len(graded),
            "untested_count": len(qs) - len(graded),
            "wrong_total": sum(int(_num(q.get("wrong_count"), 0)) for q in qs),
        }
        if graded:
            row["avg_score"] = round(
                sum(_num(q.get("mastery_score"), 0) for q in graded) / len(graded), 1
            )
            row["last_rated_at"] = max(
                (str(q.get("last_redo_at") or "") for q in graded), default=""
            )
            rated_rows.append(row)
        else:
            # 没摸过底的知识点：avg_score 用 None 而不是 0（用 0 会重现
            # "没练过显示成最薄弱"的老问题）
            row["avg_score"] = None
            untested_rows.append(row)

    # ⚠️ 必须分成两个列表各自排序。
    # 若把 avg_score=None 的项混进同一个列表再 sort，Python 会拿 None 与 float
    # 比较，直接 TypeError → 接口 500。这是本次改动最容易踩的坑。
    rated_rows.sort(key=lambda r: (r["avg_score"], -r["wrong_total"]))
    untested_rows.sort(key=lambda r: -r["untested_count"])

    return {
        "weak_points": rated_rows[:limit],
        "untested_points": untested_rows[:limit],
        "rated_total": len(rated_rows),
        "untested_total": len(untested_rows),
    }
