"""存储后端抽象接口

注意：接口中不包含图片相关的操作。原始图片只是 LLM 分析的输入，
不落盘、不进 markdown，因此存储层只需处理纯文字内容。
"""

from typing import Protocol, Optional


class StorageBackend(Protocol):
    """存储后端接口定义"""

    async def save_question(
        self,
        question_id: str,
        account_id: str,
        child_id: str,
        subject: str,
        frontmatter: dict,
        body: str,
    ) -> str:
        """
        保存错题

        Args:
            question_id: 错题 ID
            account_id: 账号 ID
            child_id: 孩子 ID
            subject: 学科
            frontmatter: 元数据
            body: Markdown 正文（纯文字）

        Returns:
            存储 ID（文件路径或云端笔记 ID）
        """
        ...

    async def list_questions(
        self,
        account_id: str,
        child_id: str,
        subject: Optional[str] = None,
    ) -> list[dict]:
        """
        列出错题

        Args:
            account_id: 账号 ID
            child_id: 孩子 ID
            subject: 学科（可选）

        Returns:
            错题列表，每项包含元数据
        """
        ...

    async def read_question(self, storage_id: str) -> dict:
        """
        读取错题详情

        Args:
            storage_id: 存储 ID

        Returns:
            错题数据（元数据 + 正文）
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
            frontmatter: 更新后的元数据
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
