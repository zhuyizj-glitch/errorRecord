"""学习阶段轴测试（v2.0）：阶段排序、孩子当前阶段、超纲过滤。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.stages import STAGES, stage_rank, is_valid_stage
from app.api.deps import get_auth_service
from app.db import Database
from app.services.auth_service import AuthService
from app.services.storage_manager import StorageManager
from main import app


class StageOrderTest(unittest.TestCase):
    def test_semester_order(self):
        self.assertLess(stage_rank("高一上月考1"), stage_rank("高一上月考2"))
        self.assertLess(stage_rank("高一上月考2"), stage_rank("高一上期中"))
        self.assertLess(stage_rank("高一上期中"), stage_rank("高一上月考3"))
        self.assertLess(stage_rank("高一上月考4"), stage_rank("高一上期末"))
        self.assertLess(stage_rank("高一上期末"), stage_rank("高一下月考1"))
        self.assertLess(stage_rank("高三下期末"), stage_rank("高考模拟"))

    def test_unknown_and_valid(self):
        self.assertEqual(stage_rank(""), -1)
        self.assertEqual(stage_rank(None), -1)
        self.assertEqual(stage_rank("不存在的阶段"), -1)
        self.assertTrue(is_valid_stage("高一上期中"))
        self.assertFalse(is_valid_stage("高一上期中x"))
        self.assertIn("高一上月考1", STAGES)


class StageApiTest(unittest.TestCase):
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

    def tearDown(self):
        for p in self._patches:
            p.stop()
        app.dependency_overrides.clear()
        self._tmp.cleanup()

    def _child(self, stage):
        return self.client.post("/api/children", json={
            "name": "女儿", "emoji": "👧", "subjects": ["数学"], "current_stage": stage}).json()

    def _mistake(self, child_id):
        self.client.post("/api/questions", json={
            "child_id": child_id, "subject": "数学", "topic": "函数",
            "error_date": "2026-11-18", "correct_answer": "略", "source_type": "印刷题",
            "difficulty": "中等", "question_text": "题干", "knowledge_points": ["函数的奇偶性"]})

    def _zhenti(self, stage):
        return self.client.post("/api/zhenti/questions", json={
            "subject": "数学", "year": "2026", "source": "测试卷", "stage": stage,
            "questions": [{"question_form": "independent", "question_text": "题",
                           "correct_answer": "答", "knowledge_points": ["函数的奇偶性"]}]}).json()["ids"][0]

    def test_child_stage_and_available_stages(self):
        child = self._child("高一上期中")
        self.assertEqual(child["current_stage"], "高一上期中")
        listed = self.client.get("/api/children").json()
        self.assertIn("高一上月考1", listed["available_stages"])
        # 更新阶段
        updated = self.client.patch(f"/api/children/{child['id']}", json={
            "name": "女儿", "emoji": "👧", "subjects": ["数学"], "current_stage": "高一上期末"}).json()
        self.assertEqual(updated["current_stage"], "高一上期末")
        # 非法阶段被拒
        bad = self.client.post("/api/children", json={
            "name": "x", "emoji": "🧒", "subjects": ["数学"], "current_stage": "乱写"})
        self.assertEqual(bad.status_code, 422)

    def test_recommend_excludes_ahead_stage(self):
        child = self._child("高一上期中")
        self._mistake(child["id"])
        mid = self._zhenti("高一上期中")
        final = self._zhenti("高一上期末")
        rec = self.client.get("/api/zhenti/recommend", params={"child_id": child["id"]}).json()
        ids = [r["id"] for r in rec["recommendations"]]
        self.assertIn(mid, ids)
        self.assertNotIn(final, ids)  # 期末题超纲，被排除
        # 孩子升到期末阶段 → 期末题解锁
        self.client.patch(f"/api/children/{child['id']}", json={
            "name": "女儿", "emoji": "👧", "subjects": ["数学"], "current_stage": "高一上期末"})
        rec = self.client.get("/api/zhenti/recommend", params={"child_id": child["id"]}).json()
        ids = [r["id"] for r in rec["recommendations"]]
        self.assertIn(mid, ids)
        self.assertIn(final, ids)

    def test_no_stage_set_no_filter(self):
        child = self._child("")  # 未设阶段
        self._mistake(child["id"])
        self._zhenti("高一上期末")
        rec = self.client.get("/api/zhenti/recommend", params={"child_id": child["id"]}).json()
        self.assertEqual(rec["total"], 1)  # 不过滤

    def test_stage_saved_and_filterable(self):
        self._child("高一上期中")
        zid = self._zhenti("高一上期中")
        detail = self.client.get(f"/api/zhenti/questions/{zid}").json()
        self.assertEqual(detail["stage"], "高一上期中")
        dims = self.client.get("/api/zhenti/dimensions").json()
        self.assertIn("高一上期中", dims["stages"])
        self.assertEqual(self.client.get("/api/zhenti/questions",
                                         params={"stage": "高一上期中"}).json()["total"], 1)
        self.assertEqual(self.client.get("/api/zhenti/questions",
                                         params={"stage": "高一上期末"}).json()["total"], 0)
