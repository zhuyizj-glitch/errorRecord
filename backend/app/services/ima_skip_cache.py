"""IMA 笔记跳过缓存

记录「已确认不是本系统的错题笔记」以及它们的 modify_time。下一轮同步遇到
同一篇且未变更的笔记，就不必再读正文。

为什么需要：知识库里除了错题，还有历史格式的笔记、别的用途的笔记。它们每次
同步都会被完整读一遍然后丢弃——在笔记较多时，这部分开销会超过真正的错题。
实测（8.40）：一次同步读 29 条，其中只有 1 条是有效错题。

为什么用 modify_time 判定、而不是「summary 里没看到 account_id 就跳过」：
后者会因为 summary 被截断而误杀真正的错题，而错题漏同步是静默的数据丢失。
modify_time 是服务端给的确定性信号，只有「确实没变过」才会跳过。

缓存文件损坏或缺失时一律当作空缓存——最坏的结果只是多读几条，不会漏。
"""

import json
import logging
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# 跳过原因，便于排查
REASON_NOT_A_QUESTION = "not_a_question"
REASON_FOREIGN_ACCOUNT = "foreign_account"


class ImaSkipCache:
    """已确认无需处理的 IMA 笔记及其版本戳。"""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (settings.config_dir / "ima_skip_cache.json")
        self.entries: dict[str, dict] = {}
        self.dirty = False
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.entries = {
                    str(k): v for k, v in data.items() if isinstance(v, dict)
                }
        except Exception as e:
            # 损坏就当作空，重新积累即可——多读几条好过因为读不了缓存而报错
            logger.warning(f"跳过缓存无法解析，将重建: {e}")
            self.entries = {}

    def should_skip(self, note_id: str, modified_at) -> bool:
        """该笔记的修改时间与记录一致（或未变）时可以跳过读取。"""
        entry = self.entries.get(note_id)
        if not entry or not modified_at:
            return False
        return entry.get("modified_at") == modified_at

    def mark(self, note_id: str, modified_at, reason: str) -> None:
        if not note_id or not modified_at:
            return
        current = self.entries.get(note_id)
        if current and current.get("modified_at") == modified_at:
            return
        self.entries[note_id] = {"modified_at": modified_at, "reason": reason}
        self.dirty = True

    def forget(self, note_id: str) -> None:
        if self.entries.pop(note_id, None) is not None:
            self.dirty = True

    def prune_absent(self, present_ids: set[str]) -> int:
        """清掉已经不在知识库里的条目，避免文件无限增长。"""
        stale = [nid for nid in self.entries if nid not in present_ids]
        for note_id in stale:
            self.entries.pop(note_id, None)
        if stale:
            self.dirty = True
        return len(stale)

    def save(self) -> None:
        if not self.dirty:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.entries, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.dirty = False
        except Exception as e:
            logger.error(f"写入跳过缓存失败 {self.path}: {e}")
