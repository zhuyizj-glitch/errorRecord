"""同步 API 路由"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import require_admin
from app.models.auth import Account
from app.services.sync_service import get_sync_service
from app.core.config import settings

router = APIRouter()


class RebuildRequest(BaseModel):
    """
    重建参数。

    prune：删除只在本地、IMA 里没有的错题文件，默认关闭。
    skip_unchanged：跳过云端未变更的笔记。默认 False——重建的前提是本地不可信，
    所以默认逐条重读；确信缓存只是缺了几条时可开。
    """
    prune: bool = False
    skip_unchanged: bool = False


@router.post("/sync/to-obsidian")
async def manual_sync_to_obsidian(_: Account = Depends(require_admin)):
    """
    手动触发同步到 Obsidian（保守模式）

    写入前比对版本，不会用旧快照覆盖本地更新的记录。日常用这个。
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


@router.post("/sync/rebuild-cache")
async def rebuild_cache(
    req: RebuildRequest = RebuildRequest(),
    _: Account = Depends(require_admin),
):
    """
    从 IMA 重建本地缓存（以 IMA 为准，强制覆盖）

    用于本地缓存丢失、损坏或不可信时。与 /sync/to-obsidian 的区别是：
    重建跳过冲突保护，让云端内容直接落到本地——此时本地的版本号没有参考价值。

    返回结果里的 `local_only` 是「只在本地、IMA 里没有」的错题数量。
    IMA 既然是权威来源，出现这类错题意味着某次写入没落到云端，
    值得看一眼。默认只报告不删除，确认后再用 prune=true 清理。
    """
    if not settings.ima_enabled:
        raise HTTPException(status_code=400, detail="IMA 存储未启用，无法重建缓存")

    sync_service = get_sync_service()
    result = await sync_service.rebuild_cache(
        prune=req.prune, skip_unchanged=req.skip_unchanged
    )

    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=502, detail=f"重建失败: {result['error']}")

    return {"success": True, "rebuild_result": result}


@router.get("/sync/status")
async def get_sync_status(_: Account = Depends(require_admin)):
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
async def get_sync_config(_: Account = Depends(require_admin)):
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
