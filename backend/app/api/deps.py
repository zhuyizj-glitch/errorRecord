"""依赖注入与统一认证边界。"""

from fastapi import Cookie, Depends, HTTPException

from app.models.auth import Account
from app.services.auth_service import AuthService


SESSION_COOKIE = "mistakes_session"


def get_auth_service() -> AuthService:
    return AuthService()


def get_current_account(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    auth: AuthService = Depends(get_auth_service),
) -> Account:
    account = auth.resolve_session(session_token) if session_token else None
    if not account:
        raise HTTPException(status_code=401, detail="请先登录")
    return account


def require_admin(account: Account = Depends(get_current_account)) -> Account:
    if account.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return account


def get_active_account(account: Account = Depends(get_current_account)) -> Account:
    if account.must_change_password:
        raise HTTPException(status_code=403, detail="PASSWORD_CHANGE_REQUIRED")
    return account
