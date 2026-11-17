"""异步任务 API"""

import asyncio
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Body

from app.api.deps import get_active_account, get_auth_service
from app.api.routes.upload import TEMP_DIR
from app.models.auth import Account
from app.services.auth_service import AuthService
from app.services.task_manager import task_manager, TaskStatus
from app.services import llm

router = APIRouter()

# 串行锁：保证同一时间只跑一个 AI 分析。
#
# 多图上传时前端会为**每张图各建一个任务**（这样完成一张就能立刻看到一张的结果）。
# 若它们并发执行，会同时向 AI 服务发多个请求 —— 可能触发限流、也可能互相拖慢。
# 串起来跑更稳，而且用户本来就想一张一张看到结果。
#
# 单进程 uvicorn 下 asyncio.Lock 就够；将来若改成多 worker，需要换成外部队列。
_analysis_lock = asyncio.Lock()


class CreateTaskRequest(BaseModel):
    child_id: str
    subject: str
    image_ids: list[dict]


class RefineRequest(BaseModel):
    feedback: str  # 用户的反馈/建议
    current_result: dict  # 当前的分析结果


class RegenerateRequest(BaseModel):
    image_ids: list[dict]


def _require_child(auth: AuthService, account_id: str, child_id: str, subject: str):
    with auth.db.connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM children JOIN child_subjects ON children.id = child_subjects.child_id "
            "WHERE children.id = ? AND children.account_id = ? "
            "AND child_subjects.subject = ? AND child_subjects.enabled = 1",
            (child_id, account_id, subject),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="孩子或课程不存在")


def _owned_task(task_id: str, account_id: str):
    task = task_manager.get_task(task_id)
    if not task or task.account_id != account_id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


async def _run_analysis(task_id: str, image_paths: list[Path]):
    """后台执行 AI 分析（串行：同一时间只跑一个）"""
    async with _analysis_lock:
        try:
            await task_manager.update_status(task_id, TaskStatus.PROCESSING)
            result = await llm.analyze_images(image_paths)
            await task_manager.update_status(task_id, TaskStatus.COMPLETED, result=result)
        except Exception as e:
            await task_manager.update_status(task_id, TaskStatus.FAILED, error=str(e))


@router.post("/tasks")
async def create_task(
    req: CreateTaskRequest,
    background_tasks: BackgroundTasks,
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """
    创建异步分析任务。
    立即返回任务 ID，分析在后台执行。
    """
    # 验证图片路径
    _require_child(auth, account.id, req.child_id, req.subject)
    valid_paths = []
    account_dir = (TEMP_DIR / account.id).resolve()
    for img in req.image_ids:
        path = Path(img.get("path", "")).resolve()
        if path.parent == account_dir and path.is_file():
            valid_paths.append(path)

    if not valid_paths:
        raise HTTPException(status_code=400, detail="没有找到有效的图片文件")

    # 创建任务
    task = task_manager.create_task(account.id, req.child_id, req.subject, req.image_ids)

    # 后台执行分析
    background_tasks.add_task(_run_analysis, task.id, valid_paths)

    return {
        "task_id": task.id,
        "status": task.status.value,
        "created_at": task.created_at,
    }


@router.get("/tasks")
async def list_tasks(
    child_id: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
):
    """列出所有任务（按创建时间倒序）"""
    tasks = task_manager.list_tasks(account.id, child_id)
    return {"tasks": tasks, "total": len(tasks)}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, account: Account = Depends(get_active_account)):
    """获取任务状态和结果"""
    task = _owned_task(task_id, account.id)
    return task.to_dict()


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, account: Account = Depends(get_active_account)):
    """删除任务"""
    _owned_task(task_id, account.id)
    del task_manager.tasks[task_id]
    return {"success": True}


async def _run_refine(task_id: str, image_paths: list[Path], feedback: str, current_result: dict):
    """后台执行反馈优化（与普通分析共用同一把锁，所以也是串行的）"""
    async with _analysis_lock:
        try:
            await task_manager.update_status(task_id, TaskStatus.PROCESSING)
            result = await llm.refine_analysis(image_paths, feedback, current_result)
            await task_manager.update_status(task_id, TaskStatus.COMPLETED, result=result)
        except Exception as e:
            await task_manager.update_status(task_id, TaskStatus.FAILED, error=str(e))


@router.post("/tasks/{task_id}/refine")
async def refine_task(
    task_id: str,
    req: RefineRequest,
    background_tasks: BackgroundTasks,
    account: Account = Depends(get_active_account),
):
    """
    根据用户反馈重新优化分析结果。
    """
    task = _owned_task(task_id, account.id)

    # 获取图片路径
    valid_paths = []
    for img in task.image_ids:
        path = Path(img.get("path", ""))
        if path.exists():
            valid_paths.append(path)

    if not valid_paths:
        raise HTTPException(status_code=400, detail="没有找到有效的图片文件")

    # 后台执行优化
    background_tasks.add_task(_run_refine, task_id, valid_paths, req.feedback, req.current_result)

    return {
        "task_id": task_id,
        "status": "processing",
        "message": "正在根据您的反馈重新分析...",
    }


@router.post("/tasks/{task_id}/regenerate")
async def regenerate_task(
    task_id: str,
    req: RegenerateRequest,
    background_tasks: BackgroundTasks,
    account: Account = Depends(get_active_account),
):
    """
    重新分析任务（使用新的图片）。
    """
    task = _owned_task(task_id, account.id)

    # 获取图片路径
    valid_paths = []
    account_dir = (TEMP_DIR / account.id).resolve()
    for img in req.image_ids:
        path = Path(img.get("path", "")).resolve()
        if path.parent == account_dir and path.is_file():
            valid_paths.append(path)

    if not valid_paths:
        raise HTTPException(status_code=400, detail="没有找到有效的图片文件")

    # 更新任务的图片
    task.image_ids = req.image_ids

    # 后台执行分析
    background_tasks.add_task(_run_analysis, task_id, valid_paths)

    return {
        "task_id": task_id,
        "status": "processing",
        "message": "正在重新分析...",
    }
