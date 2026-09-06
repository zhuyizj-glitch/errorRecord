"""掌握度评分 & 重复犯错检测"""

from datetime import date, timedelta
from typing import Optional


def calculate_mastery_score(
    correct_count: int,
    wrong_count: int,
    consecutive_correct: int,
) -> int:
    """
    计算掌握度分数（综合方案）

    基础分 = 做对率 × 60 分（权重 60%）
    连续奖励 = min(连续做对次数, 5) × 8 分（权重 40%）
    mastery_score = 基础分 + 连续奖励

    参数:
        correct_count: 重做中做对的次数
        wrong_count: 重做中做错的次数
        consecutive_correct: 当前连续做对次数

    返回:
        mastery_score: 0-100 分

    示例:
        - 做错 3 次，做对 0 次，连续 0 次 → 0 + 0 = 0 分
        - 做错 2 次，做对 1 次，连续 1 次 → 20 + 8 = 28 分
        - 做错 1 次，做对 2 次，连续 2 次 → 40 + 16 = 56 分
        - 做错 0 次，做对 3 次，连续 3 次 → 60 + 24 = 84 分
        - 做错 0 次，做对 5 次，连续 5 次 → 60 + 40 = 100 分
    """
    total_attempts = correct_count + wrong_count

    # 如果还没重做过，给一个初始分数（基于做错的事实）
    if total_attempts == 0:
        return 0

    # 基础分：做对率 × 60
    accuracy = correct_count / total_attempts if total_attempts > 0 else 0
    base_score = accuracy * 60

    # 连续奖励：min(连续做对, 5) × 8
    consecutive_bonus = min(consecutive_correct, 5) * 8

    # 总分
    score = base_score + consecutive_bonus

    return min(100, max(0, int(score)))


def mastery_level_from_score(score: int, consecutive_correct: int = 0) -> str:
    """
    根据分数和连续做对次数返回掌握等级

    掌握标准：
    - ≥ 80 分 + 连续做对 ≥ 3 次 → high（已掌握）
    - ≥ 50 分 → medium（待加强）
    - < 50 分 → low（薄弱）
    """
    if score >= 80 and consecutive_correct >= 3:
        return "high"
    elif score >= 50:
        return "medium"
    else:
        return "low"


def mastery_status_from(redo_count: int, level: str) -> str:
    """
    根据重做次数和等级返回掌握状态

    - redo_count = 0 → new（刚录入，还没重做过）
    - level = high → mastered（已掌握）
    - otherwise → reviewing（复习中）
    """
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
