# MarketLens: Decisions and Verified Facts

Every external fact the project relies on is recorded here with its source and the date it was checked. Re-verify before each stage that depends on it.

## Project decisions (user-confirmed)

| Date | Decision | Notes |
|---|---|---|
| 2026-10-10 | Project name: **MarketLens** | |
| 2026-10-10 | Prices and currency are written in **English** (Western digits, ISO currency code in `currency`). | |
| 2026-10-10 | Currency: **QAR is the primary currency, with multi-currency support** (for example USD alongside it). | Planned for Stage 1: store `price` + `currency` as listed, plus a normalized `price_qar` computed from configured exchange rates, so price filters work across currencies ("under $900" also matches listings priced in QAR). The rates' source and date go in this file. |
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
| Languages | "over 100 languages". **Arabic is not named explicitly.** Stage 2 adds a cross-lingual sanity check (Arabic query to English listing and the reverse) before building on it. | same |
| Free-tier rate limits | **Not published as numbers in the docs.** Per-model limits are shown in AI Studio (https://aistudio.google.com/rate-limit). Preview/experimental models are more restricted. RPD resets at midnight Pacific. | https://ai.google.dev/gemini-api/docs/rate-limits |
| Consequence | The user should read their actual RPM/TPM/RPD in AI Studio before Stage 1; the generator and ingestion job will read limits from config and back off on HTTP 429. | |

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
