"""账号密码、邀请码和会话服务。"""

import base64
import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.db import Database, database
from app.models.auth import Account, InviteToken, SessionToken


class AuthError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, db: Database = database, now: Callable[[], datetime] = utc_now):
        self.db = db
        self.now = now

    @staticmethod
    def _normalize_username(username: str) -> str:
        normalized = username.strip().casefold()
        if not re.fullmatch(r"[\w.-]{3,64}", normalized, flags=re.UNICODE):
            raise AuthError("用户名须为 3-64 位字母、数字、点、横线或下划线")
        return normalized

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < 10:
            raise AuthError("密码至少需要 10 个字符")

    @classmethod
    def _password_fields(cls, password: str) -> tuple[str, str]:
        cls._validate_password(password)
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return base64.b64encode(digest).decode(), base64.b64encode(salt).decode()

    @staticmethod
    def _account(row) -> Account:
        return Account(
            id=row["id"], username=row["username"], display_name=row["display_name"],
            password_hash=row["password_hash"], password_salt=row["password_salt"],
            role=row["role"], must_change_password=bool(row["must_change_password"]),
        )

    def has_accounts(self) -> bool:
        with self.db.connect() as connection:
            return connection.execute("SELECT 1 FROM accounts LIMIT 1").fetchone() is not None

    def create_initial_admin(self, username: str, display_name: str, password: str) -> Account:
        username = self._normalize_username(username)
        password_hash, password_salt = self._password_fields(password)
        account_id = f"acc_{uuid.uuid4().hex}"
        try:
            with self.db.transaction() as connection:
                if connection.execute("SELECT 1 FROM accounts LIMIT 1").fetchone():
                    raise AuthError("管理员已经初始化")
                connection.execute(
                    "INSERT INTO accounts "
                    "(id, username, display_name, password_hash, password_salt, role) "
                    "VALUES (?, ?, ?, ?, ?, 'admin')",
                    (account_id, username, display_name.strip(), password_hash, password_salt),
                )
                row = connection.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        except AuthError:
            raise
        return self._account(row)

    def verify_password(self, account: Account, password: str) -> bool:
        salt = base64.b64decode(account.password_salt)
        expected = base64.b64decode(account.password_hash)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)

    def get_account(self, account_id: str) -> Account | None:
        with self.db.connect() as connection:
            row = connection.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        return self._account(row) if row else None

    def authenticate(self, username: str, password: str) -> Account | None:
        try:
            username = self._normalize_username(username)
        except AuthError:
            return None
        with self.db.connect() as connection:
            row = connection.execute("SELECT * FROM accounts WHERE username = ?", (username,)).fetchone()
        account = self._account(row) if row else None
        return account if account and self.verify_password(account, password) else None

    def create_invite(self, admin_id: str, expires_in: timedelta) -> InviteToken:
        invite_id = f"inv_{uuid.uuid4().hex}"
        code = secrets.token_urlsafe(24)
        expires_at = _iso(self.now() + expires_in)
        with self.db.transaction() as connection:
            admin = connection.execute(
                "SELECT role FROM accounts WHERE id = ?", (admin_id,)
            ).fetchone()
            if not admin or admin["role"] != "admin":
                raise AuthError("仅管理员可以创建邀请码")
            connection.execute(
                "INSERT INTO invites (id, code_hash, created_by, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (invite_id, _hash_token(code), admin_id, _iso(self.now()), expires_at),
            )
        return InviteToken(invite_id, code, expires_at)

    def revoke_invite(self, admin_id: str, invite_id: str) -> None:
        with self.db.transaction() as connection:
            admin = connection.execute(
                "SELECT role FROM accounts WHERE id = ?", (admin_id,)
            ).fetchone()
            if not admin or admin["role"] != "admin":
                raise AuthError("仅管理员可以作废邀请码")
            updated = connection.execute(
                "UPDATE invites SET revoked_at = ? WHERE id = ? AND used_at IS NULL",
                (_iso(self.now()), invite_id),
            )
            if updated.rowcount != 1:
                raise AuthError("邀请码不存在或已经使用")

    def register_with_invite(
        self, code: str, username: str, display_name: str, password: str
    ) -> Account:
        username = self._normalize_username(username)
        password_hash, password_salt = self._password_fields(password)
        account_id = f"acc_{uuid.uuid4().hex}"
        now = _iso(self.now())
        with self.db.transaction() as connection:
            invite = connection.execute(
                "SELECT * FROM invites WHERE code_hash = ?", (_hash_token(code),)
            ).fetchone()
            if not invite:
                raise AuthError("邀请码无效")
            if invite["used_at"]:
                raise AuthError("邀请码已使用")
            if invite["revoked_at"]:
                raise AuthError("邀请码已作废")
            if datetime.fromisoformat(invite["expires_at"]) <= self.now():
                raise AuthError("邀请码已过期")
            try:
                connection.execute(
                    "INSERT INTO accounts "
                    "(id, username, display_name, password_hash, password_salt, role) "
                    "VALUES (?, ?, ?, ?, ?, 'user')",
                    (account_id, username, display_name.strip(), password_hash, password_salt),
                )
            except Exception as exc:
                raise AuthError("用户名已存在") from exc
            connection.execute(
                "UPDATE invites SET used_by = ?, used_at = ? WHERE id = ?",
                (account_id, now, invite["id"]),
            )
            row = connection.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        return self._account(row)

    def create_session(self, account_id: str, expires_in: timedelta) -> SessionToken:
        token = secrets.token_urlsafe(32)
        now = _iso(self.now())
        expires_at = _iso(self.now() + expires_in)
        with self.db.transaction() as connection:
            connection.execute(
                "INSERT INTO sessions (id_hash, account_id, created_at, expires_at, last_seen_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (_hash_token(token), account_id, now, expires_at, now),
            )
        return SessionToken(token, expires_at)

    def resolve_session(self, token: str) -> Account | None:
        with self.db.transaction() as connection:
            row = connection.execute(
                "SELECT accounts.*, sessions.expires_at FROM sessions "
                "JOIN accounts ON accounts.id = sessions.account_id WHERE sessions.id_hash = ?",
                (_hash_token(token),),
            ).fetchone()
            if not row:
                return None
            if datetime.fromisoformat(row["expires_at"]) <= self.now():
                connection.execute("DELETE FROM sessions WHERE id_hash = ?", (_hash_token(token),))
                return None
            connection.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE id_hash = ?",
                (_iso(self.now()), _hash_token(token)),
            )
        return self._account(row)

    def revoke_session(self, token: str) -> None:
        with self.db.transaction() as connection:
            connection.execute("DELETE FROM sessions WHERE id_hash = ?", (_hash_token(token),))

    def revoke_all_sessions(self, account_id: str) -> None:
        with self.db.transaction() as connection:
            connection.execute("DELETE FROM sessions WHERE account_id = ?", (account_id,))

    def change_password(self, account_id: str, current_password: str, new_password: str) -> None:
        account = self.get_account(account_id)
        if not account or not self.verify_password(account, current_password):
            raise AuthError("当前密码错误")
        password_hash, password_salt = self._password_fields(new_password)
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE accounts SET password_hash = ?, password_salt = ?, "
                "must_change_password = 0, updated_at = ? WHERE id = ?",
                (password_hash, password_salt, _iso(self.now()), account_id),
            )
            connection.execute("DELETE FROM sessions WHERE account_id = ?", (account_id,))
