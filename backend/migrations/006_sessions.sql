-- 006: anonymous conversation state (Stage 8).
-- One row per chat session: the filters in force, the text used for retrieval, the last
-- results shown and a short message history. No authentication; the client makes up the id.

create table sessions (
    session_id       text primary key,
    filter_state     jsonb,                      -- SearchFilters, or null after "start over"
    search_query     text not null default '',   -- accumulated text used for retrieval
    last_result_ids  bigint[] not null default '{}',
    history          jsonb not null default '[]'::jsonb,  -- last messages, newest last
    turns            integer not null default 0,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

create index sessions_updated_at_idx on sessions (updated_at);

alter table sessions enable row level security;
