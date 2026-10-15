"""Session state in Postgres (Stage 8). The backend keeps nothing in memory between requests,
so any instance can serve any message of a conversation."""

import json
from dataclasses import dataclass, field

import asyncpg

from app.models.filters import SearchFilters

HISTORY_LIMIT = 20  # messages kept per session (user + assistant)
SEARCH_QUERY_LIMIT = 500


@dataclass
class Session:
    session_id: str
    filters: SearchFilters | None = None
    search_query: str = ""
    last_result_ids: list[int] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    turns: int = 0

    def remember(self, role: str, text: str) -> None:
        self.history = [*self.history, {"role": role, "text": text}][-HISTORY_LIMIT:]


def combine_query(previous: str, message: str) -> str:
    """Text used for retrieval: the conversation so far, so a follow-up such as "cheaper ones"
    still embeds near the item. Keeps the start (the item) and the end (the latest ask)."""
    text = f"{previous} {message}".strip() if previous else message
    if len(text) <= SEARCH_QUERY_LIMIT:
        return text
    half = SEARCH_QUERY_LIMIT // 2
    return f"{text[:half]} {text[-half:]}"


class SessionStore:
    async def load(self, conn: asyncpg.Connection, session_id: str) -> Session:
        row = await conn.fetchrow(
            """select filter_state, search_query, last_result_ids, history, turns
               from sessions where session_id = $1""",
            session_id,
        )
        if row is None:
            return Session(session_id)
        state = row["filter_state"]
        if isinstance(state, str):
            state = json.loads(state)
        history = row["history"]
        if isinstance(history, str):
            history = json.loads(history)
        return Session(
            session_id=session_id,
            filters=SearchFilters.model_validate(state) if state else None,
            search_query=row["search_query"],
            last_result_ids=list(row["last_result_ids"]),
            history=list(history),
            turns=row["turns"],
        )

    async def save(self, conn: asyncpg.Connection, session: Session) -> None:
        state = session.filters.model_dump_json(exclude_defaults=True) if session.filters else None
        await conn.execute(
            """insert into sessions (session_id, filter_state, search_query, last_result_ids,
                                     history, turns)
               values ($1, $2::jsonb, $3, $4, $5::jsonb, $6)
               on conflict (session_id) do update set
                   filter_state = excluded.filter_state, search_query = excluded.search_query,
                   last_result_ids = excluded.last_result_ids, history = excluded.history,
                   turns = excluded.turns, updated_at = now()""",
            session.session_id,
            state,
            session.search_query,
            session.last_result_ids,
            json.dumps(session.history, ensure_ascii=False),
            session.turns,
        )
