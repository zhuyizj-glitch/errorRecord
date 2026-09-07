"""同步服务 - 定时同步和手动触发"""

import logging
from datetime import datetime
from typing import Optional

from app.services.storage_manager import get_storage_manager
from app.services.ima_storage import IMAStorageBackend

logger = logging.getLogger(__name__)


class SyncService:
    """同步服务"""

    def __init__(self):
        self.storage_manager = get_storage_manager()
        self.last_sync_time: Optional[datetime] = None
        self.sync_stats: dict = {}

    async def sync_to_obsidian(self) -> dict:
        """
        从 IMA 同步到 Obsidian

        Returns:
            同步统计信息
        """
        try:
            logger.info("开始同步: IMA → Obsidian")

            if isinstance(self.storage_manager.primary, IMAStorageBackend):
                stats = await self.storage_manager.sync_to_obsidian()
                self.last_sync_time = datetime.now()
                self.sync_stats = stats
                logger.info(f"同步完成: {stats}")
                return stats
            else:
                logger.info("当前不是 IMA 主存储模式，跳过同步")
                return {"skipped": True, "reason": "not_ima_mode"}

        except Exception as e:
            logger.error(f"同步失败: {e}")
            return {"error": str(e)}

    async def get_sync_status(self) -> dict:
        """
        获取同步状态

        Returns:
            同步状态信息
        """
        return {
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "last_sync_stats": self.sync_stats,
            "primary_storage": type(self.storage_manager.primary).__name__,
            "fallback_storage": type(self.storage_manager.fallback).__name__ if self.storage_manager.fallback else None,
        }

    def get_next_sync_time(self, interval_hours: int = 12) -> Optional[datetime]:
        """
        计算下次同步时间

        Args:
            interval_hours: 同步间隔（小时）

        Returns:
            下次同步时间，如果从未同步过则返回 None
        """
        if not self.last_sync_time:
            return None

        from datetime import timedelta
        return self.last_sync_time + timedelta(hours=interval_hours)


# 全局同步服务实例
_sync_service: Optional[SyncService] = None


def get_sync_service() -> SyncService:
    """获取同步服务单例"""
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService()
    return _sync_service
