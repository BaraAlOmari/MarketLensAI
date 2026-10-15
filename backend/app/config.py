"""Application settings. Every value comes from environment variables (or backend/.env)."""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent

# Fixed USD pegs (docs/decisions.md): QAR 3.64, SAR 3.75, AED 3.6725 per USD.
DEFAULT_FX_RATES_TO_QAR = {
    "QAR": Decimal("1"),
    "USD": Decimal("3.64"),
    "SAR": Decimal("0.970667"),
    "AED": Decimal("0.991150"),
}


class Settings(BaseSettings):
    # Absolute path, so scripts work from any working directory.
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

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

    # Embedding quota. Free tier for gemini-embedding-2: 100 RPM, 1,000 RPD, 30k input TPM
    # (AI Studio, 2026-10-11). Every text in a batch call counts as one request.
    embedding_rpm_limit: int = Field(default=100, gt=0)
    embedding_tpm_limit: int = Field(default=30_000, gt=0)
    embedding_rpd_limit: int = Field(default=1_000, gt=0)
    embedding_query_reserve: int = Field(default=100, ge=0)  # left for search queries
    embedding_batch_size: int = Field(default=45, ge=1, le=100)  # 2 calls fit in 90 RPM
    # Paid-tier list price, used only to report what a run would cost (free tier is $0).
    embedding_price_per_mtok_usd: Decimal = Decimal("0.20")

    # Query understanding (Stage 4): the LLM fills a filter form; Python maps it to SQL.
    # Free tier for gemini-3.5-flash-lite: 15 RPM, 500 RPD (AI Studio, 2026-10-13).
    extraction_enabled: bool = True
    extraction_model: str = "gemini-3.5-flash-lite"
    extraction_rpm_limit: int = Field(default=15, gt=0)
    extraction_timeout_s: float = Field(default=20, gt=0)
    extraction_max_attempts: int = Field(default=2, ge=1, le=8)  # interactive: one retry
    extraction_thinking_level: str = "minimal"  # flash-lite default; minimal|low|medium|high
    # Paid-tier list prices per 1M tokens (pricing page, 2026-10-13), for cost reporting.
    extraction_input_price_per_mtok_usd: Decimal = Decimal("0.30")
    extraction_output_price_per_mtok_usd: Decimal = Decimal("2.50")

    # Retrieval (Stage 5): "hybrid" = vector + full-text fused with RRF; "vector" = Stage 4.
    retrieval_mode: Literal["hybrid", "vector"] = "hybrid"
    hybrid_candidates: int = Field(default=50, ge=10, le=200)  # per side, before fusion
    rrf_k: int = Field(default=60, ge=1)
    # What the full-text side searches: the LLM's extracted keywords (exact tokens such as
    # 512GB or M4 Max), or the raw query. With no keywords the full-text side is skipped.
    hybrid_keywords: Literal["llm", "query"] = "llm"

    # Currency: QAR is the base; every listing also stores price_qar for cross-currency filters.
    base_currency: str = "QAR"
    fx_rates_to_qar: dict[str, Decimal] = Field(
        default_factory=lambda: dict(DEFAULT_FX_RATES_TO_QAR)
    )

    # Synthetic data generator (Stage 1). Free tier for gemini-3.8-flash: 5 RPM, 20 RPD
    # (AI Studio, 2026-10-10), so pace below the RPM and pack many listings per request.
    generator_model: str | None = None  # None -> llm_model
    generator_rpm: float = Field(default=4, gt=0)
    generator_batch_size: int = Field(default=50, ge=1, le=80)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
