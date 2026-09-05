"""文件操作服务 - Markdown 和图片的读写"""

import re
import yaml
from pathlib import Path
from datetime import date
from typing import Optional

from app.core.config import settings


def _child_subject_dir(child: str, subject: str) -> Path:
    """获取孩子某学科的目录"""
    return settings.vault / child / subject


def _assets_dir(child: str, subject: str, question_id: str) -> Path:
    """获取题目图片存放目录"""
    return settings.vault / "_assets" / child / subject / question_id


def _generate_filename(question_id: str, error_date: date) -> str:
    """生成 markdown 文件名"""
    return f"{error_date.isoformat()}-{question_id}.md"


def _build_markdown(frontmatter: dict, body: str) -> str:
    """构建 markdown 文件内容"""
    fm = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return f"---\n{fm}---\n\n{body}"


def save_question(
    question_id: str,
    child: str,
    subject: str,
    frontmatter: dict,
    body: str,
) -> Path:
    """保存错题 markdown 文件"""
    dir_path = _child_subject_dir(child, subject)
    dir_path.mkdir(parents=True, exist_ok=True)

    filename = _generate_filename(question_id, date.fromisoformat(frontmatter["error_date"]))
    file_path = dir_path / filename

    content = _build_markdown(frontmatter, body)
    file_path.write_text(content, encoding="utf-8")
    return file_path


def save_image(image_data: bytes, child: str, subject: str, question_id: str, filename: str) -> Path:
    """保存图片到 _assets 目录"""
    dir_path = _assets_dir(child, subject, question_id)
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / filename
    file_path.write_bytes(image_data)
    return file_path


def list_questions(child: str, subject: Optional[str] = None) -> list[dict]:
    """列出错题（解析 frontmatter）"""
    results = []
    base = settings.vault / child
    if not base.exists():
        return results

    subjects = [subject] if subject else [d.name for d in base.iterdir() if d.is_dir()]

    for subj in subjects:
        subj_dir = base / subj
        if not subj_dir.exists():
            continue
        for md_file in sorted(subj_dir.glob("*.md"), reverse=True):
            try:
                fm = _parse_frontmatter(md_file)
                fm["_file"] = str(md_file)
                fm["_id"] = fm.get("id", md_file.stem)
                results.append(fm)
            except Exception:
                continue
    return results


def read_question(file_path: str) -> dict:
    """读取单个错题文件"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    fm = _parse_frontmatter(path)
    fm["_file"] = str(path)
    fm["_body"] = _parse_body(path)
    return fm


def update_question(file_path: str, frontmatter: dict, body: Optional[str] = None) -> Path:
    """更新错题文件"""
    path = Path(file_path)
    if body is None:
        body = _parse_body(path)
    content = _build_markdown(frontmatter, body)
    path.write_text(content, encoding="utf-8")
    return path


def delete_question(file_path: str, child: str, subject: str, question_id: str) -> None:
    """删除错题文件和对应图片"""
    path = Path(file_path)
    if path.exists():
        path.unlink()

    # 删除图片目录
    assets_dir = _assets_dir(child, subject, question_id)
    if assets_dir.exists():
        import shutil
        shutil.rmtree(assets_dir)


def _parse_frontmatter(md_path: Path) -> dict:
    """解析 markdown 文件的 frontmatter"""
    text = md_path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.+?)\n---", text, re.DOTALL)
    if not match:
        raise ValueError(f"无 frontmatter: {md_path}")
    return yaml.safe_load(match.group(1)) or {}


def _parse_body(md_path: Path) -> str:
    """解析 markdown 文件的正文"""
    text = md_path.read_text(encoding="utf-8")
    match = re.match(r"^---\n.+?\n---\n\n?", text, re.DOTALL)
    if match:
        return text[match.end():]
    return text
