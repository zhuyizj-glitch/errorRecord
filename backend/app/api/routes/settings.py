"""设置接口"""

import json
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.settings import Settings, TestConnectionRequest
from app.services import llm

router = APIRouter()


def _is_masked_key(key: str) -> bool:
    """检测 API Key 是否是脱敏后的值"""
    return "•" in key or "…" in key or "***" in key


def _load_real_key() -> str:
    """从配置文件加载真实的 API Key"""
    settings_file = settings.settings_file
    if not settings_file.exists():
        return ""
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    return data.get("llm", {}).get("api_key", "")


@router.get("/settings")
async def get_settings():
    """获取 LLM 设置（API Key 脱敏）"""
    settings_file = settings.settings_file
    if not settings_file.exists():
        return {"llm": {"api_base": "", "api_key": "", "model": ""}}
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    llm_data = data.get("llm", {})
    # 脱敏 API Key
    if llm_data.get("api_key"):
        key = llm_data["api_key"]
        llm_data["api_key"] = key[:8] + "••••••" + key[-4:] if len(key) > 12 else "••••••"
    return data


@router.put("/settings")
async def save_settings(s: Settings):
    """保存 LLM 设置（如果 API Key 是脱敏的，保留原 key）"""
    settings_file = settings.settings_file
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    # 如果前端发回的 API Key 是脱敏的，保留原始 key
    if _is_masked_key(s.llm.api_key):
        real_key = _load_real_key()
        if real_key:
            s.llm.api_key = real_key

    settings_file.write_text(s.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
    return {"success": True}


@router.post("/settings/test")
async def test_connection(req: TestConnectionRequest):
    """测试 LLM 连接（如果 API Key 是脱敏的，使用配置文件中的真实 key）"""
    api_key = req.api_key
    if _is_masked_key(api_key):
        api_key = _load_real_key()
        if not api_key:
            raise HTTPException(status_code=400, detail="API Key 未配置，请先填写完整的 API Key")

    try:
        result = await llm.test_connection(req.api_base, api_key, req.model)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接失败: {e}")
