"""文件存储后端 - 基于本地文件系统"""

import logging
from pathlib import Path
from typing import Optional
from datetime import date

from app.services.storage_backend import StorageBackend
from app.services import file_ops
from app.core.config import settings

logger = logging.getLogger(__name__)


class FileStorageBackend:
    """基于本地文件系统的存储后端"""

    async def save_question(
        self,
        question_id: str,
        child: str,
        subject: str,
        frontmatter: dict,
        body: str,
        images: list[tuple[bytes, str]] = None,
    ) -> str:
        """保存错题到本地文件"""
        try:
            # 保存图片
            if images:
                for image_data, filename in images:
                    file_ops.save_image(image_data, child, subject, question_id, filename)

            # 保存 Markdown 文件
            file_path = file_ops.save_question(question_id, child, subject, frontmatter, body)
            logger.info(f"错题已保存到文件: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"保存错题失败: {e}")
            raise

    async def list_questions(
        self,
        child: str,
        subject: Optional[str] = None,
    ) -> list[dict]:
        """列出本地文件中的错题"""
        try:
            return file_ops.list_questions(child, subject)
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
            # 从 storage_id 解析出 child, subject, question_id
            path = Path(storage_id)
            # 路径格式: /vault/child/subject/date-question_id.md
            subject = path.parent.name
            child = path.parent.parent.name
            filename = path.stem  # date-question_id
            question_id = filename.split("-", 1)[1] if "-" in filename else filename

            file_ops.delete_question(storage_id, child, subject, question_id)
            logger.info(f"错题已删除: {storage_id}")
            return True
        except Exception as e:
            logger.error(f"删除错题失败: {e}")
            return False

    async def get_image_url(self, storage_id: str, filename: str) -> Optional[str]:
        """获取本地图片的访问路径（返回相对路径）"""
        try:
            # 从 storage_id 解析出 child, subject, question_id
            path = Path(storage_id)
            subject = path.parent.name
            child = path.parent.parent.name
            filename_base = path.stem
            question_id = filename_base.split("-", 1)[1] if "-" in filename_base else filename_base

            # 返回 API 访问路径
            return f"/api/questions/{question_id}/images/{filename}?child={child}&subject={subject}"
        except Exception as e:
            logger.error(f"获取图片 URL 失败: {e}")
            return None

    async def sync_from(self, source: StorageBackend) -> dict:
        """从另一个存储后端同步数据到本地"""
        stats = {"created": 0, "updated": 0, "deleted": 0, "errors": 0}

        try:
            # 获取源存储中的所有孩子
            # 这里假设源存储实现了 list_children 方法
            # 如果没有，需要从现有数据中推断

            # 简化实现：遍历常见结构
            for child in ["daughter", "son"]:
                for subject in ["数学", "语文", "英语", "物理", "化学", "生物", "历史", "地理", "政治"]:
                    try:
                        source_questions = await source.list_questions(child, subject)
                        local_questions = await self.list_questions(child, subject)

                        local_ids = {q.get("id") for q in local_questions}

                        for q in source_questions:
                            q_id = q.get("id")
                            if q_id and q_id not in local_ids:
                                # 创建新错题
                                storage_id = q.get("_file") or q.get("storage_id")
                                if storage_id:
                                    full_data = await source.read_question(storage_id)
                                    body = full_data.pop("_body", "")
                                    full_data.pop("_file", None)

                                    await self.save_question(
                                        question_id=q_id,
                                        child=child,
                                        subject=subject,
                                        frontmatter=full_data,
                                        body=body,
                                    )
                                    stats["created"] += 1

                    except Exception as e:
                        logger.error(f"同步 {child}/{subject} 失败: {e}")
                        stats["errors"] += 1

        except Exception as e:
            logger.error(f"同步过程出错: {e}")

        logger.info(f"同步完成: {stats}")
        return stats
