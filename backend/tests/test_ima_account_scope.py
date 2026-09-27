"""IMA 共享知识库的账号范围测试。"""

import json
import unittest

from app.services.ima_storage import IMAStorageBackend


def note_content(metadata: dict) -> str:
    return f"```json\n{json.dumps(metadata, ensure_ascii=False)}\n```\n正文"


class FakeImaClient:
    def __init__(self):
        self.notes = {
            "n1": note_content({
                "id": "q1", "account_id": "acc_1", "child_id": "child_1",
                "child_name": "孩子一", "subject": "数学", "error_date": "2026-09-27",
            }),
            "n2": note_content({
                "id": "q2", "account_id": "acc_2", "child_id": "child_2",
                "child_name": "孩子二", "subject": "数学", "error_date": "2026-09-27",
            }),
            "legacy": note_content({"id": "old", "child": "daughter", "subject": "数学"}),
        }

    async def list_notes(self):
        return [{"id": note_id} for note_id in self.notes]

    async def get_note(self, note_id):
        return {"content": self.notes[note_id]}


class FakeFileStorage:
    def __init__(self):
        self.saved = []

    async def list_questions(self, account_id, child_id, subject=None):
        return []

    async def save_question(self, **kwargs):
        self.saved.append(kwargs)
        return f"/{kwargs['question_id']}.md"

    async def update_question(self, **kwargs):
        return True


class ImaAccountScopeTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.storage = IMAStorageBackend()
        self.storage.client = FakeImaClient()

    async def test_list_only_returns_requested_account_and_child(self):
        questions = await self.storage.list_questions("acc_1", "child_1", "数学")
        self.assertEqual([question["id"] for question in questions], ["q1"])

    async def test_sync_only_writes_known_account_child_pairs(self):
        files = FakeFileStorage()

        stats = await self.storage.sync_to_obsidian(files, {("acc_1", "child_1")})

        self.assertEqual([item["question_id"] for item in files.saved], ["q1"])
        self.assertEqual(stats, {"created": 1, "updated": 0, "skipped": 1, "errors": 1})


if __name__ == "__main__":
    unittest.main()
