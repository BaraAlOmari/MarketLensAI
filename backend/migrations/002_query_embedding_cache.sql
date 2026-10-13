-- 002: cache of query embeddings (Stage 3).
-- Every free-tier embedding request counts against 1,000/day, so repeated searches and eval
-- re-runs reuse stored vectors. Keyed by model + dimension + exact input text (after the
-- query prefix), so a model or dimension change never returns a stale vector.

create table query_embedding_cache (
    model         text not null,
    dimension     integer not null,
    input_sha256  text not null,               -- sha256 of the exact text sent to the model
    input_text    text not null,
    embedding     extensions.vector not null,  -- no typmod: dimension is a column above
    hits          integer not null default 0,
    created_at    timestamptz not null default now(),
    last_used_at  timestamptz not null default now(),
    primary key (model, dimension, input_sha256)
);

alter table query_embedding_cache enable row level security;
