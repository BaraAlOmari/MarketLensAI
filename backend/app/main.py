import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, search
from app.config import Settings, get_settings
from app.db import create_pool
from app.logging_setup import RequestIdMiddleware, configure_logging
from app.providers.embeddings import get_embedding_provider
from app.providers.gemini import GeminiJsonClient
from app.providers.llm import GeminiLLMProvider
from app.providers.query_cache import CachedQueryEmbedder
from app.providers.ratelimit import SlidingWindowLimiter
from app.providers.rerank import GeminiListwiseReranker
from app.retrieval.catalog import load_catalog
from app.retrieval.reranking import CachedReranker
from app.retrieval.service import SearchService
from app.retrieval.understanding import QueryUnderstanding

logger = logging.getLogger(__name__)


def llm_limiter(settings: Settings, limiters: dict, model: str) -> SlidingWindowLimiter:
    """One limiter per Gemini model: extraction and reranking share a free-tier quota."""
    if model not in limiters:
        limiters[model] = SlidingWindowLimiter(max(1, int(settings.extraction_rpm_limit * 0.9)))
    return limiters[model]


def build_reranker(settings: Settings, pool, limiters: dict) -> CachedReranker | None:
    if not settings.rerank_enabled:
        return None
    client = GeminiJsonClient(
        settings.gemini_api_key.get_secret_value(),
        settings.rerank_model,
        timeout_s=settings.rerank_timeout_s,
        max_attempts=settings.rerank_max_attempts,
        base_delay_s=1.0,
        api="generate_content",
    )
    reranker = GeminiListwiseReranker(
        client,
        limiter=llm_limiter(settings, limiters, settings.rerank_model),
        thinking_level=settings.rerank_thinking_level,
    )
    return CachedReranker(pool, reranker)


async def build_understanding(
    settings: Settings, pool, limiters: dict
) -> QueryUnderstanding | None:
    """Query understanding needs the catalog (for the LLM's allowed values) and an API key."""
    if not settings.extraction_enabled or settings.llm_provider != "gemini":
        return None
    try:
        async with pool.acquire() as conn:
            catalog = await load_catalog(conn)
    except Exception as exc:  # noqa: BLE001 - search still works unfiltered
        logger.error("catalog load failed; query understanding off: %s", type(exc).__name__)
        return None
    client = GeminiJsonClient(
        settings.gemini_api_key.get_secret_value(),
        settings.extraction_model,
        timeout_s=settings.extraction_timeout_s,
        max_attempts=settings.extraction_max_attempts,  # then search runs unfiltered
        base_delay_s=1.0,
        api="generate_content",  # Interactions mislabels fields for this schema (decisions.md)
    )
    llm = GeminiLLMProvider(
        client,
        catalog,
        sorted(settings.fx_rates_to_qar),
        rpm_limit=settings.extraction_rpm_limit,
        thinking_level=settings.extraction_thinking_level,
        limiter=llm_limiter(settings, limiters, settings.extraction_model),
    )
    return QueryUnderstanding(pool, llm, catalog, settings.fx_rates_to_qar)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.db_pool = await create_pool(settings)
        embedder = understanding = reranker = None
        limiters: dict = {}
        if app.state.db_pool is not None and settings.gemini_api_key is not None:
            embedder = CachedQueryEmbedder(app.state.db_pool, get_embedding_provider(settings))
            understanding = await build_understanding(settings, app.state.db_pool, limiters)
            reranker = build_reranker(settings, app.state.db_pool, limiters)
        else:
            logger.warning("search disabled: needs DATABASE_URL and GEMINI_API_KEY")
        app.state.search_service = SearchService(
            app.state.db_pool,
            embedder,
            understanding,
            settings.fx_rates_to_qar,
            retrieval_mode=settings.retrieval_mode,
            hybrid_candidates=settings.hybrid_candidates,
            rrf_k=settings.rrf_k,
            hybrid_keywords=settings.hybrid_keywords,
            reranker=reranker,
            rerank_candidates=settings.rerank_candidates,
            rerank_top_n=settings.rerank_top_n,
        )
        try:
            yield
        finally:
            if app.state.db_pool is not None:
                await app.state.db_pool.close()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(search.router)
    return app


app = create_app()
