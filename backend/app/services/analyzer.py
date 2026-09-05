"""掌握度评分 & 重复犯错检测"""

from datetime import date, timedelta
from typing import Optional


def calculate_mastery_score(
    redo_count: int,
    low_diff_errors: int = 0,
    error_type_count: int = 1,
    last_error_date: Optional[date] = None,
) -> int:
    """
    计算掌握度分数（满分 100 扣减制）

    扣分项                          公式                        上限
    ────────────────────────────────────────────────────────────────
    错误次数                        redo_count × 8              扣 40
    低难度还错（difficulty ≤ 2）    low_diff_errors × 5         扣 15
    多种错误类型                     (error_type_count - 1) × 5  扣 15
    近期犯错时间衰减                max(0, 10 - 距今天数 × 1.5)  扣 10
    """
    deductions = 0

    # 错误次数扣分
    deductions += min(redo_count * 8, 40)

    # 低难度还错扣分
    deductions += min(low_diff_errors * 5, 15)

    # 多种错误类型扣分
    deductions += min((error_type_count - 1) * 5, 15)

    # 近期犯错时间衰减
    if last_error_date:
        days_ago = (date.today() - last_error_date).days
        deductions += max(0, int(10 - days_ago * 1.5))

    return max(0, 100 - deductions)


def mastery_level_from_score(score: int) -> str:
    """根据分数返回掌握等级"""
    if score >= 70:
        return "high"
    elif score >= 40:
        return "medium"
    else:
        return "low"


def mastery_status_from(redo_count: int, level: str) -> str:
    """根据重做次数和等级返回掌握状态"""
    if redo_count == 0:
        return "new"
    elif level == "high":
        return "mastered"
    else:
        return "reviewing"


def detect_repeat_streak(error_dates: list[date], threshold_days: int = 7) -> dict:
    """
    检测重复犯错模式

    返回:
        repeat_streak: 当前连续重复犯错次数
        max_repeat_streak: 历史最高连续重复次数
        repeat_pattern: 是否处于重复犯错模式
    """
    if not error_dates:
        return {"repeat_streak": 0, "max_repeat_streak": 0, "repeat_pattern": False}

    sorted_dates = sorted(error_dates)
    current_streak = 1
    max_streak = 1

    for i in range(1, len(sorted_dates)):
        gap = (sorted_dates[i] - sorted_dates[i - 1]).days
        if gap <= threshold_days:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 1

    return {
        "repeat_streak": current_streak,
        "max_repeat_streak": max_streak,
        "repeat_pattern": max_streak >= 2,
    }
