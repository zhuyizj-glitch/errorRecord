"""旧版 daughter/son vault 的账号目录迁移测试。"""

import tempfile
import unittest
from pathlib import Path

import yaml
import json

from app.db import Database
from app.services.auth_service import AuthService
from app.services.ima_storage import IMAStorageBackend
from scripts.migrate_to_accounts import migrate_ima_notes, migrate_local_vault


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
    async def test_legacy_ima_note_receives_account_metadata(self):
        class Client:
            def __init__(self):
                self.updated = []

            async def list_notes(self):
                return [{"id": "n1"}]

            async def get_note(self, note_id):
                metadata = {"id": "q1", "child": "daughter", "subject": "数学"}
                return {"content": f"```json\n{json.dumps(metadata)}\n```\n正文"}

            async def update_note(self, **kwargs):
                self.updated.append(kwargs)
                return True

        storage = IMAStorageBackend()
        storage.client = Client()

        result = await migrate_ima_notes(
            storage, "acc_1", {"daughter": "child_1", "son": "child_2"}, dry_run=False
        )

        self.assertEqual(result, {"matched": 1, "updated": 1, "errors": []})
        content = storage.client.updated[0]["content"]
        self.assertIn('"account_id": "acc_1"', content)
        self.assertIn('"child_id": "child_1"', content)
        self.assertIn('"child_name": "女儿"', content)


if __name__ == "__main__":
    unittest.main()
