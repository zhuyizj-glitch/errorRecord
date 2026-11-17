"""IMA 客户端的限频重试行为测试。

批量读取（列表、同步、重建）必然撞上 IMA 的限频，这是实测确认的常态
而不是异常（见 8.39）。直接失败会让同步中途断掉，而且看不出原因。
"""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from app.services.ima_client import IMAClient


class FakeProc:
    """替身子进程：返回预设的 returncode 与输出。"""

    def __init__(self, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


def response(code: int, msg: str = "ok", data: dict | None = None) -> bytes:
    return json.dumps({"code": code, "msg": msg, "data": data or {}}).encode("utf-8")


class RateLimitRetryTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = IMAClient()
        # 绕开真实凭证文件
        self.client._get_credentials = lambda: ("cid", "key")

    def test_rate_limit_detection(self):
        self.assertTrue(IMAClient._is_rate_limited("IMA 业务错误: 请求频率超限，请稍后重试"))
        self.assertTrue(IMAClient._is_rate_limited("Too Many Requests"))
        self.assertTrue(IMAClient._is_rate_limited("rate limit exceeded"))
        self.assertFalse(IMAClient._is_rate_limited("IMA 业务错误: apikey鉴权失败"))
        self.assertFalse(IMAClient._is_rate_limited("IMA 业务错误: 携带无效的 ID"))

    async def test_rate_limit_is_retried_then_succeeds(self):
        calls = []
        sleeps = []

        async def fake_exec(*args, **kwargs):
            calls.append(args)
            if len(calls) < 3:
                return FakeProc(stdout=response(20002, "请求频率超限，请稍后重试"))
            return FakeProc(stdout=response(0, "ok", {"content": "hello"}))

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        with patch("asyncio.create_subprocess_exec", fake_exec), \
             patch("asyncio.sleep", fake_sleep):
            data = await self.client._call_api("openapi/note/v1/get_doc_content", {})

        self.assertEqual(data, {"content": "hello"})
        self.assertEqual(len(calls), 3, "两次限频后第三次应当成功")
        self.assertEqual(len(sleeps), 2, "每次限频退避一次")
        self.assertEqual(sleeps, [2.0, 4.0], "退避应当是指数增长")

    async def test_retry_gives_up_after_max_attempts(self):
        calls = []

        async def fake_exec(*args, **kwargs):
            calls.append(args)
            return FakeProc(stdout=response(20002, "请求频率超限，请稍后重试"))

        async def fake_sleep(_seconds):
            return None

        with patch("asyncio.create_subprocess_exec", fake_exec), \
             patch("asyncio.sleep", fake_sleep):
            with self.assertRaises(Exception) as ctx:
                await self.client._call_api("x", {})

        self.assertIn("频率超限", str(ctx.exception))
        self.assertEqual(len(calls), 5, "初次 + 4 次重试后放弃")

    async def test_other_errors_are_not_retried(self):
        calls = []

        async def fake_exec(*args, **kwargs):
            calls.append(args)
            return FakeProc(stdout=response(20004, "apikey鉴权失败"))

        async def fake_sleep(_seconds):
            return None

        with patch("asyncio.create_subprocess_exec", fake_exec), \
             patch("asyncio.sleep", fake_sleep):
            with self.assertRaises(Exception):
                await self.client._call_api("x", {})

        self.assertEqual(len(calls), 1, "鉴权失败重试没有意义，应当立刻失败")

    async def test_nonzero_exit_is_raised(self):
        async def fake_exec(*args, **kwargs):
            return FakeProc(returncode=1, stderr="节点脚本崩了".encode("utf-8"))

        async def fake_sleep(_seconds):
            return None

        with patch("asyncio.create_subprocess_exec", fake_exec), \
             patch("asyncio.sleep", fake_sleep):
            with self.assertRaises(Exception) as ctx:
                await self.client._call_api("x", {})

        self.assertIn("节点脚本崩了", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
