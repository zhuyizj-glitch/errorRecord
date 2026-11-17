"""设置数据模型"""

from pydantic import BaseModel
from typing import Optional


class LLMSettings(BaseModel):
    """LLM API 配置"""
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o"
    system_prompt: Optional[str] = None
    # 单次 AI 调用的超时（秒）。
    # 现在多图上传会拆成「每张图一个任务」串行跑，单次输出量小了很多，
    # 120 秒对一张复杂的整页题也够（实测最复杂的单页约 41 秒）。
    timeout: int = 120
    # 单次回答的最大 token 数。留空则用 llm.py 里的 DEFAULT_MAX_TOKENS。
    #
    # ⚠️ 推理型模型（DeepSeek V4 系列、o 系列等）会把「思考过程」也算进这个额度，
    # 思考常吃掉几千 token，留给正文的就不够了 —— 表现为正文 JSON 被截断，
    # 报错「LLM 返回的不是有效 JSON (Unterminated string)」。
    # 用这类模型时务必给足，或在设置里显式调大。
    max_tokens: Optional[int] = None


class Settings(BaseModel):
    """完整设置"""
    llm: LLMSettings = LLMSettings()


class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    api_base: str
    api_key: str
    model: str
