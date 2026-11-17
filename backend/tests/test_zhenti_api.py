"""真题库接口全流程测试（v2.0）：入库、筛选、练习、转错题、推荐、隔离、PDF 导入。"""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.api.deps import get_auth_service
from app.db import Database
from app.services import file_ops, zhenti_ops
from app.services.auth_service import AuthService
from app.services.storage_manager import StorageManager
from main import app


def png_bytes(width=300, height=300):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def pdf_bytes():
    """用 Pillow 生成单页 PDF（测试 PDF 上传链路）"""
    buffer = io.BytesIO()
    Image.new("RGB", (400, 600), "white").save(buffer, format="PDF")
    return buffer.getvalue()


SAVE_PAYLOAD = {
    "subject": "数学",
    "year": "2024",
    "source": "2024年中考数学卷",
    "questions": [{
        "number": "12",
        "question_text": "解方程 $x^2 - 5x + 6 = 0$",
        "correct_answer": "$x = 2$ 或 $x = 3$",
        "solution_steps": "因式分解 $(x-2)(x-3)=0$",
        "topic": "一元二次方程",
        "knowledge_points": ["一元二次方程", "因式分解"],
        "difficulty": "中等",
    }],
}


class ZhentiApiTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        vault = self._tmp.name
        database = Database(f"sqlite:///{Path(vault) / 'app.db'}")
        database.initialize()
        self.auth = AuthService(database)
        app.dependency_overrides[get_auth_service] = lambda: self.auth
        self._patches = [
            patch.object(settings, "vault_path", vault),
            patch.object(settings, "ima_enabled", False),
            patch("app.services.storage_manager.get_storage_manager",
                  return_value=StorageManager()),
        ]
        for p in self._patches:
            p.start()
        self.client = TestClient(app)
        self.account = self.client.post("/api/auth/initialize", json={
            "username": "owner", "display_name": "管理员",
            "password": "correct horse battery",
        }).json()["account"]
        self.child = self.client.post("/api/children", json={
            "name": "女儿", "emoji": "👧", "subjects": ["数学"],
        }).json()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        app.dependency_overrides.clear()
        self._tmp.cleanup()

    def _save_zhenti(self):
        res = self.client.post("/api/zhenti/questions", json=SAVE_PAYLOAD)
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()["ids"][0]

    def _create_mistake(self, kps):
        res = self.client.post("/api/questions", json={
            "child_id": self.child["id"], "subject": "数学", "topic": "测试",
            "error_date": "2026-11-17", "correct_answer": "略",
            "source_type": "印刷题", "difficulty": "中等",
            "question_text": "题干", "knowledge_points": kps,
        })
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()["id"]

    def test_save_list_detail_patch_delete(self):
        zid = self._save_zhenti()

        listed = self.client.get("/api/zhenti/questions").json()
        self.assertEqual(listed["total"], 1)
        self.assertEqual(listed["questions"][0]["year"], "2024")

        # 筛选
        self.assertEqual(self.client.get(
            "/api/zhenti/questions", params={"knowledge_point": "一元二次方程"}
        ).json()["total"], 1)
        self.assertEqual(self.client.get(
            "/api/zhenti/questions", params={"year": "2023"}
        ).json()["total"], 0)

        # 详情：结构化段落 + LaTeX 原样
        detail = self.client.get(f"/api/zhenti/questions/{zid}").json()
        self.assertTrue(detail["_structured"])
        self.assertIn("$x^2 - 5x + 6 = 0$", detail["_question"])
        self.assertIn("$x = 2$", detail["_answer"])

        # 修正知识点与年份（文件名随之变化）
        patched = self.client.patch(f"/api/zhenti/questions/{zid}", json={
            "knowledge_points": ["一元二次方程", "判别式"], "year": "2023",
        })
        self.assertEqual(patched.status_code, 200, patched.text)
        detail = self.client.get(f"/api/zhenti/questions/{zid}").json()
        self.assertEqual(detail["knowledge_points"], ["一元二次方程", "判别式"])
        self.assertEqual(detail["year"], "2023")
        self.assertIn("2023", Path(detail["_file"]).name)

        # 删除
        self.assertEqual(
            self.client.delete(f"/api/zhenti/questions/{zid}").status_code, 200)
        self.assertEqual(self.client.get("/api/zhenti/questions").json()["total"], 0)
        self.assertEqual(
            self.client.get(f"/api/zhenti/questions/{zid}").status_code, 404)

    def test_practice_per_child_and_to_mistake(self):
        zid = self._save_zhenti()

        # 练习：错一次
        res = self.client.post(f"/api/zhenti/questions/{zid}/practice", json={
            "child_id": self.child["id"], "result": "wrong", "note": "计算失误",
        })
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["practice_count"], 1)
        self.assertEqual(res.json()["child_practice_count"], 1)

        # 非法结果被拒
        self.assertEqual(self.client.post(
            f"/api/zhenti/questions/{zid}/practice",
            json={"child_id": self.child["id"], "result": "maybe"},
        ).status_code, 400)

        # 转为错题：进入掌握度体系，初始 0 分
        res = self.client.post(f"/api/zhenti/questions/{zid}/to-mistake", json={
            "child_id": self.child["id"],
        })
        self.assertEqual(res.status_code, 200, res.text)
        qid = res.json()["question_id"]
        questions = self.client.get(
            "/api/questions", params={"child_id": self.child["id"]}).json()["questions"]
        created = next(q for q in questions if q["id"] == qid)
        self.assertEqual(created["mastery_score"], 0)
        self.assertEqual(created["knowledge_points"], ["一元二次方程", "因式分解"])
        self.assertIn("真题转化", created["tags"])
        # 家长备注在正文里（列表接口不带正文），取详情验证
        detail = self.client.get(f"/api/questions/{qid}", params={
            "child_id": self.child["id"], "subject": "数学"}).json()
        self.assertIn("2024年中考数学卷", detail["_body"])

        # 真题侧记录了转化
        detail = self.client.get(f"/api/zhenti/questions/{zid}").json()
        self.assertEqual(detail["converted_to"][0]["question_id"], qid)

    def test_weak_points_and_recommend(self):
        self._create_mistake(["一元二次方程"])
        self._create_mistake(["一元二次方程", "因式分解"])
        zid = self._save_zhenti()

        weak = self.client.get(
            "/api/zhenti/weak-points", params={"child_id": self.child["id"]}).json()
        self.assertEqual(weak["weak_points"][0]["knowledge_point"], "一元二次方程")
        self.assertEqual(weak["weak_points"][0]["weight"], 2.0)

        rec = self.client.get(
            "/api/zhenti/recommend", params={"child_id": self.child["id"]}).json()
        self.assertEqual(rec["total"], 1)
        self.assertEqual(rec["recommendations"][0]["id"], zid)
        self.assertEqual(rec["recommendations"][0]["match_score"], 3.0)
        self.assertIn("一元二次方程", rec["recommendations"][0]["matched_points"])
        # 「因式分解」有真题匹配，不在缺口列表
        self.assertEqual(rec["unmatched_points"], [])

        # 录一道没有真题匹配的薄弱点 → 显式暴露缺口
        self._create_mistake(["光合作用"])
        rec = self.client.get(
            "/api/zhenti/recommend", params={"child_id": self.child["id"]}).json()
        self.assertIn("光合作用", rec["unmatched_points"])

    def test_import_task_with_mocked_llm(self):
        uploaded = self.client.post(
            "/api/upload/images",
            files={"files": ("page.png", png_bytes(), "image/png")},
        ).json()
        mock_result = {
            "subject": "数学",
            "questions": [{
                "number": "1", "question_text": "1+1=?",
                "correct_answer": "2", "knowledge_points": ["加法"],
            }],
        }
        with patch("app.services.llm.analyze_exam_images",
                   new=AsyncMock(return_value=mock_result)) as mock:
            res = self.client.post("/api/zhenti/import", json={
                "subject": "数学", "year": "2024", "source": "模拟卷",
                "image_ids": uploaded["image_ids"],
            })
            self.assertEqual(res.status_code, 200, res.text)
            task_id = res.json()["task_id"]
            # TestClient 会同步执行后台任务
            task = self.client.get(f"/api/tasks/{task_id}").json()
            self.assertEqual(task["status"], "completed")
            self.assertEqual(task["kind"], "zhenti")
            self.assertEqual(task["meta"]["year"], "2024")
            self.assertEqual(task["result"]["questions"][0]["correct_answer"], "2")
            mock.assert_called_once()
            # 词汇表参数已传入（list 类型）
            self.assertIsInstance(mock.call_args[0][1], list)

        tasks = self.client.get("/api/zhenti/tasks").json()
        self.assertEqual(tasks["total"], 1)

    def test_pdf_upload_expands_to_pages(self):
        res = self.client.post(
            "/api/upload/images",
            files={"files": ("exam.pdf", pdf_bytes(), "application/pdf")},
        )
        self.assertEqual(res.status_code, 200, res.text)
        images = res.json()["image_ids"]
        self.assertEqual(len(images), 1)
        self.assertIn("第1页", images[0]["filename"])
        self.assertTrue(Path(images[0]["path"]).exists())
        self.assertTrue(images[0]["path"].endswith(".png"))

    def test_account_isolation(self):
        self._save_zhenti()
        # 邀请第二个账号
        code = self.client.post("/api/admin/invites", json={}).json()["code"]
        self.client.post("/api/auth/logout")
        other = self.client.post("/api/auth/register", json={
            "invite_code": code, "username": "other", "display_name": "其他家长",
            "password": "another long password",
        }).json()["account"]
        self.assertEqual(self.client.get("/api/zhenti/questions").json()["total"], 0)
        self.assertEqual(self.client.get(
            "/api/zhenti/weak-points", params={"child_id": self.child["id"]}
        ).status_code, 404)
        # 切回原账号仍能看到
        self.client.post("/api/auth/logout")
        self.client.post("/api/auth/login", json={
            "username": "owner", "password": "correct horse battery"})
        self.assertEqual(self.client.get("/api/zhenti/questions").json()["total"], 1)
        self.assertNotEqual(other["id"], self.account["id"])
