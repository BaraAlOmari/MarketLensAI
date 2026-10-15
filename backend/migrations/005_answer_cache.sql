-- 005: cache of generated answers (Stage 7).
-- The raw model output (summary + recommended numbers) is stored, not the grounded text, so a
-- change to the grounding rules applies to cached answers too. The key covers the query and
-- every listing's id and text exactly as the model saw them.

create table answer_cache (
    model          text not null,
    prompt_hash    text not null,
    input_sha256   text not null,
    query_text     text not null,
    listing_ids    bigint[] not null,
    summary        text not null,
    recommended    integer[] not null,
    input_tokens   integer not null default 0,
    output_tokens  integer not null default 0,
    thought_tokens integer not null default 0,
    hits           integer not null default 0,
    created_at     timestamptz not null default now(),
    last_used_at   timestamptz not null default now(),
    primary key (model, prompt_hash, input_sha256)
);

alter table answer_cache enable row level security;
