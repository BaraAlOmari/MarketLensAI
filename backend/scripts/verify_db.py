"""Verify the Supabase connection and that pgvector is active.

Usage (from backend/):
    .venv/Scripts/python scripts/verify_db.py            # check only
    .venv/Scripts/python scripts/verify_db.py --enable   # also CREATE EXTENSION if missing
"""

import argparse
import asyncio
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings  # noqa: E402


async def main(enable: bool) -> int:
    settings = get_settings()
    if settings.database_url is None:
        print("FAIL: DATABASE_URL is not set (see backend/.env.example)")
        return 1

    try:
        conn = await asyncpg.connect(
            settings.database_url.get_secret_value(),
            timeout=settings.db_connect_timeout_s,
            statement_cache_size=0,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: could not connect: {exc.__class__.__name__}: {exc}")
        return 1

    try:
        server = await conn.fetchval("show server_version")
        print(f"OK: connected (Postgres {server})")

        row = await conn.fetchrow(
            """select e.extversion, n.nspname
               from pg_extension e join pg_namespace n on n.oid = e.extnamespace
               where e.extname = 'vector'"""
        )
        if row is None and enable:
            await conn.execute("create extension if not exists vector with schema extensions")
            print("OK: created extension vector in schema extensions")
            row = await conn.fetchrow(
                """select e.extversion, n.nspname
                   from pg_extension e join pg_namespace n on n.oid = e.extnamespace
                   where e.extname = 'vector'"""
            )
        if row is None:
            print(
                "FAIL: pgvector is not enabled (enable it in the dashboard or re-run with --enable)"
            )
            return 1
        version, schema = row["extversion"], row["nspname"]
        print(f"OK: pgvector {version} installed in schema '{schema}'")

        dist = await conn.fetchval(
            f"select '[1,2,3]'::{schema}.vector OPERATOR({schema}.<->) '[1,2,4]'::{schema}.vector"
        )
        print(f"OK: vector distance query works (L2 distance = {dist})")

        dim = settings.embedding_dimension
        print(f"OK: configured EMBEDDING_DIMENSION={dim} (HNSW on vector supports <= 2000)")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--enable", action="store_true", help="create the vector extension if missing"
    )
    sys.exit(asyncio.run(main(parser.parse_args().enable)))
