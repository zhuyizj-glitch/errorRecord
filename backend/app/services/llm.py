"""LLM API 调用服务（OpenAI 兼容格式）"""

import httpx
import json
import base64
import io
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
        "max_tokens": 4096,
    }

    headers = {
        "Authorization": f"Bearer {llm_settings.api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=llm_settings.timeout) as client:
        resp = await client.post(
            f"{llm_settings.api_base}/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        resp.encoding = "utf-8"
        data = resp.json()

    # 提取回复文本
    reply = data["choices"][0]["message"]["content"]

    # 尝试解析 JSON
    try:
        import re
        # 去掉可能的 markdown 代码块标记
        cleaned = reply.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # 修复非法的转义字符（如 \p \s \D 等 LaTeX 命令）
        # 合法转义: \" \\ \/ \b \f \n \r \t \uXXXX
        # 非法转义保留反斜杠：\p → \\p（JSON 中表示字面量 \p）
        def fix_escape(match):
            char = match.group(1)
            if char in '"\\/bfnrtu':
                return match.group(0)  # 合法转义，保持不变
            # 非法转义，双写反斜杠使其合法
            return '\\\\' + char
        cleaned = re.sub(r'\\(.)', fix_escape, cleaned)

        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM 返回的不是有效 JSON (error: {e}):\n{reply[:500]}")


async def test_connection(api_base: str, api_key: str, model: str) -> dict:
    """测试 LLM API 连接"""
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "请回复 '连接成功'。"},
        ],
        "max_tokens": 20,
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
- 继续使用纯文本格式，避免 LaTeX
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
        "max_tokens": 4096,
    }

    headers = {
        "Authorization": f"Bearer {llm_settings.api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=llm_settings.timeout) as client:
        resp = await client.post(
            f"{llm_settings.api_base}/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        resp.encoding = "utf-8"
        data = resp.json()

    reply = data["choices"][0]["message"]["content"]

    # 解析 JSON（复用相同的逻辑）
    try:
        import re
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
            if char in '"\\/bfnrtu':
                return match.group(0)
            return '\\\\' + char
        cleaned = re.sub(r'\\(.)', fix_escape, cleaned)

        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM 返回的不是有效 JSON (error: {e}):\n{reply[:500]}")
