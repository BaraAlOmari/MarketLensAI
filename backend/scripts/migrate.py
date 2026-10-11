"""Apply backend/migrations/*.sql in filename order, once each, inside a transaction.

Usage (from backend/):
    .venv/Scripts/python scripts/migrate.py            # apply pending migrations
    .venv/Scripts/python scripts/migrate.py --status   # list applied / pending
"""

import argparse
import asyncio
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import BACKEND_DIR, get_settings  # noqa: E402

MIGRATIONS_DIR = BACKEND_DIR / "migrations"

CREATE_TRACKING_TABLE = """
create table if not exists schema_migrations (
    filename   text primary key,
    applied_at timestamptz not null default now()
);
alter table schema_migrations enable row level security;
"""


async def main(status_only: bool) -> int:
    settings = get_settings()
    if settings.database_url is None:
        print("FAIL: DATABASE_URL is not set")
        return 1
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    conn = await asyncpg.connect(
        settings.database_url.get_secret_value(), statement_cache_size=0, timeout=15
    )
    try:
        await conn.execute(CREATE_TRACKING_TABLE)
        applied = {
            r["filename"] for r in await conn.fetch("select filename from schema_migrations")
        }
        pending = [f for f in files if f.name not in applied]
        if status_only:
            for f in files:
                print(f"{'applied' if f.name in applied else 'PENDING'}  {f.name}")
            return 0
        if not pending:
            print("OK: no pending migrations")
            return 0
        for f in pending:
            async with conn.transaction():
                await conn.execute(f.read_text(encoding="utf-8"))
                await conn.execute("insert into schema_migrations (filename) values ($1)", f.name)
            print(f"OK: applied {f.name}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    sys.exit(asyncio.run(main(parser.parse_args().status)))
