"""图片上传校验与临时文件回收测试（对应 discuss.md 6.2）。"""

import io
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from app.api.routes import upload as upload_module
from app.api.deps import get_auth_service
from app.db import Database
from app.services.auth_service import AuthService
from main import app


def png_bytes(width: int = 300, height: int = 300) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def heic_like_bytes() -> bytes:
    """构造带 HEIF brand 的文件头，用于验证嗅探逻辑（Pillow 无法真正解码）。"""
    return b"\x00\x00\x00\x18ftypheic" + b"\x00" * 32


class UploadValidationTest(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        vault = Path(self._temp.name) / "vault"
        vault.mkdir()
        # 隔离临时目录，避免碰到真实的 /tmp/mistakes_uploads
        self.upload_root = Path(self._temp.name) / "uploads"
        self.upload_root.mkdir()
        self._upload_dir_patch = patch.object(upload_module, "TEMP_DIR", self.upload_root)
        self._upload_dir_patch.start()
        database = Database(f"sqlite:///{Path(self._temp.name) / 'app.db'}")
        database.initialize()
        auth = AuthService(database)
        app.dependency_overrides[get_auth_service] = lambda: auth
        self.client = TestClient(app)
        self.client.post("/api/auth/initialize", json={
            "username": "owner", "display_name": "管理员",
            "password": "correct horse battery",
        })

    def tearDown(self):
        app.dependency_overrides.clear()
        self._upload_dir_patch.stop()
        self._temp.cleanup()

    def upload(self, *files):
        return self.client.post(
            "/api/upload/images",
            files=[("files", (name, data, "application/octet-stream")) for name, data in files],
        )

    def test_valid_png_is_accepted(self):
        response = self.upload(("q.png", png_bytes()))
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(len(payload["image_ids"]), 1)
        self.assertEqual(payload["image_ids"][0]["filename"], "q.png")
        self.assertEqual(payload["warnings"], [])

    def test_unsupported_extension_is_rejected(self):
        response = self.upload(("note.pdf", png_bytes()))
        self.assertEqual(response.status_code, 400)
        self.assertIn("格式不受支持", response.json()["detail"])

    def test_non_image_content_disguised_as_png_is_rejected(self):
        response = self.upload(("fake.png", b"this is definitely not an image"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("不是有效的图片文件", response.json()["detail"])

    def test_oversized_file_is_rejected(self):
        oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * (upload_module.MAX_FILE_BYTES + 1)
        response = self.upload(("big.png", oversized))
        self.assertEqual(response.status_code, 400)
        self.assertIn("超过 20MB", response.json()["detail"])

    def test_too_many_files_are_rejected(self):
        files = [(f"q{i}.png", png_bytes()) for i in range(upload_module.MAX_FILES_PER_UPLOAD + 1)]
        response = self.upload(*files)
        self.assertEqual(response.status_code, 400)
        self.assertIn("最多上传", response.json()["detail"])

    def test_empty_file_is_rejected(self):
        response = self.upload(("empty.png", b""))
        self.assertEqual(response.status_code, 400)
        self.assertIn("空文件", response.json()["detail"])

    def test_low_resolution_warns_but_does_not_block(self):
        response = self.upload(("small.png", png_bytes(50, 50)))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["image_ids"]), 1)
        self.assertEqual(len(response.json()["warnings"]), 1)
        self.assertIn("分辨率偏低", response.json()["warnings"][0])

    def test_high_resolution_has_no_warning(self):
        response = self.upload(("big.png", png_bytes(800, 600)))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["warnings"], [])

    def test_heic_header_is_recognised(self):
        response = self.upload(("photo.heic", heic_like_bytes()))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["image_ids"]), 1)

    def test_jpeg_is_accepted(self):
        buffer = io.BytesIO()
        Image.new("RGB", (300, 300), "white").save(buffer, format="JPEG")
        response = self.upload(("photo.jpg", buffer.getvalue()))
        self.assertEqual(response.status_code, 200, response.text)

    def test_anonymous_upload_is_rejected(self):
        anonymous = TestClient(app)
        response = anonymous.post(
            "/api/upload/images",
            files={"files": ("q.png", png_bytes(), "image/png")},
        )
        self.assertEqual(response.status_code, 401)


    def test_upload_triggers_sweep_of_expired_files(self):
        """每次上传顺带回收过期文件（保存流程已不再负责清理）。"""
        expired = self.upload_root / "acc_old" / "stale.png"
        expired.parent.mkdir(parents=True, exist_ok=True)
        expired.write_bytes(b"x")
        stale = time.time() - upload_module.TEMP_TTL_SECONDS - 60
        os.utime(expired, (stale, stale))

        self.assertEqual(self.upload(("q.png", png_bytes())).status_code, 200)

        self.assertFalse(expired.exists(), "上传时应当回收过期文件")
        self.assertFalse(expired.parent.exists(), "空的账号目录也应清理")


class TempCleanupTest(unittest.TestCase):
    """临时图片的 TTL 回收逻辑。"""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.upload_root = Path(self._temp.name) / "uploads"
        self.upload_root.mkdir()
        self._patch = patch.object(upload_module, "TEMP_DIR", self.upload_root)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._temp.cleanup()

    def make_file(self, relative: str, age_seconds: float) -> Path:
        path = self.upload_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
        stamp = time.time() - age_seconds
        os.utime(path, (stamp, stamp))
        return path

    def test_expired_files_removed_and_fresh_files_kept(self):
        expired = self.make_file("acc_1/old.png", upload_module.TEMP_TTL_SECONDS + 60)
        fresh = self.make_file("acc_1/fresh.png", 60)

        removed = upload_module.sweep_expired_uploads()

        self.assertEqual(removed, 1)
        self.assertFalse(expired.exists())
        self.assertTrue(fresh.exists(), "未过期的文件必须保留")

    def test_empty_account_directory_is_removed(self):
        self.make_file("acc_1/old.png", upload_module.TEMP_TTL_SECONDS + 60)

        upload_module.sweep_expired_uploads()

        self.assertFalse((self.upload_root / "acc_1").exists())

    def test_directory_with_fresh_file_is_kept(self):
        self.make_file("acc_1/old.png", upload_module.TEMP_TTL_SECONDS + 60)
        self.make_file("acc_1/fresh.png", 60)

        upload_module.sweep_expired_uploads()

        self.assertTrue((self.upload_root / "acc_1").exists())

    def test_sweep_handles_missing_directory(self):
        missing = self.upload_root / "does-not-exist"
        with patch.object(upload_module, "TEMP_DIR", missing):
            self.assertEqual(upload_module.sweep_expired_uploads(), 0)

    def test_sweep_leaves_nothing_for_never_saved_tasks(self):
        """没保存的任务，临时文件到期后自动回收，不会永久堆积。"""
        for i in range(3):
            self.make_file(f"acc_{i}/q.png", upload_module.TEMP_TTL_SECONDS + 1)

        removed = upload_module.sweep_expired_uploads()

        self.assertEqual(removed, 3)
        self.assertEqual(list(self.upload_root.rglob("*")), [])


if __name__ == "__main__":
    unittest.main()
