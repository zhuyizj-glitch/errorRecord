"""错题文件名格式、安全化与改名同步测试。

文件名采用「人名·学科·日期-id.md」：
- 人名与学科是用户可控的，必须清洗后才能拼进文件名
- id 留在末尾，既保证唯一（同日同主题可能有两道题），也是 find_question_file 的锚点
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.api.deps import get_auth_service
from app.db import Database
from app.services import file_ops
from app.services.auth_service import AuthService
from main import app


class QuestionFilenameTest(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.vault = Path(self._temp.name) / "vault"
        self.vault.mkdir()
        database = Database(f"sqlite:///{Path(self._temp.name) / 'app.db'}")
        database.initialize()
        auth = AuthService(database)
        app.dependency_overrides[get_auth_service] = lambda: auth
        self._vault_patch = patch.object(settings, "vault_path", str(self.vault))
        self._vault_patch.start()
        self.client = TestClient(app)
        self.account = self.client.post("/api/auth/initialize", json={
            "username": "owner", "display_name": "管理员",
            "password": "correct horse battery",
        }).json()["account"]

    def tearDown(self):
        app.dependency_overrides.clear()
        self._vault_patch.stop()
        self._temp.cleanup()

    def make_child(self, name: str, subjects: list[str]) -> dict:
        response = self.client.post("/api/children", json={
            "name": name, "emoji": "🧒", "subjects": subjects,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def add_question(self, child: dict, subject: str = "数学", topic: str = "一元二次方程") -> str:
        response = self.client.post("/api/questions", json={
            "child_id": child["id"], "subject": subject, "topic": topic,
            "error_date": "2026-09-20", "source_type": "手写题", "difficulty": "中等",
            "question_text": "解方程", "correct_answer": "x=2",
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    def files_of(self, child: dict, subject: str = "数学") -> list[str]:
        directory = self.vault / "accounts" / self.account["id"] / child["id"] / subject
        return sorted(p.name for p in directory.glob("*.md"))

    # ── 命名格式 ──

    def test_filename_is_readable_and_ends_with_id(self):
        child = self.make_child("女儿", ["数学"])
        question_id = self.add_question(child)

        names = self.files_of(child)
        self.assertEqual(len(names), 1)
        self.assertEqual(names[0], f"女儿·数学·2026-09-20-{question_id}.md")

    def test_find_question_file_locates_by_id(self):
        child = self.make_child("女儿", ["数学"])
        question_id = self.add_question(child)

        found = file_ops.find_question_file(
            self.account["id"], child["id"], "数学", question_id
        )

        self.assertIsNotNone(found, "后缀匹配应当仍能定位文件")
        self.assertTrue(found.name.endswith(f"-{question_id}.md"))

    def test_two_questions_same_day_and_topic_do_not_collide(self):
        child = self.make_child("女儿", ["数学"])
        first = self.add_question(child)
        second = self.add_question(child)

        names = self.files_of(child)
        self.assertEqual(len(names), 2, "同一天同一主题的两道题不能撞名")
        self.assertTrue(any(n.endswith(f"-{first}.md") for n in names))
        self.assertTrue(any(n.endswith(f"-{second}.md") for n in names))

    # ── 安全化 ──

    def test_path_separator_in_child_name_is_sanitized(self):
        """人名里的 "/" 若不处理，会把文件写到意料之外的目录。"""
        child = self.make_child("女儿/数学", ["数学"])
        self.add_question(child)

        names = self.files_of(child)
        self.assertEqual(len(names), 1)
        self.assertNotIn("/", names[0])
        self.assertTrue(names[0].startswith("女儿_数学·"), names[0])

        # 文件确实落在该孩子的学科目录下，没有多出一层
        directory = self.vault / "accounts" / self.account["id"] / child["id"] / "数学"
        self.assertEqual(len(list(directory.iterdir())), 1)

    def test_windows_reserved_characters_are_sanitized(self):
        child = self.make_child('女:儿*?<>|"', ["数学"])
        self.add_question(child)

        name = self.files_of(child)[0]
        for char in ': * ? < > | "':
            if char != " ":
                self.assertNotIn(char, name, f"文件名不该含 {char!r}：{name}")

    def test_overlong_child_name_is_truncated(self):
        """API 允许最长 40 字的人名（约 120 字节），超过文件名预算时必须截断。"""
        child = self.make_child("超长名字" * 10, ["数学"])  # 40 个汉字
        self.add_question(child)

        name = self.files_of(child)[0]
        self.assertLessEqual(len(name.encode("utf-8")), 255, "不得超过文件系统的名字上限")
        self.assertNotIn("�", name, "按字节截断不能切出半个汉字")
        self.assertIn("·数学·2026-09-20-", name, "学科与日期部分必须完整保留")
        self.assertLess(name.count("超"), 40, "人名部分应当被截短")

    def test_empty_after_sanitizing_falls_back_to_placeholder(self):
        # 名字全是非法字符，清洗后为空，应当回落到占位符而不是崩溃
        child = self.make_child("/", ["数学"])
        self.add_question(child)

        name = self.files_of(child)[0]
        self.assertTrue(name.startswith("_·"), name)

    # ── 改名同步 ──

    def test_renaming_child_renames_files_and_updates_frontmatter(self):
        child = self.make_child("女儿", ["数学"])
        question_id = self.add_question(child)
        self.assertEqual(self.files_of(child)[0], f"女儿·数学·2026-09-20-{question_id}.md")

        response = self.client.patch(f"/api/children/{child['id']}", json={
            "name": "大女儿", "emoji": "👩", "subjects": ["数学"],
        })

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["renamed_files"], 1, "应当同步重命名 1 个文件")
        self.assertEqual(self.files_of(child)[0], f"大女儿·数学·2026-09-20-{question_id}.md")

        found = file_ops.find_question_file(
            self.account["id"], child["id"], "数学", question_id
        )
        self.assertIn("child_name: 大女儿", found.read_text(),
                      "frontmatter 里的人名也要一起刷新")

    def test_rename_without_name_change_does_not_touch_files(self):
        child = self.make_child("女儿", ["数学"])
        question_id = self.add_question(child)

        response = self.client.patch(f"/api/children/{child['id']}", json={
            "name": "女儿", "emoji": "👧", "subjects": ["数学"],
        })

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("renamed_files", response.json(), "名字没变就不该有重命名动作")
        self.assertEqual(self.files_of(child)[0], f"女儿·数学·2026-09-20-{question_id}.md")

    def test_renaming_child_handles_multiple_subjects(self):
        child = self.make_child("女儿", ["数学", "语文"])
        self.add_question(child, subject="数学")
        self.add_question(child, subject="语文", topic="阅读理解")

        self.client.patch(f"/api/children/{child['id']}", json={
            "name": "大女儿", "emoji": "👩", "subjects": ["数学", "语文"],
        })

        self.assertTrue(self.files_of(child, "数学")[0].startswith("大女儿·数学·"))
        self.assertTrue(self.files_of(child, "语文")[0].startswith("大女儿·语文·"))

    def test_rename_skips_unparseable_files_without_failing(self):
        """历史遗留的坏文件不该让改名失败。"""
        child = self.make_child("女儿", ["数学"])
        question_id = self.add_question(child)
        broken = self.vault / "accounts" / self.account["id"] / child["id"] / "数学" / "坏文件.md"
        broken.write_text("没有 frontmatter 的内容", encoding="utf-8")

        response = self.client.patch(f"/api/children/{child['id']}", json={
            "name": "大女儿", "emoji": "👩", "subjects": ["数学"],
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["renamed_files"], 1)
        self.assertTrue(broken.exists(), "无法解析的文件保持原样")
        found = file_ops.find_question_file(
            self.account["id"], child["id"], "数学", question_id
        )
        self.assertTrue(found.name.startswith("大女儿·数学·"))

    # ── 移动错题 ──

    def test_moving_question_updates_filename(self):
        first = self.make_child("女儿", ["数学"])
        second = self.make_child("儿子", ["语文"])
        question_id = self.add_question(first)

        response = self.client.patch(f"/api/questions/{question_id}", params={
            "child_id": first["id"], "subject": "数学",
            "new_child_id": second["id"], "new_subject": "语文",
        })

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.files_of(first), [], "原位置不应留下文件")
        self.assertEqual(self.files_of(second, "语文"), [f"儿子·语文·2026-09-20-{question_id}.md"])

    def test_moving_question_within_same_child_updates_filename(self):
        child = self.make_child("女儿", ["数学", "语文"])
        question_id = self.add_question(child, subject="数学")

        self.client.patch(f"/api/questions/{question_id}", params={
            "child_id": child["id"], "subject": "数学", "new_subject": "语文",
        })

        self.assertEqual(self.files_of(child, "数学"), [])
        self.assertEqual(self.files_of(child, "语文"), [f"女儿·语文·2026-09-20-{question_id}.md"])


if __name__ == "__main__":
    unittest.main()
