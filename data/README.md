# Synthetic data

`listings.jsonl` is the MarketLens dataset: 2,205 synthetic marketplace listings for Qatar, in English, Gulf Arabic and mixed text. Each line is one listing in the `NormalizedListing` shape (`backend/app/models/listing.py`), plus a `meta` block with the generator's ground truth (writer used, near-duplicate links, price outlier tags, styles). The loader strips `meta`; the Stage 3 eval reads it.

Nothing here is real. There was no scraping, and seller names are random.

## How it is made

1. **Facts** (`generator/facts.py`, `generator/catalog.py`, `generator/locales.py`). A seeded sampler picks every structured field: category, model, specs, condition, price (QAR first, then converted to the listing's currency), location, language, sale/rent, and near-duplicates. The same seed always gives the same facts.
2. **Text.** Each listing's title and description come from one of two writers:
   - `TemplateWriter`: an offline English and Gulf-Arabic phrase bank. Instant, free, deterministic.
   - `GeminiWriter`: rewrites listings in batches of 50 from the facts. Output is validated (language, length, no written prices) and cached in `cache/<locale>-s<seed>/`.

   Each listing uses its Gemini text when available, otherwise the template text.
3. **Messiness** comes from per-listing style hints: `terse`, `typos`, `abbrev`, `caps`, `detailed`, `emoji`, `partial` (some specs left out of the text), `casual`. On top of that, 15% of optional attributes are dropped, about 5% of listings are near-duplicates, and 3% are mispriced.

## Commands (run from `backend/`)

```powershell
.venv\Scripts\python ..\data\generate.py build            # rebuild listings.jsonl (no API calls)
.venv\Scripts\python ..\data\generate.py rewrite -n 19    # up to 19 Gemini batches, then rebuild
.venv\Scripts\python ..\data\generate.py status           # Gemini vs template text so far
.venv\Scripts\python scripts\load_listings.py             # upsert into Postgres (idempotent)
.venv\Scripts\python scripts\spot_check.py                # writes docs/stage1-spot-check.md
.venv\Scripts\python scripts\embed_listings.py            # embed new/changed rows (Stage 2)
```

Options: `--locale qa|us`, `--seed N`, `--currency-mix QAR:0.7,USD:0.3`, `--out path.jsonl`, plus `--model` and `--batch-size` for `rewrite`. Any non-default configuration writes to `listings-<locale>-s<seed>.jsonl`, leaving the main dataset alone.

With the free tier (20 requests/day), `rewrite -n 19` once a day converts about 950 listings per day.

Daily routine while text is still converting: `rewrite -n 19`, then `load_listings.py` (clears the embedding of every row whose text changed), then `embed_listings.py` (embeds up to 900 rows per day on the free tier).
