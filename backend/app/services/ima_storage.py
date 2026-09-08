"""IMA 存储后端 - 基于腾讯 IMA 云存储"""

import json
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

        两个 IMA 特性决定了这个结构：

        1. IMA 忽略 API 传的 title，自己从内容里提取 → 标题作为 H1 放最前面
        2. IMA 会重写 Markdown：`_` 转义成 `\\_`、列表 `-` 变 `*`、字段间插空行、
           多行字符串被拆断。YAML frontmatter 在这种改写下必然解析失败，
           所以元数据用 ```json 代码块包裹 —— 代码块内容 IMA 不会动。

        结构：
            # 【女儿·数学】一元二次方程（计算错误） 2026-09-08
            ```json
            {"id": "...", "child": "...", ...}
            ```
            正文
        """
        meta_json = json.dumps(frontmatter, ensure_ascii=False, indent=2, default=str)
        parts = []
        if title:
            parts.append(f"# {title}\n")
        parts.append(f"```json\n{meta_json}\n```\n")
        parts.append(body)
        return "\n".join(parts)

    def _parse_note_content(self, content: str) -> tuple[dict, str]:
        """
        解析笔记内容，提取元数据和正文

        按优先级尝试多种格式，兼容历史数据：
        1. ```json 代码块（当前格式，最可靠）
        2. 标准 YAML frontmatter（---）
        3. IMA 改写后的 YAML（*** + 转义字符 + 空行）
        """
        import re

        # 剥掉开头的 H1 标题（我们自己加的，IMA 用它做标题）
        content = re.sub(r"^#\s+.+?\n+", "", content, count=1)

        # 格式 1: ```json 代码块（当前格式）
        match = re.match(r"^```json\s*\n(.+?)\n```\s*\n?(.*)", content, re.DOTALL)
        if match:
            try:
                meta = json.loads(match.group(1))
                return meta, match.group(2).strip()
            except json.JSONDecodeError as e:
                logger.warning(f"JSON 元数据解析失败: {e}")

        # 格式 2: 标准 YAML frontmatter
        match = re.match(r"^---\n(.+?)\n---\n\n?(.*)", content, re.DOTALL)
        if match:
            try:
                meta = yaml.safe_load(match.group(1)) or {}
                return meta, match.group(2)
            except yaml.YAMLError as e:
                logger.warning(f"YAML frontmatter 解析失败: {e}")

        # 格式 3: IMA 改写后的 YAML（历史数据）
        match = re.match(r"^\*\*\*\s*\n(.+?)\n(?:\*\*\*|-{3,})\s*\n?(.*)", content, re.DOTALL)
        if match:
            meta = self._parse_ima_mangled_yaml(match.group(1))
            if meta:
                return meta, match.group(2).strip()

        # 兜底：内容里直接有 YAML 字段
        if "id:" in content and "child:" in content:
            meta = self._parse_ima_mangled_yaml(content)
            if meta:
                # 正文从第一个 Markdown 标题开始
                body_match = re.search(r"^#{1,6}\s+.+$", content, re.MULTILINE)
                body = content[body_match.start():] if body_match else ""
                return meta, body

        logger.warning("无法解析笔记元数据")
        return {}, content

    def _parse_ima_mangled_yaml(self, text: str) -> dict:
        """
        解析被 IMA 改写过的 YAML

        IMA 的改写行为：
        - 下划线转义：`error_type` → `error\\_type`
        - 星号转义：`*` → `\\*`
        - 字段间插入空行
        - 列表项 `- item` → `* item`
        - 多行字符串被拆成多个段落（无法完整还原，只能尽力）

        策略：逐行提取 `key: value` 对，忽略无法解析的部分。
        比整体 yaml.safe_load 更健壮 —— 单个字段坏了不影响其他字段。
        """
        import re

        # 还原转义
        text = text.replace("\\_", "_").replace("\\*", "*")

        meta = {}
        current_key = None
        list_items = []

        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            # 列表项（IMA 把 - 变成了 *）
            if stripped.startswith(("* ", "- ")):
                if current_key:
                    list_items.append(stripped[2:].strip())
                continue

            # key: value
            kv = re.match(r"^([a-zA-Z_][\w]*)\s*:\s*(.*)$", stripped)
            if kv:
                # 先收尾上一个列表字段
                if current_key and list_items:
                    meta[current_key] = list_items
                    list_items = []

                key, raw_value = kv.group(1), kv.group(2).strip()
                current_key = key

                if not raw_value:
                    # 可能是列表或嵌套结构的开头
                    continue

                meta[key] = self._coerce_yaml_scalar(raw_value)
                current_key = None
            # 其他行（多行字符串的续行等）直接丢弃

        # 收尾
        if current_key and list_items:
            meta[current_key] = list_items

        return meta

    @staticmethod
    def _coerce_yaml_scalar(raw: str):
        """把 YAML 标量字符串转成 Python 值"""
        # 去引号
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
            return raw[1:-1]

        # 布尔
        low = raw.lower()
        if low in ("true", "yes"):
            return True
        if low in ("false", "no"):
            return False
        if low in ("null", "~", ""):
            return None

        # 数字
        try:
            return int(raw)
        except ValueError:
            pass
        try:
            return float(raw)
        except ValueError:
            pass

        return raw

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
        """
        列出 IMA 中的错题

        注意：需要逐条读取笔记内容才能拿到 frontmatter 做过滤，
        所以这个操作的请求数与笔记总数成正比，较慢。
        """
        try:
            # 取全部笔记（自动分页）
            all_notes = await self.client.list_notes()
            if not all_notes:
                return []

            results = []
            for note in all_notes:
                note_id = note.get("id")
                if not note_id:
                    continue

                # 获取笔记完整内容
                note_content = await self.client.get_note(note_id)
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
                frontmatter["_storage_id"] = note_id
                frontmatter["_file"] = note_id  # 兼容现有代码
                results.append(frontmatter)

            logger.info(f"IMA 错题列表: {child}/{subject or '全部'} → {len(results)} 条")
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
        """
        从 IMA 同步到 Obsidian（本地文件）

        遍历 IMA 所有笔记（自动分页），解析出错题后写入本地。
        本地已存在的更新，不存在的新建。
        """
        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

        try:
            # 取全部笔记（自动分页）
            all_notes = await self.client.list_notes()
            if not all_notes:
                logger.info("IMA 中没有笔记，跳过同步")
                return stats

            # 本地已有错题的缓存：{(child, subject): {id: file_path}}
            local_cache: dict[tuple, dict] = {}

            for note in all_notes:
                note_id = note.get("id")
                if not note_id:
                    continue

                try:
                    # 读取笔记内容并解析
                    note_content = await self.client.get_note(note_id)
                    if not note_content:
                        continue

                    frontmatter, body = self._parse_note_content(
                        note_content.get("content", "")
                    )

                    child = frontmatter.get("child")
                    subject = frontmatter.get("subject")
                    question_id = frontmatter.get("id")

                    # 不是错题笔记（缺少必要字段），跳过
                    if not all([child, subject, question_id]):
                        stats["skipped"] += 1
                        continue

                    # 清理内部字段
                    clean_fm = {
                        k: v for k, v in frontmatter.items()
                        if not k.startswith("_")
                    }

                    # 查本地（带缓存，避免重复扫目录）
                    cache_key = (child, subject)
                    if cache_key not in local_cache:
                        local_list = await file_storage.list_questions(child, subject)
                        local_cache[cache_key] = {
                            q.get("id"): q.get("_file")
                            for q in local_list
                            if q.get("id")
                        }

                    local_file = local_cache[cache_key].get(question_id)

                    if local_file:
                        # 更新现有文件
                        await file_storage.update_question(
                            storage_id=local_file,
                            frontmatter=clean_fm,
                            body=body,
                        )
                        stats["updated"] += 1
                    else:
                        # 新建
                        new_path = await file_storage.save_question(
                            question_id=question_id,
                            child=child,
                            subject=subject,
                            frontmatter=clean_fm,
                            body=body,
                        )
                        local_cache[cache_key][question_id] = new_path
                        stats["created"] += 1

                except Exception as e:
                    logger.error(f"同步笔记 {note_id} 失败: {e}")
                    stats["errors"] += 1

            logger.info(f"IMA → Obsidian 同步完成: {stats}")
            return stats

        except Exception as e:
            logger.error(f"同步过程出错: {e}")
            stats["errors"] += 1
            return stats
