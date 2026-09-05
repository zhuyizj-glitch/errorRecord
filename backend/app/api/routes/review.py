"""复习接口"""

from fastapi import APIRouter, Query

from app.services import file_ops, review_scheduler

router = APIRouter()


@router.get("/review/plan")
async def get_review_plan(child: str = Query(...)):
    """获取今日待复习的错题列表"""
    questions = file_ops.list_questions(child)
    plan = review_scheduler.get_review_plan(questions)
    return {"plan": plan, "total": len(plan)}
