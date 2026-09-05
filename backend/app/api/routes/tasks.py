"""异步任务 API"""

import asyncio
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Body

from app.services.task_manager import task_manager, TaskStatus
from app.services import llm

router = APIRouter()


class CreateTaskRequest(BaseModel):
    child: str
    subject: str
    image_ids: list[dict]


class RefineRequest(BaseModel):
    feedback: str  # 用户的反馈/建议
    current_result: dict  # 当前的分析结果


class RegenerateRequest(BaseModel):
    image_ids: list[dict]


async def _run_analysis(task_id: str, image_paths: list[Path]):
    """后台执行 AI 分析"""
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
):
    """
    创建异步分析任务。
    立即返回任务 ID，分析在后台执行。
    """
    # 验证图片路径
    valid_paths = []
    for img in req.image_ids:
        path = Path(img.get("path", ""))
        if path.exists():
            valid_paths.append(path)

    if not valid_paths:
        raise HTTPException(status_code=400, detail="没有找到有效的图片文件")

    # 创建任务
    task = task_manager.create_task(req.child, req.subject, req.image_ids)

    # 后台执行分析
    background_tasks.add_task(_run_analysis, task.id, valid_paths)

    return {
        "task_id": task.id,
        "status": task.status.value,
        "created_at": task.created_at,
    }


@router.get("/tasks")
async def list_tasks(child: Optional[str] = Query(None)):
    """列出所有任务（按创建时间倒序）"""
    tasks = task_manager.list_tasks(child)
    return {"tasks": tasks, "total": len(tasks)}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """获取任务状态和结果"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task.to_dict()


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    del task_manager.tasks[task_id]
    return {"success": True}


async def _run_refine(task_id: str, image_paths: list[Path], feedback: str, current_result: dict):
    """后台执行反馈优化"""
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
):
    """
    根据用户反馈重新优化分析结果。
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

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
):
    """
    重新分析任务（使用新的图片）。
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 获取图片路径
    valid_paths = []
    for img in req.image_ids:
        path = Path(img.get("path", ""))
        if path.exists():
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
