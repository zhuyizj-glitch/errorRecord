"""认证 HTTP API 测试。"""

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.deps import get_auth_service
from app.db import Database
from app.services.auth_service import AuthService
from main import app


class AuthApiTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = Database(f"sqlite:///{Path(self.temp_dir.name) / 'app.db'}")
        database.initialize()
        self.auth = AuthService(database)
        app.dependency_overrides[get_auth_service] = lambda: self.auth
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.temp_dir.cleanup()

    def _initialize(self):
        return self.client.post("/api/auth/initialize", json={
            "username": "owner", "display_name": "管理员", "password": "correct horse battery",
        })

    def test_initialization_is_available_only_once(self):
        self.assertEqual(self.client.get("/api/auth/status").json(), {"initialized": False})

        response = self._initialize()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["account"]["role"], "admin")
        self.assertNotIn("password_hash", response.text)
        self.assertIn("mistakes_session", response.cookies)
        self.assertEqual(self.client.get("/api/auth/status").json(), {"initialized": True})
        self.assertEqual(self._initialize().status_code, 409)

    def test_login_me_and_logout(self):
        self._initialize()
        self.client.post("/api/auth/logout")

        invalid = self.client.post("/api/auth/login", json={
            "username": "owner", "password": "wrong password",
        })
        self.assertEqual(invalid.status_code, 401)

        logged_in = self.client.post("/api/auth/login", json={
            "username": "OWNER", "password": "correct horse battery",
        })
        self.assertEqual(logged_in.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").json()["username"], "owner")

        self.assertEqual(self.client.post("/api/auth/logout").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_register_consumes_invite_and_logs_in(self):
        admin_response = self._initialize()
        admin_id = admin_response.json()["account"]["id"]
        invite = self.auth.create_invite(admin_id, timedelta(days=1))
        self.client.post("/api/auth/logout")

        response = self.client.post("/api/auth/register", json={
            "invite_code": invite.code, "username": "parent", "display_name": "家长",
            "password": "another correct password",
        })

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["account"]["role"], "user")
        self.assertEqual(self.client.get("/api/auth/me").json()["username"], "parent")
        repeated = self.client.post("/api/auth/register", json={
            "invite_code": invite.code, "username": "other", "display_name": "其他",
            "password": "another correct password",
        })
        self.assertEqual(repeated.status_code, 400)

    def test_repeated_login_failures_are_rate_limited(self):
        for _ in range(5):
            response = self.client.post("/api/auth/login", json={
                "username": "blocked-user", "password": "wrong password",
            })
            self.assertEqual(response.status_code, 401)

        blocked = self.client.post("/api/auth/login", json={
            "username": "blocked-user", "password": "wrong password",
        })
        self.assertEqual(blocked.status_code, 429)

    def test_change_password_revokes_old_session(self):
        self._initialize()
        old_token = self.client.cookies.get("mistakes_session")

        changed = self.client.post("/api/auth/change-password", json={
            "current_password": "correct horse battery", "new_password": "new correct password",
        })

        self.assertEqual(changed.status_code, 200, changed.text)
        new_token = self.client.cookies.get("mistakes_session")
        self.assertNotEqual(old_token, new_token)
        old_client = TestClient(app, cookies={"mistakes_session": old_token})
        self.assertEqual(old_client.get("/api/auth/me").status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)


if __name__ == "__main__":
    unittest.main()
