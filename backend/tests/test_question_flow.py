"""上传图片、保存错题与复习提交的接口回归测试。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.api.deps import get_auth_service
from app.db import Database
from app.services.auth_service import AuthService
from app.services.file_storage import FileStorageBackend
from main import app


class QuestionFlowTest(unittest.TestCase):
    def test_upload_save_and_redo(self):
        with tempfile.TemporaryDirectory() as vault:
            database = Database(f"sqlite:///{Path(vault) / 'app.db'}")
            database.initialize()
            auth = AuthService(database)
            app.dependency_overrides[get_auth_service] = lambda: auth
            with patch.object(settings, "vault_path", vault), patch(
                "app.services.storage_manager.get_storage_manager",
                return_value=FileStorageBackend(),
            ):
                client = TestClient(app)
                account = client.post("/api/auth/initialize", json={
                    "username": "owner", "display_name": "管理员",
                    "password": "correct horse battery",
                }).json()["account"]
                child = client.post("/api/children", json={
                    "name": "女儿", "emoji": "👧", "subjects": ["数学"],
                }).json()
                uploaded = client.post(
                    "/api/upload/images",
                    files={"files": ("sample.png", b"test-image", "image/png")},
                )
                self.assertEqual(uploaded.status_code, 200)
                image = uploaded.json()["image_ids"][0]

                payload = {
                    "child_id": child["id"], "subject": "数学", "topic": "接口测试",
                    "error_date": "2026-09-16", "correct_answer": "42",
                    "source_type": "test", "difficulty": "easy", "question_text": "6 × 7",
                    "image_ids": [image],
                }
                invalid = client.post("/api/questions", json={
                    **payload, "image_ids": [{**image, "path": "/etc/passwd"}],
                })
                self.assertEqual(invalid.status_code, 400)

                saved = client.post("/api/questions", json=payload)
                self.assertEqual(saved.status_code, 200, saved.text)
                question_id = saved.json()["id"]
                self.assertEqual(saved.json()["images_saved"], 1)
                note = Path(vault) / "accounts" / account["id"] / child["id"] / "数学" / f"2026-09-16-{question_id}.md"
                image_file = Path(vault) / "_assets/accounts" / account["id"] / child["id"] / "数学" / question_id / "sample.png"
                self.assertEqual(image_file.read_bytes(), b"test-image")
                self.assertIn(
                    f"../../../../_assets/accounts/{account['id']}/{child['id']}/数学/{question_id}/sample.png",
                    note.read_text(),
                )
                self.assertFalse(Path(image["path"]).exists())

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
