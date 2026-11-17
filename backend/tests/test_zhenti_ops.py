"""真题库文件操作测试（v2.0）"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.services import zhenti_ops


def make_item(**overrides) -> dict:
    item = {
        "number": "12",
        "question_text": "解方程 $x^2 - 5x + 6 = 0$",
        "correct_answer": "$x = 2$ 或 $x = 3$",
        "solution_steps": "因式分解 $(x-2)(x-3)=0$",
        "topic": "一元二次方程",
        "knowledge_points": ["一元二次方程", "因式分解"],
        "difficulty": "中等",
    }
    item.update(overrides)
    return item


class ZhentiOpsTest(unittest.TestCase):
    def test_save_read_list_find_update_delete(self):
        with tempfile.TemporaryDirectory() as vault:
            with patch.object(settings, "vault_path", vault):
                item = make_item()
                fm = zhenti_ops.new_frontmatter("abcd1234", "acc_1", "数学", "2024", "2024中考卷", item)
                path = zhenti_ops.save_zhenti("abcd1234", "acc_1", "数学", fm, zhenti_ops.build_body(item))

                # 文件名约定：来源·学科·年份-id.md，id 结尾
                self.assertEqual(path.name, "2024中考卷·数学·2024-abcd1234.md")
                self.assertTrue(path.exists())

                # LaTeX 原样保存
                text = path.read_text(encoding="utf-8")
                self.assertIn("$x^2 - 5x + 6 = 0$", text)

                data = zhenti_ops.read_zhenti(str(path))
                self.assertEqual(data["id"], "abcd1234")
                self.assertEqual(data["knowledge_points"], ["一元二次方程", "因式分解"])
                self.assertIn("## 原题", data["_body"])
                self.assertIn("## 参考答案", data["_body"])
                # 派生字段不落盘
                self.assertNotIn("_body", text)
                self.assertNotIn("_file", text)

                items = zhenti_ops.list_zhenti("acc_1")
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["year"], "2024")

                found = zhenti_ops.find_zhenti_file("acc_1", "abcd1234")
                self.assertEqual(found, path)
                # 跨学科查找也能命中
                self.assertEqual(zhenti_ops.find_zhenti_file("acc_1", "abcd1234", "数学"), path)
                self.assertIsNone(zhenti_ops.find_zhenti_file("acc_1", "不存在"))

                data["practice_count"] = 3
                zhenti_ops.update_zhenti(str(path), data)
                self.assertEqual(zhenti_ops.read_zhenti(str(path))["practice_count"], 3)

                zhenti_ops.delete_zhenti(str(path))
                self.assertFalse(path.exists())
                self.assertEqual(zhenti_ops.list_zhenti("acc_1"), [])

    def test_account_isolation(self):
        with tempfile.TemporaryDirectory() as vault:
            with patch.object(settings, "vault_path", vault):
                item = make_item()
                fm = zhenti_ops.new_frontmatter("aaaa1111", "acc_1", "数学", "2024", "卷A", item)
                zhenti_ops.save_zhenti("aaaa1111", "acc_1", "数学", fm, zhenti_ops.build_body(item))

                self.assertEqual(len(zhenti_ops.list_zhenti("acc_1")), 1)
                self.assertEqual(zhenti_ops.list_zhenti("acc_2"), [])
                self.assertIsNone(zhenti_ops.find_zhenti_file("acc_2", "aaaa1111"))

    def test_unsafe_source_filename(self):
        with tempfile.TemporaryDirectory() as vault:
            with patch.object(settings, "vault_path", vault):
                item = make_item()
                fm = zhenti_ops.new_frontmatter("bbbb2222", "acc_1", "数学", "2024", "来源/含\\非法:字符", item)
                path = zhenti_ops.save_zhenti("bbbb2222", "acc_1", "数学", fm, zhenti_ops.build_body(item))
                self.assertTrue(path.exists())
                self.assertNotIn("/", path.name)
