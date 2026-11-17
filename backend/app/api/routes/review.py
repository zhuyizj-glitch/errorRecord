"""复习接口"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_active_account, get_auth_service
from app.models.auth import Account
from app.services.auth_service import AuthService
from app.services import file_ops, review_scheduler
from app.services.body_parser import decorate_with_sections

router = APIRouter()


@router.get("/review/plan")
async def get_review_plan(
    child_id: str = Query(...),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """获取今日待复习的错题列表（含题干与答案）

    这里必须带 include_body=True：题干、正确答案、解题过程、错因分析
    **全在 markdown 正文里**，不带正文的话复习页拿不到任何可显示的内容
    （此前正是如此 —— 页面只显示"知识点"，点开答案是"请回到错题列表查看"）。

    返回结构对前端是纯增量：`plan` / `total` 两个键不变，每道题多出
    `_body` / `_question` / `_answer` / `_solution` / `_error_analysis`
    / `_parent_note` / `_structured`。
    """
    with auth.db.connect() as connection:
        child = connection.execute(
            "SELECT 1 FROM children WHERE id = ? AND account_id = ?",
            (child_id, account.id),
        ).fetchone()
    if not child:
        raise HTTPException(status_code=404, detail="孩子不存在")

    questions = file_ops.list_questions(account.id, child_id, include_body=True)
    plan = review_scheduler.get_review_plan(questions)
    items = [decorate_with_sections(q) for q in plan]
    return {"plan": items, "total": len(items)}
