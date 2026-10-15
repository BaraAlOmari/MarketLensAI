-- 004: cache of reranker orderings (Stage 6).
-- Keyed by model, prompt hash, and a hash of the query + top_n + every candidate's id and text,
-- so a changed candidate list or a changed listing text never reuses a stale order.

create table rerank_cache (
    model          text not null,
    prompt_hash    text not null,
    input_sha256   text not null,
    query_text     text not null,
    candidate_ids  bigint[] not null,
    ranked_ids     bigint[] not null,   -- full order, best first
    ranked         integer not null,    -- how many came from the reranker
    invalid        integer not null default 0,
    input_tokens   integer not null default 0,
    output_tokens  integer not null default 0,
    thought_tokens integer not null default 0,
    hits           integer not null default 0,
    created_at     timestamptz not null default now(),
    last_used_at   timestamptz not null default now(),
    primary key (model, prompt_hash, input_sha256)
);

alter table rerank_cache enable row level security;
