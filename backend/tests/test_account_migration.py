"""旧版 daughter/son vault 的账号目录迁移测试。"""

import tempfile
import unittest
from pathlib import Path

import yaml
import json

from app.db import Database
from app.services.auth_service import AuthService
from app.services.ima_storage import IMAStorageBackend
from scripts.migrate_to_accounts import audit_ima_notes, migrate_local_vault


class AccountMigrationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.vault = self.root / "vault"
        self.database = Database(f"sqlite:///{self.root / 'app.db'}")
        self.database.initialize()
        self.admin = AuthService(self.database).create_initial_admin(
            "owner", "管理员", "correct horse battery"
        )
        note_dir = self.vault / "daughter" / "数学"
        note_dir.mkdir(parents=True)
        (note_dir / "2026-01-01-q1.md").write_text(
            "---\n" + yaml.safe_dump({
                "id": "q1", "child": "daughter", "subject": "数学",
                "error_date": "2026-01-01",
            }, allow_unicode=True) + "---\n\n![原题](../../_assets/daughter/数学/q1/a.png)\n",
            encoding="utf-8",
        )
        asset = self.vault / "_assets" / "daughter" / "数学" / "q1"
        asset.mkdir(parents=True)
        (asset / "a.png").write_bytes(b"image")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dry_run_changes_nothing(self):
        result = migrate_local_vault(self.database, self.vault, self.admin.id, dry_run=True)
        self.assertEqual(result["questions"], 1)
        self.assertTrue((self.vault / "daughter/数学/2026-01-01-q1.md").exists())
        self.assertFalse((self.vault / "accounts").exists())

    def test_migration_backs_up_moves_and_is_idempotent(self):
        first = migrate_local_vault(self.database, self.vault, self.admin.id, dry_run=False)
        second = migrate_local_vault(self.database, self.vault, self.admin.id, dry_run=False)

        self.assertEqual(first["questions"], 1)
        self.assertEqual(second["questions"], 0)
        with self.database.connect() as connection:
            child = connection.execute(
                "SELECT id, name FROM children WHERE account_id = ? AND name = '女儿'",
                (self.admin.id,),
            ).fetchone()
            child_count = connection.execute(
                "SELECT COUNT(*) AS count FROM children WHERE account_id = ?",
                (self.admin.id,),
            ).fetchone()["count"]
        self.assertEqual(child_count, 2)
        note = self.vault / "accounts" / self.admin.id / child["id"] / "数学" / "2026-01-01-q1.md"
        image = self.vault / "_assets/accounts" / self.admin.id / child["id"] / "数学/q1/a.png"
        self.assertTrue(note.exists())
        self.assertEqual(image.read_bytes(), b"image")
        content = note.read_text()
        self.assertIn(f"account_id: {self.admin.id}", content)
        self.assertIn(f"child_id: {child['id']}", content)
        self.assertIn(f"_assets/accounts/{self.admin.id}/{child['id']}/数学/q1/a.png", content)
        self.assertTrue(any((self.vault / "_migration_backups").iterdir()))


class ImaMigrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_ima_notes_are_audited_without_writing(self):
        """
        IMA OpenAPI 没有修改笔记的接口，因此补齐账号元数据无法执行。
        审计只统计受影响的笔记，绝不写入——写入需要 update 接口，
        而替身客户端不该假装拥有真客户端没有的能力。
        """

        class Client:
            def __init__(self):
                self.calls = []

            async def list_notes(self):
                return [{"id": "n1"}, {"id": "n2"}]

            async def get_note(self, note_id):
                if note_id == "n1":
                    metadata = {"id": "q1", "child": "daughter", "subject": "数学"}
                else:
                    metadata = {"id": "q2", "account_id": "acc_1", "child_id": "child_1",
                                "subject": "数学"}
                return {"content": f"```json\n{json.dumps(metadata)}\n```\n正文"}

        storage = IMAStorageBackend()
        storage.client = Client()
        # 真客户端确实没有 update_note，这里如实反映
        self.assertFalse(hasattr(storage.client, "update_note"))

        result = await audit_ima_notes(storage, "acc_1", {"daughter": "child_1"})

        self.assertEqual(result["matched"], 1, "只应命中缺账号元数据的旧笔记")
        self.assertEqual(result["updated"], 0, "审计不应写入任何内容")
        self.assertIn("不支持修改笔记", result["unsupported_reason"])
        self.assertEqual(
            result["affected_notes"],
            [{"note_id": "n1", "question_id": "q1", "legacy_child": "daughter"}],
        )

    async def test_update_question_is_rejected_in_favour_of_append_event(self):
        """
        IMA 不支持修改笔记，update_question 必须显式失败而不是静默返回 False
        —— 后者曾让「同步到 IMA」长期无声失效（见 8.31）。
        状态变更的正路是 append_event。
        """

        class Client:
            pass

        storage = IMAStorageBackend()
        storage.client = Client()

        with self.assertRaises(NotImplementedError):
            await storage.update_question("n1", {"id": "q1"}, "正文")

        self.assertFalse(await storage.delete_question("n1"))


if __name__ == "__main__":
    unittest.main()
