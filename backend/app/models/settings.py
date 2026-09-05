"""设置数据模型"""

from pydantic import BaseModel
from typing import Optional


class LLMSettings(BaseModel):
    """LLM API 配置"""
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o"
    system_prompt: Optional[str] = None
    timeout: int = 60


class Settings(BaseModel):
    """完整设置"""
    llm: LLMSettings = LLMSettings()


class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    api_base: str
    api_key: str
    model: str
