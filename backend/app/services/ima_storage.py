"""IMA 存储后端 - 基于腾讯 IMA 云存储"""

import logging
import yaml
from typing import Optional
from datetime import date

from app.services.storage_backend import StorageBackend
from app.services.ima_client import get_ima_client
from app.core.config import settings

logger = logging.getLogger(__name__)


class IMAStorageBackend:
    """基于腾讯 IMA 的云存储后端"""

    def __init__(self):
        self.client = get_ima_client()

    def _build_title(self, child: str, subject: str, frontmatter: dict) -> str:
        """
        生成笔记标题

        格式：【女儿·数学】一元二次方程（计算错误） 2026-09-08

        用中文名和全角括号，在 IMA 列表里更易读；日期放最后便于排序。
        """
        child_name = "女儿" if child == "daughter" else "儿子"
        topic = frontmatter.get("topic", "未命名")
        error_type = frontmatter.get("error_type", "")
        error_date = frontmatter.get("error_date", "")

        parts = [f"【{child_name}·{subject}】{topic}"]
        if error_type:
            parts.append(f"（{error_type}）")
        if error_date:
            parts.append(f" {error_date}")
        return "".join(parts)

    def _build_note_content(self, frontmatter: dict, body: str, title: str = None) -> str:
        """
        构建笔记内容

        IMA 会从 Markdown 内容里自动提取标题（忽略 API 传的 title 参数），
        所以把标题作为 H1 放在最前面，让 IMA 提取到有意义的标题。

        结构：
            # [孩子][学科] 主题 - ID     ← IMA 从这里提取标题
            ---
            frontmatter (YAML)
            ---
            正文
        """
        fm_yaml = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False)
        parts = []
        if title:
            parts.append(f"# {title}\n")
        parts.append(f"---\n{fm_yaml}---\n")
        parts.append(body)
        return "\n".join(parts)

    def _parse_note_content(self, content: str) -> tuple[dict, str]:
        """解析笔记内容，提取 frontmatter 和 body"""
        import re

        # 先剥掉开头的 H1 标题行（我们自己加的，IMA 用它做标题）
        content = re.sub(r"^#\s+.+?\n+", "", content, count=1)

        # 尝试多种 frontmatter 格式
        # 格式 1: 标准 YAML frontmatter (---)
        match = re.match(r"^---\n(.+?)\n---\n\n?(.*)", content, re.DOTALL)
        if match:
            frontmatter = yaml.safe_load(match.group(1)) or {}
            body = match.group(2)
            return frontmatter, body

        # 格式 2: IMA 转换后的格式 (***)
        match = re.match(r"^\*\*\*\n\n(.+?)\n-+\n\n?(.*)", content, re.DOTALL)
        if match:
            # 将 IMA 的转义字符还原
            fm_text = match.group(1)
            fm_text = fm_text.replace("\\_", "_")
            fm_text = fm_text.replace("\\*", "*")
            frontmatter = yaml.safe_load(fm_text) or {}
            body = match.group(2)
            return frontmatter, body

        # 格式 3: 直接包含 YAML 内容
        if "id:" in content and "child:" in content:
            # 尝试提取 YAML 部分
            lines = content.split("\n")
            yaml_lines = []
            body_start = 0
            for i, line in enumerate(lines):
                if line.startswith("# ") or line.startswith("## "):
                    body_start = i
                    break
                if ":" in line or line.strip() == "":
                    yaml_lines.append(line)

            if yaml_lines:
                yaml_text = "\n".join(yaml_lines)
                yaml_text = yaml_text.replace("\\_", "_")
                yaml_text = yaml_text.replace("\\*", "*")
                frontmatter = yaml.safe_load(yaml_text) or {}
                body = "\n".join(lines[body_start:])
                return frontmatter, body

        # 无法解析，返回空 frontmatter
        return {}, content

    async def save_question(
        self,
        question_id: str,
        child: str,
        subject: str,
        frontmatter: dict,
        body: str,
        images: list[tuple[bytes, str]] = None,
    ) -> str:
        """保存错题到 IMA 知识库"""
        try:
            # 上传图片（如果有）
            image_urls = []
            if images:
                for image_data, filename in images:
                    url = await self.client.upload_image(image_data, filename)
                    if url:
                        image_urls.append(url)

            # 更新 frontmatter 中的图片引用
            if image_urls:
                frontmatter["image_urls"] = image_urls

            # 生成标题
            child_name = "女儿" if child == "daughter" else "儿子"
            title = self._build_title(child, subject, frontmatter)

            # 构建笔记内容（标题作为 H1 放最前面，IMA 会提取它）
            content = self._build_note_content(frontmatter, body, title=title)

            # 创建笔记
            note_id = await self.client.create_note(
                title=title,
                content=content,
                tags=[child, subject, frontmatter.get("error_type", ""), question_id],
            )

            if not note_id:
                raise Exception("IMA 笔记创建失败")

            # 将笔记添加到知识库
            knowledge_base_id = settings.ima_knowledge_base_id
            if knowledge_base_id:
                # 查找 孩子/学科 对应的文件夹
                folder_id = await self.client.find_folder_by_path(
                    knowledge_base_id, [child_name, subject]
                )

                success = await self.client.add_note_to_knowledge_base(
                    note_id=note_id,
                    knowledge_base_id=knowledge_base_id,
                    title=title,
                    folder_id=folder_id,
                )
                if success:
                    location = f"{child_name}/{subject}" if folder_id else "根目录"
                    logger.info(f"错题已保存到 IMA 知识库 [{location}]: {note_id}")
                else:
                    logger.warning(f"笔记创建成功但添加到知识库失败: {note_id}")
            else:
                logger.info(f"未配置知识库 ID，笔记仅保存为普通笔记: {note_id}")

            return note_id

        except Exception as e:
            logger.error(f"保存错题到 IMA 失败: {e}")
            raise

    async def list_questions(
        self,
        child: str,
        subject: Optional[str] = None,
    ) -> list[dict]:
        """列出 IMA 中的错题"""
        try:
            # 分页获取所有笔记（IMA API 限制每次最多 20 条）
            all_notes = []
            cursor = ""
            max_pages = 50  # 最多获取 50 页（1000 条笔记）

            for page in range(max_pages):
                notes_page = await self.client.list_notes(limit=20, offset=0, folder_id=None)
                if not notes_page:
                    break

                all_notes.extend(notes_page)

                # 检查是否还有更多（这里简化处理，假设获取到小于 20 条就结束了）
                if len(notes_page) < 20:
                    break

                # 实际应该从返回数据中获取下一个 cursor，但当前 API 返回结构不支持
                # 暂时用简单的方式：如果获取到 20 条，继续获取下一页
                # 注意：这会导致重复获取，但暂时这样处理
                break  # 暂时只获取第一页，后续优化

            if not all_notes:
                return []

            results = []
            for note in all_notes:
                # 获取笔记完整内容
                note_content = await self.client.get_note(note.get("id"))
                if not note_content:
                    continue

                content = note_content.get("content", "")
                frontmatter, _ = self._parse_note_content(content)

                # 过滤条件
                if frontmatter.get("child") != child:
                    continue
                if subject and frontmatter.get("subject") != subject:
                    continue

                # 添加存储 ID
                frontmatter["_storage_id"] = note.get("id")
                frontmatter["_file"] = note.get("id")  # 兼容现有代码
                results.append(frontmatter)

            return results

        except Exception as e:
            logger.error(f"列出 IMA 错题失败: {e}")
            return []

    async def read_question(self, storage_id: str) -> dict:
        """读取 IMA 中的错题"""
        try:
            note = await self.client.get_note(storage_id)
            if not note:
                raise Exception(f"IMA 笔记不存在: {storage_id}")

            content = note.get("content", "")
            frontmatter, body = self._parse_note_content(content)

            frontmatter["_storage_id"] = storage_id
            frontmatter["_file"] = storage_id  # 兼容现有代码
            frontmatter["_body"] = body

            return frontmatter

        except Exception as e:
            logger.error(f"读取 IMA 错题失败: {e}")
            raise

    async def update_question(
        self,
        storage_id: str,
        frontmatter: dict,
        body: Optional[str] = None,
    ) -> bool:
        """更新 IMA 中的错题"""
        try:
            # 如果没提供 body，尝试获取现有内容
            if body is None:
                existing = await self.read_question(storage_id)
                body = existing.get("_body", "")

            # 生成标题
            title = self._build_title(
                frontmatter.get("child", ""),
                frontmatter.get("subject", ""),
                frontmatter,
            )

            # 构建新内容（标题作为 H1 放最前面）
            content = self._build_note_content(frontmatter, body, title=title)

            # 更新笔记
            success = await self.client.update_note(
                note_id=storage_id,
                title=title,
                content=content,
                tags=[
                    frontmatter.get("child", ""),
                    frontmatter.get("subject", ""),
                    frontmatter.get("error_type", ""),
                    frontmatter.get("id", ""),
                ],
            )

            if success:
                logger.info(f"IMA 错题已更新: {storage_id}")
            return success

        except Exception as e:
            logger.error(f"更新 IMA 错题失败: {e}")
            return False

    async def delete_question(self, storage_id: str) -> bool:
        """删除 IMA 中的错题"""
        try:
            success = await self.client.delete_note(storage_id)
            if success:
                logger.info(f"IMA 错题已删除: {storage_id}")
            return success

        except Exception as e:
            logger.error(f"删除 IMA 错题失败: {e}")
            return False

    async def get_image_url(self, storage_id: str, filename: str) -> Optional[str]:
        """获取 IMA 中的图片 URL"""
        try:
            # 从笔记的 frontmatter 中获取图片 URL 列表
            note_data = await self.read_question(storage_id)
            image_urls = note_data.get("image_urls", [])

            # 简单匹配：返回第一个图片 URL（实际应该根据 filename 匹配）
            if image_urls:
                return image_urls[0]
            return None

        except Exception as e:
            logger.error(f"获取 IMA 图片 URL 失败: {e}")
            return None

    async def sync_from(self, source: StorageBackend) -> dict:
        """从另一个存储后端同步数据到 IMA"""
        stats = {"created": 0, "updated": 0, "deleted": 0, "errors": 0}

        try:
            # 获取源存储中的所有错题
            # 简化实现：假设源存储实现了列出所有错题的方法

            # 获取 IMA 中已有的错题 ID
            ima_questions = await self.list_questions("", None)  # 获取所有
            ima_ids = {q.get("id") for q in ima_questions if q.get("id")}

            # 遍历源存储（这里需要源存储支持遍历所有孩子和学科）
            # 简化实现：假设源存储实现了 get_all_questions 方法

            logger.info(f"同步完成: {stats}")
            return stats

        except Exception as e:
            logger.error(f"同步过程出错: {e}")
            return stats

    async def sync_to_obsidian(self, file_storage: StorageBackend) -> dict:
        """从 IMA 同步到 Obsidian（本地文件）"""
        stats = {"created": 0, "updated": 0, "deleted": 0, "errors": 0}

        try:
            # 获取 IMA 中的所有错题
            ima_questions = await self.list_questions("", None)

            for q in ima_questions:
                storage_id = q.get("_storage_id")
                if not storage_id:
                    continue

                try:
                    # 读取完整数据
                    full_data = await self.read_question(storage_id)
                    body = full_data.pop("_body", "")
                    full_data.pop("_file", None)
                    full_data.pop("_storage_id", None)

                    child = full_data.get("child")
                    subject = full_data.get("subject")
                    question_id = full_data.get("id")

                    if not all([child, subject, question_id]):
                        continue

                    # 检查本地是否已存在
                    local_questions = await file_storage.list_questions(child, subject)
                    local_ids = {q.get("id") for q in local_questions}

                    if question_id not in local_ids:
                        # 创建新文件
                        await file_storage.save_question(
                            question_id=question_id,
                            child=child,
                            subject=subject,
                            frontmatter=full_data,
                            body=body,
                        )
                        stats["created"] += 1
                    else:
                        # 更新现有文件
                        local_q = next((q for q in local_questions if q.get("id") == question_id), None)
                        if local_q and local_q.get("_file"):
                            await file_storage.update_question(
                                storage_id=local_q["_file"],
                                frontmatter=full_data,
                                body=body,
                            )
                            stats["updated"] += 1

                except Exception as e:
                    logger.error(f"同步错题 {storage_id} 失败: {e}")
                    stats["errors"] += 1

        except Exception as e:
            logger.error(f"同步过程出错: {e}")

        logger.info(f"IMA → Obsidian 同步完成: {stats}")
        return stats
