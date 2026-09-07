"""同步 API 路由"""

from fastapi import APIRouter, HTTPException
from app.services.sync_service import get_sync_service
from app.core.config import settings

router = APIRouter()


@router.post("/sync/to-obsidian")
async def manual_sync_to_obsidian():
    """
    手动触发同步到 Obsidian

    Returns:
        同步结果统计
    """
    if not settings.ima_enabled:
        raise HTTPException(
            status_code=400,
            detail="IMA 存储未启用，无需同步"
        )

    sync_service = get_sync_service()
    result = await sync_service.sync_to_obsidian()

    return {
        "success": True,
        "sync_result": result,
    }


@router.get("/sync/status")
async def get_sync_status():
    """
    获取同步状态

    Returns:
        同步状态信息
    """
    sync_service = get_sync_service()
    status = await sync_service.get_sync_status()

    # 添加下次同步时间
    next_sync = sync_service.get_next_sync_time(settings.ima_sync_interval_hours)
    status["next_sync_time"] = next_sync.isoformat() if next_sync else None
    status["sync_interval_hours"] = settings.ima_sync_interval_hours

    return status


@router.get("/sync/config")
async def get_sync_config():
    """
    获取同步配置信息

    Returns:
        同步配置
    """
    return {
        "ima_enabled": settings.ima_enabled,
        "sync_interval_hours": settings.ima_sync_interval_hours,
        "primary_storage": "IMA" if settings.ima_enabled else "File",
        "fallback_storage": "File" if settings.ima_enabled else None,
    }
