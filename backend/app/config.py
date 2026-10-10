"""Application settings. Every value comes from environment variables (or backend/.env)."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MarketLens"
    environment: str = "local"
    log_level: str = "INFO"

    # Comma-separated list of allowed browser origins.
    cors_origins: str = "http://localhost:3000"

    # Supabase Postgres. Use the Session pooler string (IPv4, port 5432) for local dev.
    database_url: SecretStr | None = None
    db_pool_min_size: int = 0
    db_pool_max_size: int = 5
    db_connect_timeout_s: float = 10.0

    # LLM + embeddings (swappable through config; see docs/decisions.md for verification).
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.8-flash"
    embedding_provider: str = "gemini"
    embedding_model: str = "gemini-embedding-2"
    embedding_dimension: int = Field(default=1536, ge=128, le=2000)
    gemini_api_key: SecretStr | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
