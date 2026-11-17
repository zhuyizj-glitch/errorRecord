"""时区工具测试

这些测试守护一个具体的线上故障：

    后端跑在 Docker 容器里，而容器默认是 UTC。北京时间每天 00:00–08:00 之间，
    容器内的 date.today() 会比中国的"今天"晚一天 —— 那段时间打开「今日复习」
    拿到的是昨天的计划，新录入错题的 error_date 也会记成前一天。

修复方式：业务代码统一改用 app.core.timeutil.today()（显式 UTC+8），
并在 docker-compose.yml 里设置 TZ=Asia/Shanghai 作为第二层保险。
"""

import re
import unittest
from datetime import date, datetime, timedelta, timezone

from app.core import timeutil


class TimeutilTest(unittest.TestCase):
    def test_china_tz_is_utc_plus_8(self):
        """中国自 1991 年起无夏令时，偏移恒定 +8"""
        self.assertEqual(timeutil.CHINA_TZ.utcoffset(None), timedelta(hours=8))

    def test_now_is_timezone_aware(self):
        """必须带时区信息，否则后续换算会静默出错"""
        self.assertIsNotNone(timeutil.now().tzinfo)

    def test_today_matches_beijing_date(self):
        expected = datetime.now(timezone(timedelta(hours=8))).date()
        self.assertEqual(timeutil.today(), expected)

    def test_today_iso_is_date_format(self):
        self.assertRegex(timeutil.today_iso(), r"^\d{4}-\d{2}-\d{2}$")

    def test_beijing_early_morning_differs_from_utc(self):
        """复现故障场景本身。

        北京时间 2026-10-08 07:00 == UTC 2026-10-07 23:00。
        如果用 date.today()（容器里是 UTC），得到的是 10-07 —— 比孩子那里的
        「今天」少一天。这正是本次修复要消除的差异。
        """
        beijing_early_morning = datetime(2026, 10, 8, 7, 0, tzinfo=timeutil.CHINA_TZ)
        same_moment_utc = beijing_early_morning.astimezone(timezone.utc)

        self.assertEqual(beijing_early_morning.date(), date(2026, 10, 8))
        self.assertEqual(same_moment_utc.date(), date(2026, 10, 7))

    def test_boundary_exactly_at_beijing_midnight(self):
        """北京时间刚过午夜：UTC 还是前一天"""
        just_after_midnight = datetime(2026, 10, 8, 0, 30, tzinfo=timeutil.CHINA_TZ)
        self.assertEqual(just_after_midnight.astimezone(timezone.utc).date(), date(2026, 10, 7))

        # 而北京时间 08:00 之后，两者才回到同一天
        after_8am = datetime(2026, 10, 8, 8, 30, tzinfo=timeutil.CHINA_TZ)
        self.assertEqual(after_8am.astimezone(timezone.utc).date(), date(2026, 10, 8))


class ReviewSchedulerTimezoneTest(unittest.TestCase):
    """复习计划必须基于北京时间的今天"""

    def setUp(self):
        from app.services import review_scheduler

        self.scheduler = review_scheduler
        self.today = timeutil.today()

    def test_plan_includes_only_due_questions(self):
        questions = [
            {"id": "due_today", "next_review_date": self.today.isoformat(), "mastery_score": 10},
            {
                "id": "due_tomorrow",
                "next_review_date": (self.today + timedelta(days=1)).isoformat(),
                "mastery_score": 20,
            },
            {
                "id": "overdue",
                "next_review_date": (self.today - timedelta(days=3)).isoformat(),
                "mastery_score": 30,
            },
        ]

        due_ids = [q["id"] for q in self.scheduler.get_review_plan(questions)]

        # 到期与逾期的都该出现，明天的不该
        self.assertEqual(sorted(due_ids), ["due_today", "overdue"])

    def test_plan_sorted_by_mastery_ascending(self):
        questions = [
            {"id": "strong", "next_review_date": self.today.isoformat(), "mastery_score": 90},
            {"id": "weak", "next_review_date": self.today.isoformat(), "mastery_score": 10},
            {"id": "medium", "next_review_date": self.today.isoformat(), "mastery_score": 50},
        ]

        due_ids = [q["id"] for q in self.scheduler.get_review_plan(questions)]

        # 最薄弱的排最前
        self.assertEqual(due_ids, ["weak", "medium", "strong"])

    def test_next_review_date_is_china_date(self):
        next_date, interval = self.scheduler.calculate_next_review("low", "correct", 1)

        self.assertEqual(interval, 1)
        self.assertEqual(next_date, self.today + timedelta(days=1))

    def test_no_date_today_left_in_business_code(self):
        """防止有人日后又把 date.today() 写回来。

        用 AST 解析而不是文本匹配 —— 文本匹配会把文档字符串和注释里
        「提到这个写法」的地方也判为违规（本测试的第一版就误报过一次）。
        从语法树里找真实的函数调用，才不会有假阳性。
        """
        import ast
        from pathlib import Path

        app_dir = Path(__file__).resolve().parent.parent / "app"
        offenders = []

        for py_file in app_dir.rglob("*.py"):
            if py_file.name == "timeutil.py":
                continue  # 它自身的文档里会提到这个写法，且它是唯一的定义处

            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute) or func.attr != "today":
                    continue

                value = func.value
                is_date_today = isinstance(value, ast.Name) and value.id == "date"
                is_datetime_date_today = isinstance(value, ast.Attribute) and value.attr == "date"

                if is_date_today or is_datetime_date_today:
                    rel = py_file.relative_to(app_dir.parent)
                    offenders.append(f"{rel}:{node.lineno}")

        self.assertEqual(offenders, [], f"这些地方仍在用 date.today()：{offenders}")


if __name__ == "__main__":
    unittest.main()
