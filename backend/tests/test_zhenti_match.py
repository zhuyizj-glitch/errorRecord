"""薄弱点聚合与真题推荐算法测试（v2.0）"""

import unittest

from app.services import zhenti_match


def mistake(kps, score=0, status="reviewing"):
    return {"knowledge_points": kps, "mastery_score": score, "mastery_status": status}


def zhenti(kps, year="2024", history=None):
    return {
        "id": "x", "subject": "数学", "year": year,
        "knowledge_points": kps,
        "practice_history": history or [],
    }


class NormalizeTest(unittest.TestCase):
    def test_strip_and_collapse(self):
        self.assertEqual(zhenti_match.normalize_kp("  一元二次  方程 "), "一元二次 方程")
        self.assertEqual(zhenti_match.normalize_kp(""), "")
        self.assertEqual(zhenti_match.normalize_kp(None), "")


class WeakPointsTest(unittest.TestCase):
    def test_mastered_excluded(self):
        weak = zhenti_match.collect_weak_points([
            mistake(["A"], score=90, status="mastered"),
            mistake(["B"], score=0),
        ])
        self.assertEqual([w["knowledge_point"] for w in weak], ["B"])

    def test_weight_aggregation_and_order(self):
        weak = zhenti_match.collect_weak_points([
            mistake(["A", "B"], score=0),      # A+1.0 B+1.0
            mistake(["A"], score=50),          # A+0.5
            mistake(["C"], score=80, status="reviewing"),  # C+0.2
        ])
        self.assertEqual([w["knowledge_point"] for w in weak], ["A", "B", "C"])
        self.assertEqual(weak[0]["weight"], 1.5)
        self.assertEqual(weak[0]["question_count"], 2)
        self.assertEqual(weak[0]["avg_mastery"], 25.0)

    def test_empty_and_blank_tags(self):
        self.assertEqual(zhenti_match.collect_weak_points([]), [])
        self.assertEqual(zhenti_match.collect_weak_points([mistake(["", "  "])]), [])


class VocabTest(unittest.TestCase):
    def test_dedup_and_normalize(self):
        vocab = zhenti_match.knowledge_vocab(
            [mistake(["A", " B "])], [zhenti(["A", "C"])]
        )
        self.assertEqual(vocab, ["A", "B", "C"])


class RecommendTest(unittest.TestCase):
    def setUp(self):
        self.weak = zhenti_match.collect_weak_points([
            mistake(["A", "B"], score=0),
            mistake(["A"], score=50),
        ])  # A=1.5 B=1.0

    def test_score_and_order(self):
        bank = [
            zhenti(["B"]),        # 1.0
            zhenti(["A", "B"]),   # 2.5
            zhenti(["C"]),        # 0 → 不推荐
        ]
        recs = zhenti_match.recommend(self.weak, bank, "child_1")
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]["match_score"], 2.5)
        self.assertEqual(recs[0]["matched_points"], ["A", "B"])
        self.assertEqual(recs[1]["match_score"], 1.0)

    def test_child_practice_count_tiebreak(self):
        bank = [
            zhenti(["A"], history=[{"child_id": "child_1", "result": "correct"}]),
            zhenti(["A"], year="2023"),
        ]
        recs = zhenti_match.recommend(self.weak, bank, "child_1")
        # 同分：child_1 没练过的优先（哪怕年份旧）
        self.assertEqual(recs[0]["year"], "2023")
        self.assertEqual(recs[0]["child_practice_count"], 0)
        self.assertEqual(recs[1]["child_practice_count"], 1)
        # 另一个孩子视角：练过的记录不算他的
        recs2 = zhenti_match.recommend(self.weak, bank, "child_2")
        self.assertEqual(recs2[0]["child_practice_count"], 0)

    def test_subject_filter_and_limit(self):
        bank = [zhenti(["A"]), {**zhenti(["A"]), "subject": "物理"}]
        recs = zhenti_match.recommend(self.weak, bank, "c", subject="数学")
        self.assertEqual(len(recs), 1)
        self.assertEqual(len(zhenti_match.recommend(self.weak, bank, "c", limit=1)), 1)
