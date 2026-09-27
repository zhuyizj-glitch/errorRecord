"""复习接口"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_active_account, get_auth_service
from app.models.auth import Account
from app.services.auth_service import AuthService
from app.services import file_ops, review_scheduler

router = APIRouter()


@router.get("/review/plan")
async def get_review_plan(
    child_id: str = Query(...),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """获取今日待复习的错题列表"""
    with auth.db.connect() as connection:
        child = connection.execute(
            "SELECT 1 FROM children WHERE id = ? AND account_id = ?",
            (child_id, account.id),
        ).fetchone()
    if not child:
        raise HTTPException(status_code=404, detail="孩子不存在")
    questions = file_ops.list_questions(account.id, child_id)
    plan = review_scheduler.get_review_plan(questions)
    return {"plan": plan, "total": len(plan)}
