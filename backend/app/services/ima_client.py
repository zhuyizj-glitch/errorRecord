"""腾讯 IMA API 客户端 - 使用 ima-skills skill"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class IMAClient:
    """IMA API 客户端 - 通过 ima-skills skill 调用"""

    def __init__(self):
        self.skill_dir = Path.home() / ".claude/skills/@tencent-adm/ima-skills"
        self.ima_api_script = self.skill_dir / "ima_api.cjs"
        self.credentials_file_client_id = Path.home() / ".config/ima/client_id"
        self.credentials_file_api_key = Path.home() / ".config/ima/api_key"

    def _get_credentials(self) -> tuple[str, str]:
        """获取 IMA 凭证"""
        try:
            client_id = self.credentials_file_client_id.read_text().strip()
            api_key = self.credentials_file_api_key.read_text().strip()
            return client_id, api_key
        except Exception as e:
            logger.error(f"读取凭证失败: {e}")
            raise

    async def _call_api(self, endpoint: str, payload: dict) -> dict:
        """调用 IMA API"""
        try:
            client_id, api_key = self._get_credentials()
            # 凭证 + 更新检查时间戳位置（凭证目录只读，需重定向到可写路径）
            opts = json.dumps({
                "clientId": client_id,
                "apiKey": api_key,
                "lastCheckFile": "/tmp/ima_last_update_check",
            })

            # 调用 ima_api.cjs 脚本
            proc = await asyncio.create_subprocess_exec(
                "node", str(self.ima_api_script),
                endpoint, json.dumps(payload), opts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                error_msg = stderr.decode('utf-8')
                logger.error(f"API 调用失败: {error_msg}")
                raise Exception(f"API 调用失败: {error_msg}")

            response = json.loads(stdout.decode('utf-8'))

            # 检查业务错误
            if response.get("code") != 0:
                error_msg = response.get("msg", "未知错误")
                logger.error(f"IMA 业务错误: {error_msg}")
                raise Exception(f"IMA 业务错误: {error_msg}")

            return response.get("data", {})

        except Exception as e:
            logger.error(f"IMA API 调用异常: {e}")
            raise

    async def create_note(self, title: str, content: str, tags: list[str] = None) -> Optional[str]:
        """
        创建笔记

        Args:
            title: 笔记标题
            content: 笔记内容（Markdown 格式）
            tags: 标签列表

        Returns:
            note_id: 笔记 ID，失败返回 None
        """
        try:
            # 确保 UTF-8 编码
            title = self._ensure_utf8(title)
            content = self._ensure_utf8(content)

            payload = {
                "title": title,
                "content": content,
                "content_format": 1,  # 1 = markdown
            }

            # 使用 import_doc 端点创建笔记
            data = await self._call_api("openapi/note/v1/import_doc", payload)

            note_id = data.get("note_id") or data.get("docid")
            logger.info(f"IMA 笔记创建成功: {note_id}")
            return note_id

        except Exception as e:
            logger.error(f"IMA 笔记创建异常: {e}")
            return None

    async def list_knowledge_bases(self, query: str = "", limit: int = 20) -> Optional[list[dict]]:
        """
        列出知识库

        Args:
            query: 搜索关键词（空字符串表示列出所有）
            limit: 返回数量限制（最大 20）

        Returns:
            知识库列表，失败返回 None
        """
        try:
            payload = {
                "query": query,
                "cursor": "",
                "limit": min(limit, 20),
            }

            data = await self._call_api("openapi/wiki/v1/search_knowledge_base", payload)

            # API 返回的字段名是 info_list, kb_id, kb_name
            knowledge_bases = []
            info_list = data.get("info_list", [])
            for item in info_list:
                knowledge_bases.append({
                    "id": item.get("kb_id"),
                    "name": item.get("kb_name"),
                    "description": item.get("description", ""),
                    "content_count": int(item.get("content_count", 0)),
                    "member_count": int(item.get("member_count", 0)),
                    "creator": item.get("creator"),
                    "role_type": item.get("role_type"),
                    "base_type": item.get("base_type"),
                })

            logger.info(f"IMA 知识库列表获取成功: {len(knowledge_bases)} 个")
            return knowledge_bases

        except Exception as e:
            logger.error(f"IMA 知识库列表获取异常: {e}")
            return None

    async def add_note_to_knowledge_base(
        self,
        note_id: str,
        knowledge_base_id: str,
        title: str,
        folder_id: str = None,
    ) -> bool:
        """
        将笔记添加到知识库

        Args:
            note_id: 笔记 ID
            knowledge_base_id: 知识库 ID
            title: 标题（必填）
            folder_id: 文件夹 ID（可选，省略则添加到根目录）

        Returns:
            是否添加成功
        """
        try:
            payload = {
                "knowledge_base_id": knowledge_base_id,
                "media_type": 11,  # 11 = 笔记类型
                "title": title,
                "note_info": {
                    "content_id": note_id,
                },
            }

            if folder_id:
                payload["folder_id"] = folder_id

            data = await self._call_api("openapi/wiki/v1/add_knowledge", payload)
            media_id = data.get("media_id")
            logger.info(f"笔记 {note_id} 已添加到知识库 {knowledge_base_id}, media_id={media_id}")
            return True

        except Exception as e:
            logger.error(f"添加笔记到知识库失败: {e}")
            return False

    # IMA API 单页上限
    PAGE_SIZE = 20
    # 分页遍历的安全上限（防止 API 异常导致无限循环）
    MAX_PAGES = 100

    async def _paginate(
        self,
        endpoint: str,
        base_payload: dict,
        list_field: str,
        max_items: int = None,
    ) -> list[dict]:
        """
        分页遍历 IMA API，返回全部结果

        IMA 的分页机制（实测）：
        - cursor 传数字字符串表示偏移量（"0" / "20" / "40" ...）
        - 响应的 is_end 标记是否到底
        - 不返回 next_cursor 字段，需自己累加偏移

        Args:
            endpoint: API 端点
            base_payload: 基础请求参数（不含 cursor/limit）
            list_field: 响应中列表字段名，如 "note_book_list"
            max_items: 最多取多少条，None 表示全部

        Returns:
            合并后的完整列表
        """
        all_items = []
        offset = 0

        for page in range(self.MAX_PAGES):
            payload = {
                **base_payload,
                "cursor": "" if offset == 0 else str(offset),
                "limit": self.PAGE_SIZE,
            }

            data = await self._call_api(endpoint, payload)
            items = data.get(list_field, []) or []
            all_items.extend(items)

            # 到底了
            if data.get("is_end"):
                break

            # 本页没数据也停（防御 is_end 不可靠的情况）
            if not items:
                break

            # 够了
            if max_items and len(all_items) >= max_items:
                all_items = all_items[:max_items]
                break

            offset += len(items)
        else:
            logger.warning(
                f"{endpoint} 分页达到安全上限 {self.MAX_PAGES} 页"
                f"（{self.MAX_PAGES * self.PAGE_SIZE} 条），可能未取完"
            )

        return all_items

    async def find_folder_by_path(
        self,
        knowledge_base_id: str,
        path_parts: list[str],
    ) -> Optional[str]:
        """
        按路径查找文件夹 ID

        Args:
            knowledge_base_id: 知识库 ID
            path_parts: 路径片段，如 ["女儿", "数学"]

        Returns:
            文件夹 ID，未找到返回 None
        """
        try:
            current_folder_id = None

            for part in path_parts:
                base_payload = {"knowledge_base_id": knowledge_base_id}
                if current_folder_id:
                    base_payload["folder_id"] = current_folder_id

                # 分页遍历，避免文件夹多时漏掉
                items = await self._paginate(
                    endpoint="openapi/wiki/v1/get_knowledge_list",
                    base_payload=base_payload,
                    list_field="knowledge_list",
                )

                found = None
                for item in items:
                    # media_type 99 = 文件夹
                    if item.get("media_type") == 99 and item.get("title") == part:
                        found = item.get("media_id")
                        break

                if not found:
                    logger.warning(f"未找到文件夹: {'/'.join(path_parts)} (缺少 '{part}')")
                    return None

                current_folder_id = found

            return current_folder_id

        except Exception as e:
            logger.error(f"查找文件夹失败: {e}")
            return None

    async def list_knowledge_items(
        self,
        knowledge_base_id: str,
        folder_id: str = None,
    ) -> list[dict]:
        """
        列出知识库内容（自动分页，取全部）

        Args:
            knowledge_base_id: 知识库 ID
            folder_id: 文件夹 ID（可选，省略则列根目录）

        Returns:
            内容列表
        """
        try:
            base_payload = {"knowledge_base_id": knowledge_base_id}
            if folder_id:
                base_payload["folder_id"] = folder_id

            items = await self._paginate(
                endpoint="openapi/wiki/v1/get_knowledge_list",
                base_payload=base_payload,
                list_field="knowledge_list",
            )
            logger.info(f"知识库内容获取成功: {len(items)} 条")
            return items

        except Exception as e:
            logger.error(f"知识库内容获取失败: {e}")
            return []

    async def list_notes(
        self,
        limit: int = None,
        offset: int = 0,
        folder_id: str = None,
    ) -> Optional[list[dict]]:
        """
        列出笔记（自动分页，取全部）

        Args:
            limit: 最多返回多少条，None 表示取全部（自动翻页）
            offset: 起始偏移量（默认 0）
            folder_id: 文件夹 ID（可选）

        Returns:
            笔记列表，失败返回 None
        """
        try:
            base_payload = {}
            if folder_id:
                base_payload["folder_id"] = folder_id

            # 单页就够时走快路径，避免多余请求
            if limit and limit <= self.PAGE_SIZE and offset == 0:
                payload = {**base_payload, "cursor": "", "limit": limit}
                data = await self._call_api(
                    "openapi/note/v1/list_note_by_folder_id", payload
                )
                raw_items = data.get("note_book_list", []) or []
            else:
                raw_items = await self._paginate(
                    endpoint="openapi/note/v1/list_note_by_folder_id",
                    base_payload=base_payload,
                    list_field="note_book_list",
                    max_items=limit,
                )
                if offset:
                    raw_items = raw_items[offset:]

            notes = []
            for item in raw_items:
                basic_info = item.get("basic_info", {}).get("basic_info", {})
                notes.append({
                    "id": basic_info.get("docid"),
                    "title": basic_info.get("title"),
                    "content": basic_info.get("summary", ""),
                    "created_at": basic_info.get("create_time"),
                    "modified_at": basic_info.get("modify_time"),
                })

            logger.info(f"IMA 笔记列表获取成功: {len(notes)} 条")
            return notes

        except Exception as e:
            logger.error(f"IMA 笔记列表获取异常: {e}")
            return None

    async def search_notes(self, query: str, limit: int = 20) -> Optional[list[dict]]:
        """
        搜索笔记

        Args:
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            搜索结果列表，失败返回 None
        """
        try:
            # 确保 UTF-8 编码
            query = self._ensure_utf8(query)

            payload = {
                "search_type": 0,  # 0 = 按标题搜索
                "query_info": {
                    "title": query,
                },
                "start": 0,
                "end": limit,
            }

            data = await self._call_api("openapi/note/v1/search_note", payload)

            notes = []
            search_results = data.get("search_note_infos", [])
            for item in search_results:
                note_info = item.get("note_book_info", {})
                notes.append({
                    "id": note_info.get("note_id"),
                    "title": note_info.get("title"),
                    "content": note_info.get("summary", ""),
                })

            logger.info(f"IMA 笔记搜索成功: {len(notes)} 条结果")
            return notes

        except Exception as e:
            logger.error(f"IMA 笔记搜索异常: {e}")
            return None

    def _ensure_utf8(self, text: str) -> str:
        """确保字符串是 UTF-8 编码"""
        if text is None:
            return ""
        return text.encode("utf-8").decode("utf-8")

    async def test_connection(self) -> bool:
        """
        测试 IMA API 连接

        Returns:
            连接是否成功
        """
        try:
            # 尝试列出笔记来测试连接
            data = await self._call_api("openapi/note/v1/list_note_by_folder_id", {
                "cursor": "",
                "limit": 1,
            })
            logger.info("IMA API 连接测试成功")
            return True

        except Exception as e:
            logger.error(f"IMA API 连接测试失败: {e}")
            return False

    async def get_note(self, note_id: str) -> Optional[dict]:
        """
        获取笔记详情（包含完整内容）

        Args:
            note_id: 笔记 ID

        Returns:
            笔记详情，失败返回 None
        """
        try:
            # 使用 get_doc_content API 获取笔记内容
            payload = {
                "note_id": note_id,
                "target_content_format": 1,  # 1 = Markdown
            }

            data = await self._call_api("openapi/note/v1/get_doc_content", payload)

            if data:
                return {
                    "id": note_id,
                    "content": data.get("content", ""),
                }

            logger.warning(f"IMA 笔记内容为空: {note_id}")
            return None

        except Exception as e:
            logger.error(f"IMA 笔记获取异常: {e}")
            return None

    async def upload_image(self, image_data: bytes, filename: str) -> Optional[str]:
        """
        上传图片到 IMA

        注意: IMA API 可能不直接支持图片上传，
        这个方法暂时返回 None，实际使用时可能需要将图片
        转换为 base64 嵌入到笔记内容中。

        Args:
            image_data: 图片二进制数据
            filename: 文件名

        Returns:
            Optional[str]: 图片 URL 或 ID，失败返回 None
        """
        logger.warning("IMA API 图片上传功能暂未实现，建议使用 base64 嵌入")
        return None

    async def close(self):
        """关闭客户端（无需操作，因为使用 subprocess）"""
        pass


# 全局客户端实例（延迟初始化）
_ima_client: Optional[IMAClient] = None


def get_ima_client() -> IMAClient:
    """获取 IMA 客户端单例"""
    global _ima_client
    if _ima_client is None:
        _ima_client = IMAClient()
    return _ima_client
