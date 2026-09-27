"""账号数据库结构测试。"""

import tempfile
import unittest
from pathlib import Path

from app.db import Database
from app.core.config import Settings


class DatabaseTest(unittest.TestCase):
    def test_database_url_uses_standard_environment_name(self):
        settings = Settings(_env_file=None, DATABASE_URL="sqlite:////tmp/custom.db")
        self.assertEqual(settings.database_url, "sqlite:////tmp/custom.db")

    def test_initialize_is_idempotent_and_creates_required_tables(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Database(f"sqlite:///{Path(temp_dir) / 'app.db'}")

            database.initialize()
            database.initialize()

            self.assertEqual(
                database.table_names(),
                {"accounts", "sessions", "invites", "children", "child_subjects"},
            )

    def test_username_and_child_subject_are_unique(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Database(f"sqlite:///{Path(temp_dir) / 'app.db'}")
            database.initialize()

            with database.transaction() as connection:
                connection.execute(
                    "INSERT INTO accounts (id, username, display_name, password_hash, password_salt, role) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    ("acc_1", "owner", "Owner", "hash", "salt", "admin"),
                )
                connection.execute(
                    "INSERT INTO children (id, account_id, name, emoji) VALUES (?, ?, ?, ?)",
                    ("child_1", "acc_1", "孩子", "🧒"),
                )
                connection.execute(
                    "INSERT INTO child_subjects (child_id, subject, enabled) VALUES (?, ?, 1)",
                    ("child_1", "数学"),
                )

            with self.assertRaises(Exception):
                with database.transaction() as connection:
                    connection.execute(
                        "INSERT INTO accounts (id, username, display_name, password_hash, password_salt, role) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        ("acc_2", "owner", "Other", "hash", "salt", "user"),
                    )

            with self.assertRaises(Exception):
                with database.transaction() as connection:
                    connection.execute(
                        "INSERT INTO child_subjects (child_id, subject, enabled) VALUES (?, ?, 1)",
                        ("child_1", "数学"),
                    )


if __name__ == "__main__":
    unittest.main()
