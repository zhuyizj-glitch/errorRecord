"""存储后端抽象接口"""

from typing import Protocol, Optional
from datetime import date


class StorageBackend(Protocol):
    """存储后端接口定义"""

    async def save_question(
        self,
        question_id: str,
        child: str,
        subject: str,
        frontmatter: dict,
        body: str,
        images: list[tuple[bytes, str]] = None,
    ) -> str:
        """
        保存错题

        Args:
            question_id: 错题 ID
            child: 孩子标识
            subject: 学科
            frontmatter: YAML frontmatter 数据
            body: Markdown 正文
            images: 图片列表 [(图片数据, 文件名)]

        Returns:
            存储 ID（可能是文件路径、数据库 ID 等）
        """
        ...

    async def list_questions(
        self,
        child: str,
        subject: Optional[str] = None,
    ) -> list[dict]:
        """
        列出错题

        Args:
            child: 孩子标识
            subject: 学科（可选）

        Returns:
            错题列表，每项包含 frontmatter 数据
        """
        ...

    async def read_question(self, storage_id: str) -> dict:
        """
        读取错题详情

        Args:
            storage_id: 存储 ID

        Returns:
            错题数据（frontmatter + body）
        """
        ...

    async def update_question(
        self,
        storage_id: str,
        frontmatter: dict,
        body: Optional[str] = None,
    ) -> bool:
        """
        更新错题

        Args:
            storage_id: 存储 ID
            frontmatter: 更新后的 frontmatter
            body: 更新后的正文（可选）

        Returns:
            是否更新成功
        """
        ...

    async def delete_question(self, storage_id: str) -> bool:
        """
        删除错题

        Args:
            storage_id: 存储 ID

        Returns:
            是否删除成功
        """
        ...

    async def get_image_url(self, storage_id: str, filename: str) -> Optional[str]:
        """
        获取图片访问 URL

        Args:
            storage_id: 存储 ID
            filename: 文件名

        Returns:
            图片 URL，如果存储不支持则返回 None
        """
        ...

    async def sync_from(self, source: "StorageBackend") -> dict:
        """
        从另一个存储后端同步数据

        Args:
            source: 源存储后端

        Returns:
            同步统计 {created: int, updated: int, deleted: int}
        """
        ...
