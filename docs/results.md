# Results

Every stage that changes retrieval re-runs the eval set (`eval/queries.json`, 45 queries, frozen 2026-10-13) and appends a row here. The set is never tuned to pass. How relevance is decided: [eval/README.md](../eval/README.md).

Reproduce any row (from `backend/`): `.venv\Scripts\python ..\eval\run.py`. Query embeddings are cached in Postgres, so re-runs give the same numbers without using quota.

## Runs

Recall@10 counts the share of relevant listings found in the top 10 (denominator capped at 10). *Wrong in top 10* is the share of all shown results that break at least one of the user's constraints; it keeps queries with only 2 or 3 right answers honest, since those can reach Recall@10 = 1.0 with most of the page wrong. MRR is the mean of 1 / rank of the first relevant listing (0 if none in the top 10). Latency is measured server-side; cost is the paid-tier price of embedding one query (the free tier is $0).

| Date | Run | Recall@10 | MRR | Wrong in top 10 | Zero-hit queries | Latency mean / p95 (ms) | Est. cost/query | Details |
|---|---|---|---|---|---|---|---|---|
| 2026-10-13 | Stage 3 baseline (vector only) | 0.853 | 0.919 | 31% | 0/45 | 891 / 921 | $0.0000046 | [report](../eval/results/2026-10-13-stage-3-baseline-vector-only.md) |
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
