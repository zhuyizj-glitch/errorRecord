"""存储管理器 - 根据配置选择存储后端"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.services import file_ops
from app.services.storage_backend import StorageBackend
from app.services.file_storage import FileStorageBackend
from app.services.ima_storage import IMAStorageBackend

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    """统一的版本标记格式，便于按字符串比较先后。"""
    return datetime.now(timezone.utc).isoformat()


# 不进入事件快照的字段：身份类字段不可变，created_at 是创建时间，
# redo_history 由折叠逻辑逐条追加而不是整体覆盖。
_FIELDS_NOT_IN_EVENT = {
    "id", "account_id", "ima_note_id", "created_at", "redo_history",
    "ima_modified_at",  # 纯本地缓存用的版本戳，不该写进云端事件
}


def _build_event(frontmatter: dict, event: Optional[dict]) -> dict:
    """
    构造要追加到 IMA 笔记的事件。

    事件携带**当前可变状态的完整快照**，而不是增量指令：折叠时逐条覆盖即可，
    不需要重放计算，也不怕漏掉某个事件导致状态算错。代价是每条事件约几百字节，
    而一次重做才产生一条，可以接受。

    `type` 与 `rev` 放在最后写入，避免被快照里的同名字段覆盖。
    """
    meta = dict(event or {})
    event_type = meta.pop("type", "patch")
    rev = int(frontmatter.get("rev") or 1) + 1

    snapshot = {
        key: value
        for key, value in frontmatter.items()
        if key not in _FIELDS_NOT_IN_EVENT
    }
    return {
        "at": frontmatter.get("updated_at"),
        **snapshot,
        **meta,
        "type": event_type,
        "rev": rev,
    }


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

    @property
    def ima_mode(self) -> bool:
        return isinstance(self.primary, IMAStorageBackend)

    async def save_question(self, *args, **kwargs) -> str:
        """
        保存错题（双写策略）

        IMA 模式下同时写入 IMA 和本地文件：
        - IMA 作为主存储（云端，稳定，权威）
        - 本地文件供 Obsidian 阅读，并作为读取层的快速数据源

        任一失败不影响另一个，只要有一个成功就算成功。
        """
        frontmatter = kwargs.get("frontmatter")
        if isinstance(frontmatter, dict):
            frontmatter["updated_at"] = utc_now_iso()
            frontmatter.setdefault("rev", 1)  # 基础块的版本号，事件从 2 开始

        primary_id = None
        fallback_id = None
        primary_err = None

        # 写主存储
        try:
            primary_id = await self.primary.save_question(*args, **kwargs)
        except Exception as e:
            primary_err = e
            logger.error(f"主存储写入失败: {e}")

        # 写备用存储（双写，不是降级）
        if self.fallback:
            # 把 IMA 笔记 ID 记进本地副本，后续重做/移动才能定位到对应的云端笔记。
            # IMA 侧不需要这个字段，所以只在写本地前注入。
            if primary_id and isinstance(frontmatter, dict):
                frontmatter["ima_note_id"] = primary_id
            try:
                fallback_id = await self.fallback.save_question(*args, **kwargs)
            except Exception as e:
                logger.error(f"备用存储写入失败: {e}")

        # 两个都失败才抛错
        if primary_id is None and fallback_id is None:
            raise primary_err or Exception("所有存储后端写入失败")

        if primary_id and fallback_id:
            logger.info(f"双写成功: IMA={primary_id}, File={fallback_id}")
        elif primary_id:
            logger.warning(f"仅主存储成功: {primary_id}")
        else:
            logger.warning(f"仅备用存储成功: {fallback_id}")

        # 返回本地路径（供现有读取链路使用），没有则返回主存储 ID
        return fallback_id or primary_id

    async def update_question(
        self,
        frontmatter: dict,
        body: Optional[str] = None,
        event: Optional[dict] = None,
    ) -> bool:
        """
        更新错题：IMA 追加事件（权威），本地刷新缓存（尽力而为）。

        IMA 没有修改接口，所以可变状态以**追加事件**的方式记录，读取时把
        基础块与事件折叠成当前状态（见 8.33 / 8.37）。本地文件是可丢弃的
        物化视图，随时能从 IMA 重建（见 8.36）。

        `event` 描述这次改动的性质，至少包含 `type`（redo / patch）。
        默认 patch，表示只更新字段、不产生重做记录。

        返回值的语义：
        - IMA 模式：**以事件写入 IMA 是否成功为准**。本地缓存刷新失败不算失败，
          因为缓存可以重建；反过来则不行，事件没写进去就等于这次改动丢了。
        - 文件模式：以本地写入是否成功为准。
        """
        # 剔除 _file / _storage_id 等内部字段，避免写进存储
        frontmatter = {k: v for k, v in dict(frontmatter).items() if not k.startswith("_")}
        frontmatter["updated_at"] = utc_now_iso()
        question_id = frontmatter.get("id")

        if self.ima_mode:
            note_id = frontmatter.get("ima_note_id")
            if note_id:
                payload = _build_event(frontmatter, event)
                appended = await self.primary.append_event(note_id, payload)
                if not appended:
                    logger.error(f"事件写入 IMA 失败，本次改动未生效: {question_id}")
                    return False

                refreshed = self._refresh_local_cache(frontmatter, body)
                if not refreshed:
                    logger.warning(
                        f"事件已写入 IMA，但本地缓存刷新失败（可重建）: {question_id}"
                    )
                return True

            # 缺少云端笔记 ID：无法追加。退回只写本地，并在日志里说清楚。
            logger.warning(
                f"错题 {question_id} 缺少 ima_note_id，本次改动只落到本地缓存；"
                "执行一次同步可补齐该字段"
            )

        return self._refresh_local_cache(frontmatter, body)

    def _refresh_local_cache(self, frontmatter: dict, body: Optional[str]) -> bool:
        """把折叠后的状态写进本地缓存文件。失败不影响主流程。"""
        question_id = frontmatter.get("id")
        local_path = file_ops.find_question_file(
            str(frontmatter.get("account_id", "")),
            str(frontmatter.get("child_id", "")),
            str(frontmatter.get("subject", "")),
            str(question_id or ""),
        )
        if not local_path:
            logger.warning(f"未找到本地缓存文件: {question_id}")
            return False
        try:
            file_ops.update_question(str(local_path), frontmatter, body)
            return True
        except Exception as e:
            logger.error(f"刷新本地缓存失败 {question_id}: {e}")
            return False

    async def read_authoritative(self, note_id: Optional[str]) -> Optional[dict]:
        """
        从权威存储（IMA）读取单条错题，供「读—改—写」类操作使用。

        列表和详情走本地缓存已经够用，但重做、移动这类要基于当前状态做计算的
        操作必须拿最新数据：本地缓存可能落后（例如你在 IMA 客户端直接改过笔记）。

        取不到时返回 None，由调用方退回本地缓存。
        """
        if not self.ima_mode or not note_id:
            return None
        try:
            return await self.primary.read_question(note_id)
        except Exception as e:
            logger.warning(f"从 IMA 读取 {note_id} 失败，将退回本地缓存: {e}")
            return None

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

    async def sync_to_obsidian(
        self,
        allowed_scopes: set[tuple[str, str]],
        force: bool = False,
        prune: bool = False,
        dry_run: bool = False,
        skip_unchanged: bool = True,
    ) -> dict:
        """
        把 IMA 的内容物化到本地缓存（仅当使用 IMA 时有效）。

        force=True 为重建模式：以 IMA 为准强制覆盖本地。
        dry_run=True 只统计不写入。
        skip_unchanged=True 时跳过云端未变更的笔记，避免逐条读正文。
        """
        if self.ima_mode and isinstance(self.fallback, FileStorageBackend):
            return await self.primary.sync_to_obsidian(
                self.fallback, allowed_scopes,
                force=force, prune=prune, dry_run=dry_run,
                skip_unchanged=skip_unchanged,
            )
        logger.info("当前不是 IMA + File 模式，跳过同步")
        return {
            "created": 0, "updated": 0, "forced": 0, "skipped": 0, "unchanged": 0,
            "preskipped": 0, "conflicts": 0, "errors": 0, "pruned": 0, "local_only": 0,
        }


# 全局存储管理器实例
_storage_manager: Optional[StorageManager] = None


def get_storage_manager() -> StorageManager:
    """获取存储管理器单例"""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = StorageManager()
    return _storage_manager
