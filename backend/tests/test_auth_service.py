"""密码、邀请码和会话服务测试。"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.db import Database
from app.services.auth_service import AuthError, AuthService


class Clock:
    def __init__(self):
        self.value = datetime(2026, 9, 27, 8, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


class AuthServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(f"sqlite:///{Path(self.temp_dir.name) / 'app.db'}")
        self.database.initialize()
        self.clock = Clock()
        self.auth = AuthService(self.database, now=self.clock)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_password_is_hashed_and_verified(self):
        account = self.auth.create_initial_admin("Owner", "家庭管理员", "correct horse battery")

        self.assertNotEqual(account.password_hash, "correct horse battery")
        self.assertTrue(self.auth.verify_password(account, "correct horse battery"))
        self.assertFalse(self.auth.verify_password(account, "wrong password"))

    def test_invite_can_only_register_one_account(self):
        admin = self.auth.create_initial_admin("Owner", "家庭管理员", "correct horse battery")
        invite = self.auth.create_invite(admin.id, expires_in=timedelta(days=1))

        account = self.auth.register_with_invite(
            invite.code, "Parent", "家长", "another correct password"
        )

        self.assertEqual(account.username, "parent")
        with self.assertRaisesRegex(AuthError, "邀请码已使用"):
            self.auth.register_with_invite(
                invite.code, "Another", "另一位", "another correct password"
            )

    def test_expired_and_revoked_invites_are_rejected(self):
        admin = self.auth.create_initial_admin("owner", "管理员", "correct horse battery")
        expired = self.auth.create_invite(admin.id, expires_in=timedelta(minutes=1))
        self.clock.value += timedelta(minutes=2)
        with self.assertRaisesRegex(AuthError, "邀请码已过期"):
            self.auth.register_with_invite(expired.code, "user1", "用户一", "long password one")

        active = self.auth.create_invite(admin.id, expires_in=timedelta(days=1))
        self.auth.revoke_invite(admin.id, active.id)
        with self.assertRaisesRegex(AuthError, "邀请码已作废"):
            self.auth.register_with_invite(active.code, "user2", "用户二", "long password two")

    def test_session_expires_and_can_be_revoked(self):
        account = self.auth.create_initial_admin("owner", "管理员", "correct horse battery")
        session = self.auth.create_session(account.id, expires_in=timedelta(minutes=10))

        self.assertEqual(self.auth.resolve_session(session.token).id, account.id)
        self.auth.revoke_session(session.token)
        self.assertIsNone(self.auth.resolve_session(session.token))

        second = self.auth.create_session(account.id, expires_in=timedelta(minutes=10))
        self.clock.value += timedelta(minutes=11)
        self.assertIsNone(self.auth.resolve_session(second.token))


if __name__ == "__main__":
    unittest.main()
