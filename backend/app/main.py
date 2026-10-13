import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, search
from app.config import Settings, get_settings
from app.db import create_pool
from app.logging_setup import RequestIdMiddleware, configure_logging
from app.providers.embeddings import get_embedding_provider
from app.providers.query_cache import CachedQueryEmbedder
from app.retrieval.service import SearchService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.db_pool = await create_pool(settings)
        embedder = None
        if app.state.db_pool is not None and settings.gemini_api_key is not None:
            embedder = CachedQueryEmbedder(app.state.db_pool, get_embedding_provider(settings))
        else:
            logger.warning("search disabled: needs DATABASE_URL and GEMINI_API_KEY")
        app.state.search_service = SearchService(app.state.db_pool, embedder)
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
