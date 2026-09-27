"""管理员邀请码和密码重置 API 测试。"""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.deps import get_auth_service
from app.db import Database
from app.services.auth_service import AuthService
from main import app


class AdminApiTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = Database(f"sqlite:///{Path(self.temp_dir.name) / 'app.db'}")
        database.initialize()
        self.auth = AuthService(database)
        app.dependency_overrides[get_auth_service] = lambda: self.auth
        self.admin = TestClient(app)
        initialized = self.admin.post("/api/auth/initialize", json={
            "username": "owner", "display_name": "管理员", "password": "correct horse battery",
        })
        self.admin_id = initialized.json()["account"]["id"]

    def tearDown(self):
        app.dependency_overrides.clear()
        self.temp_dir.cleanup()

    def _create_user(self):
        invite = self.admin.post("/api/admin/invites", json={"expires_in_days": 2}).json()
        user = TestClient(app)
        registered = user.post("/api/auth/register", json={
            "invite_code": invite["code"], "username": "parent", "display_name": "家长",
            "password": "another correct password",
        })
        return user, registered.json()["account"]

    def test_admin_can_create_list_and_revoke_invites(self):
        created = self.admin.post("/api/admin/invites", json={"expires_in_days": 2})
        self.assertEqual(created.status_code, 201, created.text)
        invite = created.json()
        self.assertTrue(invite["code"])

        listed = self.admin.get("/api/admin/invites")
        self.assertEqual(listed.status_code, 200)
        self.assertNotIn("code", listed.json()["invites"][0])

        revoked = self.admin.delete(f"/api/admin/invites/{invite['id']}")
        self.assertEqual(revoked.status_code, 204)
        self.assertEqual(self.admin.get("/api/admin/invites").json()["invites"][0]["status"], "revoked")

    def test_normal_user_cannot_access_admin_endpoints(self):
        user, _ = self._create_user()
        self.assertEqual(user.get("/api/admin/invites").status_code, 403)
        self.assertEqual(user.get("/api/admin/accounts").status_code, 403)

    def test_password_reset_revokes_sessions_and_forces_change(self):
        user, account = self._create_user()
        self.assertEqual(user.get("/api/auth/me").status_code, 200)

        reset = self.admin.post(f"/api/admin/accounts/{account['id']}/reset-password")

        self.assertEqual(reset.status_code, 200, reset.text)
        temporary_password = reset.json()["temporary_password"]
        self.assertTrue(temporary_password)
        self.assertEqual(user.get("/api/auth/me").status_code, 401)

        login = user.post("/api/auth/login", json={
            "username": "parent", "password": temporary_password,
        })
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()["account"]["must_change_password"])


if __name__ == "__main__":
    unittest.main()
