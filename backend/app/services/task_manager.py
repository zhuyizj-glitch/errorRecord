"""异步任务管理器 - 管理图片分析任务"""

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict


class TaskStatus(str, Enum):
    PENDING = "pending"       # 等待处理
    PROCESSING = "processing" # 分析中
    COMPLETED = "completed"   # 完成
    FAILED = "failed"         # 失败


@dataclass
class AnalysisTask:
    id: str
    child: str
    subject: str
    image_ids: list[dict]
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str = ""
    completed_at: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class TaskManager:
    """单例任务管理器"""

    def __init__(self):
        self.tasks: dict[str, AnalysisTask] = {}
        self._lock = asyncio.Lock()

    def create_task(self, child: str, subject: str, image_ids: list[dict]) -> AnalysisTask:
        """创建新任务"""
        task_id = uuid.uuid4().hex[:8]
        task = AnalysisTask(
            id=task_id,
            child=child,
            subject=subject,
            image_ids=image_ids,
        )
        self.tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[AnalysisTask]:
        """获取任务"""
        return self.tasks.get(task_id)

    def list_tasks(self, child: Optional[str] = None) -> list[dict]:
        """列出任务（按创建时间倒序）"""
        tasks = list(self.tasks.values())
        if child:
            tasks = [t for t in tasks if t.child == child]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks]

    async def update_status(self, task_id: str, status: TaskStatus,
                            result: Optional[dict] = None,
                            error: Optional[str] = None):
        """更新任务状态"""
        async with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.status = status
                if result is not None:
                    task.result = result
                if error is not None:
                    task.error = error
                if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    task.completed_at = datetime.now().isoformat()

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理旧任务"""
        now = datetime.now()
        to_remove = []
        for task_id, task in self.tasks.items():
            if task.completed_at:
                completed = datetime.fromisoformat(task.completed_at)
                if (now - completed).total_seconds() > max_age_hours * 3600:
                    to_remove.append(task_id)
        for task_id in to_remove:
            del self.tasks[task_id]


# 全局单例
task_manager = TaskManager()
