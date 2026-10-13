# MarketLens: Decisions and Verified Facts

Every external fact the project relies on is recorded here with its source and the date it was checked. Re-verify before each stage that depends on it.

## Project decisions (user-confirmed)

| Date | Decision | Notes |
|---|---|---|
| 2026-10-10 | Project name: **MarketLens** | |
| 2026-10-10 | Prices and currency are written in **English** (Western digits, ISO currency code in `currency`). | |
| 2026-10-10 | Currency: **QAR is the primary currency, with multi-currency support** (for example USD alongside it). | Each listing stores `price` + `currency` as listed, plus a normalized `price_qar` computed from configured rates (`FX_RATES_TO_QAR`), so price filters work across currencies ("under $900" also matches listings priced in QAR). Rates are below under *FX pegs*. |
| 2026-10-10 | Synthetic text uses a **mix**: an offline phrase bank writes every listing's text immediately, and Gemini rewrites listings in batches as daily quota allows. | User choice. With 20 requests/day, Gemini alone would block Stage 2 for 2-3 days. Gemini stays the main writer, as the spec requires; template text is the fallback. Each record's `meta.writer` says which wrote it. |
| 2026-10-10 | Listing text is **bilingual: English and Arabic**. | Requires a multilingual embedding model (see below). Queries may arrive in either language. |
| 2026-10-10 | Supabase project is created by the user, following `docs/supabase-setup.md`. | Agent never handles the database password directly beyond the local `.env`. |
| 2026-10-10 | Reranker approach is deferred to Stage 6. | Spec section 11. |

## Engineering decisions

| Date | Decision | Reason |
|---|---|---|
| 2026-10-10 | Backend: Python 3.11, FastAPI, **asyncpg** (no ORM), pydantic-settings. | Spec: keep it simple, call SDKs directly. Raw SQL keeps pgvector/FTS/RRF queries visible. |
| 2026-10-10 | Gemini via the official **`google-genai`** SDK; no LangChain. | Spec rule 7. |
| 2026-10-10 | Local and deployed DB access uses the Supabase **Session pooler** (IPv4, port 5432). | The direct connection is IPv6-only on the free plan; many home networks and Azure egress are IPv4. |
| 2026-10-10 | asyncpg runs with `statement_cache_size=0`. | Required if we later switch to the transaction pooler (port 6543); harmless in session mode. |
| 2026-10-10 | `/health` always returns `status: "ok"` while the API is up. DB connectivity and pgvector version are reported as informational fields. | Liveness should not fail because the free Supabase project is paused. |
| 2026-10-10 | Frontend calls FastAPI from the **server** (route handler / server component) via `BACKEND_URL`. | No backend URL in the browser bundle; avoids CORS for server calls. CORS is still configured for the later streaming chat. |
| 2026-10-10 | Embedding dimension **1536** stored as pgvector `vector(1536)`. | Recommended Matryoshka size for `gemini-embedding-2`; under the 2,000-dim HNSW limit for `vector`. About 6 KB per row, roughly 12 MB for 2,000 listings plus index, well within 500 MB. |
| 2026-10-10 | Frontend: Next.js 16.4 App Router + TypeScript + Tailwind 4 (create-next-app defaults, `cacheComponents: true`). Prettier + ESLint. Backend: ruff (lint + format) + pytest. | Spec: linting, formatting, test runner. |

### Stage 1: schema and synthetic data

| Date | Decision | Reason |
|---|---|---|
| 2026-10-10 | **Python decides every structured fact** (category, brand/model, specs, condition, price, currency, location, language, near-duplicate links) from a seeded catalog (`data/generator/`). The writer (template or Gemini) only writes title + description, from those facts. | Ground truth for the Stage 3 eval comes from the generator, not from LLM output, so it is reliable. The same seed always gives the same facts. |
| 2026-10-10 | Gemini text is **validated** before use: right language, length limits, and **no written prices** (regex). A rejected item keeps its template text and is retried at most twice. | The structured price is the only source of truth for prices (spec section 4). |
| 2026-10-10 | Schema deviations from spec section 6: added `source` + `external_id` (unique together; makes loading idempotent), `price_qar`, `language`, `updated_at`. The btree price index is on **`price_qar`** rather than `price`. | Filters compare normalized prices. Upserts need a stable key. |
| 2026-10-10 | `id` is `bigint` identity (not uuid). | The LLM will cite listing IDs in Stage 7; short integers cost fewer tokens and are harder to garble. |
| 2026-10-10 | `fts` = `to_tsvector('english', search_text) \|\| to_tsvector('arabic', search_text)`. | Supabase Postgres 17 ships an `arabic` text-search config (checked with `pg_ts_config`). Listings mix both languages. Revisit in Stage 5. |
| 2026-10-10 | HNSW index on `embedding` is **deferred to Stage 2** (created after embeddings load). | Spec Stage 2: "build HNSW index after loading". |
| 2026-10-10 | Row Level Security enabled on `listings` and `schema_migrations`, with no policies. | The Supabase Data API (anon key) cannot read or write them. The backend's `postgres` role bypasses RLS. |
| 2026-10-10 | When `search_text` changes on upsert, `embedding` is reset to null. | Stage 2's resumable job re-embeds exactly the changed rows. |
| 2026-10-10 | `image_url` is null for synthetic listings. | No real photos. Random stock photos would mislead. Stage 9 renders a category placeholder. |
| 2026-10-10 | Catalog stops at models released in 2025. | 2026 launches were not verified. |
| 2026-10-10 | Gemini is called through the **Interactions API** (`client.aio.interactions.create`, `response_format` JSON schema, `thinking_level="low"`, `store=False`). | Current docs (structured-output, thinking pages, 2026-10-10) document this API. `gemini-3.8-flash` supports thinking levels low/medium/high (default medium). |
| 2026-10-10 | Generator pacing: 4 requests/min, 50 listings per request. Daily-quota 429s stop the run cleanly, and progress is cached in `data/cache/`. | Free tier for `gemini-3.8-flash` on this project: **5 RPM, 20 RPD** (user read from AI Studio, 2026-10-10). |

### Stage 2: embeddings and ingestion

| Date | Decision | Reason |
|---|---|---|
| 2026-10-11 | `EmbeddingProvider` interface (`embed_documents(texts, titles)`, `embed_query(text)`) with `GeminiEmbeddingProvider` as the first implementation, chosen by `EMBEDDING_PROVIDER`. | Spec section 5: swappable providers. |
| 2026-10-11 | Documents are embedded as `title: {title} \| text: {search_text}` and queries as `task: search result \| query: {text}`. | Google's recommended asymmetric-retrieval prefixes for `gemini-embedding-2` (no `task_type`). |
| 2026-10-11 | Each text is sent as its **own `Content`**. | A plain list of strings is folded by the SDK into one Content, which `gemini-embedding-2` turns into one aggregated embedding (checked in SDK source and docs; covered by a unit test). |
| 2026-10-11 | The job is **paced per text**, not per call: at most 90 texts and 27k estimated tokens per minute (90% of the limits), 45 texts per call. The daily budget is `RPD − 100 reserved for search queries − texts already sent today` (Pacific day, from `docs/logs/embedding-runs.jsonl`). | Measured: one call with 60 texts followed by a second with 60 hit the 100 RPM limit, so each text counts as a request. 2,205 listings therefore take 3 free-tier days. |
| 2026-10-11 | Tokens are **estimated** as characters ÷ 2.5. | The embed response has no usage metadata on the Gemini API. `count_tokens` on sampled listings gave about 3.0 characters per token (English 3.04, Arabic 2.81, mixed 2.97), so ÷ 2.5 overestimates slightly, which keeps pacing safe and costs conservative. |
| 2026-10-11 | Pending = `embedding is null or embedding_model <> EMBEDDING_MODEL`. Vectors are written per batch, and only if `md5(search_text)` still matches what was embedded. | Resumable and re-runnable (no-op when nothing is pending). Changing the model re-embeds everything; a concurrent reload never leaves a stale vector. |
| 2026-10-11 | The dimension lives in the column type (`vector(1536)`); the job refuses to run if `EMBEDDING_DIMENSION` differs. | Spec: model name and dimension stored in config and in the database. |
| 2026-10-11 | Gemini-written synthetic listings are embedded first. | Template-text rows will change after the next `rewrite`, so embedding them early would waste free-tier requests. |
| 2026-10-11 | HNSW index (`vector_cosine_ops`, default `m=16`, `ef_construction=64`) is created by the embed job once no rows are pending, followed by `ANALYZE`. Queries set `hnsw.iterative_scan = relaxed_order` so filtered searches still return enough rows. | Spec: build the index after loading. pgvector 0.8 iterative scans fix the "filter after ANN" recall drop. |
| 2026-10-12 | `with_retries` is the **only real retry layer**. It also retries google-genai's wrapped `APIConnectionError`/`APITimeoutError` (found by class name and `raise ... from` cause chain). The Interactions client is created with `HttpRetryOptions(attempts=1)` (the SDK minimum, 1 internal retry), and every attempt has a hard `asyncio.wait_for` deadline. | On 2026-10-12 a dropped connection crashed the rewrite (the wrapper class was not recognized), and a later batch hung for 15+ minutes because the SDK's default 3 internal retries × 240 s timeout ran inside each of our 6 attempts. The embeddings client (classic `models` API) has no SDK retries by default. |

### Stage 3: evaluation harness and baseline

| Date | Decision | Reason |
|---|---|---|
| 2026-10-13 | **Relevance comes from structured facts**, not text: each query has a `relevant` spec (category, models, conditions, price, sale/rent, location, attributes) evaluated against `data/listings.jsonl` by `eval/ground_truth.py`. | Spec: derive ground truth from the generator's metadata. The answers do not depend on how messy the text is, or on later Gemini rewrites (which change text only). |
| 2026-10-13 | Vague phrases have a written mapping (`eval/README.md`): "great condition" = like_new/good, "around X" = ±15%, "low mileage" = ≤ 50,000 km, monthly rent compares yearly ÷ 12, and so on. | Spec section 7 asks for documented mappings. Stage 4 must use the same ones, or the eval would measure disagreement about words rather than retrieval. |
| 2026-10-13 | 45 queries: 29 English, 12 Arabic, 4 mixed; all 6 categories; tags for price, condition, attribute, model, rent/sale, location and vague intent. Frozen before the first baseline run. `ph05` (no brand-new Pixel 10 Pro exists) and `fu02` (no good L-shaped sofa under 1,500 QAR) were changed *before* that run because their answer sets were empty. | An empty answer set cannot be scored. No query was changed after seeing any retrieval result. |
| 2026-10-13 | Recall@10 uses `min(relevant, 10)` as the denominator. A **"wrong in top 10"** share (results breaking at least one constraint) is reported alongside it. | Without the cap, a query with 40 right answers could never exceed 0.25. Without the wrong-share, queries with 2 right answers look perfect while 8 of 10 results are wrong. |
| 2026-10-13 | Eval results are keyed by `external_id`, not the database `id`. | Stable across reloads and databases. |
| 2026-10-13 | `eval/run.py` runs the FastAPI app **in-process** (httpx `ASGITransport` + the app lifespan) by default, or a live server with `--url`. | One command, same code path as production, no server to start. |
| 2026-10-13 | `POST /api/search` rejects unknown fields (`extra="forbid"`), including `filters`, until Stage 4. Errors: 422 bad input, 503 not configured, 429 embedding quota exhausted, 502 upstream failure (details logged, not returned). | A filter the API silently ignores would look like a working filter. |
| 2026-10-13 | Query embeddings are cached in `query_embedding_cache` (migration 002), keyed by sha256 of model, dimension and the exact model input. The query is only whitespace-normalized; case and wording are kept. | Every free-tier embedding counts against 1,000/day; the cache makes eval re-runs free and exactly reproducible. Lowercasing could change meaning ("US" vs "us"). |
| 2026-10-13 | Latency: one database round trip per search when `limit ≤ 20` (no `SET` needed, since pgvector's default `ef_search` 40 ≥ 2 × limit), and a cached search uses a single pooled connection for lookup + search. Cache misses release the connection during the embedding call. | Each round trip to Supabase from the dev machine is about 313 ms. Supavisor ignores `server_settings` sent at connect (tested: `hnsw.ef_search` stayed 40). Cached latency went from 1,507 ms to about 850 ms with identical scores. |
| 2026-10-13 | Fixed a Stage 1 template bug: mixed-language rental titles could end in "للبيع" ("for sale"). 9 listings were rewritten (facts unchanged), re-embedded, and covered by a regression test. The baseline was recorded after the fix. | Found while reading baseline failures. The rent list has the same length as the sale list, so every other listing's text is byte-identical. |

## Verified facts

### Google Gemini API (checked 2026-10-10)

| Fact | Value | Source |
|---|---|---|
| Stable Flash text models | `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite` | https://ai.google.dev/gemini-api/docs/models |
| Recommended for new projects | 3.5 Flash-Lite or 3.8 Flash | same |
| Gemini 2.5 Flash / Flash-Lite | Access limited to users who used them before. **Not used.** | same |
| Shut down | Gemini 2.0 Flash, 2.0 Flash-Lite, `gemini-3.1-flash-lite-preview`, Gemini 3 Pro Preview | same |
| **Chosen LLM default** | `LLM_MODEL=gemini-3.8-flash` (fallback option `gemini-3.5-flash-lite` if free-tier quota is too tight) | config only, no code change |
| Embedding model | `gemini-embedding-2`, **Stable** on its model page (last updated 2026-04-28). Text, image, video, audio, PDF input. | https://ai.google.dev/gemini-api/docs/models/gemini-embedding-2 |
| Inconsistency noted | The models overview lists `gemini-embedding-2-preview`; the dedicated model page and the embeddings guide say stable `gemini-embedding-2`. We follow the dedicated page. | both pages above |
| Embedding input limit | 8,192 tokens | same |
| Embedding output dimension | Default 3072, any value 128 to 3072 (Matryoshka); recommended 768 / 1536 / 3072. Set via `EmbedContentConfig(output_dimensionality=...)`. | https://ai.google.dev/gemini-api/docs/embeddings |
| Task types | `gemini-embedding-2` **does not accept `task_type`**. Use a text prefix instead, for example `task: search result \| query: {content}`. | same |
| Batching (checked 2026-10-11) | Multiple parts in one `contents` give **one aggregated embedding**; wrap each input in its own `Content` for separate vectors. A list of strings only gives separate vectors on `gemini-embedding-001`. No max item count is stated; the 8,192-token input limit applies. | https://ai.google.dev/gemini-api/docs/embeddings |
| Normalization (checked 2026-10-11) | `gemini-embedding-2` auto-normalizes truncated dimensions (measured norm 1.0 at 1536). | same |
| Pricing (checked 2026-10-11) | `gemini-embedding-2` text input: free tier free of charge; paid **$0.20 / 1M tokens**, Batch API $0.10 / 1M (Batch not available on free tier). | https://ai.google.dev/gemini-api/docs/pricing |
| Languages | "over 100 languages". **Arabic is not named explicitly.** Stage 2 adds a cross-lingual sanity check (Arabic query to English listing and the reverse) before building on it. | same |
| Free-tier rate limits | **Not published as numbers in the docs.** Per-model limits are shown in AI Studio (https://aistudio.google.com/rate-limit). Preview/experimental models are more restricted. RPD resets at midnight Pacific. | https://ai.google.dev/gemini-api/docs/rate-limits |
| This project's free tier | `gemini-3.8-flash`: **5 RPM, 20 RPD**. `gemini-embedding-2`: **100 RPM, 1,000 RPD, 30k input tokens/min** (both read by the user in AI Studio, 2026-10-10/11). The generator and ingestion job read limits from config and back off on HTTP 429. | AI Studio |

### FX pegs (checked 2026-10-10)

| Currency | Rate | Source |
|---|---|---|
| QAR | 3.64 per USD (fixed by Royal Decree No. 34 of 2001) | https://www.wise.com/il/currency-converter/currencies/qar-qatari-rial ; https://www.arabianbusiness.com/gcc/qatar-won-t-depeg-against-dollar-513908 |
| SAR | 3.75 per USD (since 1986) → 0.970667 QAR | https://gulfnews.com/business/markets/saudi-arabia-breaks-gulf-silence-on-peg-seen-here-to-stay-1.1573457 |
| AED | 3.6725 per USD → 0.991150 QAR | https://gulfnews.com/business/markets/dollar-peg-here-to-stay-uae-central-bank-official-says-1.1424317 |

These are secondary sources (no central-bank page came up). The pegs are long-standing, so fixed rates suit a synthetic demo. A floating currency (EUR, GBP) would need a dated rate added to `FX_RATES_TO_QAR`.

### Supabase (checked 2026-10-10)

| Fact | Value | Source |
|---|---|---|
| Free plan DB size | 500 MB per project | https://supabase.com/pricing |
| Free active projects | 2 | same |
| Inactivity pause | Free projects **pause after 1 week of inactivity** | same |
| Egress | 5 GB (+5 GB cached egress) | same |
| File storage | 1 GB | same |
| Compute | Shared CPU, 500 MB RAM | same |
| pgvector | Extension name `vector`; enable via Database > Extensions, or `create extension vector with schema extensions;` | https://supabase.com/docs/guides/database/extensions/pgvector |
| Connection modes | Direct `db.<ref>.supabase.co:5432` is **IPv6** on free plan. Shared pooler session mode `aws-<n>-<region>.pooler.supabase.com:5432`, user `postgres.<ref>`, IPv4, supports prepared statements. Transaction mode same host, port 6543, no prepared statements (asyncpg: `statement_cache_size=0`). | https://supabase.com/docs/guides/database/connecting-to-postgres |

### pgvector (checked 2026-10-10)

| Fact | Value | Source |
|---|---|---|
| HNSW max dimensions | `vector`: 2,000; `halfvec`: 4,000 | https://github.com/pgvector/pgvector |
| Latest release listed | v0.8.7 (Supabase's installed version is reported by `scripts/verify_db.py`) | same |

### Azure free tier (checked 2026-10-10, needed in Stage 11)

| Fact | Value | Source |
|---|---|---|
| Azure Container Apps (consumption) | First **180,000 vCPU-seconds, 360,000 GiB-seconds, 2 million requests per subscription per month** free; scale to zero supported, with no usage charge at zero replicas | https://azure.microsoft.com/en-us/pricing/details/container-apps/ |
| Azure Static Web Apps, Free plan | 100 GB bandwidth/subscription, 0.5 GB storage (0.25 GB/app), 2 custom domains/app, free SSL, managed Functions API. Site stops being served when over quota. Next.js hybrid support **not stated** on the pricing page; re-check in Stage 11. | https://azure.microsoft.com/en-us/pricing/details/app-service/static/ |
| Free account | "65+ always-free services"; separate 12-month free amounts for new customers only | https://azure.microsoft.com/en-us/pricing/free-services |
| Tentative plan | Backend container on Container Apps (scale to zero, so expect cold starts); frontend on Static Web Apps or a second Container App. Decide in Stage 11. | |

### Library versions pinned (checked 2026-10-10 on PyPI / npm)

fastapi 0.143.0, uvicorn 0.54.0, asyncpg 0.32.0, pydantic 2.14.0, pydantic-settings 2.15.0, google-genai 2.29.0, ruff 0.17.0, pytest 9.1.1, pytest-asyncio 1.4.0, httpx 0.28.1. next 16.4.0, react 19.3.0, prettier 3.9.10.

Known warning: Starlette now warns that using `httpx` with `TestClient` is deprecated in favor of `httpx2`. Tests pass; revisit when adding the `/api/search` integration tests.

`npm audit`: 0 vulnerabilities in production dependencies; 5 high-severity advisories in dev tooling only (create-next-app defaults), not shipped.
