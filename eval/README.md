# Eval

A fixed set of 45 search queries with known right answers, used to measure every retrieval change. The set was written in Stage 3, before any improvement, and is never tuned to pass. It was frozen on 2026-10-13. Two queries were adjusted before the first run because no listing matched them (`ph05`, `fu02`; see `docs/decisions.md`).

## Files

| File | What it is |
|---|---|
| `queries.json` | The queries. Each one has the text a user would type, its language, tags, and a `relevant` spec. |
| `ground_truth.py` | Turns each `relevant` spec into the set of matching listings, using the generator's facts. Writes `ground_truth.json`. |
| `ground_truth.json` | Generated: the relevant `external_id`s per query (for review and diffs). |
| `run.py` | Sends every query to `POST /api/search` and scores the top 10. |
| `results/` | One `.json` (all details) and `.md` (readable report) per run. |

## How relevance is decided

A listing is relevant when its **structured facts** satisfy every rule in the query's `relevant` spec. The facts come from `data/listings.jsonl`: category, brand, model, condition, sale or rent, location, price in QAR, and attributes. The listing text is never used. Because Python generated the facts and the text was written from them, the answers stay correct no matter how messy the text is.

| Rule | Meaning |
|---|---|
| `category` | Must match exactly. A wrong category is the only reason reported for such a result. |
| `brands`, `models` | The listing's brand or model is one of these. "Gaming laptop", "SUV" and "sedan" are written out as model lists. |
| `conditions` | The listing's condition is one of these. |
| `listing_type` | `sale` or `rent`. |
| `location` | Case-insensitive substring of the listing's location or its `neighborhood` attribute. |
| `price` | `min` / `max` / `around` in a currency, converted to QAR with the fixed pegs. `basis: "month"` compares yearly rents as yearly ÷ 12. |
| `attrs` | Attribute equals a value, or `{"min"}`, `{"max"}`, `{"in"}`, `{"contains"}`. A **missing** attribute never matches, since the generator dropped it and the buyer can't know. |

## Vague phrases

The same mapping must be used by query understanding (Stage 4), so the eval and the system agree on what words mean.

| Phrase | Mapping |
|---|---|
| "used", "مستعمل" | condition in like_new, good, fair, poor (anything but new) |
| "brand new", "جديد" | condition = new |
| "like new" | new or like_new |
| "great / excellent condition", "بحالة ممتازة" | like_new or good (spec section 7) |
| "good condition" | new, like_new or good (at least good) |
| "under X", "less than X", "أقل من X" | ≤ X |
| "around X" | X ± 15% |
| "X or newer" | year ≥ X |
| "low mileage", "ممشى قليل" | mileage ≤ 50,000 km |
| "riyals", "ريال", "QAR" | QAR. "$" is USD (3.64 QAR). |
| "a month" (rent) | compare monthly rent; yearly rents count as ÷ 12 |
| "cheap", "lightweight", "for a student" | no hard constraint unless a number is given; the model list carries the intent |

## Metrics

- **Recall@10** = relevant listings in the top 10 ÷ min(relevant count, 10). With 40 relevant listings, a perfect top 10 scores 1.0, not 0.25.
- **MRR** = mean over queries of 1 / rank of the first relevant listing in the top 10 (0 if none).
- **Wrong results**: every top-10 listing that is not relevant, labelled with the constraints it breaks. These counts are the failure categories in `docs/results.md`.
- **Latency**: server-side time from `debug.timings_ms`. **Cost**: the paid-tier price of embedding the query (free tier: $0).

## Commands (from `backend/`)

```powershell
.venv\Scripts\python ..\eval\ground_truth.py                 # rebuild ground_truth.json, check no query is empty
.venv\Scripts\python ..\eval\run.py                          # score the current system
.venv\Scripts\python ..\eval\run.py --label "Stage 4 filters" --record   # also append a row to docs/results.md
.venv\Scripts\python ..\eval\run.py --url http://localhost:8000          # against a running server
.venv\Scripts\python ..\eval\run.py --no-extract                         # the Stage 3 baseline again
.venv\Scripts\python ..\eval\run.py --concurrency 2 --extraction-timeout 60 --extraction-attempts 3
                                                                       # fill the LLM cache after a prompt change
```

LLM extractions are cached too (`query_extraction_cache`), keyed by a hash of the prompt, schema and catalog. A prompt or catalog change therefore re-extracts all 45 queries once (45 of the 500 free daily Flash-Lite requests). Changes to the Python mapping or guards reuse the cache and cost nothing.

The first run embeds each query once (45 free-tier requests). Query vectors are cached in Postgres (`query_embedding_cache`), so later runs reproduce the same numbers without using quota.
