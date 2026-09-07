"""定时任务调度器"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.services.sync_service import get_sync_service

logger = logging.getLogger(__name__)

# 全局调度器实例
scheduler: AsyncIOScheduler = None


async def scheduled_sync():
    """定时同步任务"""
    try:
        logger.info("执行定时同步任务...")
        sync_service = get_sync_service()
        result = await sync_service.sync_to_obsidian()
        logger.info(f"定时同步完成: {result}")
    except Exception as e:
        logger.error(f"定时同步失败: {e}")


def start_scheduler():
    """启动调度器"""
    global scheduler

    if scheduler is not None:
        logger.warning("调度器已在运行")
        return

    scheduler = AsyncIOScheduler()

    # 添加定时同步任务
    if settings.ima_enabled:
        interval_hours = settings.ima_sync_interval_hours
        scheduler.add_job(
            scheduled_sync,
            'interval',
            hours=interval_hours,
            id='sync_to_obsidian',
            name=f'同步到 Obsidian (每 {interval_hours} 小时)',
            replace_existing=True,
        )
        logger.info(f"定时同步任务已启动: 每 {interval_hours} 小时")

    scheduler.start()


def stop_scheduler():
    """停止调度器"""
    global scheduler

    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("调度器已停止")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    if settings.ima_enabled:
        start_scheduler()
    yield
    # 关闭时
    stop_scheduler()
