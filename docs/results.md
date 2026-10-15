# Results

Every stage that changes retrieval re-runs the eval set (`eval/queries.json`, 45 queries, frozen 2026-10-13) and appends a row here. The set is never tuned to pass. How relevance is decided: [eval/README.md](../eval/README.md).

Reproduce any row (from `backend/`): `.venv\Scripts\python ..\eval\run.py`. Query embeddings are cached in Postgres, so re-runs give the same numbers without using quota.

## Runs

Recall@10 counts the share of relevant listings found in the top 10 (denominator capped at 10). *Wrong in top 10* is the share of all shown results that break at least one of the user's constraints; it keeps queries with only 2 or 3 right answers honest, since those can reach Recall@10 = 1.0 with most of the page wrong. MRR is the mean of 1 / rank of the first relevant listing (0 if none in the top 10). Latency is measured server-side; cost is the paid-tier price of embedding one query (the free tier is $0).

| Date | Run | Recall@10 | MRR | Wrong in top 10 | Zero-hit queries | Latency mean / p95 (ms) | Est. cost/query | Details |
|---|---|---|---|---|---|---|---|---|
| 2026-10-13 | Stage 3 baseline (vector only) | 0.853 | 0.919 | 31% | 0/45 | 891 / 921 | $0.0000046 | [report](../eval/results/2026-10-13-stage-3-baseline-vector-only.md) |
| 2026-10-14 | Stage 4 query understanding | 0.996 | 1.000 | 1% | 0/45 | 1168 / 1146 | $0.000402 | [report](../eval/results/2026-10-14-stage-4-query-understanding.md) |
| 2026-10-14 | Stage 5 hybrid (vector + full-text, RRF) | 0.996 | 1.000 | 1% | 0/45 | 1177 / 1159 | $0.000402 | [report](../eval/results/2026-10-14-stage-5-hybrid-vector-full-text-rrf.md) |
| 2026-10-15 | Stage 6 rerank (Gemini listwise) | 1.000 | 1.000 | 0% | 0/45 | 1517 / 1490 | $0.001301 | [report](../eval/results/2026-10-15-stage-6-rerank-gemini-listwise.md) |
<!-- runs:end -->

## Stage 3 baseline: vector search only

`POST /api/search` embeds the query and returns the 10 nearest listings by cosine distance. There are no filters and no keyword search. Full per-query report: [eval/results/2026-10-13-stage-3-baseline-vector-only.md](../eval/results/2026-10-13-stage-3-baseline-vector-only.md).

**Headline.** Vector search finds the right *kind* of item almost every time: every query had at least one correct listing in the top 10, and MRR is 0.919. But **31% of everything it shows breaks something the user asked for** (138 of 450 results). Recall@10 = 0.853 looks better than the experience is, because many queries have only a handful of right answers. For example, `ap06` ("2-bedroom apartment for rent in Lusail") finds both right listings, yet 8 of its 10 results are wrong.

### Failure categories

| Broken constraint | Wrong results | Queries | What happens |
|---|---|---|---|
| **price** | 30 | 7 | Numbers in the query are ignored. "cheap android phone under 1000 riyals" ranks a 1,200 QAR Galaxy A56 first and a 4,199 QAR Mate X6 9th. "compound villa for rent under 15000 a month" returns 7 villas over budget, including two at 216,000 and 226,000 QAR a year. |
| **condition** | 28 | 9 | "brand new iPhone 15 Pro Max" puts three *like new* units in the top 10. "L-shaped sofa in good condition" returns three *fair* ones. Condition words barely move the vector. |
| **bedrooms / property attributes** | 25 + 7 + 4 + 2 | 6 + 1 + 2 + 2 | "furnished 1BR in The Pearl" returns studios, 2BR and 3BR flats: the location matches, but the bedroom count is ignored. "penthouse with sea view" returns 7 penthouses without one. |
| **mileage** | 12 | 2 | "SUV with less than 50,000 km" ranks 50,800, 50,200 and 51,500 km cars first (close in meaning, wrong side of the line), and further down shows cars with 73,100 to 349,400 km. Numeric thresholds are invisible to embeddings. |
| **model** | 10 | 7 | Neighbouring models leak in: an iPhone 15 for "iPhone 15 Pro Max", a MacBook Pro 14 M4 Pro for "MacBook Pro M4 Max 1TB". |
| **rent vs sale** | 6 | 2 | The Arabic query "شقة غرفتين للإيجار في لوسيل" ("2-bedroom apartment *for rent* in Lusail") ranks a *for sale* flat first. Four of its 10 results are for sale. |
| **storage** | 5 | 2 | "Galaxy S24 Ultra 512GB" and "MacBook Pro M4 Max 1TB" also return 256GB and 2TB units: exact spec tokens need keyword search. |
| other (delivery, location, brand, GCC specs, ...) | 14 | 7 | Mostly single cases. |

As expected from the spec, **price and condition are the top two failures**. Both are hard constraints that Stage 4 will apply as SQL filters.

### What works

- **Cross-lingual search is not the weak spot.** Arabic queries score Recall@10 0.885 and MRR 0.958, slightly above English (0.831 / 0.908). Mixed-language queries score 0.908 / 0.875.
- **Model and item names are found reliably**: MRR is 1.000 on the 18 model queries.
- The weakest tags are exactly the hard constraints: `price` 0.773, `vague` 0.770 (these carry price or mileage limits), `attribute` 0.814.

### Latency and cost

- Server-side mean **891 ms** with every query embedding cached. Almost all of it is network: each database round trip from the dev machine (Qatar) to the Supabase region takes about 313 ms, and a cached search needs about 2.5 of them (cache lookup, search, connection reset).
- An uncached query adds the embedding call, about 1 to 3.6 seconds on the free tier.
- Deployed next to the database, both numbers drop to tens of milliseconds plus the embedding call.
- **Cost:** $0 on the free tier. At paid prices, embedding one query costs about $0.0000046 (≈23 tokens at $0.20 / 1M). There are no LLM calls yet.

## Stage 4: query understanding (LLM filters + SQL)

`gemini-3.5-flash-lite` fills a fixed filter form for each query. Python checks it (category scoping, grounding, two backstops), maps vague phrases with the rules in `eval/README.md`, and applies the result as SQL `WHERE` inside the vector search. Full report: [eval/results/2026-10-14-stage-4-query-understanding.md](../eval/results/2026-10-14-stage-4-query-understanding.md).

| | Baseline | Stage 4 |
|---|---|---|
| Recall@10 | 0.853 | **0.996** |
| MRR | 0.919 | **1.000** |
| Wrong in top 10 | 31% (138 of 450) | **1% (2 of 371)** |
| Price-constraint failures | 30 results in 7 queries | **0** ✅ (Stage 4 acceptance) |
| Condition failures | 28 | 0 |
| Bedroom / mileage / storage failures | 25 / 12 / 5 | 0 / 0 / 0 |

By group, Recall@10 is now 1.000 for Arabic, mixed, price, attribute and rent/sale queries, 0.993 for English, 0.982 for condition and 0.978 for vague queries. 17 queries return fewer than 10 listings. That is correct: with exact filters, some queries simply have fewer matches (for example, "2-bedroom apartment for rent in Lusail" has exactly 2).

**What is left.** The only wrong results (2) are in `lp03`, "lightweight laptop for a university student in good condition". "Lightweight" and "for a student" are intent, not filters, so vector search alone has to pick ultrabooks over gaming laptops. That is Stage 5/6 work (keyword search, reranking).

### How it got here (attempts that did not ship)

| Attempt | Recall@10 | MRR | Wrong | Empty pages | What went wrong |
|---|---|---|---|---|---|
| 1. Interactions API, no guards ([report](../eval/results/2026-10-13-stage-4-attempt-1-interactions-api.md)) | 0.734 | 0.811 | 27% | 7 | 22 of 45 extractions failed (Gemini overloaded: 503s, 21–233 s per call), and the rest invented fields: "studio for rent" got `storage_gb = 512`, "office chair with delivery" got `location = Lusail` and `year ≥ 2020`. A regression from the baseline. |
| 2. Interactions API + guards ([report](../eval/results/2026-10-13-stage-4-attempt-2-interactions-api-guards.md)) | 0.834 | 0.894 | 23% | 2 | Guards removed the invented fields, but the model still put values in the wrong field ("2 bedroom" → `storage_gb = 2`, "2020 or newer" → a price under 2020) and missed others. |
| 3. generateContent API + guards + backstops (shipped) | **0.996** | **1.000** | **1%** | 0 | |

The cause of attempts 1 and 2 was the **API, not the model**. The same model, prompt and schema gave mislabelled fields through the Interactions API and correct ones through `generateContent` (side-by-side test, 2026-10-14). Extraction now uses `generateContent`. The backstops (an explicit "under N" becomes a price, "2BR" or "غرفتين" becomes bedrooms, used only when the LLM left the field empty) fixed the last three queries: `ap02`, `ap06` and `vi02`.

### Does it generalise? (unscored sanity check)

I wrote both the eval queries and the extraction rules, and the backstops were added after seeing eval failures, so a perfect score could be overfitting. As a check, 10 **new** queries with different wording were run once and their filters read by hand. They are not part of the eval set. Examples: "need a used galaxy s25 ultra below 3500 riyal", "3BR villa to rent in Al Waab max 20k monthly", "شقة 3 غرف للبيع في الخليج الغربي", "Nissan Patrol 2022 or later with under 120,000 km".

- **9 of 10 fully correct**, including Arabic, "20k monthly", and "120,000 km" correctly read as mileage rather than price.
- **1 partly right**: "Lexus LX 600 accident free gcc" got accident-free but missed GCC specs.
- The price backstop fired on 3 of the 10. Missing an explicit price is a general weakness of the model, not something specific to these 45 queries.
- "penthouse for sale in The Pearl over 3 million" correctly returned **nothing**: the dataset has 4 penthouses for sale, none in The Pearl. Vector search alone would have shown 10 wrong listings. Stage 7 should say "no exact matches" here instead of an empty page.

### Caveats

- The eval and the system share one definition of vague phrases (by design), and the data's facts are clean and synthetic. A real marketplace, with missing or wrong attributes, would score lower. Treat these numbers as a comparison between stages, not as real-world accuracy.
- Exact filters trade recall for precision when an attribute is missing: a listing whose seller left out the mileage never matches "under 50,000 km".

### Latency, cost and reliability

- **Uncached query:** about 9.6 s server-side on 2026-10-14. Of that, extraction is a mean of 8.0 s (max 12.5 s), running concurrently with the embedding call. On 2026-10-13 the same calls took 21–233 s or failed with 503 "high demand". The default `EXTRACTION_TIMEOUT_S = 20` would then have fallen back to unfiltered search for most queries. That fallback rate is the main production risk of the free tier.
- **Cached query:** about 1.2 s mean (the recorded row), almost all of it database round trips from the dev machine.
- **Cost per uncached query at paid prices:** about **$0.0004**, from ≈ 883 input + 53 output tokens for the extraction plus ≈ 23 tokens for the embedding. On the free tier it is $0, with 500 extractions per day.
- 503 retries count against the daily limit: on 2026-10-13 the 500/day quota was used up mostly by failed calls.

## Stage 5: hybrid retrieval (vector + full-text, fused with RRF)

Each search now takes the top 50 by vector distance and the top 50 by Postgres full-text rank (`ts_rank` on the English + Arabic `fts` column, query words OR-ed), both under the same Stage 4 filters. The two lists are merged with Reciprocal Rank Fusion (k = 60): `score = Σ 1 / (60 + rank)`. One SQL round trip; latency is unchanged. Report: [eval/results/2026-10-14-stage-5-hybrid-vector-full-text-rrf.md](../eval/results/2026-10-14-stage-5-hybrid-vector-full-text-rrf.md).

| Variant | Recall@10 | MRR | Wrong in top 10 | Report |
|---|---|---|---|---|
| Vector + filters (Stage 4 behaviour) | 0.996 | 1.000 | 1% | [vector-only](../eval/results/2026-10-14-stage-5-variant-vector-only.md) |
| **Hybrid, full-text on the LLM's keywords (shipped)** | **0.996** | **1.000** | **1%** | [shipped](../eval/results/2026-10-14-stage-5-hybrid-vector-full-text-rrf.md) |
| Hybrid, full-text on the raw query | 0.987 | 1.000 | 2% | [raw-query](../eval/results/2026-10-14-stage-5-variant-raw-query.md) |
| Hybrid on the raw query, **no LLM filters** | 0.689 | 0.907 | 43% | [no-filters](../eval/results/2026-10-14-stage-5-variant-raw-query-no-filters.md) |
| Vector, no LLM filters (Stage 3 baseline) | 0.853 | 0.919 | 31% | [baseline](../eval/results/2026-10-13-stage-3-baseline-vector-only.md) |

### Which queries improved or regressed

**Shipped variant (LLM keywords): no query changed score.** The full-text side was active in only 9 of 45 queries, the ones where the LLM extracted exact tokens ("512GB", "1TB", "M4", "foldable", "مفروش"). It reordered the top 10 in 5 of them. Every reordered listing was already relevant, so Recall@10 and MRR cannot move: after Stage 4's filters the eval is close to saturated. What the reordering did, checked by hand:

- `ph03` "Samsung Galaxy S24 Ultra 512GB": the two listings that say "512GB" in both title and description moved to #1 and #2, above one that mentions it only once in its description. ✓
- `lp01` "MacBook Air M4 with 16GB RAM": a 32GB unit (relevant, since it has at least 16 GB) dropped out of the top 4 for listings that say "16GB". ✓
- `ap07` "استوديو مفروش للإيجار": a studio whose text doesn't say "مفروش" dropped out of the top 4. ✓
- `lp05` "MacBook Pro M4 Max 1TB": two exact matches swapped places (#3 ↔ #4); the one with "1TB" only in its description moved down. Neutral.
- `vi03` "townhouse for sale": an Arabic-only listing ("تاون هاوس للبيع") dropped out of the top 4, because it doesn't contain the English word "townhouse". ✗ This is the cost of keyword matching: it is bound to one language.

**Raw-query variant (not shipped): 2 regressions, 1 improvement.**

- `ph06` "foldable phone in like new condition": Recall@10 1.00 → 0.60. "like new" is already a filter, but matching it again promoted non-foldable like-new phones (Pixel 10, OnePlus 13). "foldable" itself barely appears in listings.
- `car08` "سيارة سيدان اقتصادية اقل من 30 الف": 1.00 → 0.90. "سيارة" ("car") matches every car listing, and an MG ZS SUV moved in.
- `lp03` "lightweight laptop for a university student": 0.80 → 0.90, the only gain.

### Why the raw query does worse, and what changed because of it

- **`ts_rank` has no IDF.** It does not know that "used", "for", "في" and "سيارة" appear in hundreds of listings while "Lusail" or "foldable" are rare, so common words dominate. Without filters this is plain to see: hybrid on the raw query scores 0.689, below vector-only 0.853.
- **It double-counts constraints the filters already enforce.** "Used", "under 1000" and "for sale" are hard filters from Stage 4; matching them again as keywords only adds noise.
- **Shipped design:** the full-text side searches the LLM's `keywords` (exact tokens such as model numbers and specs, the field the Stage 4 form already extracts). If there are no keywords, there is no full-text side and the order is pure vector. Keyword-score ties are broken by vector similarity rather than by id.
- **A hidden Stage 4 miss surfaced.** For "townhouse for sale" the LLM had not extracted "for sale". Vector ranking happened to put the sale listings first, so Stage 4 still scored 1.0; full-text on "townhouse" promoted the rentals. A third backstop now fills `listing_type` from an explicit "for sale" / "for rent" / "للبيع" / "للإيجار" when the LLM leaves it empty. It does not change the Stage 4 score, which is 0.996 with or without it.

### Takeaway

On this eval, hybrid retrieval adds no measurable recall: the hard constraints are already exact filters, and vector search ranks well inside them. It helps where an exact token matters but is not a filter (listings that state "512GB" or "16GB" outright now come first), at a small cost for listings written only in the other language. This dataset is synthetic with clean facts. On real listings, where specs are often missing from the structured fields and exist only in the text, the full-text side should matter more. Stage 6 (reranking) is the next place to look for gains in ordering.

## Stage 6: reranking (Gemini listwise)

After hybrid retrieval, the top candidates (up to 50, mean 18.6 after filters) go to `gemini-3.5-flash-lite` in one call. Each candidate is one numbered line (title, structured facts, price, start of the description). The model returns candidate numbers, best first, at most 10. Code keeps only valid, unique numbers; candidates it leaves out keep their retrieval order after the ranked ones. The reranker can only reorder; it cannot add a listing or undo a filter. Switchable with `RERANK_ENABLED` or `rerank: false` per request. Report: [eval/results/2026-10-15-stage-6-rerank-gemini-listwise.md](../eval/results/2026-10-15-stage-6-rerank-gemini-listwise.md).

### With and without

| | Rerank off (= Stage 5) | Rerank on |
|---|---|---|
| Recall@10 | 0.996 | **1.000** |
| MRR | 1.000 | 1.000 |
| Wrong in top 10 | 1% (2 results) | **0%** |
| Server latency, all cached (mean / p95) | 1,159 / 1,289 ms ([report](../eval/results/2026-10-15-stage-6-variant-rerank-off.md)) | 1,517 / 1,490 ms |
| Server latency, new query | ≈ 9.6 s (extraction + embedding, measured 2026-10-14) | ≈ 17 s estimated: the rerank call (**7.3 s mean**, measured 2026-10-15) runs after retrieval, so it adds to the 9.6 s instead of overlapping it. With extraction cached: 8.6 s mean, 17.0 s p95. |
| LLM calls per new query | 1 (extraction) | 2 (extraction + rerank), both from the same 500/day free quota |
| Input tokens for the rerank call | – | 2,626 mean, 8,257 max (50 candidates) |
| Est. cost per new query, paid tier | $0.0004 | **$0.0013** (about 3×) |
| Invalid candidate numbers returned | – | 0 of 45 calls |

### Which queries changed

- **Improved: `lp03`** "lightweight laptop for a university student in good condition", Recall@10 0.80 → 1.00. Before: IdeaPad Slim 5, Pavilion 15 (a heavy 15-inch laptop, not relevant), XPS 13 and others. After: Surface Laptop 7 (it was at vector rank 34) and Zenbook 14 OLEDs. This is exactly the case reranking is for: intent words with no filter behind them, which vector similarity alone ranked poorly.
- **Regressed by the metrics: none.** No query lost recall or MRR.
- **Reordered: 35 of 45 top 10s,** invisible to Recall/MRR because the reordered listings were already relevant. Checked by hand:
  - **"Cheap" is not honoured.** For `car04` "cheap sedan for daily commute under 40k", the cheapest car (6,550 QAR) went from #1 to #6, and #1 is now 33,500 QAR. `ph04` "cheap android phone under 1000 riyals" shows the same pattern. Sorting by price is something code should do deterministically (a soft "sort by price" hint from the extraction), not something to trust an LLM reranker with.
  - **Mileage helped slightly.** For `car03` "SUV with less than 50,000 km", lower-mileage cars moved up (24,200 / 41,100 / 24,300 km at the top instead of 24,200 / 47,500 / 49,400).
  - **Less variety.** On queries with models, the top 10 averaged 2.15 distinct models before and 1.92 after. For `lp03` it is now 8 Zenbook 14 OLEDs out of 10: all relevant, but a shopper would want more choice.
  - Fully constrained queries (`ap05` penthouse with sea view, `vi01` 5-bedroom villa with pool) kept the same top results.

### Takeaway

The reranker earns its place on vague-intent queries, the one kind the filters and keyword search cannot handle: it fixed the last failing query. Everywhere else it reshuffles results that were already correct, and it does not apply soft preferences such as "cheap". It roughly triples the cost of a new query and adds about 7 s on today's free tier. Cached queries pay only about 0.35 s more (one extra lookup). Kept **on by default**, because the pipeline in the spec includes it and caching hides the cost for repeated queries. `RERANK_ENABLED=false` is the switch if interactive latency matters more than vague-query quality. Natural follow-ups (not done): a deterministic "sort by price" hint for "cheap" and "cheapest", and a diversity cap such as at most 3 listings per model in the top 10.
