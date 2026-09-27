"""错题、图片与 vault 路径的账号隔离测试。"""

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.deps import get_auth_service
from app.core.config import settings
from app.db import Database
from app.services.auth_service import AuthService
from app.services.file_storage import FileStorageBackend
from main import app


class QuestionAccountIsolationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp_dir.name) / "vault"
        database = Database(f"sqlite:///{Path(self.temp_dir.name) / 'app.db'}")
        database.initialize()
        self.auth = AuthService(database)
        app.dependency_overrides[get_auth_service] = lambda: self.auth
        self.vault_patch = patch.object(settings, "vault_path", str(self.vault))
        self.storage_patch = patch(
            "app.services.storage_manager.get_storage_manager", return_value=FileStorageBackend()
        )
        self.vault_patch.start()
        self.storage_patch.start()

        self.admin = TestClient(app)
        admin = self.admin.post("/api/auth/initialize", json={
            "username": "owner", "display_name": "管理员", "password": "correct horse battery",
        }).json()["account"]
        invite = self.auth.create_invite(admin["id"], timedelta(days=1))
        self.user = TestClient(app)
        self.user.post("/api/auth/register", json={
            "invite_code": invite.code, "username": "parent", "display_name": "家长",
            "password": "another correct password",
        })
        self.admin_child = self.admin.post("/api/children", json={
            "name": "同名孩子", "emoji": "🧒", "subjects": ["数学"],
        }).json()
        self.user_child = self.user.post("/api/children", json={
            "name": "同名孩子", "emoji": "🧒", "subjects": ["数学"],
        }).json()
        self.admin_id = admin["id"]

    def tearDown(self):
        self.storage_patch.stop()
        self.vault_patch.stop()
        app.dependency_overrides.clear()
        self.temp_dir.cleanup()

    def test_question_and_image_are_scoped_to_logged_in_account(self):
        uploaded = self.admin.post(
            "/api/upload/images",
            files={"files": ("sample.png", b"test-image", "image/png")},
        ).json()["image_ids"]
        saved = self.admin.post("/api/questions", json={
            "child_id": self.admin_child["id"], "subject": "数学", "topic": "隔离测试",
            "source_type": "test", "difficulty": "easy", "error_date": "2026-09-27",
            "question_text": "6 × 7", "correct_answer": "42", "image_ids": uploaded,
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        question_id = saved.json()["id"]

        note = self.vault / "accounts" / self.admin_id / self.admin_child["id"] / "数学" / f"2026-09-27-{question_id}.md"
        image = self.vault / "_assets" / "accounts" / self.admin_id / self.admin_child["id"] / "数学" / question_id / "sample.png"
        self.assertTrue(note.exists())
        self.assertEqual(image.read_bytes(), b"test-image")
        content = note.read_text()
        self.assertIn(f"account_id: {self.admin_id}", content)
        self.assertIn(f"child_id: {self.admin_child['id']}", content)

        own = self.admin.get(
            f"/api/questions/{question_id}",
            params={"child_id": self.admin_child["id"], "subject": "数学"},
        )
        self.assertEqual(own.status_code, 200)
        cross = self.user.get(
            f"/api/questions/{question_id}",
            params={"child_id": self.admin_child["id"], "subject": "数学"},
        )
        self.assertEqual(cross.status_code, 404)
        cross_image = self.user.get(
            f"/api/questions/{question_id}/images/sample.png",
            params={"child_id": self.admin_child["id"], "subject": "数学"},
        )
        self.assertEqual(cross_image.status_code, 404)

        own_review = self.admin.get(
            "/api/review/plan", params={"child_id": self.admin_child["id"]}
        )
        cross_review = self.user.get(
            "/api/review/plan", params={"child_id": self.admin_child["id"]}
        )
        self.assertEqual(own_review.status_code, 200)
        self.assertEqual(own_review.json()["total"], 1)
        self.assertEqual(cross_review.status_code, 404)

        own_stats = self.admin.get(
            "/api/stats/overview", params={"child_id": self.admin_child["id"]}
        )
        cross_stats = self.user.get(
            "/api/stats/overview", params={"child_id": self.admin_child["id"]}
        )
        self.assertEqual(own_stats.json()["total"], 1)
        self.assertEqual(cross_stats.status_code, 404)

    def test_analysis_tasks_are_scoped_to_logged_in_account(self):
        uploaded = self.admin.post(
            "/api/upload/images",
            files={"files": ("task.png", b"task-image", "image/png")},
        ).json()["image_ids"]
        with patch(
            "app.api.routes.tasks.llm.analyze_images",
            new=AsyncMock(return_value={"question_text": "test"}),
        ):
            created = self.admin.post("/api/tasks", json={
                "child_id": self.admin_child["id"], "subject": "数学", "image_ids": uploaded,
            })
        self.assertEqual(created.status_code, 200, created.text)
        task_id = created.json()["task_id"]
        self.assertEqual(self.admin.get(f"/api/tasks/{task_id}").status_code, 200)
        self.assertEqual(self.user.get(f"/api/tasks/{task_id}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
