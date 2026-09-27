"""账号级孩子与课程 API 测试。"""

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.deps import get_auth_service
from app.db import Database
from app.services.auth_service import AuthService
from main import app


class ChildrenApiTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(f"sqlite:///{Path(self.temp_dir.name) / 'app.db'}")
        self.database.initialize()
        self.auth = AuthService(self.database)
        self.vault = Path(self.temp_dir.name) / "vault"
        self.vault_patch = patch("app.core.config.settings.vault_path", str(self.vault))
        self.vault_patch.start()
        app.dependency_overrides[get_auth_service] = lambda: self.auth
        self.admin = TestClient(app)
        initialized = self.admin.post("/api/auth/initialize", json={
            "username": "owner", "display_name": "管理员", "password": "correct horse battery",
        }).json()["account"]
        invite = self.auth.create_invite(initialized["id"], timedelta(days=1))
        self.user = TestClient(app)
        self.user.post("/api/auth/register", json={
            "invite_code": invite.code, "username": "parent", "display_name": "家长",
            "password": "another correct password",
        })

    def tearDown(self):
        app.dependency_overrides.clear()
        self.vault_patch.stop()
        self.temp_dir.cleanup()

    def test_accounts_only_see_their_own_children(self):
        first = self.admin.post("/api/children", json={
            "name": "小明", "emoji": "🧒", "subjects": ["语文", "数学"],
        })
        second = self.user.post("/api/children", json={
            "name": "小明", "emoji": "👦", "subjects": ["英语", "物理"],
        })
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 201, second.text)

        admin_children = self.admin.get("/api/children").json()["children"]
        user_children = self.user.get("/api/children").json()["children"]
        self.assertEqual([child["id"] for child in admin_children], [first.json()["id"]])
        self.assertEqual([child["id"] for child in user_children], [second.json()["id"]])

        cross_account = self.user.patch(f"/api/children/{first.json()['id']}", json={
            "name": "越权修改", "emoji": "🧒", "subjects": ["数学"],
        })
        self.assertEqual(cross_account.status_code, 404)

    def test_subjects_use_whitelist_and_disabling_preserves_row(self):
        invalid = self.admin.post("/api/children", json={
            "name": "孩子", "emoji": "🧒", "subjects": ["编程"],
        })
        self.assertEqual(invalid.status_code, 422)

        created = self.admin.post("/api/children", json={
            "name": "孩子", "emoji": "🧒", "subjects": ["数学", "化学"],
        }).json()
        account_id = self.admin.get("/api/auth/me").json()["id"]
        math_dir = self.vault / "accounts" / account_id / created["id"] / "数学"
        chemistry_dir = self.vault / "accounts" / account_id / created["id"] / "化学"
        self.assertTrue(math_dir.is_dir())
        self.assertTrue(chemistry_dir.is_dir())
        updated = self.admin.patch(f"/api/children/{created['id']}", json={
            "name": "孩子", "emoji": "🧒", "subjects": ["数学"],
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["subjects"], ["数学"])

        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT enabled FROM child_subjects WHERE child_id = ? AND subject = '化学'",
                (created["id"],),
            ).fetchone()
        self.assertEqual(row["enabled"], 0)
        self.assertTrue(chemistry_dir.is_dir())


if __name__ == "__main__":
    unittest.main()
