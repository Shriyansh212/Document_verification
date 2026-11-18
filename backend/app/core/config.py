from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Document Verification Pipeline"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = False

    database_url: str = "sqlite:///./data/verification.db"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    tesseract_cmd: str = ""

    max_file_size_mb: int = 10
    upload_dir: str = "./data/uploads"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
