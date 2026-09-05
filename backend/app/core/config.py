"""应用配置"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path


class Settings(BaseSettings):
    vault_path: str = "/vault"
    config_path: str = "/app/config"
    cors_origins: str = "http://localhost:5173"

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
