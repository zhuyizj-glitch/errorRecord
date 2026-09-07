"""应用配置"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path


# 查找 .env 文件
def find_env_file():
    """查找 .env 文件位置"""
    # 尝试多个位置
    locations = [
        Path(__file__).parent.parent.parent / ".env",  # backend/.env
        Path(__file__).parent.parent.parent.parent / ".env",  # project root/.env
        Path.cwd() / ".env",
    ]
    for loc in locations:
        if loc.exists():
            return str(loc)
    return None


class Settings(BaseSettings):
    vault_path: str = "/vault"
    config_path: str = "/app/config"
    cors_origins: str = "http://localhost:5173"

    # IMA 配置
    ima_api_key: str = ""
    ima_client_id: str = ""
    ima_sync_interval_hours: int = 12
    ima_enabled: bool = False  # 功能开关
    ima_knowledge_base_id: str = ""  # 错题集知识库 ID

    class Config:
        env_file = find_env_file()
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # 忽略 .env 中未定义的变量

    @property
    def cors_origin_list(self) -> list[str]:
        return [s.strip() for s in self.cors_origins.split(",") if s.strip()]

    @property
    def vault(self) -> Path:
        return Path(self.vault_path)

    @property
    def config_dir(self) -> Path:
        return Path(self.config_path)

    @property
    def settings_file(self) -> Path:
        return self.config_dir / "settings.json"


settings = Settings()
