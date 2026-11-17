"""把错题 markdown 的正文拆成结构化段落

正文模板由 `routes/questions.py` 生成，形如：

    ## 原题

    > **题目内容**：……

    ## 正确答案

    ……

    ## 解题过程

    ……

    ## 错误分析
    **错误点：** ……
    **错因诊断：** ……
    **建议：** ……

    ## 家长备注

    ……

但**不能指望它总是这个形状**：

  · 历史版本生成的文件格式不同
  · IMA 会改写代码块之外的 Markdown（`_` → `\\_`、`*` → `_`、插入空行）
  · AI 生成的练习题用 `## 易错点` 而不是 `## 错误分析`

所以解析必须宽松，并且**必须能回落到整段原文** —— 识别不到段落时返回
`structured=False` + 完整 `raw`，由调用方整段渲染。绝不能因为格式不匹配就显示空白，
那会让人以为数据丢了。
"""

import re

# 二级或三级标题。容忍行首空白、标题尾部的 `#`、以及被转义成 `\#` 的情况。
_HEADING_RE = re.compile(r"^[ \t]*#{2,3}[ \t]*(?:\\?#*)?[ \t]*(.+?)[ \t]*$", re.MULTILINE)

# 题目内容在正文里是引用块 + 加粗前缀：`> **题目内容**：……`
#
# ⚠️ 引用前缀 `> ` 必须写成可选：段内容会先经 _clean_section() 剥掉每行开头的 `> `，
# 到这里时已经只剩 `**题目内容**：`。但也要容忍没剥干净的情况（比如同一行里出现）。
_QUESTION_PREFIX_RE = re.compile(
    r"^\s*(?:>\s*)?\*{0,2}题目内容\*{0,2}\s*[：:]\s*", re.MULTILINE
)

# 段标题别名：规范名 -> 可能出现的写法
#
# 「易错点」是给 AI 生成的练习题预留的 —— 用 ## 易错点 落盘，
# 复习页渲染、导出排版、结果解析三处都能直接复用，不必为练习题写分支。
SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "question": ("原题", "题目", "试题", "题干"),
    "answer": ("正确答案", "参考答案", "答案"),
    "solution": ("解题过程", "解题步骤", "解答", "解析", "解题思路"),
    "error_analysis": ("错误分析", "错因分析", "易错点", "错误原因", "错因"),
    "parent_note": ("家长备注", "家长笔记", "备注"),
}

_ALIAS_TO_SECTION: dict[str, str] = {
    alias: section
    for section, aliases in SECTION_ALIASES.items()
    for alias in aliases
}


def _normalize_heading(raw: str) -> str:
    """把标题行归一化成可以查别名表的形式。

    去空白、去加粗标记、去首尾冒号 —— 不同版本的模板与 IMA 的改写都可能引入这些。
    """
    text = raw.strip().strip("*").strip()
    return text.rstrip("：:").strip()


def _clean_section(content: str) -> str:
    """清掉段落内容的引用前缀（`> `）与多余空白"""
    lines = [re.sub(r"^\s*>\s?", "", line) for line in content.splitlines()]
    return "\n".join(lines).strip()


def parse_question_body(body: str) -> dict:
    """解析正文，返回各段落。

    返回的 dict 一定包含这些键（缺失的为空字符串）：

        structured       bool —— 是否识别出至少一个已知段标题
        question / answer / solution / error_analysis / parent_note
        plain            未被识别归类的段落（拼接）
        raw              原始正文，兜底渲染用
    """
    raw = body or ""
    result: dict = {
        "structured": False,
        "question": "",
        "answer": "",
        "solution": "",
        "error_analysis": "",
        "parent_note": "",
        "plain": "",
        "raw": raw,
    }
    if not raw.strip():
        return result

    matches = list(_HEADING_RE.finditer(raw))
    if not matches:
        # 连一个标题都没有：整篇当 plain，由调用方回落渲染 raw
        result["plain"] = raw.strip()
        return result

    sections: dict[str, list[str]] = {}
    unclassified: list[str] = []

    # 第一个标题之前的内容
    head = raw[: matches[0].start()].strip()
    if head:
        unclassified.append(head)

    for i, match in enumerate(matches):
        title = _normalize_heading(match.group(1))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        content = raw[match.end():end]

        section = _ALIAS_TO_SECTION.get(title)
        if section:
            sections.setdefault(section, []).append(_clean_section(content))
        else:
            # 不认识的标题：连着内容一起进 plain，保证不丢东西
            unclassified.append(f"## {title}\n{content.strip()}")

    for section, chunks in sections.items():
        result[section] = "\n\n".join(c for c in chunks if c).strip()

    # 题目段落还要剥掉 `> **题目内容**：` 这层壳
    if result["question"]:
        result["question"] = _QUESTION_PREFIX_RE.sub("", result["question"]).strip()

    result["plain"] = "\n\n".join(unclassified).strip()
    result["structured"] = any(
        result[key]
        for key in ("question", "answer", "solution", "error_analysis", "parent_note")
    )
    return result


def decorate_with_sections(fm: dict) -> dict:
    """给一条错题挂上解析后的段落（供复习页、练习题详情、PDF 导出共用）。

    ⚠️ 派生字段一律 `_` 前缀，且**只在响应里构造** —— 绝不能挂到
    `read_question()` 上：那条路径的返回值会被「移动孩子/学科」直接交给
    `save_question()`，漏过滤就会把 `_body: <整篇正文>` 写进 YAML frontmatter。
    `file_ops._build_markdown()` 里有过滤兜底，但别让脏数据产生才是第一道防线。
    """
    parsed = parse_question_body(fm.get("_body") or "")
    return {
        **fm,
        "_structured": parsed["structured"],
        # 无法结构化时用 plain 兜底，尽量让页面有内容可显示（不能空白）
        "_question": parsed["question"] or parsed["plain"],
        "_answer": parsed["answer"],
        "_solution": parsed["solution"],
        "_error_analysis": parsed["error_analysis"],
        "_parent_note": parsed["parent_note"],
    }
