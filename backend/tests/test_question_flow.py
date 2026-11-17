"""上传图片、保存错题与复习提交的接口回归测试。"""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.api.deps import get_auth_service
from app.db import Database
from app.services.auth_service import AuthService
from app.services.storage_manager import StorageManager
from app.services import file_ops
from main import app


def png_bytes(width: int = 300, height: int = 300) -> bytes:
    """生成一张真实 PNG，用于通过上传接口的格式校验。"""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class QuestionFlowTest(unittest.TestCase):
    def test_upload_save_and_redo(self):
        with tempfile.TemporaryDirectory() as vault:
            database = Database(f"sqlite:///{Path(vault) / 'app.db'}")
            database.initialize()
            auth = AuthService(database)
            app.dependency_overrides[get_auth_service] = lambda: auth
            with patch.object(settings, "vault_path", vault), patch.object(
                settings, "ima_enabled", False
            ), patch(
                "app.services.storage_manager.get_storage_manager",
                return_value=StorageManager(),
            ):
                client = TestClient(app)
                account = client.post("/api/auth/initialize", json={
                    "username": "owner", "display_name": "管理员",
                    "password": "correct horse battery",
                }).json()["account"]
                child = client.post("/api/children", json={
                    "name": "女儿", "emoji": "👧", "subjects": ["数学"],
                }).json()
                sample_png = png_bytes()
                uploaded = client.post(
                    "/api/upload/images",
                    files={"files": ("sample.png", sample_png, "image/png")},
                )
                self.assertEqual(uploaded.status_code, 200)
                image = uploaded.json()["image_ids"][0]
                # 上传只到临时目录，为分析准备，不进 vault
                self.assertTrue(Path(image["path"]).exists())

                payload = {
                    "child_id": child["id"], "subject": "数学", "topic": "接口测试",
                    "error_date": "2026-09-16", "correct_answer": "42",
                    "source_type": "test", "difficulty": "easy", "question_text": "6 × 7",
                }
                saved = client.post("/api/questions", json=payload)
                self.assertEqual(saved.status_code, 200, saved.text)
                question_id = saved.json()["id"]

                # 按 question_id 定位（不硬编码完整文件名，改为校验命名格式）
                note = file_ops.find_question_file(
                    account["id"], child["id"], "数学", question_id
                )
                self.assertIsNotNone(note, "应当能按 question_id 定位到文件")
                self.assertTrue(
                    note.name.startswith("女儿·数学·2026-09-16-"),
                    f"文件名应为 人名·学科·日期-id 格式，实际 {note.name}",
                )

                # 正文是纯文字：不含图片引用，也不产生 _assets 目录
                content = note.read_text()
                self.assertIn("## 正确答案", content)
                self.assertNotIn("![", content)
                self.assertFalse((Path(vault) / "_assets").exists())

                # 临时图片在保存后仍然存在，由上传接口按 TTL 回收，而非保存流程删除
                self.assertTrue(Path(image["path"]).exists())

                for result in ("correct", "wrong"):
                    redo = client.post(
                        f"/api/questions/{question_id}/redo",
                        params={"child_id": child["id"], "subject": "数学"},
                        json={"result": result},
                    )
                    self.assertEqual(redo.status_code, 200, redo.text)
                    self.assertTrue(redo.json()["success"])
            app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
