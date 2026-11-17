"""真题库文件操作（v2.0）

真题是账号级题库：vault/accounts/{账号}/zhenti/{学科}/*.md。
与错题（file_ops）的区别：
- 不绑定孩子，目录里没有 child_id 层
- 可编辑、可删除（题库素材，不是学习记录）
- 只走文件存储，不进 IMA 事件模型（IMA 已弃用）

markdown 读写复用 file_ops 的底层工具，保证格式与过滤规则一致。
"""

import logging
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core import timeutil
from app.services.file_ops import (
    FILENAME_SEPARATOR,
    _build_markdown,
    _split_markdown,
    safe_filename_component,
)

logger = logging.getLogger(__name__)

_SOURCE_BUDGET = 60
_SUBJECT_BUDGET = 24


def _zhenti_dir(account_id: str, subject: str) -> Path:
    return settings.vault / "accounts" / account_id / "zhenti" / subject


def _generate_filename(zhenti_id: str, frontmatter: dict, subject: str) -> str:
    """文件名：来源·学科·年份-id.md

    id 必须留在末尾：find_zhenti_file 按 "*-{id}.md" 后缀定位，
    与错题的约定一致。
    """
    source = safe_filename_component(str(frontmatter.get("source", "")), _SOURCE_BUDGET)
    subj = safe_filename_component(subject, _SUBJECT_BUDGET)
    year = safe_filename_component(str(frontmatter.get("year", "")), 12)
    return (
        f"{source}{FILENAME_SEPARATOR}{subj}{FILENAME_SEPARATOR}"
        f"{year}-{zhenti_id}.md"
    )


def build_body(item: dict) -> str:
    """真题正文模板（按形态渲染，供 Obsidian 阅读）。

    结构化数据（子题、标签）存在 frontmatter，正文是人类可读渲染。
    段标题与 body_parser.SECTION_ALIASES 兼容。
    """
    form = item.get("question_form", "independent")

    if form in ("material_group", "passage"):
        parts = []
        label = "语篇" if form == "passage" else "共享材料"
        parts += [f"## {label}", "", item.get("passage") or "（无）"]
        if item.get("has_diagram") and item.get("diagram_description"):
            parts += ["", f"> **图形描述**：{item['diagram_description']}"]
        subs = item.get("sub_questions") or []
        if subs:
            parts += ["", "## 子题"]
            for i, sub in enumerate(subs, 1):
                num = sub.get("number") or str(i)
                parts += ["", f"### 第 {num} 题", "",
                          f"> **题目内容**：{sub.get('question_text', '')}", "",
                          f"**参考答案**：{sub.get('correct_answer', '') or '（待补充）'}"]
                if sub.get("solution_steps"):
                    parts += ["", f"**解析**：{sub['solution_steps']}"]
        return "\n".join(parts)

    # independent
    parts = ["## 原题", "", f"> **题目内容**：{item.get('question_text', '')}"]
    if item.get("has_diagram") and item.get("diagram_description"):
        parts += ["", f"> **图形描述**：{item['diagram_description']}"]
    parts += ["", "## 参考答案", "", item.get("correct_answer", "") or "（待补充）"]
    if item.get("solution_steps"):
        parts += ["", "## 解题分析", "", item["solution_steps"]]
    return "\n".join(parts)


def new_frontmatter(
    zhenti_id: str, account_id: str, subject: str, year: str, source: str, item: dict
) -> dict:
    """新真题的初始 frontmatter（练习计数从零开始，含三形态与组织轴字段）"""
    return {
        "id": zhenti_id,
        "account_id": account_id,
        "subject": subject,
        "year": year,
        "source": source,
        "number": item.get("number") or "",
        "question_form": item.get("question_form", "independent"),
        "question_type": item.get("question_type"),
        "rating": item.get("rating"),
        "topic": item.get("topic") or "",
        "knowledge_points": item.get("knowledge_points") or [],
        "era": item.get("era"),
        "module": item.get("module"),
        "difficulty": item.get("difficulty") or "中等",
        "has_diagram": bool(item.get("has_diagram")),
        "diagram_description": item.get("diagram_description"),
        "passage": item.get("passage"),
        "sub_questions": item.get("sub_questions") or [],
        "created_at": timeutil.today().isoformat(),
        "practice_count": 0,
        "correct_count": 0,
        "wrong_count": 0,
        "last_practice_at": None,
        "practice_history": [],
        "converted_to": [],
    }


def save_zhenti(
    zhenti_id: str, account_id: str, subject: str, frontmatter: dict, body: str
) -> Path:
    directory = _zhenti_dir(account_id, subject)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _generate_filename(zhenti_id, frontmatter, subject)
    path.write_text(_build_markdown(frontmatter, body), encoding="utf-8")
    return path


def read_zhenti(file_path: str) -> dict:
    """读取真题：frontmatter + _body + _file（派生字段不落盘）"""
    path = Path(file_path)
    fm, body = _split_markdown(path.read_text(encoding="utf-8"))
    return {**fm, "_body": body, "_file": str(path)}


def list_zhenti(
    account_id: str, subject: Optional[str] = None, *, include_body: bool = False
) -> list[dict]:
    """列出账号真题库（解析 frontmatter；可选带正文）"""
    base = _zhenti_dir(account_id, subject) if subject else (
        settings.vault / "accounts" / account_id / "zhenti"
    )
    if not base.exists():
        return []

    paths = sorted(base.glob("*.md")) if subject else sorted(base.glob("*/*.md"))
    items: list[dict] = []
    for path in paths:
        try:
            fm, body = _split_markdown(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"跳过无法解析的真题文件 {path.name}: {exc}")
            continue
        entry = {**fm, "_file": str(path)}
        if include_body:
            entry["_body"] = body
        items.append(entry)
    return items


def find_zhenti_file(
    account_id: str, zhenti_id: str, subject: Optional[str] = None
) -> Optional[Path]:
    """按 "*-{id}.md" 后缀定位真题文件；subject 缺省时跨学科查找"""
    base = _zhenti_dir(account_id, subject) if subject else (
        settings.vault / "accounts" / account_id / "zhenti"
    )
    if not base.exists():
        return None
    pattern = f"*-{zhenti_id}.md"
    candidates = base.glob(pattern) if subject else base.glob(f"*/{pattern}")
    for candidate in sorted(candidates):
        return candidate
    return None


def update_zhenti(file_path: str, frontmatter: dict, body: Optional[str] = None) -> Path:
    path = Path(file_path)
    if body is None:
        _, body = _split_markdown(path.read_text(encoding="utf-8"))
    path.write_text(_build_markdown(frontmatter, body), encoding="utf-8")
    return path


def delete_zhenti(file_path: str) -> None:
    path = Path(file_path)
    if path.exists():
        path.unlink()
