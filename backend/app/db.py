"""asyncpg connection pool (no ORM). Optional: the API still starts without a database."""

import logging

import asyncpg

from app.config import Settings

logger = logging.getLogger(__name__)

# Applied to every pooled connection. Supavisor ignores settings sent at connect, and a
# role-level default would change behaviour for everything else using the database.
# strict_order: when a WHERE filter rejects HNSW candidates, keep scanning (pgvector 0.8)
# instead of returning fewer rows than asked for, and keep exact distance order.
SESSION_SETTINGS = "SET hnsw.iterative_scan = 'strict_order';"


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.execute(SESSION_SETTINGS)


async def _reset_connection(conn: asyncpg.Connection) -> None:
    # asyncpg's default reset (RESET ALL, ...) plus our settings, in the same round trip.
    await conn.execute(conn.get_reset_query() + "\n" + SESSION_SETTINGS)


async def create_pool(settings: Settings) -> asyncpg.Pool | None:
    if settings.database_url is None:
        logger.warning("DATABASE_URL not set; starting without a database pool")
        return None
    try:
        return await asyncpg.create_pool(
            dsn=settings.database_url.get_secret_value(),
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            timeout=settings.db_connect_timeout_s,
            # Required for Supabase's transaction pooler (port 6543); harmless elsewhere.
            statement_cache_size=0,
            init=_init_connection,
            reset=_reset_connection,
        )
    except (OSError, asyncpg.PostgresError) as exc:
        logger.error("database pool creation failed: %s", exc.__class__.__name__)
        return None


async def check_database(pool: asyncpg.Pool | None) -> dict:
    """Report connectivity and the installed pgvector version, without raising."""
    if pool is None:
        return {"configured": False, "ok": False, "pgvector": None}
    try:
        async with pool.acquire(timeout=5) as conn:
            version = await conn.fetchval(
                "select extversion from pg_extension where extname = 'vector'", timeout=5
            )
        return {"configured": True, "ok": True, "pgvector": version}
    except Exception as exc:  # noqa: BLE001 - health checks must never raise
        logger.error("database health check failed: %s", exc.__class__.__name__)
        return {"configured": True, "ok": False, "pgvector": None}
