-- 003: cache of LLM query extractions (Stage 4).
-- The raw parse (the LLM's filled-in form) is stored, not the SQL filters, so changes to the
-- Python mapping never need a new LLM call. `prompt_hash` covers the system prompt, the JSON
-- schema and the catalog values in it: any change to those misses the cache automatically.

create table query_extraction_cache (
    model          text not null,
    prompt_hash    text not null,
    input_sha256   text not null,
    query_text     text not null,
    parse          jsonb not null,
    input_tokens   integer not null default 0,
    output_tokens  integer not null default 0,
    thought_tokens integer not null default 0,
    hits           integer not null default 0,
    created_at     timestamptz not null default now(),
    last_used_at   timestamptz not null default now(),
    primary key (model, prompt_hash, input_sha256)
);

alter table query_extraction_cache enable row level security;
