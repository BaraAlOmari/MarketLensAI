-- 001: listings table (Stage 1).
-- The HNSW index on `embedding` is created in Stage 2, after embeddings are loaded.

create type listing_condition as enum ('new', 'like_new', 'good', 'fair', 'poor');
create type listing_type as enum ('sale', 'rent');
create type price_period as enum ('total', 'month', 'year');

create table listings (
    id            bigint generated always as identity primary key,
    source        text not null,               -- which ListingSource produced it
    external_id   text not null,               -- id within that source (stable across reloads)
    title         text not null,
    description   text not null,
    category      text not null,
    brand         text,
    model         text,
    price         numeric(14, 2) not null check (price >= 0),
    currency      char(3) not null,
    price_qar     numeric(14, 2) not null check (price_qar >= 0),  -- normalized for filtering
    condition     listing_condition,           -- null allowed for property listings
    listing_type  listing_type not null default 'sale',
    price_period  price_period not null default 'total',
    attributes    jsonb not null default '{}'::jsonb,
    location      text not null,
    seller_name   text not null,
    image_url     text,
    language      text not null check (language in ('en', 'ar', 'mixed')),
    search_text   text not null,               -- title + description + key attributes
    fts           tsvector generated always as (
                      to_tsvector('english'::regconfig, search_text)
                      || to_tsvector('arabic'::regconfig, search_text)
                  ) stored,
    embedding       extensions.vector(1536),   -- must equal EMBEDDING_DIMENSION
    embedding_model text,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now(),

    constraint listings_source_external_id_key unique (source, external_id),
    constraint listings_price_period_matches_type check (
        (listing_type = 'sale' and price_period = 'total')
        or (listing_type = 'rent' and price_period in ('month', 'year'))
    ),
    constraint listings_condition_required check (
        condition is not null or category in ('apartments', 'villas')
    )
);

create index listings_fts_idx          on listings using gin (fts);
create index listings_price_qar_idx    on listings (price_qar);
create index listings_category_idx     on listings (category);
create index listings_condition_idx    on listings (condition);
create index listings_listing_type_idx on listings (listing_type);

-- The backend connects as `postgres` (bypasses RLS). With RLS on and no policies,
-- Supabase's public Data API (anon key) can neither read nor write this table.
alter table listings enable row level security;
