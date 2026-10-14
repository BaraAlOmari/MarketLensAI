# Results

Every stage that changes retrieval re-runs the eval set (`eval/queries.json`, 45 queries, frozen 2026-10-13) and appends a row here. The set is never tuned to pass. How relevance is decided: [eval/README.md](../eval/README.md).

Reproduce any row (from `backend/`): `.venv\Scripts\python ..\eval\run.py`. Query embeddings are cached in Postgres, so re-runs give the same numbers without using quota.

## Runs

Recall@10 counts the share of relevant listings found in the top 10 (denominator capped at 10). *Wrong in top 10* is the share of all shown results that break at least one of the user's constraints; it keeps queries with only 2 or 3 right answers honest, since those can reach Recall@10 = 1.0 with most of the page wrong. MRR is the mean of 1 / rank of the first relevant listing (0 if none in the top 10). Latency is measured server-side; cost is the paid-tier price of embedding one query (the free tier is $0).

| Date | Run | Recall@10 | MRR | Wrong in top 10 | Zero-hit queries | Latency mean / p95 (ms) | Est. cost/query | Details |
|---|---|---|---|---|---|---|---|---|
| 2026-10-13 | Stage 3 baseline (vector only) | 0.853 | 0.919 | 31% | 0/45 | 891 / 921 | $0.0000046 | [report](../eval/results/2026-10-13-stage-3-baseline-vector-only.md) |
| 2026-10-14 | Stage 4 query understanding | 0.996 | 1.000 | 1% | 0/45 | 1168 / 1146 | $0.000402 | [report](../eval/results/2026-10-14-stage-4-query-understanding.md) |
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
