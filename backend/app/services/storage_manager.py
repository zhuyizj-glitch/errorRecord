"""存储管理器 - 根据配置选择存储后端"""

import logging
from typing import Optional

from app.core.config import settings
from app.services.storage_backend import StorageBackend
from app.services.file_storage import FileStorageBackend
from app.services.ima_storage import IMAStorageBackend

logger = logging.getLogger(__name__)


class StorageManager:
    """存储管理器 - 主备存储策略"""

    def __init__(self):
        """初始化存储管理器"""
        self.primary: StorageBackend
        self.fallback: Optional[StorageBackend]

        if settings.ima_enabled:
            # IMA 作为主存储，文件作为降级方案
            self.primary = IMAStorageBackend()
            self.fallback = FileStorageBackend()
            logger.info("存储模式: IMA (主) + File (备)")
        else:
            # 仅使用文件存储
            self.primary = FileStorageBackend()
            self.fallback = None
            logger.info("存储模式: File (仅本地)")

    async def save_question(self, *args, **kwargs) -> str:
        """保存错题（主备策略）"""
        try:
            result = await self.primary.save_question(*args, **kwargs)
            return result
        except Exception as e:
            if self.fallback:
                logger.warning(f"主存储失败，切换到备用存储: {e}")
                try:
                    result = await self.fallback.save_question(*args, **kwargs)
                    return result
                except Exception as e2:
                    logger.error(f"备用存储也失败: {e2}")
                    raise
            else:
                raise

    async def list_questions(self, *args, **kwargs) -> list[dict]:
        """列出错题（主备策略）"""
        try:
            return await self.primary.list_questions(*args, **kwargs)
        except Exception as e:
            if self.fallback:
                logger.warning(f"主存储失败，切换到备用存储: {e}")
                return await self.fallback.list_questions(*args, **kwargs)
            else:
                raise

    async def read_question(self, storage_id: str) -> dict:
        """读取错题（主备策略）"""
        try:
            return await self.primary.read_question(storage_id)
        except Exception as e:
            if self.fallback:
                logger.warning(f"主存储失败，切换到备用存储: {e}")
                return await self.fallback.read_question(storage_id)
            else:
                raise

    async def update_question(self, storage_id: str, *args, **kwargs) -> bool:
        """更新错题（主备策略）"""
        try:
            return await self.primary.update_question(storage_id, *args, **kwargs)
        except Exception as e:
            if self.fallback:
                logger.warning(f"主存储失败，切换到备用存储: {e}")
                return await self.fallback.update_question(storage_id, *args, **kwargs)
            else:
                raise

    async def delete_question(self, storage_id: str) -> bool:
        """删除错题（主备策略）"""
        try:
            return await self.primary.delete_question(storage_id)
        except Exception as e:
            if self.fallback:
                logger.warning(f"主存储失败，切换到备用存储: {e}")
                return await self.fallback.delete_question(storage_id)
            else:
                raise

    async def get_image_url(self, storage_id: str, filename: str) -> Optional[str]:
        """获取图片 URL（主备策略）"""
        try:
            url = await self.primary.get_image_url(storage_id, filename)
            if url:
                return url
        except Exception as e:
            logger.warning(f"主存储获取图片 URL 失败: {e}")

        if self.fallback:
            return await self.fallback.get_image_url(storage_id, filename)
        return None

    async def sync_to_obsidian(self) -> dict:
        """同步到 Obsidian（仅当使用 IMA 时有效）"""
        if isinstance(self.primary, IMAStorageBackend) and isinstance(self.fallback, FileStorageBackend):
            return await self.primary.sync_to_obsidian(self.fallback)
        else:
            logger.info("当前不是 IMA + File 模式，跳过同步")
            return {"created": 0, "updated": 0, "deleted": 0}


# 全局存储管理器实例
_storage_manager: Optional[StorageManager] = None


def get_storage_manager() -> StorageManager:
    """获取存储管理器单例"""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = StorageManager()
    return _storage_manager
