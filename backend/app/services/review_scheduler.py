"""间隔复习计划计算

⚠️ 「今天」一律用 timeutil.today()（北京时间），不要用 date.today()。
   后端跑在 Docker 容器里，容器默认 UTC；北京时间 00:00–08:00 之间
   date.today() 会得到前一天，导致那段时间的复习计划错算。
   详见 app/core/timeutil.py 的说明。
"""

from datetime import date, timedelta

from app.core import timeutil


def calculate_next_review(mastery_level: str, redo_result: str, current_interval: int) -> tuple[date, int]:
    """
    计算下次复习日期和新的间隔天数

    规则：
    - low（薄弱）：每天，间隔保持 1 天
    - medium（待加强）：重做对 → 间隔 ×1.5；重做错 → 间隔重置为 1
    - high（已掌握）：重做对 → 间隔 ×2；重做错 → 间隔重置为 3
    """
    if mastery_level == "low":
        interval = 1
    elif mastery_level == "medium":
        if redo_result == "correct":
            interval = max(1, int(current_interval * 1.5))
        else:
            interval = 1
    else:  # high
        if redo_result == "correct":
            interval = max(1, current_interval * 2)
        else:
            interval = 3

    next_date = timeutil.today() + timedelta(days=interval)
    return next_date, interval


def get_review_plan(questions: list[dict]) -> list[dict]:
    """筛选今日待复习的错题，按优先级排序"""
    today = timeutil.today()
    due = []

    for q in questions:
        next_review = q.get("next_review_date")
        if not next_review:
            continue
        if isinstance(next_review, str):
            next_review = date.fromisoformat(next_review)
        if next_review <= today:
            due.append(q)

    # 按 mastery_score 升序（最薄弱的优先）
    due.sort(key=lambda q: q.get("mastery_score", 100))
    return due
