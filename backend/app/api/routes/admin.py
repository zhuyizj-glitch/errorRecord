"""管理员账号与邀请码 API。"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_auth_service, require_admin
from app.models.auth import Account
from app.services.auth_service import AuthError, AuthService


router = APIRouter()


class CreateInviteRequest(BaseModel):
    expires_in_days: int = Field(default=7, ge=1, le=90)


@router.post("/admin/invites", status_code=status.HTTP_201_CREATED)
def create_invite(
    req: CreateInviteRequest,
    admin: Account = Depends(require_admin),
    auth: AuthService = Depends(get_auth_service),
):
    invite = auth.create_invite(admin.id, timedelta(days=req.expires_in_days))
    return {"id": invite.id, "code": invite.code, "expires_at": invite.expires_at}


@router.get("/admin/invites")
def list_invites(
    _: Account = Depends(require_admin),
    auth: AuthService = Depends(get_auth_service),
):
    return {"invites": auth.list_invites()}


@router.delete("/admin/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invite(
    invite_id: str,
    admin: Account = Depends(require_admin),
    auth: AuthService = Depends(get_auth_service),
):
    try:
        auth.revoke_invite(admin.id, invite_id)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/accounts")
def list_accounts(
    _: Account = Depends(require_admin),
    auth: AuthService = Depends(get_auth_service),
):
    return {"accounts": auth.list_accounts()}


@router.post("/admin/accounts/{account_id}/reset-password")
def reset_password(
    account_id: str,
    admin: Account = Depends(require_admin),
    auth: AuthService = Depends(get_auth_service),
):
    try:
        password = auth.reset_password(admin.id, account_id)
    except AuthError as exc:
        code = 404 if "不存在" in str(exc) else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return {"temporary_password": password}
