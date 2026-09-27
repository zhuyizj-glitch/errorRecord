"""初始化、注册、登录和个人密码 API。"""

from datetime import timedelta
from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.api.deps import SESSION_COOKIE, get_auth_service, get_current_account
from app.core.config import settings
from app.models.auth import Account
from app.services.auth_service import AuthError, AuthService


router = APIRouter()
SESSION_AGE = timedelta(days=30)


class LoginLimiter:
    def __init__(self, max_failures: int = 5, window_seconds: int = 300):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.failures: dict[str, deque[float]] = defaultdict(deque)
        self.lock = Lock()

    def _active(self, key: str) -> deque[float]:
        attempts = self.failures[key]
        cutoff = monotonic() - self.window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        return attempts

    def blocked(self, key: str) -> bool:
        with self.lock:
            return len(self._active(key)) >= self.max_failures

    def fail(self, key: str) -> None:
        with self.lock:
            self._active(key).append(monotonic())

    def clear(self, key: str) -> None:
        with self.lock:
            self.failures.pop(key, None)


login_limiter = LoginLimiter()


class InitializeRequest(BaseModel):
    username: str
    display_name: str
    password: str


class RegisterRequest(InitializeRequest):
    invite_code: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _public_account(account: Account) -> dict:
    return {
        "id": account.id,
        "username": account.username,
        "display_name": account.display_name,
        "role": account.role,
        "must_change_password": account.must_change_password,
    }


def _set_session(response: Response, auth: AuthService, account_id: str) -> None:
    session = auth.create_session(account_id, SESSION_AGE)
    response.set_cookie(
        SESSION_COOKIE, session.token, max_age=int(SESSION_AGE.total_seconds()),
        httponly=True, secure=settings.cookie_secure, samesite="lax", path="/",
    )


@router.get("/auth/status")
def auth_status(auth: AuthService = Depends(get_auth_service)):
    return {"initialized": auth.has_accounts()}


@router.post("/auth/initialize", status_code=status.HTTP_201_CREATED)
def initialize(req: InitializeRequest, response: Response, auth: AuthService = Depends(get_auth_service)):
    try:
        account = auth.create_initial_admin(req.username, req.display_name, req.password)
    except AuthError as exc:
        raise HTTPException(
            status_code=409 if "已经初始化" in str(exc) else 400, detail=str(exc)
        ) from exc
    _set_session(response, auth, account.id)
    return {"account": _public_account(account)}


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, response: Response, auth: AuthService = Depends(get_auth_service)):
    try:
        account = auth.register_with_invite(
            req.invite_code, req.username, req.display_name, req.password
        )
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _set_session(response, auth, account.id)
    return {"account": _public_account(account)}


@router.post("/auth/login")
def login(
    req: LoginRequest,
    response: Response,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    client_host = request.client.host if request.client else "unknown"
    limit_key = f"{client_host}:{req.username.strip().casefold()}"
    if login_limiter.blocked(limit_key):
        raise HTTPException(status_code=429, detail="登录失败次数过多，请稍后再试")
    account = auth.authenticate(req.username, req.password)
    if not account:
        login_limiter.fail(limit_key)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    login_limiter.clear(limit_key)
    _set_session(response, auth, account.id)
    return {"account": _public_account(account)}


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    auth: AuthService = Depends(get_auth_service),
):
    if session_token:
        auth.revoke_session(session_token)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/auth/me")
def me(account: Account = Depends(get_current_account)):
    return _public_account(account)


@router.post("/auth/change-password")
def change_password(
    req: ChangePasswordRequest,
    response: Response,
    account: Account = Depends(get_current_account),
    auth: AuthService = Depends(get_auth_service),
):
    try:
        auth.change_password(account.id, req.current_password, req.new_password)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _set_session(response, auth, account.id)
    return {"success": True}
