"""认证领域模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Account:
    id: str
    username: str
    display_name: str
    password_hash: str
    password_salt: str
    role: str
    must_change_password: bool


@dataclass(frozen=True)
class InviteToken:
    id: str
    code: str
    expires_at: str


@dataclass(frozen=True)
class SessionToken:
    token: str
    expires_at: str
