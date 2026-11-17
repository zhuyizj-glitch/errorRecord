"""同步服务 - 定时同步和手动触发"""

import logging
from datetime import datetime
from typing import Optional

from app.services.storage_manager import get_storage_manager
from app.services.ima_storage import IMAStorageBackend
from app.db import database

logger = logging.getLogger(__name__)


class SyncService:
    """同步服务"""

    def __init__(self):
        self.storage_manager = get_storage_manager()
        self.last_sync_time: Optional[datetime] = None
        self.sync_stats: dict = {}

    def _allowed_scopes(self) -> set[tuple[str, str]]:
        """当前数据库里存在的 (account_id, child_id) 组合。"""
        with database.connect() as connection:
            rows = connection.execute("SELECT account_id, id FROM children").fetchall()
        return {(row["account_id"], row["id"]) for row in rows}

    async def sync_to_obsidian(self) -> dict:
        """
        从 IMA 同步到 Obsidian（保守模式）

        写入前比对版本，不会用旧快照覆盖本地更新的记录。
        """
        return await self._run(
            force=False, prune=False, skip_unchanged=True, label="IMA → Obsidian"
        )

    async def rebuild_cache(
        self, prune: bool = False, dry_run: bool = False, skip_unchanged: bool = False
    ) -> dict:
        """
        从 IMA 重建本地缓存（以 IMA 为准，强制覆盖）。

        用于本地缓存丢失、损坏或不可信时。此时本地的版本号没有参考价值，
        所以跳过冲突保护，让云端内容直接落到本地。

        prune=True 会一并删除「只在本地、IMA 里没有」的错题文件；默认只报告。
        dry_run=True 只统计不写入。

        `skip_unchanged` 默认 **False**：重建的前提就是「本地可能整个不可信」，
        所以默认把每条笔记都重新读一遍。如果你确信缓存只是缺了几条、内容没被动过，
        传 True 可大幅加速。
        """
        return await self._run(
            force=True, prune=prune, dry_run=dry_run,
            skip_unchanged=skip_unchanged, label="重建本地缓存",
        )

    async def _run(
        self, force: bool, prune: bool, dry_run: bool, skip_unchanged: bool, label: str
    ) -> dict:
        try:
            logger.info(
                f"开始{label}（force={force}, prune={prune}, "
                f"dry_run={dry_run}, skip_unchanged={skip_unchanged}）"
            )

            if not isinstance(self.storage_manager.primary, IMAStorageBackend):
                logger.info("当前不是 IMA 主存储模式，跳过")
                return {"skipped": True, "reason": "not_ima_mode"}

            stats = await self.storage_manager.sync_to_obsidian(
                self._allowed_scopes(), force=force, prune=prune,
                dry_run=dry_run, skip_unchanged=skip_unchanged,
            )
            if not dry_run:
                self.last_sync_time = datetime.now()
                self.sync_stats = stats
            logger.info(f"{label}完成: {stats}")
            return stats

        except Exception as e:
            logger.error(f"{label}失败: {e}")
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
