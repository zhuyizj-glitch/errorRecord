"""复习页与统计的第一阶段改动验证

覆盖三件事（都是这次改动新修/新增的）：

  1. `/review/plan` 必须返回题干与答案
     —— 此前只返回 frontmatter，复习页拿不到任何可显示的内容，
        只显示「知识点：xxx」，点开答案是「请回到错题列表查看」

  2. redo 能把「做错原因」存进 redo_history
     —— 后端 RedoRequest.note 早已支持，但前端一直没有输入控件

  3. 薄弱知识点把「未摸底」与「薄弱」分开
     —— 两者的 mastery_score 都是 0，混在一起会让"刚录入的新题"
        以 0 分霸占最薄弱榜首
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.deps import get_auth_service
from app.core.config import settings
from app.db import Database
from app.services.auth_service import AuthService
from app.services.body_parser import parse_question_body
from app.services.storage_manager import StorageManager
from main import app

QUESTION_BODY_PARTS = {
    "question_text": "3 ÷ 1/4 = ?",
    "correct_answer": "12",
    "solution_steps": "1. 除以一个分数等于乘它的倒数\n2. 3 × 4 = 12",
    "error_type": "计算错误",
    "error_suggestion": "复习分数除法法则",
    "error_analysis": {
        "error_point": "把除号看成乘号",
        "error_type": "计算错误",
        "root_cause": "概念不清：没有理解除以分数等于乘它的倒数",
        "suggestion": "复习分数除法法则",
    },
    "parent_note": "注意符号",
}


class ReviewAndStatsTest(unittest.TestCase):
    def _client_with_data(self, vault: str) -> tuple[TestClient, str, str]:
        """建好账号与孩子，返回 (client, child_id, subject)"""
        database = Database(f"sqlite:///{Path(vault) / 'app.db'}")
        database.initialize()
        auth = AuthService(database)
        app.dependency_overrides[get_auth_service] = lambda: auth

        client = TestClient(app)
        client.post("/api/auth/initialize", json={
            "username": "owner", "display_name": "管理员",
            "password": "correct horse battery",
        })
        child = client.post("/api/children", json={
            "name": "女儿", "emoji": "👧", "subjects": ["数学"],
        }).json()
        return client, child["id"], "数学"

    def _create_question(self, client: TestClient, child_id: str, subject: str, **overrides) -> dict:
        payload = {
            "child_id": child_id,
            "subject": subject,
            "topic": "分数除法",
            "error_date": "2026-01-01",
            "source_type": "印刷题",
            "difficulty": "中等",
            "knowledge_points": ["分数除法法则"],
            "tags": ["错题"],
            **QUESTION_BODY_PARTS,
            **overrides,
        }
        res = client.post("/api/questions", json=payload)
        self.assertIn(res.status_code, (200, 201), res.text)
        return res.json()

    def test_review_plan_returns_question_and_answer(self):
        """复习计划必须带题干与答案，否则复习页没法用"""
        with tempfile.TemporaryDirectory() as vault:
            with patch.object(settings, "vault_path", vault), patch.object(
                settings, "ima_enabled", False
            ), patch(
                "app.services.storage_manager.get_storage_manager",
                return_value=StorageManager(),
            ):
                client, child_id, subject = self._client_with_data(vault)
                self._create_question(client, child_id, subject)

                res = client.get("/api/review/plan", params={"child_id": child_id})
                self.assertEqual(res.status_code, 200, res.text)
                data = res.json()
                self.assertEqual(data["total"], 1)

                q = data["plan"][0]
                # 契约保持不变
                self.assertIn("plan", data)
                self.assertIn("total", data)
                # 新增的派生字段
                self.assertTrue(q.get("_structured"), "正文应能被解析成段落")
                self.assertEqual(q.get("_question"), "3 ÷ 1/4 = ?")
                self.assertEqual(q.get("_answer"), "12")
                self.assertIn("倒数", q.get("_solution") or "")
                self.assertIn("把除号看成乘号", q.get("_error_analysis") or "")
                self.assertEqual(q.get("_parent_note"), "注意符号")

    def test_review_plan_falls_back_for_non_template_body(self):
        """正文格式不匹配时回落整段渲染，不能空白"""
        with tempfile.TemporaryDirectory() as vault:
            with patch.object(settings, "vault_path", vault), patch.object(
                settings, "ima_enabled", False
            ), patch(
                "app.services.storage_manager.get_storage_manager",
                return_value=StorageManager(),
            ):
                client, child_id, subject = self._client_with_data(vault)
                created = self._create_question(client, child_id, subject)

                # 直接把文件正文改成一个不符合模板的形状
                from app.services import file_ops
                qs = file_ops.list_questions(
                    client.get("/api/auth/me").json()["id"], child_id
                )
                path = Path(qs[0]["_file"])
                text = path.read_text(encoding="utf-8")
                _, body = text.split("---\n\n", 1)
                path.write_text(
                    text.replace(body, "随便一段没有段标题的正文，历史文件可能长这样。"),
                    encoding="utf-8",
                )

                res = client.get("/api/review/plan", params={"child_id": child_id})
                q = res.json()["plan"][0]
                self.assertFalse(q.get("_structured"))
                # _question 回落到 plain，仍然有内容可显示
                self.assertIn("没有段标题", q.get("_question") or "")
                self.assertIn("没有段标题", q.get("_body") or "")

    def test_redo_saves_note(self):
        """做错原因必须能存下来"""
        with tempfile.TemporaryDirectory() as vault:
            with patch.object(settings, "vault_path", vault), patch.object(
                settings, "ima_enabled", False
            ), patch(
                "app.services.storage_manager.get_storage_manager",
                return_value=StorageManager(),
            ):
                client, child_id, subject = self._client_with_data(vault)
                created = self._create_question(client, child_id, subject)
                qid = created["id"]

                res = client.post(
                    f"/api/questions/{qid}/redo",
                    params={"child_id": child_id, "subject": subject},
                    json={"result": "wrong", "note": "把 ÷ 看成了 ×"},
                )
                self.assertEqual(res.status_code, 200, res.text)

                detail = client.get(
                    f"/api/questions/{qid}",
                    params={"child_id": child_id, "subject": subject},
                ).json()
                history = detail.get("redo_history") or []
                self.assertEqual(len(history), 1)
                self.assertEqual(history[0]["result"], "wrong")
                self.assertEqual(history[0]["note"], "把 ÷ 看成了 ×")
                self.assertEqual(detail.get("consecutive_correct"), 0)

    def test_weak_points_separates_untested_from_weak(self):
        """未摸底的知识点不能以 0 分霸占「最薄弱」"""
        with tempfile.TemporaryDirectory() as vault:
            with patch.object(settings, "vault_path", vault), patch.object(
                settings, "ima_enabled", False
            ), patch(
                "app.services.storage_manager.get_storage_manager",
                return_value=StorageManager(),
            ):
                client, child_id, subject = self._client_with_data(vault)

                # 两道从没重做过的题，分属两个知识点
                self._create_question(
                    client, child_id, subject, knowledge_points=["分数除法法则"]
                )
                self._create_question(
                    client, child_id, subject,
                    knowledge_points=["通分与约分"], topic="通分",
                )

                # 重做其中一道（做对），它变成「已摸底」
                qs = client.get(
                    "/api/questions", params={"child_id": child_id}
                ).json()["questions"]
                target = next(q for q in qs if "通分与约分" in (q.get("knowledge_points") or []))
                client.post(
                    f"/api/questions/{target['id']}/redo",
                    params={"child_id": child_id, "subject": subject},
                    json={"result": "correct"},
                )

                res = client.get("/api/stats/weak-points", params={"child_id": child_id})
                self.assertEqual(res.status_code, 200, res.text)
                data = res.json()

                rated_names = [r["knowledge_point"] for r in data["weak_points"]]
                untested_names = [r["knowledge_point"] for r in data["untested_points"]]

                # 重做过的进「薄弱」候选，并有分数
                self.assertIn("通分与约分", rated_names)
                rated = next(r for r in data["weak_points"] if r["knowledge_point"] == "通分与约分")
                self.assertIsNotNone(rated["avg_score"])
                self.assertEqual(rated["rated_count"], 1)

                # 没重做过的进「待摸底」，且 avg_score 为 None（不是 0）
                self.assertIn("分数除法法则", untested_names)
                untested = next(
                    r for r in data["untested_points"] if r["knowledge_point"] == "分数除法法则"
                )
                self.assertIsNone(untested["avg_score"])
                self.assertEqual(untested["question_count"], 1)

                # 关键：未摸底的绝不能出现在「最薄弱」排名里
                self.assertNotIn("分数除法法则", rated_names)

    def test_overview_separates_attempted(self):
        """概览的平均掌握度只对已摸底的题求平均"""
        with tempfile.TemporaryDirectory() as vault:
            with patch.object(settings, "vault_path", vault), patch.object(
                settings, "ima_enabled", False
            ), patch(
                "app.services.storage_manager.get_storage_manager",
                return_value=StorageManager(),
            ):
                client, child_id, subject = self._client_with_data(vault)
                a = self._create_question(client, child_id, subject)
                self._create_question(client, child_id, subject, topic="第二题")

                client.post(
                    f"/api/questions/{a['id']}/redo",
                    params={"child_id": child_id, "subject": subject},
                    json={"result": "correct"},
                )

                o = client.get("/api/stats/overview", params={"child_id": child_id}).json()
                self.assertEqual(o["total"], 2)
                self.assertEqual(o["attempted_total"], 1)
                self.assertEqual(o["untested_total"], 1)
                # 只对那一题（做对一次 = 68 分）求平均，而不是 (68+0)/2 = 34
                self.assertEqual(o["avg_mastery_score"], 68.0)


class BodyParserTest(unittest.TestCase):
    """正文解析器本身的边界"""

    def test_standard_template(self):
        body = (
            "## 原题\n\n> **题目内容**：5 × 6 = ?\n\n"
            "## 正确答案\n\n30\n\n"
            "## 解题过程\n\n五六三十\n\n"
            "## 错误分析\n**错误点：** 算成 11\n\n"
            "## 家长备注\n\n无\n"
        )
        r = parse_question_body(body)
        self.assertTrue(r["structured"])
        self.assertEqual(r["question"], "5 × 6 = ?")
        self.assertEqual(r["answer"], "30")
        self.assertIn("五六三十", r["solution"])
        self.assertIn("算成 11", r["error_analysis"])

    def test_practice_alias(self):
        """练习题用 ## 易错点 落盘，同一套解析器要能认"""
        body = "## 原题\n\n> **题目内容**：12÷4=?\n\n## 易错点\n**易错点：** 算成减法\n"
        r = parse_question_body(body)
        self.assertTrue(r["structured"])
        self.assertIn("减法", r["error_analysis"])

    def test_unknown_format_falls_back(self):
        """完全不认识时不能空白"""
        body = "没有段标题的一段话。"
        r = parse_question_body(body)
        self.assertFalse(r["structured"])
        self.assertEqual(r["raw"], body)
        self.assertIn("没有段标题", r["plain"])

    def test_empty_and_none(self):
        self.assertFalse(parse_question_body("")["structured"])
        self.assertFalse(parse_question_body(None)["structured"])


if __name__ == "__main__":
    unittest.main()
