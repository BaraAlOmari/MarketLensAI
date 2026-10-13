from types import SimpleNamespace

import pytest

from app.ingestion.embed_job import PendingRow, pack_batches, run_embedding_job, to_pgvector
from app.providers.embeddings import EmbeddingProvider, GeminiEmbeddingProvider
from app.providers.ratelimit import SlidingWindowLimiter
from app.providers.retry import QuotaExhaustedError


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


async def test_limiter_waits_for_the_window_to_free_up():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(100, clock=clock, sleep=clock.sleep)
    await limiter.acquire(60)
    await limiter.acquire(40)
    assert clock.slept == []
    await limiter.acquire(10)
    assert clock.now >= 60  # had to wait for the first acquisition to expire


async def test_limiter_rejects_requests_larger_than_capacity():
    with pytest.raises(ValueError):
        await SlidingWindowLimiter(10).acquire(11)


def test_pack_batches_respects_item_and_token_caps():
    rows = [PendingRow(i, "t", "x", "h") for i in range(7)]
    batches = pack_batches(rows, [10, 10, 10, 50, 10, 10, 10], max_items=3, max_tokens=60)
    assert batches == [[0, 1, 2], [3, 4], [5, 6]]
    assert sorted(i for b in batches for i in b) == list(range(7))


class FakeProvider(EmbeddingProvider):
    model = "fake-embed"
    dimension = 3

    def __init__(self, fail_after: int | None = None) -> None:
        self.calls: list[list[str]] = []
        self.fail_after = fail_after

    async def embed_documents(self, texts, titles=None):
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise QuotaExhaustedError("EmbedContentRequestsPerDayPerProjectPerModel")
        self.calls.append(list(texts))
        return [[1.0, 0.0, 0.0] for _ in texts]

    async def embed_query(self, text):
        return [1.0, 0.0, 0.0]


class MemoryStore:
    """Mimics PgEmbeddingStore: pending = no vector or a vector from another model."""

    def __init__(self, n: int) -> None:
        self.rows = {i: {"title": f"t{i}", "text": f"text {i}", "model": None} for i in range(n)}

    def _pending(self, model):
        return [i for i, r in self.rows.items() if r["model"] != model]

    async def count_pending(self, model):
        return len(self._pending(model))

    async def fetch_pending(self, model, limit, prefer=()):
        ids = sorted(self._pending(model), key=lambda i: (f"x{i}" not in prefer, i))[:limit]
        return [PendingRow(i, self.rows[i]["title"], self.rows[i]["text"], self.rows[i]["text"])
                for i in ids]  # fmt: skip

    async def save(self, model, rows, vectors):
        updated = 0
        for row, _ in zip(rows, vectors, strict=True):
            if self.rows[row.id]["text"] == row.text_hash:  # text unchanged since fetch
                self.rows[row.id]["model"] = model
                updated += 1
        return updated


def free_limiters():
    clock = FakeClock()
    return (
        SlidingWindowLimiter(90, clock=clock, sleep=clock.sleep),
        SlidingWindowLimiter(27_000, clock=clock, sleep=clock.sleep),
    )


JOB = {"batch_size": 50, "rpm_limit": 100, "tpm_limit": 30_000}


async def test_job_embeds_everything_and_rerun_is_a_no_op():
    store, provider = MemoryStore(120), FakeProvider()
    report = await run_embedding_job(
        store, provider, max_items=1000, limiters=free_limiters(), **JOB
    )
    assert (report.embedded, report.stopped) == (120, "done")
    assert [len(c) for c in provider.calls] == [50, 50, 20]

    again = await run_embedding_job(
        store, provider, max_items=1000, limiters=free_limiters(), **JOB
    )
    assert (again.embedded, again.api_calls, again.stopped) == (0, 0, "done")
    assert len(provider.calls) == 3


async def test_job_stops_at_budget_and_resumes_next_run():
    store, provider = MemoryStore(120), FakeProvider()
    first = await run_embedding_job(store, provider, max_items=70, limiters=free_limiters(), **JOB)
    assert (first.embedded, first.stopped) == (70, "budget")
    second = await run_embedding_job(store, provider, max_items=70, limiters=free_limiters(), **JOB)
    assert (second.pending_before, second.embedded, second.stopped) == (50, 50, "done")


async def test_daily_quota_keeps_finished_batches():
    store = MemoryStore(120)
    report = await run_embedding_job(
        store, FakeProvider(fail_after=1), max_items=1000, limiters=free_limiters(), **JOB
    )
    assert (report.embedded, report.stopped) == (50, "daily-quota")
    assert await store.count_pending("fake-embed") == 70


async def test_model_change_marks_rows_pending_and_preferred_rows_go_first():
    store = MemoryStore(10)
    await run_embedding_job(store, FakeProvider(), max_items=100, limiters=free_limiters(), **JOB)
    other = FakeProvider()
    other.model = "fake-embed-v2"
    assert await store.count_pending("fake-embed-v2") == 10
    await run_embedding_job(
        store, other, max_items=2, prefer={"x7", "x3"}, limiters=free_limiters(), **JOB
    )
    assert other.calls == [["text 3", "text 7"]]


async def test_rows_whose_text_changed_mid_run_are_not_overwritten():
    store = MemoryStore(3)
    real_save = store.save

    async def save_after_edit(model, rows, vectors):
        store.rows[1]["text"] = "edited by load_listings"
        return await real_save(model, rows, vectors)

    store.save = save_after_edit
    report = await run_embedding_job(
        store, FakeProvider(), max_items=10, limiters=free_limiters(), **JOB
    )
    assert (report.embedded, report.skipped_changed) == (2, 1)
    assert store.rows[1]["model"] is None


def test_pgvector_literal():
    assert to_pgvector([0.5, -1, 2e-05]) == "[0.5,-1.0,2e-05]"


async def test_gemini_wraps_each_text_in_its_own_content():
    """A plain list of strings would be folded into ONE aggregated embedding."""
    provider = GeminiEmbeddingProvider("test-key", "gemini-embedding-2", 4)
    seen = {}

    async def fake_embed_content(*, model, contents, config):
        seen.update(model=model, contents=contents, dim=config.output_dimensionality)
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.5] * 4) for _ in contents])

    provider._client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(embed_content=fake_embed_content))
    )
    vectors = await provider.embed_documents(["iphone 15", "شقة للإيجار"], ["A", None])
    assert len(vectors) == 2 and seen["dim"] == 4
    assert [c.parts[0].text for c in seen["contents"]] == [
        "title: A | text: iphone 15",
        "title: none | text: شقة للإيجار",
    ]
    await provider.embed_query("cheap phone")
    assert seen["contents"][0].parts[0].text == "task: search result | query: cheap phone"
