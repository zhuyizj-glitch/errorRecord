"""文件存储后端 - 基于本地文件系统"""

import logging
from typing import Optional

from app.services import file_ops

logger = logging.getLogger(__name__)


class FileStorageBackend:
    """基于本地文件系统的存储后端"""

    async def save_question(
        self,
        question_id: str,
        account_id: str,
        child_id: str,
        subject: str,
        frontmatter: dict,
        body: str,
    ) -> str:
        """保存错题到本地文件（正文为纯文字，不含图片）"""
        try:
            file_path = file_ops.save_question(
                question_id, account_id, child_id, subject, frontmatter, body
            )
            logger.info(f"错题已保存到文件: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"保存错题失败: {e}")
            raise

    async def list_questions(
        self,
        account_id: str,
        child_id: str,
        subject: Optional[str] = None,
    ) -> list[dict]:
        """列出本地文件中的错题"""
        try:
            return file_ops.list_questions(account_id, child_id, subject)
        except Exception as e:
            logger.error(f"列出错题失败: {e}")
            return []

    async def read_question(self, storage_id: str) -> dict:
        """读取本地文件中的错题"""
        try:
            return file_ops.read_question(storage_id)
        except Exception as e:
            logger.error(f"读取错题失败: {e}")
            raise

    async def update_question(
        self,
        storage_id: str,
        frontmatter: dict,
        body: Optional[str] = None,
    ) -> bool:
        """更新本地文件中的错题"""
        try:
            file_ops.update_question(storage_id, frontmatter, body)
            logger.info(f"错题已更新: {storage_id}")
            return True
        except Exception as e:
            logger.error(f"更新错题失败: {e}")
            return False

    async def delete_question(self, storage_id: str) -> bool:
        """删除本地文件中的错题"""
        try:
            file_ops.delete_question(storage_id)
            logger.info(f"错题已删除: {storage_id}")
            return True
        except Exception as e:
            logger.error(f"删除错题失败: {e}")
            return False
