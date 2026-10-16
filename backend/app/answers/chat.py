"""Chat (Stage 7): understand -> search -> grounded answer, as a stream of events.

Events, in order:
    filters   the constraints applied (sent as soon as query understanding is done)
    listings  cards built from database rows (never from LLM output)
    no_match  only when nothing matches: real counts for dropping each one filter
    token     the reply text, in small chunks
    nearby    only after no_match: the closest listings, each with the filters it misses
    done      cited listing ids, grounding report, timings
    error     only if search itself is unavailable (then `done` follows)

The reply is generated in full and grounded (citations checked, sentences with prices or
links removed) BEFORE any token is sent. A price that slipped into the model's text can
therefore never reach the client, at the cost of the text starting a moment later.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from decimal import Decimal

import asyncpg

from app.answers.grounding import Grounded, ground, template_answer
from app.answers.relax import (
    ARABIC,
    Relaxation,
    misses,
    nearby_filters,
    no_match_message,
    relax_counts,
)
from app.conversation.merge import (
    describe,
    drop_removed_keywords,
    median_price,
    merge,
    split_reset,
    wants_cheaper,
)
from app.conversation.store import Session, SessionStore, combine_query
from app.logging_setup import log_event
from app.models.filters import SearchFilters
from app.models.search import ListingResult, SearchRequest
from app.providers.llm import (
    Answer,
    AnswerError,
    LLMProvider,
    answer_candidates,
    reply_language,
)
from app.providers.query_cache import normalize_query
from app.providers.retry import QuotaExhaustedError
from app.retrieval.service import SearchService, SearchUnavailableError, to_result
from app.retrieval.vector import LISTING_COLUMNS

logger = logging.getLogger(__name__)

HYDRATE = f"select {LISTING_COLUMNS} from listings where id = any($1::bigint[])"
WORDS_PER_TOKEN_EVENT = 4
NEARBY_LIMIT = 6  # "closest matches" shown under a no-match reply
START_OVER_EN = "Okay, starting over. What are you looking for?"
START_OVER_AR = "تمام، نبدأ من جديد. عن ماذا تبحث؟"


@dataclass(frozen=True)
class Event:
    name: str
    data: dict


def dump(filters: SearchFilters | None) -> dict | None:
    """Filters as logged and sent: only what is set."""
    return filters.model_dump(mode="json", exclude_defaults=True) if filters else None


def sse(event: Event) -> str:
    return f"event: {event.name}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


def chunks(text: str, words: int = WORDS_PER_TOKEN_EVENT) -> list[str]:
    parts = text.split(" ")
    return [" ".join(parts[i : i + words]) + (" " if i + words < len(parts) else "")
            for i in range(0, len(parts), words)]  # fmt: skip


async def hydrate(
    conn: asyncpg.Connection, results: Sequence[ListingResult]
) -> list[ListingResult]:
    """Fresh rows for the result ids, in result order: cards come from the database only."""
    if not results:
        return []
    rows = {r["id"]: r for r in await conn.fetch(HYDRATE, [r.id for r in results])}
    return [to_result(rows[r.id], score=r.score, ranks=r.ranks) for r in results if r.id in rows]


class AnswerCache:
    def __init__(self, pool: asyncpg.Pool, llm: LLMProvider) -> None:
        self.pool = pool
        self.llm = llm

    def _key(
        self, query: str, listings: Sequence[ListingResult], language: str | None = None
    ) -> str:
        parts = [normalize_query(query), [x.id for x in listings], answer_candidates(listings)]
        # The language is part of the key only when it differs from the query's own, so
        # answers cached before Stage 8 stay valid.
        if language and language != reply_language(query):
            parts.append(language)
        blob = json.dumps(parts, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()

    async def lookup(
        self, conn, query: str, listings: Sequence[ListingResult], language: str | None = None
    ) -> Answer | None:
        row = await conn.fetchrow(
            """update answer_cache set hits = hits + 1, last_used_at = now()
               where model = $1 and prompt_hash = $2 and input_sha256 = $3
               returning summary, recommended, input_tokens, output_tokens, thought_tokens""",
            self.llm.model,
            self.llm.answer_prompt_hash,
            self._key(query, listings, language),
        )
        if row is None:
            return None
        return Answer(row["summary"], list(row["recommended"]), row["input_tokens"],
                      row["output_tokens"], row["thought_tokens"], 0.0)  # fmt: skip

    async def generate_and_store(
        self, query: str, listings: Sequence[ListingResult], language: str | None = None
    ) -> Answer:
        answer = await self.llm.generate_answer(normalize_query(query), listings, language)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """insert into answer_cache
                       (model, prompt_hash, input_sha256, query_text, listing_ids, summary,
                        recommended, input_tokens, output_tokens, thought_tokens)
                   values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                   on conflict (model, prompt_hash, input_sha256) do nothing""",
                self.llm.model,
                self.llm.answer_prompt_hash,
                self._key(query, listings, language),
                normalize_query(query),
                [x.id for x in listings],
                answer.summary,
                answer.recommended,
                answer.input_tokens,
                answer.output_tokens,
                answer.thought_tokens,
            )
        return answer


class ChatService:
    def __init__(
        self,
        search: SearchService,
        answers: AnswerCache | None,
        rates_to_qar: dict[str, Decimal],
        sessions: SessionStore | None = None,
    ) -> None:
        self.search = search
        self.answers = answers
        self.rates = rates_to_qar
        self.sessions = sessions

    async def _understand(self, query: str):
        """Cached or fresh extraction; None when query understanding is off."""
        understanding = self.search.understanding
        if understanding is None:
            return None
        async with self.search.pool.acquire() as conn:
            cached = await understanding.lookup(conn, query)
        return cached or await understanding.extract_and_store(query)

    async def _load(self, session_id: str | None) -> Session:
        if session_id is None or self.sessions is None:
            return Session("")  # stateless: every message is a new search (Stage 7)
        async with self.search.pool.acquire() as conn:
            return await self.sessions.load(conn, session_id)

    async def _save(self, session: Session) -> None:
        if session.session_id and self.sessions is not None:
            async with self.search.pool.acquire() as conn:
                await self.sessions.save(conn, session)

    async def _nearby(self, query: str, filters: SearchFilters) -> dict:
        """Closest listings when nothing matches exactly (Stage 9): same words, only the
        category and sale-or-rent kept, each card with the constraints it misses."""
        try:
            response = await self.search.search(
                SearchRequest(
                    query=query, filters=nearby_filters(filters), extract=False, limit=NEARBY_LIMIT
                )
            )
            async with self.search.pool.acquire() as conn:
                cards = await hydrate(conn, response.results)
                missed = await misses(conn, [c.id for c in cards], filters, self.rates)
        except Exception:  # noqa: BLE001 - the no-match reply stands on its own
            logger.exception("nearby search failed")
            return {"listings": [], "misses": {}}
        log_event(
            logger,
            "chat.nearby",
            filters=nearby_filters(filters).model_dump(mode="json", exclude_defaults=True),
            listings=[{"id": c.id, "misses": missed.get(c.id, [])} for c in cards],
        )
        return {
            "listings": [c.model_dump(mode="json") for c in cards],
            "misses": {str(c.id): missed.get(c.id, []) for c in cards},
        }

    async def events(
        self,
        message: str,
        session_id: str | None = None,
        filters_override: SearchFilters | None = None,
    ) -> AsyncIterator[Event]:
        """`filters_override`: the person edited the filter tokens in the UI (Stage 9). Those
        filters replace the conversation's, with no extraction; `message` only labels the
        turn in the history."""
        t0 = time.perf_counter()
        timings: dict[str, float] = {}

        def lap(name: str, since: float) -> float:
            now = time.perf_counter()
            timings[name] = round((now - since) * 1000, 1)
            return now

        if self.search.pool is None or self.search.embedder is None:
            yield Event("error", {"message": "search needs DATABASE_URL and GEMINI_API_KEY"})
            yield Event("done", {"cited_ids": [], "timings_ms": {}})
            return

        # 0. Conversation state.
        session = await self._load(session_id)
        if filters_override is not None:
            prev = session.filters
            understood = None
            text = message
            filters = drop_removed_keywords(prev, filters_override)
            notes = ["filters edited"]
            # Search with what is still asked for, not the old wording (see describe).
            search_query = describe(filters) or session.search_query or message
            language = reply_language(session.search_query or message)
            warm = asyncio.create_task(self.search.embedder.embed_query(search_query))
            t = lap("understand", t0)
        else:
            reset, text = split_reset(message)
            if reset:
                session.filters, session.search_query, session.last_result_ids = None, "", []
                if not text:
                    reply = START_OVER_AR if ARABIC.search(message) else START_OVER_EN
                    session.remember("user", message)
                    session.remember("assistant", reply)
                    session.turns += 1
                    await self._save(session)
                    yield Event("filters", {"filters": None, "previous": None, "reset": True,
                                            "notes": ["start over"], "error": None})  # fmt: skip
                    yield Event("listings", {"listings": []})
                    for piece in chunks(reply):
                        yield Event("token", {"text": piece})
                    lap("total", t0)
                    yield Event("done", {"cited_ids": [], "reset": True, "no_match": False,
                                         "timings_ms": timings})  # fmt: skip
                    return
            prev = session.filters if session.filters and not session.filters.is_empty() else None

            # 1. Understand the new message (context-free, cached by its text) while its
            #    embedding is computed in parallel; then merge it into the conversation.
            warm_text = combine_query(session.search_query, text) if prev else text
            warm = asyncio.create_task(self.search.embedder.embed_query(warm_text))
            try:
                understood = await self._understand(text)
            except Exception:  # noqa: BLE001 - search still runs, with the previous filters
                logger.exception("query understanding failed")
                understood = None
            understanding = self.search.understanding
            if understood is not None and understanding is not None and prev is not None:
                understood = understanding.with_context(understood, text, prev.category)
            delta = understood.filters if understood else None
            median = None
            if prev is not None and wants_cheaper(text):
                async with self.search.pool.acquire() as conn:
                    median = await median_price(conn, prev, self.rates)
            catalog = understanding.catalog if understanding is not None else None
            filters, notes = merge(prev, delta, catalog, median)
            new_topic = prev is None or any(n.startswith("new category") for n in notes)
            # Reply in the language of the latest message, not of the accumulated query text.
            language = reply_language(text)
            search_query = text if new_topic else combine_query(session.search_query, text)
            t = lap("understand", t0)
            # How the model read this message and how it changed the conversation (Stage 10);
            # the search below then reports source "request" because it gets these filters.
            log_event(
                logger,
                "chat.understand",
                message=text[:200],
                cached=understood.cached if understood else None,
                error=understood.error if understood else "understanding unavailable",
                guard_notes=list(understood.guard_notes) if understood else [],
                read_as=dump(delta),
                previous=dump(prev),
                merged=dump(filters),
                merge_notes=notes,
            )
        yield Event(
            "filters",
            {
                "filters": filters.model_dump(mode="json", exclude_defaults=True)
                if filters
                else None,
                "previous": prev.model_dump(mode="json", exclude_defaults=True) if prev else None,
                "notes": notes,
                "error": understood.error if understood else None,
            },
        )

        # 2. Retrieve (hybrid + rerank) with the merged filters.
        try:
            await warm
            response = await self.search.search(
                SearchRequest(query=search_query, filters=filters, extract=False, debug=True)
            )
        except (SearchUnavailableError, QuotaExhaustedError) as exc:
            yield Event("error", {"message": str(exc) or "search unavailable"})
            yield Event("done", {"cited_ids": [], "timings_ms": timings})
            return
        except Exception:  # noqa: BLE001 - a broken stream helps nobody; report and close
            logger.exception("chat search failed")
            yield Event("error", {"message": "search failed upstream"})
            yield Event("done", {"cited_ids": [], "timings_ms": timings})
            return
        t = lap("search", t)

        # 3. Cards from fresh database rows; on an empty result, real relaxation counts.
        relaxations: list[Relaxation] = []
        cached_answer: Answer | None = None
        async with self.search.pool.acquire() as conn:
            cards = await hydrate(conn, response.results)
            if not cards and filters is not None and not filters.is_empty():
                relaxations = await relax_counts(conn, filters, self.rates)
            elif cards and self.answers is not None:
                cached_answer = await self.answers.lookup(conn, search_query, cards, language)
        t = lap("hydrate", t)
        yield Event("listings", {"listings": [c.model_dump(mode="json") for c in cards]})
        no_match = not cards and filters is not None and not filters.is_empty()
        if no_match:
            yield Event("no_match", {"relaxations": [r.__dict__ for r in relaxations]})

        # 4. The reply: generated in full, grounded, then streamed.
        answer_info: dict = {"cached": cached_answer is not None, "error": None}
        if not cards:
            grounded = Grounded(no_match_message(text, relaxations), [], [], 0, False)
            answer_info["source"] = "no-match template"
        else:
            answer = cached_answer
            if answer is None and self.answers is not None:
                try:
                    answer = await self.answers.generate_and_store(search_query, cards, language)
                except (AnswerError, QuotaExhaustedError) as exc:
                    answer_info["error"] = str(exc)
            if answer is None:
                grounded = Grounded(template_answer(text, len(cards)), [], [], 0, True)
                answer_info["source"] = "template"
            else:
                grounded = ground(text, answer.summary, answer.recommended, [c.id for c in cards])
                answer_info.update(
                    source="llm",
                    model=self.answers.llm.model,
                    input_tokens=answer.input_tokens,
                    output_tokens=answer.output_tokens,
                    thought_tokens=answer.thought_tokens,
                    latency_ms=answer.latency_ms,
                )
        lap("answer", t)

        # 5. Remember the turn.
        session.filters = filters
        session.search_query = search_query
        session.last_result_ids = [c.id for c in cards]
        session.remember("user", message)
        session.remember("assistant", grounded.summary)
        session.turns += 1
        await self._save(session)

        for piece in chunks(grounded.summary):
            yield Event("token", {"text": piece})
        if no_match and filters is not None:
            t = time.perf_counter()
            yield Event("nearby", await self._nearby(search_query, filters))
            lap("nearby", t)
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        # The turn in one record (Stage 10): how the message changed the search, what was
        # shown, and how the reply was checked. The search's own steps are logged above it.
        log_event(
            logger,
            "chat.turn",
            session=session.session_id,
            turn=session.turns,
            edited=filters_override is not None,
            merge_notes=notes,
            search_query=search_query[:200],
            language=language,
            cards=[c.id for c in cards],
            no_match=no_match,
            relaxations={r.constraint: r.count for r in relaxations},
            answer_source=answer_info.get("source"),
            answer_cached=answer_info.get("cached"),
            answer_error=answer_info.get("error"),
            cited_ids=grounded.cited_ids,
            grounding={
                "dropped_ids": grounded.dropped_ids,
                "removed_sentences": grounded.removed_sentences,
                "used_template": grounded.used_template,
            },
            timings_ms=timings,
        )
        yield Event(
            "done",
            {
                "cited_ids": grounded.cited_ids,
                "grounding": {
                    "dropped_ids": grounded.dropped_ids,
                    "removed_sentences": grounded.removed_sentences,
                    "used_template": grounded.used_template,
                },
                "answer": answer_info,
                "no_match": not cards,
                "relaxations": [r.__dict__ for r in relaxations],
                "session": {"turn": session.turns, "search_query": search_query},
                "search": response.debug.model_dump(mode="json") if response.debug else None,
                "timings_ms": timings,
            },
        )
