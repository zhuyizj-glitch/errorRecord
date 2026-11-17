"""IMA 存储后端 - 基于腾讯 IMA 云存储"""

import json
import logging
import re
import yaml
from pathlib import Path
from typing import Optional
from datetime import date

from app.services.storage_backend import StorageBackend
from app.services.ima_client import get_ima_client
from app.services.ima_skip_cache import (
    ImaSkipCache,
    REASON_FOREIGN_ACCOUNT,
    REASON_NOT_A_QUESTION,
)
from app.services import file_ops
from app.core.config import settings

logger = logging.getLogger(__name__)

# 笔记里的元数据代码块。IMA 会改写代码块之外的 Markdown，
# 但代码块内容原样保留（8.37 实测确认），所以元数据一律走代码块。
_JSON_BLOCK_RE = re.compile(r"```json[ \t]*\n(.*?)\n[ \t]*```", re.DOTALL)


def _ima_is_newer(ima_updated_at, local_updated_at) -> bool:
    """
    判断 IMA 版本是否不旧于本地版本。

    规则：
    - 本地没有版本标记（账号化改造前的历史文件）→ 允许覆盖
    - IMA 没有版本标记 → 不覆盖，保守处理，避免用无版本信息的数据
      冲掉本地可能更新的记录
    - 两者都有 → 按 ISO8601 字符串比较（同一格式下字典序等同时间序）
    """
    if not local_updated_at:
        return True
    if not ima_updated_at:
        return False
    return str(ima_updated_at) >= str(local_updated_at)


# 事件里不进入状态、只用于折叠过程的键
_EVENT_META_KEYS = {"type", "result", "note"}

# 列表接口返回的 summary 是笔记开头约 200 字，里面就带着元数据代码块的开头。
# 用它在读正文之前做归属判断和「是否变过」的预筛，能把 N+1 次读取降下来。
_SUMMARY_FIELDS = ("id", "account_id", "child_id", "subject")


def _meta_from_summary(summary: str) -> dict:
    """
    从 list_note 返回的 summary 里尽量提取定位字段。

    提取不到就返回空 —— 调用方会退回读正文，不会因为解析不出来而漏掉笔记。
    各字段在 JSON 块里的顺序是固定的（id 在最前，subject 紧跟 child_name），
    都落在 summary 的截断范围内。
    """
    if not summary:
        return {}
    found = {}
    for field in _SUMMARY_FIELDS:
        match = re.search(rf'"{field}"\s*:\s*"([^"]*)"', summary)
        if match:
            found[field] = match.group(1)
    return found


def _fold_events(base: dict, events: list[dict]) -> dict:
    """
    把基础元数据与后续事件折叠成当前状态。

    IMA 没有修改接口，所以状态变化只能以追加事件的方式记录（见 8.33/8.37）。
    事件只携带**可变的**字段，基础块保持不可变。折叠规则：

    - 普通字段：后者覆盖前者
    - redo 事件：额外往 redo_history 追加一条记录
    - delete 事件：标记 deleted

    事件数量与重做次数同阶，折叠是纯内存操作，开销可忽略。
    """
    state = dict(base)
    history = list(state.get("redo_history") or [])
    deleted = bool(state.get("deleted"))

    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")

        if event_type == "redo":
            history.append({
                "date": str(event.get("at", ""))[:10],
                "result": event.get("result"),
                "note": event.get("note"),
            })
        elif event_type == "delete":
            deleted = True

        state.update({
            key: value
            for key, value in event.items()
            if key not in _EVENT_META_KEYS
        })

    if history:
        state["redo_history"] = history
    if deleted:
        state["deleted"] = True

    return state


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
        child_name = frontmatter.get("child_name", child)
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

    def _build_event_content(self, event: dict) -> str:
        """
        构建追加的单个事件块。

        事件是「当前状态的快照」而不是指令：读的时候只要把事件逐条覆盖到
        基础块上即可，不需要重放计算。这样折叠逻辑足够简单，也不会因为
        漏掉某个事件而算错。

        用代码块包裹是必须的——8.37 实测确认 IMA 会改写代码块之外的
        Markdown（`_` → `\\_`、`*` → `_`、`[` → `\\[`），只有代码块内容原样保留。
        """
        payload = json.dumps(event, ensure_ascii=False, indent=2, default=str)
        return f"\n```json\n{payload}\n```\n"

    async def append_event(self, storage_id: str, event: dict) -> bool:
        """
        向已有笔记追加一个事件。

        IMA 没有修改接口，追加是唯一的写入方式。代价是笔记只增不减，
        因此事件只携带可变字段，且每道题始终只有一篇笔记（见 8.33）。
        """
        if not storage_id:
            logger.warning("缺少 IMA 笔记 ID，无法追加事件")
            return False
        try:
            success = await self.client.append_to_note(
                storage_id, self._build_event_content(event)
            )
            if success:
                logger.info(
                    f"事件已追加: note={storage_id} type={event.get('type')} "
                    f"rev={event.get('rev')}"
                )
            return success
        except Exception as e:
            logger.error(f"追加事件失败 note={storage_id}: {e}")
            return False

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
        # 第一个代码块是基础元数据；之后带 "type" 的代码块是追加的事件，
        # 必须折叠后才得到当前状态（见 8.33 / 8.37）。
        blocks = list(_JSON_BLOCK_RE.finditer(content))
        if blocks:
            try:
                meta = json.loads(blocks[0].group(1))
            except json.JSONDecodeError as e:
                logger.warning(f"JSON 元数据解析失败: {e}")
            else:
                events = []
                first_event_start = len(content)
                for block in blocks[1:]:
                    try:
                        payload = json.loads(block.group(1))
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict) and "type" in payload:
                        events.append(payload)
                        first_event_start = min(first_event_start, block.start())

                # 正文是基础块与第一个事件块之间的内容
                body = content[blocks[0].end():first_event_start].strip()
                return _fold_events(meta, events), body

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
        account_id: str,
        child_id: str,
        subject: str,
        frontmatter: dict,
        body: str,
    ) -> str:
        """
        保存错题到 IMA 知识库

        只写入分析结果的文字内容。原始图片不进 IMA——它只是 LLM 的输入，
        分析完成后不需要保留，因此正文中不含任何图片引用。
        """
        try:
            # 生成标题
            child_name = frontmatter.get("child_name", child_id)
            title = self._build_title(child_id, subject, frontmatter)

            # 构建笔记内容（标题作为 H1 放最前面，IMA 会提取它）
            content = self._build_note_content(frontmatter, body, title=title)

            # 创建笔记
            note_id = await self.client.create_note(
                title=title,
                content=content,
                tags=[child_name, subject, frontmatter.get("error_type", ""), question_id],
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
        account_id: str,
        child_id: str,
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
                if frontmatter.get("account_id") != account_id:
                    continue
                if frontmatter.get("child_id") != child_id:
                    continue
                if subject and frontmatter.get("subject") != subject:
                    continue

                # 添加存储 ID
                frontmatter["_storage_id"] = note_id
                frontmatter["_file"] = note_id  # 兼容现有代码
                # 从云端读回来的数据自带笔记 ID，后续追加事件才有落点
                frontmatter["ima_note_id"] = note_id
                results.append(frontmatter)

            logger.info(
                f"IMA 错题列表: {account_id}/{child_id}/{subject or '全部'} → {len(results)} 条"
            )
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
            # 从云端读回来的数据自带笔记 ID，后续追加事件才有落点
            frontmatter["ima_note_id"] = storage_id
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
        """
        ⚠️ 不适用于 IMA：状态变更请走 `append_event()`。

        IMA 没有修改笔记的接口。过去这里调用一个并不存在的 `update_note`
        方法，异常被吞掉后返回 False，导致「同步到 IMA」长期静默失效（见 8.31）。

        现在改为显式抛错，避免再出现「看起来成功了其实什么都没做」的情况。
        写入路径由 StorageManager.update_question 负责，它会调用 append_event。
        """
        raise NotImplementedError(
            "IMA 不支持修改笔记，请使用 append_event() 追加事件"
        )


    async def delete_question(self, storage_id: str) -> bool:
        """删除 IMA 中的错题（IMA OpenAPI 无删除接口，恒返回 False）"""
        if not hasattr(self.client, "delete_note"):
            logger.warning("IMA OpenAPI 无删除笔记接口，跳过云端删除")
            return False
        try:
            success = await self.client.delete_note(storage_id)
            if success:
                logger.info(f"IMA 错题已删除: {storage_id}")
            return success

        except Exception as e:
            logger.error(f"删除 IMA 错题失败: {e}")
            return False

    async def _local_entries(
        self,
        file_storage: StorageBackend,
        cache: dict,
        account_id: str,
        child_id: str,
        subject: str,
    ) -> dict:
        """
        取某个 (账号, 孩子, 学科) 下的本地缓存索引：{question_id: (路径, updated_at, 云端修改时间)}。

        带缓存，避免同一次同步里反复扫目录。
        """
        cache_key = (account_id, child_id, subject)
        if cache_key not in cache:
            local_list = await file_storage.list_questions(account_id, child_id, subject)
            cache[cache_key] = {
                q.get("id"): (
                    q.get("_file"),
                    q.get("updated_at"),
                    q.get("ima_modified_at"),
                )
                for q in local_list
                if q.get("id")
            }
        return cache[cache_key]

    async def sync_to_obsidian(
        self,
        file_storage: StorageBackend,
        allowed_scopes: set[tuple[str, str]],
        force: bool = False,
        prune: bool = False,
        dry_run: bool = False,
        skip_unchanged: bool = True,
    ) -> dict:
        """
        把 IMA 的内容物化到本地缓存。

        两种模式：

        - **常规同步**（force=False）：写之前比对 updated_at，只有 IMA 不旧于本地
          才覆盖。本地有更新的改动时跳过并计入 conflicts，避免用旧快照冲掉本地。
        - **重建**（force=True）：以 IMA 为准强制覆盖。用于本地缓存丢失、损坏或
          不可信时——此时 IMA 是唯一记录来源，本地的版本号没有参考价值。

        `skip_unchanged=True` 时，本地记的 `ima_modified_at` 与列表接口给出的
        `modify_time` 一致就不读正文——这是把批量操作从分钟级压到秒级的关键。
        代价是它假定本地文件没有被绕过系统改动过；想彻底重读就传 False。

        `prune=True` 时还会删除「只在本地、IMA 里没有」的错题文件。默认只统计
        不删除：那通常意味着某次写入没落到云端，是要人看一眼的完整性信号，
        不该被静默清理掉。

        `dry_run=True` 只统计不写入，用来预览重建会做什么。
        """
        stats = {
            "created": 0, "updated": 0, "forced": 0, "skipped": 0, "unchanged": 0,
            "preskipped": 0, "conflicts": 0, "errors": 0, "pruned": 0, "local_only": 0,
        }

        # 记下 IMA 侧见过的错题，用来识别「只在本地」的那些
        ima_seen: dict[tuple, set] = {}
        local_cache: dict[tuple, dict] = {}
        skip_cache = ImaSkipCache()

        try:
            all_notes = await self.client.list_notes()
            if not all_notes:
                logger.info("IMA 中没有笔记，跳过同步")

            for note in all_notes:
                note_id = note.get("id")
                if not note_id:
                    continue

                modified_at = note.get("modified_at")
                hint = _meta_from_summary(note.get("content") or "")

                # 预筛一：归属已判明、且不在允许范围 → 不必读正文
                hint_account, hint_child = hint.get("account_id"), hint.get("child_id")
                if hint_account and hint_child and (hint_account, hint_child) not in allowed_scopes:
                    # 归属确定的「别人的」笔记：记下来，下一轮连判断都省了
                    skip_cache.mark(note_id, modified_at, REASON_FOREIGN_ACCOUNT)
                    stats["errors"] += 1
                    continue

                # 预筛三：上一轮已确认不是我们的错题、且此后没变过 → 跳过读取。
                # 知识库里往往有一批历史格式或别的用途的笔记，它们每次都要被
                # 完整读一遍再丢弃；在笔记较多时这部分开销超过真正的错题。
                if skip_cache.should_skip(note_id, modified_at):
                    stats["preskipped"] += 1
                    continue

                # 预筛二：summary 已给出全部定位字段且本地版本一致 → 跳过读取。
                # 这里是整个同步唯一的省请求点，所以条件卡得严：四个字段全有、
                # 本地文件存在、且云端修改时间与物化时记录的一致，缺一不可。
                if skip_unchanged and all(hint.get(f) for f in _SUMMARY_FIELDS):
                    cache_key = (hint["account_id"], hint["child_id"], hint["subject"])
                    entries = await self._local_entries(
                        file_storage, local_cache, *cache_key
                    )
                    cached = entries.get(hint["id"])
                    if cached and cached[2] and cached[2] == modified_at:
                        ima_seen.setdefault(cache_key, set()).add(hint["id"])
                        stats["unchanged"] += 1
                        continue

                try:
                    note_content = await self.client.get_note(note_id)
                    if not note_content:
                        # get_note 在失败时返回 None（例如限频重试后仍失败）。
                        # 必须计入 errors：否则统计显示一切正常，而实际上
                        # 有笔记根本没拉到——这种「看起来成功了」最危险。
                        logger.error(f"无法获取笔记内容，跳过: {note_id}")
                        stats["errors"] += 1
                        continue

                    frontmatter, body = self._parse_note_content(
                        note_content.get("content", "")
                    )

                    account_id = frontmatter.get("account_id")
                    child_id = frontmatter.get("child_id")
                    subject = frontmatter.get("subject")
                    question_id = frontmatter.get("id")

                    if not all([account_id, child_id, subject, question_id]):
                        # 不是本系统的错题笔记（历史格式、别的用途）
                        skip_cache.mark(note_id, modified_at, REASON_NOT_A_QUESTION)
                        stats["skipped"] += 1
                        continue
                    if (account_id, child_id) not in allowed_scopes:
                        skip_cache.mark(note_id, modified_at, REASON_FOREIGN_ACCOUNT)
                        stats["errors"] += 1
                        continue

                    clean_fm = {
                        k: v for k, v in frontmatter.items()
                        if not k.startswith("_")
                    }
                    clean_fm["ima_note_id"] = note_id
                    if modified_at:
                        # 记下物化时对应的云端版本，下一轮同步据此跳过读取
                        clean_fm["ima_modified_at"] = modified_at

                    cache_key = (account_id, child_id, subject)
                    ima_seen.setdefault(cache_key, set()).add(question_id)
                    entries = await self._local_entries(
                        file_storage, local_cache, *cache_key
                    )

                    cached = entries.get(question_id)

                    if cached:
                        local_file, local_updated_at = cached[0], cached[1]
                        if not force and not _ima_is_newer(
                            clean_fm.get("updated_at"), local_updated_at
                        ):
                            logger.warning(
                                f"跳过覆盖，本地版本更新: note={note_id} "
                                f"(ima={clean_fm.get('updated_at')}, local={local_updated_at})"
                            )
                            stats["conflicts"] += 1
                            continue
                        if not dry_run:
                            await file_storage.update_question(
                                storage_id=local_file,
                                frontmatter=clean_fm,
                                body=body,
                            )
                        entries[question_id] = (
                            local_file, clean_fm.get("updated_at"), modified_at
                        )
                        # 重建模式下被强制覆盖的条目单独计数，便于看出重建真的做了什么
                        stats["forced" if force else "updated"] += 1
                    else:
                        new_path = None
                        if not dry_run:
                            new_path = await file_storage.save_question(
                                question_id=question_id,
                                account_id=account_id,
                                child_id=child_id,
                                subject=subject,
                                frontmatter=clean_fm,
                                body=body,
                            )
                        entries[question_id] = (
                            new_path, clean_fm.get("updated_at"), modified_at
                        )
                        stats["created"] += 1

                except Exception as e:
                    logger.error(f"同步笔记 {note_id} 失败: {e}")
                    stats["errors"] += 1

            skip_cache.prune_absent({n.get("id") for n in all_notes if n.get("id")})
            if not dry_run:
                skip_cache.save()

            await self._report_local_only(
                file_storage, allowed_scopes, ima_seen, stats,
                prune=prune and not dry_run,
            )

            mode = "重建模式" if force else "同步"
            if dry_run:
                mode += "·预演"
            logger.info(f"IMA → Obsidian {mode}完成: {stats}")
            return stats

        except Exception as e:
            logger.error(f"同步过程出错: {e}")
            stats["errors"] += 1
            return stats

    async def _report_local_only(
        self,
        file_storage: StorageBackend,
        allowed_scopes: set[tuple[str, str]],
        ima_seen: dict[tuple, set],
        stats: dict,
        prune: bool,
    ) -> None:
        """
        统计（并可选删除）只在本地、IMA 里没有的错题。

        IMA 是权威来源，所以这类错题意味着某次写入没落到云端。默认只报告，
        让人决定怎么处理，而不是悄悄删掉。
        """
        local_only = []
        for account_id, child_id, subject in file_ops.iter_local_scopes():
            if (account_id, child_id) not in allowed_scopes:
                continue
            seen = ima_seen.get((account_id, child_id, subject), set())
            local_list = await file_storage.list_questions(account_id, child_id, subject)
            for item in local_list:
                item_id = item.get("id")
                if item_id and item_id not in seen:
                    local_only.append({
                        "id": item_id,
                        "account_id": account_id,
                        "child_id": child_id,
                        "subject": subject,
                        "file": item.get("_file"),
                    })

        stats["local_only"] = len(local_only)
        if not local_only:
            return

        stats["local_only_ids"] = [item["id"] for item in local_only]
        logger.warning(
            f"发现 {len(local_only)} 条只在本地、未进入 IMA 的错题: "
            f"{stats['local_only_ids'][:10]}"
        )

        if not prune:
            return

        for item in local_only:
            try:
                Path(item["file"]).unlink()
                stats["pruned"] += 1
            except Exception as e:
                logger.error(f"删除本地独有文件失败 {item['file']}: {e}")
