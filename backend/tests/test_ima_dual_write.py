"""IMA 双写与同步冲突保护测试。

覆盖两个数据安全问题：
1. 重做/移动必须同时写回 IMA，否则云端永远是保存时的旧快照
2. 定时同步不得用 IMA 的旧快照覆盖本地更新的记录
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.services import file_ops
from app.services.file_storage import FileStorageBackend
from app.services.ima_skip_cache import ImaSkipCache
from app.services.ima_storage import IMAStorageBackend
from app.services.storage_manager import StorageManager

OLD = "2026-09-27T10:00:00+00:00"
NEW = "2026-09-27T12:00:00+00:00"


class FakeImaStorage(IMAStorageBackend):
    """替身 IMA 后端：继承真类以通过 StorageManager 的 isinstance 判断。"""

    def __init__(self):
        self.client = None
        self.saved = []
        self.appended = []          # [(note_id, event)]
        self.append_result = True

    async def save_question(self, **kwargs):
        self.saved.append(kwargs)
        return "note_from_ima"

    async def append_event(self, storage_id, event):
        self.appended.append((storage_id, event))
        return self.append_result


def make_manager(fake_ima) -> StorageManager:
    """绕过 __init__ 的 settings 依赖，直接注入替身后端。"""
    manager = StorageManager.__new__(StorageManager)
    manager.primary = fake_ima
    manager.fallback = FileStorageBackend()
    return manager


def base_frontmatter(**overrides) -> dict:
    frontmatter = {
        "id": "q1", "account_id": "acc_1", "child_id": "child_1", "child_name": "女儿",
        "subject": "数学", "topic": "一元二次方程", "error_type": "计算错误",
        "error_date": "2026-09-20", "mastery_score": 0,
    }
    frontmatter.update(overrides)
    return frontmatter


class DualWriteTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.vault = Path(self._temp.name) / "vault"
        self.vault.mkdir()
        self._vault_patch = patch.object(settings, "vault_path", str(self.vault))
        self._vault_patch.start()
        self._config_patch = patch.object(settings, "config_path", str(self._temp.name))
        self._config_patch.start()
        self.fake_ima = FakeImaStorage()
        self.manager = make_manager(self.fake_ima)

    def tearDown(self):
        self._config_patch.stop()
        self._vault_patch.stop()
        self._temp.cleanup()

    def read_local(self) -> dict:
        path = file_ops.find_question_file("acc_1", "child_1", "数学", "q1")
        self.assertIsNotNone(path, "本地缓存文件应当存在")
        return file_ops.read_question(str(path))

    async def save(self, **overrides):
        await self.manager.save_question(
            question_id="q1", account_id="acc_1", child_id="child_1", subject="数学",
            frontmatter=base_frontmatter(**overrides), body="正文内容",
        )

    async def test_save_injects_version_and_note_id_into_local_copy(self):
        await self.save()
        local = self.read_local()
        self.assertEqual(local["ima_note_id"], "note_from_ima")
        self.assertTrue(local.get("updated_at"), "应当写入 updated_at")
        self.assertEqual(local.get("rev"), 1, "基础块版本号从 1 开始")

    async def test_update_appends_event_instead_of_rewriting_note(self):
        """
        IMA 没有修改接口，所以更新必须以**追加事件**的方式落库。
        """
        await self.save()
        local = self.read_local()
        local["mastery_score"] = 84
        local["consecutive_correct"] = 3

        ok = await self.manager.update_question(
            local, "正文内容", event={"type": "redo", "result": "correct", "note": "没写符号"}
        )

        self.assertTrue(ok)
        self.assertEqual(len(self.fake_ima.appended), 1, "应当追加一个事件")
        note_id, event = self.fake_ima.appended[0]
        self.assertEqual(note_id, "note_from_ima")
        self.assertEqual(event["type"], "redo")
        self.assertEqual(event["rev"], 2, "事件版本号在基础块之后递增")
        self.assertEqual(event["mastery_score"], 84)
        self.assertEqual(event["result"], "correct")
        self.assertEqual(event["note"], "没写符号")
        self.assertTrue(event["at"], "事件应带时间戳")

    async def test_event_excludes_identity_fields(self):
        """身份类字段不可变，不该进入事件快照。"""
        await self.save()
        local = self.read_local()
        local["mastery_score"] = 56

        await self.manager.update_question(local, "正文内容")

        event = self.fake_ima.appended[0][1]
        for field in ("id", "account_id", "ima_note_id", "created_at"):
            self.assertNotIn(field, event, f"{field} 不该出现在事件里")

    async def test_event_defaults_to_patch_type(self):
        await self.save()
        local = self.read_local()
        local["topic"] = "改过的主题"

        await self.manager.update_question(local, "正文内容")

        self.assertEqual(self.fake_ima.appended[0][1]["type"], "patch")

    async def test_update_refreshes_local_cache(self):
        await self.save()
        local = self.read_local()
        local["mastery_score"] = 68

        await self.manager.update_question(local, "正文内容")

        cached = self.read_local()
        self.assertEqual(cached["mastery_score"], 68, "本地缓存应当同步刷新")
        # 内部字段只存在于内存中的解析结果，不应写进文件的 frontmatter
        raw = Path(cached["_file"]).read_text(encoding="utf-8")
        self.assertNotIn("_file:", raw)
        self.assertNotIn("_body:", raw)

    async def test_update_returns_false_when_append_fails(self):
        """事件没写进 IMA 就等于改动丢了，不能返回成功。"""
        await self.save()
        self.fake_ima.append_result = False
        local = self.read_local()
        local["mastery_score"] = 84

        ok = await self.manager.update_question(local, "正文内容")

        self.assertFalse(ok)

    async def test_update_without_note_id_falls_back_to_local(self):
        """
        历史错题可能没有云端笔记 ID（例如当初 IMA 写入失败），
        这时退回只写本地缓存，并在日志里说明，而不是让用户的操作失败。
        """
        file_ops.save_question("q1", "acc_1", "child_1", "数学", base_frontmatter(), "正文内容")
        local = self.read_local()
        local.pop("ima_note_id", None)
        local["mastery_score"] = 68

        ok = await self.manager.update_question(local, "正文内容")

        self.assertTrue(ok, "退回本地写入仍应成功")
        self.assertEqual(self.fake_ima.appended, [], "没有笔记 ID 时不该尝试追加")
        self.assertEqual(self.read_local()["mastery_score"], 68)


class FakeClient:
    """模拟 IMA 客户端：每篇笔记由基础块 + 若干事件块组成。"""

    def __init__(self, notes: dict[str, dict], events=None, modified_at: dict | None = None):
        events = events or {}
        self.payloads = {}
        self.modified_at = dict(modified_at or {})
        self.get_note_calls = []          # 记录读过哪些笔记，用来验证跳过是否生效
        for note_id, frontmatter in notes.items():
            parts = [f"```json\n{json.dumps(frontmatter, ensure_ascii=False)}\n```\n正文"]
            for event in events.get(note_id, []):
                parts.append(f"```json\n{json.dumps(event, ensure_ascii=False)}\n```")
            self.payloads[note_id] = "\n".join(parts)
            self.modified_at.setdefault(note_id, "1000")

    async def list_notes(self):
        # 真实的 list_note 会带 summary（笔记开头约 200 字）与 modify_time
        return [
            {
                "id": note_id,
                "modified_at": self.modified_at.get(note_id),
                "content": self.payloads[note_id][:200],
            }
            for note_id in self.payloads
        ]

    async def get_note(self, note_id):
        self.get_note_calls.append(note_id)
        return {"content": self.payloads[note_id]}

    async def append_to_note(self, note_id, content):
        self.payloads[note_id] += "\n" + content
        return True


class SyncConflictTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.vault = Path(self._temp.name) / "vault"
        self.vault.mkdir()
        self._vault_patch = patch.object(settings, "vault_path", str(self.vault))
        self._vault_patch.start()
        # 跳过缓存会写到 config 目录，测试里指到临时位置
        self._config_patch = patch.object(settings, "config_path", str(self._temp.name))
        self._config_patch.start()
        self.file_storage = FileStorageBackend()
        self.scopes = {("acc_1", "child_1")}

    def tearDown(self):
        self._config_patch.stop()
        self._vault_patch.stop()
        self._temp.cleanup()

    def build_storage(self, ima_frontmatter: dict) -> IMAStorageBackend:
        storage = IMAStorageBackend()
        storage.client = FakeClient({"n1": ima_frontmatter})
        return storage

    def write_local(self, **overrides):
        frontmatter = base_frontmatter(**overrides)
        file_ops.save_question("q1", "acc_1", "child_1", "数学", frontmatter, "本地正文")

    def read_local(self) -> dict:
        path = file_ops.find_question_file("acc_1", "child_1", "数学", "q1")
        return file_ops.read_question(str(path))

    async def test_new_local_file_is_created_and_tagged_with_note_id(self):
        storage = self.build_storage(base_frontmatter(updated_at=NEW, mastery_score=60))

        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes)

        self.assertEqual(stats["created"], 1)
        local = self.read_local()
        self.assertEqual(local["mastery_score"], 60)
        self.assertEqual(local["ima_note_id"], "n1", "同步应把云端笔记 ID 写回本地")

    async def test_sync_overwrites_when_ima_is_newer(self):
        self.write_local(updated_at=OLD, mastery_score=0)
        storage = self.build_storage(base_frontmatter(updated_at=NEW, mastery_score=84))

        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes)

        self.assertEqual(stats["updated"], 1)
        self.assertEqual(stats["conflicts"], 0)
        self.assertEqual(self.read_local()["mastery_score"], 84, "IMA 更新时应当覆盖本地")

    async def test_sync_skips_when_local_is_newer(self):
        """
        核心回归：本地做过重做（分数 84）而 IMA 还是旧快照（分数 0）时，
        同步不得把本地的重做记录抹掉。
        """
        self.write_local(updated_at=NEW, mastery_score=84, consecutive_correct=3)
        storage = self.build_storage(base_frontmatter(updated_at=OLD, mastery_score=0))

        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes)

        self.assertEqual(stats["conflicts"], 1, "应当识别为冲突并跳过")
        self.assertEqual(stats["updated"], 0)
        local = self.read_local()
        self.assertEqual(local["mastery_score"], 84, "本地的重做结果必须保留")
        self.assertEqual(local["consecutive_correct"], 3)

    async def test_sync_does_not_clobber_local_when_ima_has_no_version(self):
        """IMA 侧没有版本标记时保守处理，不用它覆盖有版本的本地文件。"""
        self.write_local(updated_at=NEW, mastery_score=84)
        storage = self.build_storage(base_frontmatter(mastery_score=0))

        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes)

        self.assertEqual(stats["conflicts"], 1)
        self.assertEqual(self.read_local()["mastery_score"], 84)

    async def test_sync_still_creates_when_local_missing(self):
        """本地文件丢失时，IMA 依然是可靠的恢复来源。"""
        storage = self.build_storage(base_frontmatter(updated_at=NEW, mastery_score=45))

        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes)

        self.assertEqual(stats["created"], 1)
        self.assertEqual(self.read_local()["mastery_score"], 45)


def build_note(base: dict, events=(), body: str = "正文内容") -> str:
    """拼出一篇 IMA 笔记：H1 标题 + 基础块 + 正文 + 若干事件块。"""
    parts = [
        "# 【女儿·数学】一元二次方程 2026-09-20\n",
        f"```json\n{json.dumps(base, ensure_ascii=False)}\n```\n",
        body,
    ]
    for event in events:
        parts.append(f"\n```json\n{json.dumps(event, ensure_ascii=False)}\n```\n")
    return "\n".join(parts)


class EventFoldingTest(unittest.TestCase):
    """基础块 + 追加事件的折叠（IMA 没有修改接口，状态只能这样累积）。"""

    def setUp(self):
        self.storage = IMAStorageBackend()

    def parse(self, base, events=(), body="正文内容"):
        return self.storage._parse_note_content(build_note(base, events, body))

    def test_base_only_note_is_returned_unchanged(self):
        """兼容历史数据：只有基础块、没有任何事件的笔记。"""
        state, body = self.parse(base_frontmatter(mastery_score=0))

        self.assertEqual(state["mastery_score"], 0)
        self.assertEqual(body, "正文内容")
        self.assertNotIn("redo_history", state)

    def test_events_override_base_fields(self):
        state, _ = self.parse(
            base_frontmatter(mastery_score=0, redo_count=0),
            [
                {"type": "redo", "rev": 2, "at": "2026-09-25", "result": "correct",
                 "mastery_score": 68, "redo_count": 1},
                {"type": "redo", "rev": 3, "at": "2026-09-27", "result": "correct",
                 "mastery_score": 76, "redo_count": 2},
            ],
        )

        self.assertEqual(state["mastery_score"], 76, "后者应当覆盖前者")
        self.assertEqual(state["redo_count"], 2)
        self.assertEqual(state["rev"], 3)

    def test_redo_history_accumulates_in_order(self):
        state, _ = self.parse(
            base_frontmatter(),
            [
                {"type": "redo", "rev": 2, "at": "2026-09-25T10:00:00+00:00",
                 "result": "correct", "note": "第一步对了"},
                {"type": "redo", "rev": 3, "at": "2026-09-27T10:00:00+00:00",
                 "result": "wrong", "note": "符号又错了"},
            ],
        )

        self.assertEqual(
            state["redo_history"],
            [
                {"date": "2026-09-25", "result": "correct", "note": "第一步对了"},
                {"date": "2026-09-27", "result": "wrong", "note": "符号又错了"},
            ],
        )

    def test_event_meta_keys_do_not_leak_into_state(self):
        state, _ = self.parse(
            base_frontmatter(),
            [{"type": "redo", "rev": 2, "at": "2026-09-27", "result": "correct",
              "note": "备注", "mastery_score": 68}],
        )

        self.assertNotIn("result", state, "result 只用于折叠，不是笔记字段")
        self.assertNotIn("note", state)
        self.assertEqual(state["mastery_score"], 68)

    def test_delete_event_marks_tombstone(self):
        state, _ = self.parse(
            base_frontmatter(),
            [{"type": "delete", "rev": 2, "at": "2026-09-27", "reason": "重复录入"}],
        )

        self.assertTrue(state["deleted"], "删除是逻辑删除，靠墓碑标记")

    def test_body_excludes_event_blocks(self):
        _, body = self.parse(
            base_frontmatter(),
            [{"type": "redo", "rev": 2, "at": "2026-09-27", "result": "correct"}],
            body="## 正确答案\n\nx = 2",
        )

        self.assertEqual(body, "## 正确答案\n\nx = 2", "正文里不该混入事件块")

    def test_malformed_event_block_is_skipped(self):
        content = build_note(
            base_frontmatter(mastery_score=0),
            [{"type": "redo", "rev": 2, "at": "2026-09-27", "mastery_score": 68}],
        )
        content += '\n```json\n{ 这不是合法 JSON }\n```\n'

        state, _ = self.storage._parse_note_content(content)

        self.assertEqual(state["mastery_score"], 68, "坏事件应被跳过，不影响其余折叠")


class SyncMaterializeTest(unittest.IsolatedAsyncioTestCase):
    """同步要把 IMA 里折叠后的状态物化到本地缓存。"""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.vault = Path(self._temp.name) / "vault"
        self.vault.mkdir()
        self._vault_patch = patch.object(settings, "vault_path", str(self.vault))
        self._vault_patch.start()
        # 跳过缓存会写到 config 目录，测试里指到临时位置
        self._config_patch = patch.object(settings, "config_path", str(self._temp.name))
        self._config_patch.start()
        self.file_storage = FileStorageBackend()
        self.scopes = {("acc_1", "child_1")}

    def tearDown(self):
        self._config_patch.stop()
        self._vault_patch.stop()
        self._temp.cleanup()

    def read_local(self, question_id="q1") -> dict:
        path = file_ops.find_question_file("acc_1", "child_1", "数学", question_id)
        self.assertIsNotNone(path)
        return file_ops.read_question(str(path))

    async def test_sync_writes_folded_state_not_raw_events(self):
        base = base_frontmatter(mastery_score=0, redo_count=0)
        events = [
            {"type": "redo", "rev": 2, "at": "2026-09-25T10:00:00+00:00",
             "result": "correct", "mastery_score": 68, "redo_count": 1},
            {"type": "redo", "rev": 3, "at": "2026-09-27T10:00:00+00:00",
             "result": "correct", "mastery_score": 76, "redo_count": 2},
        ]
        storage = IMAStorageBackend()
        storage.client = FakeClient({"n1": base}, {"n1": events})

        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes)

        self.assertEqual(stats["created"], 1)
        local = self.read_local()
        self.assertEqual(local["mastery_score"], 76, "本地应拿到折叠后的当前状态")
        self.assertEqual(local["redo_count"], 2)

        raw = Path(local["_file"]).read_text(encoding="utf-8")
        self.assertNotIn('"type": "redo"', raw, "本地缓存是物化视图，不该带事件块")
        self.assertEqual(local["ima_note_id"], "n1", "同步应把笔记 ID 写回本地")


class CacheRebuildTest(unittest.IsolatedAsyncioTestCase):
    """缓存重建：以 IMA 为准强制覆盖，并暴露「只在本地」的错题。"""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.vault = Path(self._temp.name) / "vault"
        self.vault.mkdir()
        self._vault_patch = patch.object(settings, "vault_path", str(self.vault))
        self._vault_patch.start()
        # 跳过缓存会写到 config 目录，测试里指到临时位置
        self._config_patch = patch.object(settings, "config_path", str(self._temp.name))
        self._config_patch.start()
        self.file_storage = FileStorageBackend()
        self.scopes = {("acc_1", "child_1")}

    def tearDown(self):
        self._config_patch.stop()
        self._vault_patch.stop()
        self._temp.cleanup()

    def build_storage(self, notes: dict, events=None) -> IMAStorageBackend:
        storage = IMAStorageBackend()
        storage.client = FakeClient(notes, events)
        return storage

    def write_local(self, question_id="q1", **overrides):
        frontmatter = base_frontmatter(id=question_id, **overrides)
        file_ops.save_question(question_id, "acc_1", "child_1", "数学", frontmatter, "本地正文")

    def local_file(self, question_id="q1") -> Path:
        path = file_ops.find_question_file("acc_1", "child_1", "数学", question_id)
        self.assertIsNotNone(path, f"{question_id} 的本地文件应当存在")
        return path

    async def test_rebuild_into_empty_cache(self):
        """缓存丢了：应该把 IMA 里的内容全量拉回来。"""
        storage = self.build_storage({"n1": base_frontmatter(updated_at=NEW, mastery_score=84)})

        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes, force=True)

        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["errors"], 0)
        local = file_ops.read_question(str(self.local_file()))
        self.assertEqual(local["mastery_score"], 84)
        self.assertEqual(local["ima_note_id"], "n1")
        self.assertEqual(local["_body"].strip(), "正文")

    async def test_force_overwrites_even_when_local_is_newer(self):
        """重建以 IMA 为准——本地的版本号此时不可信，照样覆盖。"""
        self.write_local(updated_at=NEW, mastery_score=99)
        storage = self.build_storage({"n1": base_frontmatter(updated_at=OLD, mastery_score=45)})

        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes, force=True)

        self.assertEqual(stats["forced"], 1)
        self.assertEqual(stats["conflicts"], 0, "重建模式不应产生冲突跳过")
        self.assertEqual(file_ops.read_question(str(self.local_file()))["mastery_score"], 45)

    async def test_regular_sync_still_protects_newer_local(self):
        """常规同步保持保守语义：不用旧快照覆盖本地更新的记录。"""
        self.write_local(updated_at=NEW, mastery_score=99)
        storage = self.build_storage({"n1": base_frontmatter(updated_at=OLD, mastery_score=45)})

        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes)

        self.assertEqual(stats["conflicts"], 1)
        self.assertEqual(stats["forced"], 0)
        self.assertEqual(file_ops.read_question(str(self.local_file()))["mastery_score"], 99)

    async def test_rebuild_folds_events_when_pulling(self):
        """重建拉回来的应当是折叠后的当前状态，而不是原始事件块。"""
        events = [
            {"type": "redo", "rev": 2, "at": "2026-09-25", "result": "correct",
             "mastery_score": 68},
            {"type": "redo", "rev": 3, "at": "2026-09-27", "result": "correct",
             "mastery_score": 76},
        ]
        storage = self.build_storage(
            {"n1": base_frontmatter(updated_at=NEW, mastery_score=0)}, {"n1": events}
        )

        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes, force=True)

        self.assertEqual(stats["created"], 1)
        local = file_ops.read_question(str(self.local_file()))
        self.assertEqual(local["mastery_score"], 76)
        self.assertEqual(len(local["redo_history"]), 2)

    async def test_local_only_items_are_reported_but_kept(self):
        """
        IMA 是记录来源，所以「只在本地」的错题意味着某次写入没落到云端。
        默认应当报告出来、但不删除。
        """
        self.write_local("q_orphan", updated_at=NEW)
        storage = self.build_storage({"n1": base_frontmatter(updated_at=NEW)})

        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes, force=True)

        self.assertEqual(stats["local_only"], 1)
        self.assertEqual(stats["local_only_ids"], ["q_orphan"])
        self.assertEqual(stats["pruned"], 0)
        self.assertTrue(self.local_file("q_orphan").exists(), "默认不该删掉它")

    async def test_prune_removes_local_only_items(self):
        self.write_local("q_orphan", updated_at=NEW)
        storage = self.build_storage({"n1": base_frontmatter(updated_at=NEW)})

        stats = await storage.sync_to_obsidian(
            self.file_storage, self.scopes, force=True, prune=True
        )

        self.assertEqual(stats["pruned"], 1)
        self.assertIsNone(
            file_ops.find_question_file("acc_1", "child_1", "数学", "q_orphan"),
            "prune 之后文件应当消失",
        )

    async def test_dry_run_counts_without_writing(self):
        storage = self.build_storage({"n1": base_frontmatter(updated_at=NEW, mastery_score=84)})

        stats = await storage.sync_to_obsidian(
            self.file_storage, self.scopes, force=True, dry_run=True
        )

        self.assertEqual(stats["created"], 1, "预演应当给出将要发生的计数")
        self.assertIsNone(
            file_ops.find_question_file("acc_1", "child_1", "数学", "q1"),
            "预演不该写任何文件",
        )

    async def test_dry_run_does_not_prune(self):
        self.write_local("q_orphan", updated_at=NEW)
        storage = self.build_storage({"n1": base_frontmatter(updated_at=NEW)})

        stats = await storage.sync_to_obsidian(
            self.file_storage, self.scopes, force=True, prune=True, dry_run=True
        )

        self.assertEqual(stats["local_only"], 1)
        self.assertEqual(stats["pruned"], 0, "预演模式下 prune 不生效")
        self.assertTrue(self.local_file("q_orphan").exists())


class SkipUnchangedTest(unittest.IsolatedAsyncioTestCase):
    """按 modify_time 跳过未变更的笔记——把批量操作从分钟级压到秒级的关键。"""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.vault = Path(self._temp.name) / "vault"
        self.vault.mkdir()
        self._vault_patch = patch.object(settings, "vault_path", str(self.vault))
        self._vault_patch.start()
        # 跳过缓存会写到 config 目录，测试里指到临时位置
        self._config_patch = patch.object(settings, "config_path", str(self._temp.name))
        self._config_patch.start()
        self.file_storage = FileStorageBackend()
        self.scopes = {("acc_1", "child_1")}

    def tearDown(self):
        self._config_patch.stop()
        self._vault_patch.stop()
        self._temp.cleanup()

    def build_storage(self, notes, events=None, modified_at=None) -> IMAStorageBackend:
        storage = IMAStorageBackend()
        storage.client = FakeClient(notes, events, modified_at)
        return storage

    def local_file(self, question_id="q1") -> Path:
        path = file_ops.find_question_file("acc_1", "child_1", "数学", question_id)
        self.assertIsNotNone(path)
        return path

    async def test_write_records_cloud_modify_time(self):
        storage = self.build_storage({"n1": base_frontmatter(updated_at=NEW)})

        await storage.sync_to_obsidian(self.file_storage, self.scopes, force=True)

        local = file_ops.read_question(str(self.local_file()))
        self.assertEqual(local["ima_modified_at"], "1000", "落盘时要记下云端版本戳")

    async def test_unchanged_note_is_not_fetched_again(self):
        storage = self.build_storage({"n1": base_frontmatter(updated_at=NEW)})
        await storage.sync_to_obsidian(self.file_storage, self.scopes, force=True)
        self.assertEqual(len(storage.client.get_note_calls), 1)

        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes)

        self.assertEqual(stats["unchanged"], 1)
        self.assertEqual(stats["created"], 0)
        self.assertEqual(stats["updated"], 0)
        self.assertEqual(len(storage.client.get_note_calls), 1, "未变更时不应再读正文")

    async def test_changed_note_is_refetched(self):
        storage = self.build_storage({"n1": base_frontmatter(updated_at=NEW)})
        await storage.sync_to_obsidian(self.file_storage, self.scopes, force=True)

        storage.client.modified_at["n1"] = "2000"   # 云端改过了
        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes)

        self.assertEqual(len(storage.client.get_note_calls), 2, "变更后必须重读")
        self.assertEqual(stats["unchanged"], 0)
        self.assertEqual(stats["updated"], 1)

    async def test_missing_stamp_is_refetched(self):
        """旧缓存没有版本戳：必须读一次，读完后补上。"""
        file_ops.save_question(
            "q1", "acc_1", "child_1", "数学", base_frontmatter(updated_at=NEW), "正文"
        )
        storage = self.build_storage({"n1": base_frontmatter(updated_at=NEW)})

        await storage.sync_to_obsidian(self.file_storage, self.scopes)

        self.assertEqual(len(storage.client.get_note_calls), 1)
        self.assertEqual(
            file_ops.read_question(str(self.local_file()))["ima_modified_at"], "1000"
        )

    async def test_skip_unchanged_false_always_reads(self):
        """重建默认逐条重读：本地可能整个不可信，不能靠版本戳蒙混。"""
        storage = self.build_storage({"n1": base_frontmatter(updated_at=NEW)})
        await storage.sync_to_obsidian(self.file_storage, self.scopes, force=True)

        stats = await storage.sync_to_obsidian(
            self.file_storage, self.scopes, force=True, skip_unchanged=False
        )

        self.assertEqual(len(storage.client.get_note_calls), 2)
        self.assertEqual(stats["unchanged"], 0)
        self.assertEqual(stats["forced"], 1)

    async def test_summary_prefilter_avoids_reading_foreign_notes(self):
        """归属明显属于别的账号：连正文都不用读。"""
        foreign = base_frontmatter(id="q_other", account_id="acc_999", child_id="child_999")
        storage = self.build_storage({"n1": foreign})

        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes)

        self.assertEqual(stats["errors"], 1)
        self.assertEqual(len(storage.client.get_note_calls), 0, "预筛命中就不该读正文")

    async def test_skipped_note_is_still_counted_as_seen(self):
        """
        跳过的笔记必须仍记为「IMA 侧见过」。否则 local_only 检测会把它
        误报成「只在本地、没进云端」——一个纯粹的假警报。
        """
        storage = self.build_storage({"n1": base_frontmatter(updated_at=NEW)})
        await storage.sync_to_obsidian(self.file_storage, self.scopes, force=True)

        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes)

        self.assertEqual(stats["unchanged"], 1)
        self.assertEqual(stats["local_only"], 0, "跳过读取不该被当成本地独有")




class SkipCacheTest(unittest.TestCase):
    """跳过缓存本身的行为。"""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.path = Path(self._temp.name) / "ima_skip_cache.json"

    def tearDown(self):
        self._temp.cleanup()

    def test_mark_and_skip_roundtrip_via_disk(self):
        cache = ImaSkipCache(self.path)
        cache.mark("n1", "1000", "not_a_question")
        cache.save()

        reloaded = ImaSkipCache(self.path)
        self.assertTrue(reloaded.should_skip("n1", "1000"))
        self.assertFalse(reloaded.should_skip("n1", "2000"), "版本变了就不该跳过")
        self.assertFalse(reloaded.should_skip("n_unknown", "1000"))

    def test_missing_modified_at_never_skips(self):
        cache = ImaSkipCache(self.path)
        cache.mark("n1", None, "not_a_question")
        self.assertFalse(cache.should_skip("n1", "1000"))
        self.assertFalse(cache.should_skip("n1", None))

    def test_corrupt_file_is_treated_as_empty(self):
        self.path.write_text("这不是 JSON", encoding="utf-8")

        cache = ImaSkipCache(self.path)

        self.assertEqual(cache.entries, {})
        cache.mark("n1", "1000", "not_a_question")
        self.assertTrue(cache.should_skip("n1", "1000"))

    def test_prune_absent_removes_stale_entries(self):
        cache = ImaSkipCache(self.path)
        cache.mark("n1", "1000", "not_a_question")
        cache.mark("n2", "1000", "not_a_question")

        removed = cache.prune_absent({"n1"})

        self.assertEqual(removed, 1)
        self.assertFalse(cache.should_skip("n2", "1000"))

    def test_save_skips_write_when_clean(self):
        cache = ImaSkipCache(self.path)
        cache.save()
        self.assertFalse(self.path.exists(), "没有变更时不该写文件")


class PreskipIntegrationTest(unittest.IsolatedAsyncioTestCase):
    """非错题笔记在第二轮同步里应当被跳过，不再重复读取。"""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.vault = Path(self._temp.name) / "vault"
        self.vault.mkdir()
        self._vault_patch = patch.object(settings, "vault_path", str(self.vault))
        self._config_patch = patch.object(settings, "config_path", str(self._temp.name))
        self._vault_patch.start()
        self._config_patch.start()
        self.file_storage = FileStorageBackend()
        self.scopes = {("acc_1", "child_1")}

    def tearDown(self):
        self._config_patch.stop()
        self._vault_patch.stop()
        self._temp.cleanup()

    def build_storage(self, notes) -> IMAStorageBackend:
        storage = IMAStorageBackend()
        storage.client = FakeClient(notes)
        return storage

    async def test_non_question_note_is_read_once_then_skipped(self):
        notes = {
            # 历史格式：没有 account_id，会被判为「非错题笔记」
            "n_legacy": {"id": "q1", "child": "daughter", "subject": "数学"},
            "n_ok": base_frontmatter(updated_at=NEW),
        }
        storage = self.build_storage(notes)

        first = await storage.sync_to_obsidian(self.file_storage, self.scopes)
        self.assertEqual(first["skipped"], 1)
        self.assertEqual(first["preskipped"], 0)
        self.assertEqual(len(storage.client.get_note_calls), 2)

        second = await storage.sync_to_obsidian(self.file_storage, self.scopes)

        self.assertEqual(second["preskipped"], 1, "非错题笔记第二轮应被跳过")
        self.assertEqual(second["unchanged"], 1, "错题本身没变，也应当跳过")
        self.assertEqual(second["skipped"], 0)
        self.assertEqual(
            len(storage.client.get_note_calls), 2,
            "第二轮一条都不该再读：两类笔记各有各的跳过依据",
        )

    async def test_changed_note_leaves_the_skip_cache(self):
        notes = {"n_legacy": {"id": "q1", "child": "daughter", "subject": "数学"}}
        storage = self.build_storage(notes)
        await storage.sync_to_obsidian(self.file_storage, self.scopes)

        storage.client.modified_at["n_legacy"] = "9999"
        stats = await storage.sync_to_obsidian(self.file_storage, self.scopes)

        self.assertEqual(stats["preskipped"], 0, "变过的笔记必须重新检查")
        self.assertEqual(len(storage.client.get_note_calls), 2)

    async def test_dry_run_does_not_persist_skip_cache(self):
        notes = {"n_legacy": {"id": "q1", "child": "daughter", "subject": "数学"}}
        storage = self.build_storage(notes)

        await storage.sync_to_obsidian(self.file_storage, self.scopes, dry_run=True)

        self.assertFalse(
            (Path(self._temp.name) / "ima_skip_cache.json").exists(),
            "预演不该留下任何持久化状态",
        )


if __name__ == "__main__":
    unittest.main()
