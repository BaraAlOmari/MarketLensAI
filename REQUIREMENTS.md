# Marketplace Search Chatbot: Build Requirements

Hand-off spec for an AI coding agent. Read the whole document, then plan before writing any code.

## 1. Purpose

Build a chatbot that searches marketplace listings from natural language. Example: "Find me a used iPhone 17 in great condition for around $900" returns all matching listings as cards, with a short grounded summary.

This is a **learning and portfolio project, not production**. The goal is to learn and demonstrate RAG and AI engineering: query understanding, hybrid retrieval, reranking, grounded generation, and measured evaluation. It is not classic document-QA RAG. Hard constraints (price, condition, category) must be applied as structured filters, while fuzzy intent is handled by semantic search.

## 2. Fixed Technology Decisions

| Layer | Decision | Notes |
|---|---|---|
| Backend | Python + FastAPI | Async, typed with Pydantic |
| Frontend | Next.js (TypeScript) | Chat UI with streaming and listing cards |
| LLM | Google Gemini API, free tier | Must be upgradeable to a paid tier or another provider without code changes beyond config |
| Data | Synthetic listings | Must be swappable for real data later behind an ingestion interface |
| Database | Supabase PostgreSQL | Single database for relational data, full-text search, and vectors |
| Vector search | pgvector | Inside the same Postgres |
| Hosting | Azure free-tier services | Must be able to scale later (stateless backend, containerized, config via environment) |

**Do not assume current model names, free-tier limits, or Azure free offerings.** Verify each against the provider's current official documentation before relying on it, and record what you verified (source and date) in `docs/decisions.md`.

## 3. Goals and Non-Goals

**Goals**

- A working end-to-end chat search over a synthetic marketplace dataset.
- A measurable evaluation harness, with scores recorded after every retrieval improvement.
- Clean abstractions so the LLM, embedding model, reranker, and data source can each be swapped.
- A deployed demo and a documented journey (baseline to final results).

**Non-goals**

- No scraping of real marketplaces. Real-data support means an ingestion interface that a future, permitted source can implement.
- No user accounts, payments, seller flows, or listing creation.
- No production-grade scale, security hardening, or SLA.

## 4. Target Architecture

```
User message
  -> 1. Query understanding (LLM structured output) -> filters + keywords
  -> 2. Hybrid retrieval over listings
        - SQL filters (price, condition, category)   hard constraints
        - Vector search (pgvector)                    fuzzy intent
        - Full-text search (Postgres tsvector)        exact terms ("256GB")
        - Merge with Reciprocal Rank Fusion (RRF)
  -> 3. Rerank top ~50 to top ~10
  -> 4. Grounded answer generation
        - LLM returns a short summary + listing IDs only
        - Backend hydrates listing data from the DB
        - UI renders cards; the LLM never supplies prices or links
```

Key rule: **the LLM may only reference listing IDs that were retrieved.** Any ID not in the retrieved set is discarded before the response is sent.

## 5. Cross-Cutting Requirements

**Abstractions (interfaces with one implementation each to start)**

- `LLMProvider`: `extract_filters(query, state)`, `generate_answer(query, listings)`. First implementation: Gemini.
- `EmbeddingProvider`: `embed_documents(texts)`, `embed_query(text)`. Store the model name and vector dimension in config and in the database.
- `Reranker`: `rerank(query, candidates) -> ordered candidates`.
- `ListingSource`: yields normalized listings for ingestion. First implementation: synthetic generator.

**Configuration and secrets**

- All keys and settings come from environment variables. Provide `.env.example`. Never commit secrets.

**Rate limits and resilience**

- Gemini free tier is rate-limited. Add retry with exponential backoff, batching for embeddings, and a resumable ingestion job that skips already-embedded rows.
- Cache embeddings and, where sensible, repeated query extractions.

**Quality**

- Type hints and Pydantic models on all request, response, and filter schemas.
- Unit tests for filter application, RRF merging, and ID validation. Integration tests for `/api/search`.
- Structured logging with a request ID. Clear error responses.
- Free-tier hosting has limited memory: do not load large local ML models in the deployed backend. Prefer API-based embeddings.

**Repository layout**

```
/backend    FastAPI app, providers, retrieval, migrations, tests
/frontend   Next.js app
/data       generator scripts and generated datasets
/eval       query sets, ground truth, eval runner, results
/docs       architecture, decisions.md, results, write-ups
```

## 6. Data Model

`listings` table (adjust types as needed, document changes):

- `id` (uuid or bigint), `title`, `description`, `category`, `brand`, `model`
- `price` (numeric), `currency`, `condition` (enum: new, like_new, good, fair, poor)
- `attributes` (JSONB, e.g. storage, color, year, mileage), `location`, `seller_name`, `image_url`
- `search_text` (title + description + key attributes, used for embedding), `fts` (generated `tsvector`)
- `embedding` (pgvector column; dimension must match the chosen embedding model, so verify the model's output dimension before creating the column), `embedding_model`, `created_at`

**Indexes:** HNSW on `embedding`, GIN on `fts`, btree on `price`, `category`, `condition`.

**Real estate (apartments and properties):** use the same `listings` table. Add `listing_type` (sale or rent) and `price_period` (total, month, or year), with a btree index on `listing_type`. Put property-specific fields in `attributes`: `property_type`, `bedrooms`, `bathrooms`, `area_sqm`, `furnished`, `floor`, `neighborhood`. `condition` may be null for property listings.

Conversation state (Stage 8): a `sessions` table holding `session_id` and `filter_state` (JSONB) plus message history, or an equivalent. No authentication; sessions are anonymous.

## 7. API Contracts (initial)

- `GET /health`: liveness.
- `POST /api/search`: body `{query, filters?, limit?}`; returns `{extracted_filters, results[], debug?}`. Used by the eval harness and the UI.
- `POST /api/chat`: body `{session_id, message}`; streams server-sent events: `filters`, `listings`, `token`, `done`.
- `GET /api/listings/{id}`: single listing.

Filter schema (Pydantic): `category`, `brand`, `model`, `min_price`, `max_price`, `currency`, `conditions[]`, `keywords[]`, `location`, `attributes{}`. Map vague phrases to explicit ranges and document the mapping (for example, "around $900" becomes roughly +/- 10 to 15 percent; "great condition" becomes like_new and good).

For property queries (for example "2-bedroom apartment to rent under $2,000 a month"), the filter schema also needs `listing_type`, `property_type`, `bedrooms`, and `min_area` / `max_area`. Apply `price_period` so monthly rents are never compared with sale prices.

## 8. Stages

Work **one stage at a time**. At the end of each stage, stop, summarize what was built, show the acceptance results, and wait for approval before starting the next stage.

### Stage 0: Scaffolding and environment

- **Tasks:** create the repo layout; set up FastAPI and Next.js skeletons; create the Supabase project and enable pgvector; add `.env.example`, linting, formatting, and a basic test runner; add `GET /health` and a frontend page that calls it.
- **Deliverables:** running backend and frontend locally; database connection verified; `docs/decisions.md` started with verified facts (Gemini free-tier limits and model names, Supabase free-tier limits, Azure free options).
- **Acceptance:** `/health` returns OK from the frontend; the pgvector extension is confirmed active.

### Stage 1: Schema and synthetic data

- **Tasks:** write migrations for `listings` and indexes; build a generator script that uses Gemini to produce 2,000 or more listings across 5 to 6 categories (for example phones, laptops, cars, furniture, apartments, and properties for sale or rent) with deliberately messy descriptions (typos, abbreviations, "barely used", "comes w/ box", partial specs); include price spread, condition spread, a sale and rent mix for property listings, and near-duplicates; make the generator configurable by locale and currency.
- **Deliverables:** migration files; generator script; dataset file stored in `/data`; a loader that implements `ListingSource`.
- **Acceptance:** at least 2,000 listings loaded; spot-check report of 20 random rows; no null required fields.

### Stage 2: Embeddings and ingestion

- **Tasks:** implement `EmbeddingProvider` (Gemini); embed `search_text` in rate-limit-safe batches; resumable job; store model name and dimension; build HNSW index after loading.
- **Deliverables:** ingestion command; log of cost and time.
- **Acceptance:** all rows embedded; re-running the job is a no-op; a nearest-neighbor query returns sensible results.

### Stage 3: Evaluation harness and baseline

- **Tasks:** write 30 to 50 test queries with known-good listing IDs (derive from the generator's metadata so ground truth is reliable); implement `eval/run.py` computing Recall@10 and MRR; implement baseline `POST /api/search` using vector search only.
- **Deliverables:** query set; eval runner; `docs/results.md` with baseline scores and a list of failure categories (expected: price and condition ignored).
- **Acceptance:** one command reproduces the baseline numbers.

### Stage 4: Query understanding

- **Tasks:** implement `LLMProvider.extract_filters` using Gemini structured output or function calling against the filter schema; apply filters as SQL `WHERE` before or alongside vector search; handle extraction failure by falling back to unfiltered search; add unit tests with representative queries.
- **Deliverables:** extraction function; updated search; updated results.
- **Acceptance:** eval re-run recorded in `docs/results.md`; price-constraint failures eliminated in the test set.

### Stage 5: Hybrid retrieval

- **Tasks:** add Postgres full-text search; merge vector and FTS rankings with RRF; keep filters applied to both.
- **Deliverables:** hybrid retrieval module; tests for RRF.
- **Acceptance:** eval re-run recorded; short note on which queries improved or regressed.

### Stage 6: Reranking

- **Tasks:** implement `Reranker`. Choose an approach that fits free-tier hosting (for example, a Gemini-based listwise reranker or a hosted rerank API with a free tier; avoid heavy local models in the deployed backend). Rerank the top ~50 to the top ~10. Make it switchable by config so its effect can be measured on and off.
- **Deliverables:** reranker; comparison table (with and without).
- **Acceptance:** eval re-run recorded with latency and cost per query.

### Stage 7: Grounded answers and chat endpoint

- **Tasks:** implement `generate_answer`: the LLM returns a short summary and listing IDs from the provided set only; validate IDs; hydrate listing data from the DB; implement `POST /api/chat` with SSE streaming (`filters`, `listings`, `token`, `done`); handle "no good matches" honestly (suggest relaxing a constraint).
- **Deliverables:** chat endpoint; tests proving hallucinated IDs are dropped.
- **Acceptance:** no response ever contains a price or link that did not come from the database.

### Stage 8: Conversation state

- **Tasks:** keep a per-session filter state; merge follow-ups ("cheaper ones", "only unlocked", "under 800") into the previous state; allow "start over".
- **Deliverables:** state store; 10 or more multi-turn cases added to the eval set.
- **Acceptance:** multi-turn cases pass; results recorded.

### Stage 9: Frontend

- **Tasks:** build the Next.js chat UI: message list, streaming text, listing cards (image, title, price, condition, location), chips showing the filters the system extracted (editable if time allows), loading and error states, responsive layout.
- **Deliverables:** working UI against the local backend.
- **Acceptance:** the example query works end to end with streaming; cards render from backend data only.

### Stage 10: Observability and hardening

- **Tasks:** structured logs per pipeline step (extracted filters, candidate counts, rerank scores, latency); optional tracing with a free-tier tool such as Langfuse; basic per-IP rate limiting; input length limits; CORS configuration; CI that runs tests and lint.
- **Deliverables:** traces or logs sufficient to explain any failed search; CI workflow.
- **Acceptance:** for any query, the logs show why each result was returned.

### Stage 11: Deployment on Azure

- **Tasks:** verify current Azure free-tier options and limits, then choose hosting for the backend (containerized) and the frontend; configure environment secrets, health checks, and CORS; set up CI/CD (for example GitHub Actions); document cold-start behavior and any free-tier pause or sleep behavior (Supabase free projects may also pause when idle, so verify this).
- **Scalability notes to document:** backend is stateless; config via environment; database connection pooling; how to move to a paid tier or autoscaling; how to swap the Gemini free tier for a paid key or another provider.
- **Deliverables:** public demo URL; deployment doc.
- **Acceptance:** the example query works on the deployed app.

### Stage 12: Documentation and portfolio polish

- **Tasks:** README with architecture diagram, setup steps, and screenshots; `docs/results.md` with a table of every step (baseline to final) and metrics; a short "what failed and why" write-up; a limitations section (synthetic data, free-tier limits).
- **Acceptance:** a stranger can clone, configure, and run the project from the README alone.

## 9. Evaluation Requirements

- The eval set is created in Stage 3, **before** any retrieval improvements, and is never tuned to pass.
- Metrics: Recall@10 and MRR, plus mean latency and estimated cost per query.
- Every stage that changes retrieval re-runs the eval and appends a row to `docs/results.md`.
- Report failures honestly, including regressions.

## 10. Agent Working Rules

1. **Plan first.** Before coding, produce a short plan covering the stage order, risks, and any questions. Ask only what blocks progress.
2. **One stage at a time.** Stop after each stage, report, and wait for approval.
3. **Verify, do not assume.** Check current docs for model names, API parameters, free-tier limits, and library versions. Cite what you checked in `docs/decisions.md`.
4. **Surgical changes.** When revising existing code, make targeted edits rather than rewriting files.
5. **Direct communication.** Give concrete steps and results, not open-ended diagnostic questions.
6. **No scraping and no real marketplace data.** Use synthetic data only unless the user explicitly provides a permitted source.
7. **Keep it simple.** Call SDKs directly. Do not add frameworks such as LangChain unless asked.
8. **Record decisions.** Any deviation from this spec goes in `docs/decisions.md` with the reason.

## 11. Open Decisions (confirm with the user at the start)

- Project name (undecided).
- Dataset locale and currency (for example USD only, or a Qatar-flavored mix of Arabic and English with QAR prices). If multilingual, the embedding model must support it.
- Reranker approach for Stage 6.
- Whether to add an optional live-search tool for a real source later (not part of this scope).

## 12. Definition of Done

- Deployed demo answers the example query with correct, grounded listing cards.
- Eval results table shows measurable improvement from baseline to final.
- LLM, embeddings, reranker, and data source are each swappable through configuration and interfaces.
- README and results documentation are complete.
