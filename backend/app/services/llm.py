"""LLM API 调用服务（OpenAI 兼容格式）"""

import httpx
import json
import base64
import io
import re
from pathlib import Path
from typing import Optional
from PIL import Image

from app.core.config import settings
from app.core.prompts import ANALYZE_QUESTION_PROMPT
from app.models.settings import LLMSettings

# 图片处理限制
MAX_IMAGE_SIZE = 1024  # 最大边长（像素）
MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 最大 4MB（base64 后约 5.3MB）
JPEG_QUALITY = 85

# 单次回答的最大 token 数（可在设置里用 max_tokens 覆盖）。
#
# 原值是 4096，对普通模型够用，但对**推理型模型**不够：
# DeepSeek V4 这类模型会先输出 reasoning_content（思考过程）再输出正文，
# 两者共享同一个 max_tokens 额度。实测 deepseek-flash 分析一张题目图时
# 思考就吃掉 2000+ token，导致正文 JSON 在 question_text 中途被截断，
# 报错「LLM 返回的不是有效 JSON (Unterminated string)」。
#
# 题目分析要一次性输出：题目文字、正确答案、解题过程、错误分析、改进建议，
# 给足余量才不会截断。推理模型单价很低，多留额度的成本可以忽略。
DEFAULT_MAX_TOKENS = 32768


def _load_settings() -> LLMSettings:
    """从配置文件加载 LLM 设置"""
    settings_file = settings.settings_file
    if not settings_file.exists():
        raise ValueError("LLM 未配置，请先在设置页面配置 AI 模型")
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    return LLMSettings(**data.get("llm", {}))


def _preprocess_image(image_path: Path) -> tuple[str, str]:
    """
    预处理图片：缩放 + 压缩为 JPEG，返回 (base64, media_type)
    """
    img = Image.open(image_path)

    # 转换为 RGB（处理 RGBA、P 等模式）
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # 缩放：保持宽高比，最长边不超过 MAX_IMAGE_SIZE
    w, h = img.size
    if max(w, h) > MAX_IMAGE_SIZE:
        scale = MAX_IMAGE_SIZE / max(w, h)
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    # 压缩为 JPEG
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    jpeg_bytes = buffer.getvalue()

    # 如果仍然太大，进一步降低质量
    if len(jpeg_bytes) > MAX_IMAGE_BYTES:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=60, optimize=True)
        jpeg_bytes = buffer.getvalue()

    b64 = base64.b64encode(jpeg_bytes).decode("utf-8")
    return b64, "image/jpeg"


def _parse_json_reply(reply: str) -> dict:
    """解析 LLM 返回的 JSON，兼容 markdown 代码块与 LaTeX 的非法转义。

    模型被要求输出 JSON，而 LaTeX 命令（如 \\frac、\\sqrt）里的反斜杠在 JSON
    字符串里必须转义成双反斜杠。推理模型偶尔会漏转义，直接输出单反斜杠的
    LaTeX —— 这里先把非法转义修回合法 JSON，再交给 json.loads。

    注意「合法转义」集合里**不含 f**：JSON 的 \\f 是换页符，但数学内容里换页符
    几乎不可能出现，而 LaTeX 里以 f 开头的命令（\\frac、\\fbox）非常常见。
    宁可把 \\f 也按字面量反斜杠处理，避免 \\frac 被误拆成「换页符 + rac」。
    """
    cleaned = reply.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    def fix_escape(match):
        char = match.group(1)
        if char in '"\\/bnrtu':  # 合法转义（不含 f，见 docstring）
            return match.group(0)
        return '\\\\' + char
    cleaned = re.sub(r'\\(.)', fix_escape, cleaned)

    return json.loads(cleaned, strict=False)


async def analyze_images(image_paths: list[Path]) -> dict:
    """调用 LLM 分析题目图片"""
    llm_settings = _load_settings()

    # 构建图片内容（预处理后再发送）
    content = []
    for i, path in enumerate(image_paths):
        b64, media_type = _preprocess_image(path)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{media_type};base64,{b64}",
            },
        })

    content.append({"type": "text", "text": "请分析这张题目图片。"})

    # 构建请求
    system_prompt = llm_settings.system_prompt or ANALYZE_QUESTION_PROMPT
    payload = {
        "model": llm_settings.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "temperature": 0.3,
        "max_tokens": llm_settings.max_tokens or DEFAULT_MAX_TOKENS,
        # 强制模型输出语法合法的 JSON。
        # 推理模型在长文本里偶尔会漏逗号、写错引号（实测在 2000-2700 字符处出错），
        # 加上这个参数由服务端保证语法合法，比事后用正则修补残破的输出可靠得多。
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {llm_settings.api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=llm_settings.timeout) as client:
            resp = await client.post(
                f"{llm_settings.api_base}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"
            data = resp.json()
    except httpx.TimeoutException:
        # ⚠️ httpx 的超时异常 str() 是空字符串 —— 直接往上抛的话，
        # 前端只会显示「失败」而没有任何原因，用户完全不知道发生了什么。
        # 所以这里换成一条能指导下一步怎么办的消息。
        raise ValueError(
            f"AI 响应超时（等了 {llm_settings.timeout} 秒未返回）。"
            "通常是因为一次要分析的题目太多 —— 建议减少一次上传的图片数量后重试。"
        ) from None
    except httpx.HTTPStatusError as e:
        detail = (e.response.text or "")[:200]
        raise ValueError(f"AI 服务返回错误 {e.response.status_code}：{detail}") from None

    # 提取回复文本
    reply = data["choices"][0]["message"]["content"]

    # 尝试解析 JSON
    try:
        return _parse_json_reply(reply)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM 返回的不是有效 JSON (error: {e}):\n{reply[:500]}")


async def test_connection(api_base: str, api_key: str, model: str) -> dict:
    """测试 LLM API 连接"""
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "请回复 '连接成功'。"},
        ],
        # 推理模型会先输出思考（reasoning_content）再输出正文，20 太小会导致
        # content 为空，用户点「测试连接」只看到成功却没回复。给足余量。
        "max_tokens": 200,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{api_base}/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        resp.encoding = "utf-8"
        data = resp.json()
    return {"status": "ok", "reply": data["choices"][0]["message"]["content"]}


async def refine_analysis(image_paths: list[Path], feedback: str, current_result: dict) -> dict:
    """根据用户反馈重新优化分析结果"""
    llm_settings = _load_settings()

    # 构建图片内容
    content = []
    for path in image_paths:
        b64, media_type = _preprocess_image(path)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{b64}"},
        })

    # 构建反馈优化提示
    current_json = json.dumps(current_result, ensure_ascii=False, indent=2)
    prompt = f"""你之前对这道题的分析结果如下：

{current_json}

用户对你的分析有以下反馈：
{feedback}

请根据用户的反馈，重新生成完整的分析结果。保持相同的 JSON 格式，但根据反馈进行相应的修改和完善。

注意：
- 如果用户指出错误，请修正
- 如果用户要求补充，请添加更多细节
- 如果用户有不同观点，请考虑并调整分析
- 数学公式继续使用 LaTeX 格式（行内用 $...$，独立成行用 $$...$$）
"""

    content.append({"type": "text", "text": prompt})

    system_prompt = llm_settings.system_prompt or "你是一位经验丰富的教师，擅长分析学生的错题。请返回 JSON 格式的分析结果。"

    payload = {
        "model": llm_settings.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "temperature": 0.3,
        "max_tokens": llm_settings.max_tokens or DEFAULT_MAX_TOKENS,
        # 强制模型输出语法合法的 JSON。
        # 推理模型在长文本里偶尔会漏逗号、写错引号（实测在 2000-2700 字符处出错），
        # 加上这个参数由服务端保证语法合法，比事后用正则修补残破的输出可靠得多。
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {llm_settings.api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=llm_settings.timeout) as client:
            resp = await client.post(
                f"{llm_settings.api_base}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"
            data = resp.json()
    except httpx.TimeoutException:
        # ⚠️ httpx 的超时异常 str() 是空字符串 —— 直接往上抛的话，
        # 前端只会显示「失败」而没有任何原因，用户完全不知道发生了什么。
        # 所以这里换成一条能指导下一步怎么办的消息。
        raise ValueError(
            f"AI 响应超时（等了 {llm_settings.timeout} 秒未返回）。"
            "通常是因为一次要分析的题目太多 —— 建议减少一次上传的图片数量后重试。"
        ) from None
    except httpx.HTTPStatusError as e:
        detail = (e.response.text or "")[:200]
        raise ValueError(f"AI 服务返回错误 {e.response.status_code}：{detail}") from None

    reply = data["choices"][0]["message"]["content"]

    # 解析 JSON（复用相同的逻辑）
    try:
        return _parse_json_reply(reply)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM 返回的不是有效 JSON (error: {e}):\n{reply[:500]}")


# ── v2.0：真题卷分析 ──────────────────────────────────────────

async def _post_chat(llm_settings: LLMSettings, payload: dict) -> dict:
    """发送 chat 请求并解析 JSON 回复（统一的超时/错误处理）。

    与 analyze_images 内的逻辑一致；新代码走这里，
    旧函数保持原样不动（避免回归风险）。
    """
    headers = {
        "Authorization": f"Bearer {llm_settings.api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=llm_settings.timeout) as client:
            resp = await client.post(
                f"{llm_settings.api_base}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"
            data = resp.json()
    except httpx.TimeoutException:
        raise ValueError(
            f"AI 响应超时（等了 {llm_settings.timeout} 秒未返回）。"
            "真题卷整页题目较多时容易超时 —— 建议减少单次上传的页数后重试。"
        ) from None
    except httpx.HTTPStatusError as e:
        detail = (e.response.text or "")[:200]
        raise ValueError(f"AI 服务返回错误 {e.response.status_code}：{detail}") from None

    reply = data["choices"][0]["message"]["content"]
    try:
        return _parse_json_reply(reply)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM 返回的不是有效 JSON (error: {e}):\n{reply[:500]}")


async def analyze_exam_images(image_paths: list[Path], vocab: list[str]) -> dict:
    """分析真题卷图片（空白卷，无学生作答）。

    vocab：库内已有知识点词汇表，注入提示词让 AI 尽量复用标签，
    提高与错题薄弱点的匹配率。
    """
    from app.core.prompts import build_exam_prompt

    llm_settings = _load_settings()

    content = []
    for path in image_paths:
        b64, media_type = _preprocess_image(path)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{b64}"},
        })
    content.append({"type": "text", "text": "请分析这张真题卷图片，按题号逐题拆分。"})

    payload = {
        "model": llm_settings.model,
        "messages": [
            {"role": "system", "content": build_exam_prompt(vocab)},
            {"role": "user", "content": content},
        ],
        "temperature": 0.3,
        "max_tokens": llm_settings.max_tokens or DEFAULT_MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }
    return await _post_chat(llm_settings, payload)
