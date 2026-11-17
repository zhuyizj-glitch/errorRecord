"""文件操作服务 - Markdown 的读写"""

import logging
import re
import yaml
from pathlib import Path
from datetime import date
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# 文件名里各段的分隔符。用全角间隔号而不是下划线或空格，
# 因为它在中文文件名里可读性最好，也不会与内容里的符号混淆。
FILENAME_SEPARATOR = "·"

# 文件名中不允许出现的字符：POSIX 的 "/"、Windows 保留字符、以及控制字符。
# OneDrive 与 macOS 都按这套规则处理。
_UNSAFE_FILENAME_CHARS = re.compile(r'[/\\:*?"<>|\x00-\x1f]')

# 单段的字节预算。macOS 单个文件名的上限是 255 字节，中文每字 3 字节，
# 给「人名 + 学科 + 日期 + id + 后缀」留足余量的同时避免超长。
_CHILD_NAME_BUDGET = 45
_SUBJECT_BUDGET = 24


def safe_filename_component(text: str, max_bytes: int) -> str:
    """
    把用户可控的文本清洗成可安全用作文件名的片段。

    人名和学科都可能被改名成含 "/" 等非法字符的内容，直接拼进文件名
    会导致写文件失败或落到意料之外的目录。这里做替换 + 按字节截断，
    截断时按字节切再解码，避免把一个汉字切成半个。
    """
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", (text or "").strip())
    cleaned = cleaned.strip(". ")  # 首尾的点和空格在部分系统上会被吃掉
    if not cleaned:
        return "未命名"

    encoded = cleaned.encode("utf-8")
    if len(encoded) > max_bytes:
        cleaned = encoded[:max_bytes].decode("utf-8", errors="ignore").strip()
    return cleaned or "未命名"


def _child_subject_dir(account_id: str, child_id: str, subject: str) -> Path:
    """获取孩子某学科的目录"""
    return settings.vault / "accounts" / account_id / child_id / subject


def ensure_subject_dir(account_id: str, child_id: str, subject: str) -> Path:
    directory = _child_subject_dir(account_id, child_id, subject)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _generate_filename(
    question_id: str, error_date: date, child_name: str, subject: str
) -> str:
    """
    生成 markdown 文件名：人名·学科·日期-id.md

    例：女儿·数学·2026-09-20-6882bdf1.md

    question_id 必须留在末尾：同一天同一主题可以有两道题，靠它保证唯一；
    同时 find_question_file 是按 "*-{id}.md" 后缀匹配定位文件的。
    """
    child = safe_filename_component(child_name, _CHILD_NAME_BUDGET)
    subj = safe_filename_component(subject, _SUBJECT_BUDGET)
    return (
        f"{child}{FILENAME_SEPARATOR}{subj}{FILENAME_SEPARATOR}"
        f"{error_date.isoformat()}-{question_id}.md"
    )


def _build_markdown(frontmatter: dict, body: str) -> str:
    """构建 markdown 文件内容

    ⚠️ 必须过滤掉 `_` 开头的派生字段（_file / _body / _question …）。
    它们只存在于内存视图里，不该进存储：
    移动孩子/学科那条路径（questions.py 的 patch）会把
    `_load_for_update()` 的完整 dict 直接交给 save_question()，
    一旦漏过滤，`_body: '整篇正文'` 就会被序列化进 frontmatter，
    把错题文件写脏、还会顺着 IMA 事件快照传到云端。
    （StorageManager.update_question 已有同样的过滤，这里是与它对齐的第二道防线。）
    """
    clean = {k: v for k, v in frontmatter.items() if not k.startswith("_")}
    fm = yaml.dump(clean, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return f"---\n{fm}---\n\n{body}"


def is_practice(fm: dict) -> bool:
    """这道题是不是「练习题」（AI 生成、与错题区分）。

    IMA 会改写笔记内容，布尔值有可能回来是字符串 "true"/"false"，
    所以这里统一收口，不要在各处直接 `fm.get("is_practice")`。
    """
    value = fm.get("is_practice")
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def save_question(
    question_id: str,
    account_id: str,
    child_id: str,
    subject: str,
    frontmatter: dict,
    body: str,
) -> Path:
    """保存错题 markdown 文件"""
    dir_path = _child_subject_dir(account_id, child_id, subject)
    dir_path.mkdir(parents=True, exist_ok=True)

    filename = _generate_filename(
        question_id,
        date.fromisoformat(frontmatter["error_date"]),
        frontmatter.get("child_name", ""),
        subject,
    )
    file_path = dir_path / filename

    content = _build_markdown(frontmatter, body)
    file_path.write_text(content, encoding="utf-8")
    return file_path


def list_questions(
    account_id: str,
    child_id: str,
    subject: Optional[str] = None,
    *,
    include_body: bool = False,
    include_practice: bool = False,
) -> list[dict]:
    """列出错题（解析 frontmatter；可选带正文、可选含练习题）

    - include_body=True  时每条附 `_body`（供复习页 / 出题参考 / 导出使用）
    - include_practice=False（默认）时**跳过练习题**。

    两个开关都是 keyword-only 且默认值等于旧行为，所以现有调用点无需改动。
    include_practice 的默认值就是「安全值」：将来新增的调用方即使忘了考虑
    练习题，也不会把它混进统计与复习计划。

    刻意**不加 limit 截断**：统计接口也走这个函数，函数内按 limit 提前 return
    会因为「哪个学科先被遍历到」而静默漏题，统计数字会悄悄算错——
    这类"看起来对其实少算了"的问题比报错难查得多。
    需要控制响应体积时，只在路由层对正文字段做长度上限。
    """
    results: list[dict] = []
    base = settings.vault / "accounts" / account_id / child_id
    if not base.exists():
        return results

    if subject:
        subjects = [subject]
    else:
        subjects = sorted(
            d.name for d in base.iterdir()
            if d.is_dir() and not d.name.startswith((".", "_"))
        )

    for subj in subjects:
        subj_dir = base / subj
        if not subj_dir.exists():
            continue
        for md_file in sorted(subj_dir.glob("*.md"), reverse=True):
            try:
                fm, body = _split_markdown(md_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not include_practice and is_practice(fm):
                continue
            fm["_file"] = str(md_file)
            fm["_id"] = fm.get("id", md_file.stem)
            if include_body:
                fm["_body"] = body
            results.append(fm)
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


def find_question_file(
    account_id: str, child_id: str, subject: str, question_id: str
) -> Optional[Path]:
    """
    按 question_id 定位本地错题文件。

    文件名以 "-{question_id}.md" 结尾，因此用后缀匹配即可，
    不需要事先知道 error_date 或文件名的可读部分。
    """
    if not all([account_id, child_id, subject, question_id]):
        return None
    directory = _child_subject_dir(account_id, child_id, subject)
    if not directory.exists():
        return None
    for candidate in sorted(directory.glob(f"*-{question_id}.md")):
        return candidate
    return None


def iter_local_scopes() -> list[tuple[str, str, str]]:
    """
    列出本地缓存里实际存在的 (account_id, child_id, subject) 组合。

    重建时用来找出「只在本地、从未进过 IMA」的错题——在 IMA 为权威来源之后，
    这类错题意味着某次写入没落到云端，是需要暴露的完整性信号。
    """
    base = settings.vault / "accounts"
    if not base.exists():
        return []

    scopes: list[tuple[str, str, str]] = []
    for account_dir in sorted(base.iterdir()):
        if not account_dir.is_dir():
            continue
        for child_dir in sorted(account_dir.iterdir()):
            if not child_dir.is_dir():
                continue
            for subject_dir in sorted(child_dir.iterdir()):
                if subject_dir.is_dir():
                    scopes.append((account_dir.name, child_dir.name, subject_dir.name))
    return scopes


def rename_questions_for_child(
    account_id: str, child_id: str, new_child_name: str
) -> int:
    """
    孩子改名后，刷新其名下所有错题的文件名与 frontmatter。

    文件名和 frontmatter 里都存了 child_name，改名后如果不处理就会陈旧。
    改名是低频的明确操作，在这里做一次批量刷新，比让所有读取方去容错更划算。

    不做的事：IMA 笔记的标题也含人名，但 IMA 没有修改接口（见 8.31），
    云端标题会停留在改名前的状态。

    返回实际重命名的文件数。
    """
    base = settings.vault / "accounts" / account_id / child_id
    if not base.exists():
        return 0

    renamed = 0
    for md_file in sorted(base.glob("*/*.md")):
        subject = md_file.parent.name
        try:
            data = read_question(str(md_file))
        except Exception as exc:
            logger.warning(f"改名时跳过无法解析的文件 {md_file.name}: {exc}")
            continue  # 无法解析的历史文件跳过，不影响改名本身

        body = data.pop("_body", "")
        data.pop("_file", None)
        question_id = str(data.get("id", ""))
        if not question_id:
            continue

        target = md_file.parent / _generate_filename(
            question_id,
            date.fromisoformat(str(data["error_date"])),
            new_child_name,
            subject,
        )
        if target == md_file:
            continue

        data["child_name"] = new_child_name
        update_question(str(md_file), data, body)

        if target.exists():
            # 目标名被占用（理论上不会，id 唯一），保留原文件名但内容已更新
            continue
        md_file.rename(target)
        renamed += 1

    return renamed


def update_question(file_path: str, frontmatter: dict, body: Optional[str] = None) -> Path:
    """更新错题文件"""
    path = Path(file_path)
    if body is None:
        body = _parse_body(path)
    content = _build_markdown(frontmatter, body)
    path.write_text(content, encoding="utf-8")
    return path


def delete_question(file_path: str) -> None:
    """删除错题文件（原图不落盘，无需清理图片）"""
    path = Path(file_path)
    if path.exists():
        path.unlink()


# 匹配 `---\n<frontmatter>\n---` 及其后的空行。
# 这一段正则同时服务 frontmatter 与正文的切分，必须与原 _parse_body 的写法逐字符等价：
# 末尾的 `\n\n?` 决定正文开头会不会多出一个空行，差一个字符详情页就会渲染出多余空行。
_FRONTMATTER_RE = re.compile(r"^---\n(.+?)\n---\n\n?", re.DOTALL)


def _split_markdown(text: str) -> tuple[dict, str]:
    """一次读取，同时产出 frontmatter 与正文。

    原先 _parse_frontmatter 与 _parse_body 各读一次同一个文件、各跑一遍正则；
    而列表场景（复习计划 / 统计 / 导出 / 出题取参考）需要同时拿到两者，
    合并后是「零额外 I/O」—— 文件本来就整个读进来了，只是正文被丢掉了。
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("无 frontmatter")
    return yaml.safe_load(match.group(1)) or {}, text[match.end():]


def _parse_frontmatter(md_path: Path) -> dict:
    """解析 markdown 文件的 frontmatter（保留给只关心元数据的调用方）"""
    try:
        fm, _ = _split_markdown(md_path.read_text(encoding="utf-8"))
    except ValueError:
        raise ValueError(f"无 frontmatter: {md_path}") from None
    return fm


def _parse_body(md_path: Path) -> str:
    """解析 markdown 文件的正文（保留给只关心正文的调用方）"""
    text = md_path.read_text(encoding="utf-8")
    try:
        _, body = _split_markdown(text)
        return body
    except ValueError:
        # 没有 frontmatter 的历史文件：整篇当正文，保持原行为
        return text
