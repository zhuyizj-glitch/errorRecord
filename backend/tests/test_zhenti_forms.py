"""三形态模型 + 时代/主题轴 + 子题双层打标测试（v2.0 校验定稿）"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.api.deps import get_auth_service
from app.db import Database
from app.services import zhenti_match, zhenti_ops
from app.services.auth_service import AuthService
from app.services.storage_manager import StorageManager
from main import app


PASSAGE_ITEM = {
    "number": "1-3", "question_form": "passage", "question_type": "阅读理解",
    "rating": "简单", "passage": "Four museums in New York...",
    "sub_questions": [
        {"number": "1", "question_text": "What do MMI and NYHS share?",
         "correct_answer": "C", "knowledge_points": ["细节理解"]},
        {"number": "2", "question_text": "Which opens year-round?",
         "correct_answer": "B", "knowledge_points": ["细节理解"]},
    ],
}
GRAMMAR_ITEM = {
    "number": "36-45", "question_form": "passage", "question_type": "语法填空",
    "rating": "中等", "passage": "The Taklamakan Desert green belt...",
    "sub_questions": [
        {"number": "43", "question_text": "..., ___ is known to all",
         "correct_answer": "which", "knowledge_points": ["定语从句·关系代词"]},
        {"number": "36", "question_text": "The city ___ (witness) great changes",
         "correct_answer": "has witnessed", "knowledge_points": ["时态·现在完成时"]},
    ],
}
HISTORY_GROUP = {
    "number": "24-26", "question_form": "material_group", "question_type": "材料选择",
    "passage": "汉武帝加强中央集权的系列措施……",
    "sub_questions": [
        {"number": "24", "question_text": "推恩令的作用", "correct_answer": "B",
         "knowledge_points": ["汉武帝·推恩令"], "era": "西汉"},
        {"number": "26", "question_text": "刺史的职责", "correct_answer": "C",
         "knowledge_points": ["汉武帝·刺史制度"], "era": "西汉"},
    ],
}


class FormsOpsTest(unittest.TestCase):
    def test_passage_save_and_read(self):
        with tempfile.TemporaryDirectory() as vault:
            with patch.object(settings, "vault_path", vault):
                fm = zhenti_ops.new_frontmatter("p1", "acc", "英语", "2025", "常州卷", PASSAGE_ITEM)
                path = zhenti_ops.save_zhenti("p1", "acc", "英语", fm, zhenti_ops.build_body(PASSAGE_ITEM))
                text = path.read_text()
                self.assertIn("## 语篇", text)
                self.assertIn("## 子题", text)
                self.assertIn("Four museums", text)
                data = zhenti_ops.read_zhenti(str(path))
                self.assertEqual(data["question_form"], "passage")
                self.assertEqual(data["rating"], "简单")
                self.assertEqual(len(data["sub_questions"]), 2)
                self.assertEqual(data["sub_questions"][0]["correct_answer"], "C")

    def test_material_group_body(self):
        with tempfile.TemporaryDirectory() as vault:
            with patch.object(settings, "vault_path", vault):
                body = zhenti_ops.build_body(HISTORY_GROUP)
                self.assertIn("## 共享材料", body)
                self.assertIn("第 24 题", body)
                self.assertIn("推恩令", body)


class FormsMatchTest(unittest.TestCase):
    def test_matchable_units(self):
        indep = {"question_form": "independent", "knowledge_points": ["A"]}
        self.assertEqual(len(zhenti_match.matchable_units(indep)), 1)
        units = zhenti_match.matchable_units(GRAMMAR_ITEM)
        self.assertEqual(len(units), 2)
        self.assertEqual(units[0]["sub_number"], "43")
        self.assertIn("定语从句·关系代词", units[0]["kp"])

    def test_subquestion_recommend(self):
        weak = [{"knowledge_point": "定语从句·关系代词", "weight": 1.0}]
        recs = zhenti_match.recommend(weak, [GRAMMAR_ITEM], "child")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["matched_sub_numbers"], ["43"])
        self.assertIn("定语从句·关系代词", recs[0]["matched_points"])

    def test_era_and_module_filter(self):
        weak = [{"knowledge_point": "汉武帝·推恩令", "weight": 1.0},
                {"knowledge_point": "汉武帝·刺史制度", "weight": 1.0}]
        # 命中西汉
        recs = zhenti_match.recommend(weak, [HISTORY_GROUP], "c", era="西汉")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["match_score"], 2.0)
        # 唐朝切片 → 无命中
        self.assertEqual(zhenti_match.recommend(weak, [HISTORY_GROUP], "c", era="唐"), [])

    def test_list_passages_rating_order(self):
        items = [
            {**GRAMMAR_ITEM, "id": "g", "subject": "英语"},   # 中等
            {**PASSAGE_ITEM, "id": "p", "subject": "英语"},   # 简单
        ]
        passages = zhenti_match.list_passages(items, subject="英语")
        self.assertEqual([p["id"] for p in passages], ["p", "g"])  # 简单在前
        only_read = zhenti_match.list_passages(items, subject="英语", question_type="阅读理解")
        self.assertEqual(len(only_read), 1)


class FormsApiTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        vault = self._tmp.name
        db = Database(f"sqlite:///{Path(vault) / 'app.db'}")
        db.initialize()
        self.auth = AuthService(db)
        app.dependency_overrides[get_auth_service] = lambda: self.auth
        self._patches = [
            patch.object(settings, "vault_path", vault),
            patch.object(settings, "ima_enabled", False),
            patch("app.services.storage_manager.get_storage_manager", return_value=StorageManager()),
        ]
        for p in self._patches:
            p.start()
        self.client = TestClient(app)
        self.client.post("/api/auth/initialize", json={
            "username": "owner", "display_name": "管理员", "password": "correct horse battery"})
        self.child = self.client.post("/api/children", json={
            "name": "女儿", "emoji": "👧", "subjects": ["英语", "历史"]}).json()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        app.dependency_overrides.clear()
        self._tmp.cleanup()

    def test_save_passage_and_recommend_subquestion(self):
        # 录一道定语从句薄弱错题
        self.client.post("/api/questions", json={
            "child_id": self.child["id"], "subject": "英语", "topic": "语法",
            "error_date": "2026-11-17", "correct_answer": "which", "source_type": "印刷题",
            "difficulty": "中等", "question_text": "定语从句题",
            "knowledge_points": ["定语从句·关系代词"]})
        # 入库语法填空语篇
        res = self.client.post("/api/zhenti/questions", json={
            "subject": "英语", "year": "2025", "source": "常州卷",
            "questions": [GRAMMAR_ITEM, PASSAGE_ITEM]})
        self.assertEqual(res.status_code, 200, res.text)

        rec = self.client.get("/api/zhenti/recommend",
                              params={"child_id": self.child["id"]}).json()
        # 子题级匹配命中语法填空
        self.assertEqual(rec["total"], 1)
        self.assertEqual(rec["recommendations"][0]["matched_sub_numbers"], ["43"])
        # 语篇梯度列表：简单(阅读)在前，中等(语法填空)在后
        self.assertEqual([p["question_type"] for p in rec["passages"]], ["阅读理解", "语法填空"])

    def test_dimensions_and_era_filter(self):
        self.client.post("/api/zhenti/questions", json={
            "subject": "历史", "year": "2026", "source": "苏北卷", "questions": [HISTORY_GROUP]})
        dims = self.client.get("/api/zhenti/dimensions", params={"subject": "历史"}).json()
        self.assertIn("西汉", dims["eras"])
        # 按朝代筛选
        filtered = self.client.get("/api/zhenti/questions",
                                   params={"subject": "历史", "era": "西汉"}).json()
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(self.client.get("/api/zhenti/questions",
                                         params={"subject": "历史", "era": "唐"}).json()["total"], 0)

    def test_to_mistake_subquestion(self):
        res = self.client.post("/api/zhenti/questions", json={
            "subject": "历史", "year": "2026", "source": "苏北卷", "questions": [HISTORY_GROUP]})
        zid = res.json()["ids"][0]
        # 指定子题 24 转错题
        res = self.client.post(f"/api/zhenti/questions/{zid}/to-mistake", json={
            "child_id": self.child["id"], "sub_number": "24"})
        self.assertEqual(res.status_code, 200, res.text)
        qid = res.json()["question_id"]
        qs = self.client.get("/api/questions", params={"child_id": self.child["id"]}).json()["questions"]
        created = next(q for q in qs if q["id"] == qid)
        self.assertEqual(created["knowledge_points"], ["汉武帝·推恩令"])
        detail = self.client.get(f"/api/questions/{qid}", params={
            "child_id": self.child["id"], "subject": "历史"}).json()
        self.assertIn("第24题", detail["_body"])
