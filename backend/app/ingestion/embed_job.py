"""Resumable embedding job: embeds rows whose embedding is missing or from another model.

Each batch is written as soon as it returns, so an interrupted run (Ctrl+C, daily quota)
loses at most one batch. Re-running with nothing pending makes no API calls.
"""

import asyncio
import logging
import time
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import asyncpg

from app.providers.embeddings import EmbeddingProvider, estimate_tokens
from app.providers.ratelimit import SlidingWindowLimiter
from app.providers.retry import QuotaExhaustedError

logger = logging.getLogger(__name__)

# Stay a little under the published per-minute limits.
HEADROOM = 0.9


@dataclass(frozen=True)
class PendingRow:
    id: int
    title: str
    search_text: str
    text_hash: str  # md5(search_text) when fetched; the write is skipped if it changed


class EmbeddingStore(Protocol):
    async def count_pending(self, model: str) -> int: ...

    async def fetch_pending(
        self, model: str, limit: int, prefer: Collection[str] = ()
    ) -> list[PendingRow]: ...

    async def save(
        self, model: str, rows: Sequence[PendingRow], vectors: Sequence[list[float]]
    ) -> int:
        """Write vectors; returns how many rows were updated."""
        ...


@dataclass
class JobReport:
    model: str
    dimension: int
    pending_before: int = 0
    embedded: int = 0
    skipped_changed: int = 0
    api_calls: int = 0
    estimated_tokens: int = 0
    stopped: str = "done"  # done | budget | daily-quota | interrupted
    duration_s: float = 0.0
    batch_times_s: list[float] = field(default_factory=list)

    def cost_usd(self, price_per_mtok: float) -> float:
        return self.estimated_tokens / 1_000_000 * price_per_mtok


def pack_batches(rows: Sequence[PendingRow], tokens: Sequence[int], max_items: int,
                 max_tokens: int) -> list[list[int]]:  # fmt: skip
    """Group row indexes so each batch stays within both the item and token caps."""
    batches: list[list[int]] = []
    current: list[int] = []
    used = 0
    for i, n in enumerate(tokens):
        if current and (len(current) >= max_items or used + n > max_tokens):
            batches.append(current)
            current, used = [], 0
        current.append(i)
        used += n
    if current:
        batches.append(current)
    return batches


async def run_embedding_job(
    store: EmbeddingStore,
    provider: EmbeddingProvider,
    *,
    max_items: int,
    batch_size: int,
    rpm_limit: int,
    tpm_limit: int,
    prefer: Collection[str] = (),
    limiters: tuple[SlidingWindowLimiter, SlidingWindowLimiter] | None = None,
    report: JobReport | None = None,
) -> JobReport:
    """Embed up to `max_items` pending rows. Every text counts as one request (RPM/RPD).

    Pass `report` to keep partial progress if the run is cancelled (Ctrl+C re-raises).
    """
    started = time.perf_counter()
    report = report or JobReport(model=provider.model, dimension=provider.dimension)
    report.pending_before = await store.count_pending(provider.model)
    if report.pending_before == 0 or max_items <= 0:
        report.stopped = "done" if report.pending_before == 0 else "budget"
        return report

    request_cap = int(rpm_limit * HEADROOM)
    token_cap = int(tpm_limit * HEADROOM)
    requests, token_window = limiters or (
        SlidingWindowLimiter(request_cap),
        SlidingWindowLimiter(token_cap),
    )
    rows = await store.fetch_pending(provider.model, max_items, prefer)
    inputs = [provider.document_input(r.search_text, r.title) for r in rows]
    tokens = [min(estimate_tokens(t), token_cap) for t in inputs]
    batches = pack_batches(rows, tokens, min(batch_size, request_cap), token_cap)

    try:
        for n, idx in enumerate(batches, 1):
            batch = [rows[i] for i in idx]
            batch_tokens = sum(tokens[i] for i in idx)
            await requests.acquire(len(batch))
            await token_window.acquire(batch_tokens)
            t0 = time.perf_counter()
            vectors = await provider.embed_documents(
                [r.search_text for r in batch], [r.title for r in batch]
            )
            report.api_calls += 1
            report.estimated_tokens += batch_tokens
            updated = await store.save(provider.model, batch, vectors)
            report.embedded += updated
            report.skipped_changed += len(batch) - updated
            report.batch_times_s.append(round(time.perf_counter() - t0, 2))
            logger.info(
                "batch %d/%d: %d rows, ~%d tokens, %.1fs",
                n, len(batches), len(batch), batch_tokens, report.batch_times_s[-1],
            )  # fmt: skip
        report.stopped = "done" if len(rows) >= report.pending_before else "budget"
    except QuotaExhaustedError:
        report.stopped = "daily-quota"
    except (KeyboardInterrupt, asyncio.CancelledError):
        report.stopped = "interrupted"
        raise
    finally:
        report.duration_s = round(time.perf_counter() - started, 1)
    return report


def to_pgvector(values: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


class PgEmbeddingStore:
    """`listings` table store. Pending = no embedding, or one made by a different model."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def column_dimension(self) -> int | None:
        typ = await self.conn.fetchval(
            """select format_type(atttypid, atttypmod) from pg_attribute
               where attrelid = 'listings'::regclass and attname = 'embedding'"""
        )
        if not typ or "(" not in typ:
            return None
        return int(typ.rsplit("(", 1)[1].rstrip(")"))

    async def count_pending(self, model: str) -> int:
        return await self.conn.fetchval(
            "select count(*) from listings where embedding is null "
            "or embedding_model is distinct from $1",
            model,
        )

    async def fetch_pending(
        self, model: str, limit: int, prefer: Collection[str] = ()
    ) -> list[PendingRow]:
        records = await self.conn.fetch(
            """select id, title, search_text, md5(search_text) as h from listings
               where embedding is null or embedding_model is distinct from $1
               order by (external_id = any($3::text[])) desc, id
               limit $2""",
            model,
            limit,
            list(prefer),
        )
        return [PendingRow(r["id"], r["title"], r["search_text"], r["h"]) for r in records]

    async def save(
        self, model: str, rows: Sequence[PendingRow], vectors: Sequence[list[float]]
    ) -> int:
        result = await self.conn.fetch(
            """update listings l set embedding = v.vec::extensions.vector,
                      embedding_model = $4, updated_at = now()
               from unnest($1::bigint[], $2::text[], $3::text[]) as v(id, h, vec)
               where l.id = v.id and md5(l.search_text) = v.h
               returning l.id""",
            [r.id for r in rows],
            [r.text_hash for r in rows],
            [to_pgvector(v) for v in vectors],
            model,
        )
        return len(result)

    async def ensure_hnsw_index(self) -> bool:
        """Create the cosine HNSW index if missing. Returns True if it was created now."""
        exists = await self.conn.fetchval("select to_regclass('listings_embedding_hnsw_idx')")
        if exists:
            return False
        await self.conn.execute(
            "create index if not exists listings_embedding_hnsw_idx on listings "
            "using hnsw (embedding extensions.vector_cosine_ops)"
        )
        return True
