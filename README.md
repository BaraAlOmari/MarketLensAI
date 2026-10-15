# MarketLens

Natural-language marketplace search: ask "Find me a used iPhone 17 in great condition for around $900" and get matching listings as cards, with a short grounded summary. A learning and portfolio project for RAG and AI engineering: query understanding, hybrid retrieval (pgvector + Postgres full-text + RRF), reranking, grounded generation, and measured evaluation.

The spec is in [REQUIREMENTS.md](REQUIREMENTS.md). Verified facts and decisions are in [docs/decisions.md](docs/decisions.md).

**Status:** Stage 8 (conversation state) complete: chat sessions remember their filters, so follow-ups like "under 2000 riyals", "what about Samsung?", "cheaper ones" or "start over" refine the search (12/12 multi-turn cases pass). Search eval: Recall@10 0.853 (baseline) → 1.000. See [docs/results.md](docs/results.md).

## Layout

```
backend/   FastAPI app (Python 3.11, asyncpg), scripts, tests
frontend/  Next.js 16 (App Router, TypeScript, Tailwind)
data/      generator scripts and generated datasets
eval/      query sets, ground truth, eval runner, results
docs/      decisions, setup guides, results
```

## Run locally (Windows / PowerShell)

Prerequisites: Python 3.11, Node 20+, and a Supabase project ([docs/supabase-setup.md](docs/supabase-setup.md)).

```powershell
# Backend
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
Copy-Item .env.example .env          # then fill in DATABASE_URL
.venv\Scripts\python scripts\verify_db.py
.venv\Scripts\python scripts\migrate.py         # create tables
.venv\Scripts\python scripts\load_listings.py   # load data/listings.jsonl
.venv\Scripts\python scripts\embed_listings.py  # embed listings (resumable; free tier ~900/day)
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev                          # http://localhost:3000
```

## Checks

| | Backend (`backend/`) | Frontend (`frontend/`) |
|---|---|---|
| Lint | `.venv\Scripts\ruff check . ..\data ..\eval` | `npm run lint` |
| Format | `.venv\Scripts\ruff format . ..\data ..\eval` | `npm run format` |
| Types | | `npm run typecheck` |
| Tests | `.venv\Scripts\python -m pytest` | |
| Eval | `.venv\Scripts\python ..\eval\run.py` | |
un.py` | |
| Build | | `npm run build` |
