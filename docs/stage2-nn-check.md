# Stage 2 Nearest-Neighbor Check

Generated 2026-10-13 13:14 UTC by `backend/scripts/nn_check.py`. Model `gemini-embedding-2`, 1536 dimensions, cosine distance.

## Acceptance

| Check | Result | Target |
|---|---|---|
| Rows embedded | 2205 / 2205 ✅ | all |
| HNSW index | present ✅ | present |
| Query plan | ->  Index Scan using listings_embedding_hnsw_idx on listings  (cost=497.37..3545.43 rows=2205 width=90) | index scan |
| same language (category precision@10) | 100% ✅ | >= 90% |
| cross lingual (category precision@10) | 100% ✅ | >= 80% |
| near duplicates (recall@5) | 100% ✅ | >= 80% |
| Overall | PASS ✅ |  |

Near-duplicate pairs checked: 105 (pairs where both rows are embedded).

**embedding_model per row**

| embedding_model | rows |
|---|---|
| gemini-embedding-2 | 2205 |

## Query probes

*Precision* = share of the 10 nearest listings in the expected category. *Other-lang* = how many of those 10 are in a different language than the query. *Cross-lingual* = precision when searching only listings in the other language.

| query | lang | expected | precision@10 | other-lang | cross-lingual |
|---|---|---|---|---|---|
| used iPhone 15 Pro in good condition | en | phones | 100% | 3/10 | 100% |
| MacBook Air for a university student | en | laptops | 100% | 1/10 | 100% |
| Toyota Land Cruiser 2020 low mileage | en | cars | 100% | 2/10 | 100% |
| comfortable sofa for the living room | en | furniture | 100% | 2/10 | 100% |
| 2 bedroom apartment for rent in Lusail | en | apartments | 100% | 0/10 | 100% |
| villa with a private pool in Al Waab | en | villas | 100% | 2/10 | 100% |
| ايفون 15 برو مستعمل بحالة ممتازة | ar | phones | 100% | 7/10 | 100% |
| لابتوب للدراسة الجامعية | ar | laptops | 100% | 1/10 | 100% |
| لاند كروزر موديل 2020 ممشى قليل | ar | cars | 100% | 5/10 | 100% |
| كنب مريح للصالة | ar | furniture | 100% | 1/10 | 100% |
| شقة غرفتين للإيجار في لوسيل | ar | apartments | 100% | 7/10 | 100% |
| فيلا مع مسبح خاص في الوعب | ar | villas | 100% | 7/10 | 100% |

## Top results

**used iPhone 15 Pro in good condition**

- 0.824 · phones · en · Apple iPhone 15 Pro 128GB
- 0.822 · phones · en · iPhone 15 Pro 256GB eSIM only Najma
- 0.816 · phones · ar · iPhone 15 Pro 512GB Black Dual SIM
- *other language only:*
  - 0.816 · phones · ar · iPhone 15 Pro 512GB Black Dual SIM
  - 0.798 · phones · mixed · iPhone 15 Pro Max - used للبيع
  - 0.797 · phones · mixed · iPhone 15 Pro 256GB Silver نظيف

**MacBook Air for a university student**

- 0.697 · laptops · en · MacBook Air 13 M4 24GB/256GB Al Wakrah 💻
- 0.695 · laptops · en · MacBook Air 13 M2 16GB Bin Mahmoud 💻
- 0.695 · laptops · en · Apple MacBook Air 13 M2 8GB 256GB 2022
- *other language only:*
  - 0.689 · laptops · mixed · Apple MacBook Air 13 M2 8GB/512GB like new
  - 0.684 · laptops · mixed · MacBook Air 15 M4 16GB 256GB umm salal
  - 0.683 · laptops · ar · MacBook Air 13 M2 512GB السد

**Toyota Land Cruiser 2020 low mileage**

- 0.792 · cars · en · 2020 TOYOTA LAND CRUISER PRADO TX ACCIDENT FREE!!
- 0.775 · cars · mixed · land cruiser معروض للبيع
- 0.770 · cars · en · Toyota Land Cruiser GR Sport V6 Al Rayyan
- *other language only:*
  - 0.775 · cars · mixed · land cruiser معروض للبيع
  - 0.757 · cars · ar · تويوتا لاند كروزر 2026 فضي وكالة أصفار 🚗
  - 0.748 · cars · ar · تويوتا لاند كروزر 2015 قير عادي اسود

**comfortable sofa for the living room**

- 0.697 · furniture · en · 3-seater sofa for sale
- 0.697 · furniture · en · Green 3-Seater Fabric Sofa in The Pearl
- 0.695 · furniture · en · 3-seater sofa for sale
- *other language only:*
  - 0.689 · furniture · ar · كنب ثلاثي شبه جديد
  - 0.684 · furniture · ar · كنب 3 ركاب قماش نظيف
  - 0.682 · furniture · ar · للبيع كنب ثلاثي

**2 bedroom apartment for rent in Lusail**

- 0.836 · apartments · en · 2br apt for rent lusail
- 0.826 · apartments · en · 2BR Penthouse in Lusail 20th Floor Pool
- 0.815 · apartments · en · FURNISHED 2BR APT LUSAIL HIGH FLOOR!!
- *other language only:*
  - 0.801 · apartments · mixed · 2br apt for sale lusail للبيع
  - 0.800 · apartments · mixed · 🔥 1BR apt for rent in Lusail
  - 0.794 · apartments · mixed · 2BR Semi Furnished Apartment Lusail للبيع

**villa with a private pool in Al Waab**

- 0.829 · villas · en · Spacious 3BR Villa with Private Pool in Al Waab
- 0.819 · villas · en · Spacious 5BR Villa for Rent in Al Waab 🏡✨
- 0.814 · villas · en · 3BR unfurnished villa in Al Waab w/ pool
- *other language only:*
  - 0.790 · villas · mixed · 5BR VILLA FOR RENT IN AL WAAB!!
  - 0.775 · villas · mixed · 7BR Villa for Rent in Al Waab حديقة
  - 0.768 · villas · mixed · Standalone 4BR villa in West Bay with private pool للإيجار

**ايفون 15 برو مستعمل بحالة ممتازة**

- 0.794 · phones · ar · iPhone 15 Pro 512GB Black Dual SIM
- 0.790 · phones · en · Apple iPhone 15 Pro 128GB
- 0.783 · phones · mixed · iPhone 15 Pro Max - used للبيع
- *other language only:*
  - 0.790 · phones · en · Apple iPhone 15 Pro 128GB
  - 0.783 · phones · mixed · iPhone 15 Pro Max - used للبيع
  - 0.781 · phones · mixed · Apple iPhone 15 Pro Max 512GB أزرق استخدام حشمة

**لابتوب للدراسة الجامعية**

- 0.680 · laptops · ar · لابتوب Dell XPS 13 نظيف جدا مع الشاحن 💻
- 0.680 · laptops · ar · لابتوب Dell XPS 14 جديد بالكرتون 💻✨
- 0.679 · laptops · mixed · Lenovo IdeaPad Slim 5 Ryzen 5 شبه جديد
- *other language only:*
  - 0.679 · laptops · mixed · Lenovo IdeaPad Slim 5 Ryzen 5 شبه جديد
  - 0.671 · laptops · en · Lenovo IdeaPad Slim 5 14" Ryzen 5 ✨
  - 0.670 · laptops · mixed · spectre x360 14 laptop للبيع

**لاند كروزر موديل 2020 ممشى قليل**

- 0.775 · cars · mixed · land cruiser معروض للبيع
- 0.761 · cars · en · 2020 TOYOTA LAND CRUISER PRADO TX ACCIDENT FREE!!
- 0.747 · cars · ar · تويوتا لاند كروزر 2015 قير عادي اسود
- *other language only:*
  - 0.775 · cars · mixed · land cruiser معروض للبيع
  - 0.761 · cars · en · 2020 TOYOTA LAND CRUISER PRADO TX ACCIDENT FREE!!
  - 0.741 · cars · en · 2024 TOYOTA LAND CRUISER VXR PEARL WHITE LIKE NEW!!

**كنب مريح للصالة**

- 0.705 · furniture · ar · كنب على شكل L Home Centre للبيع
- 0.705 · furniture · ar · كنب L-shaped مخمل جديد Home Centre
- 0.705 · furniture · ar · كنب ثلاثي شبه جديد
- *other language only:*
  - 0.684 · furniture · mixed · كنب زاوية جلد Home Centre L-shaped sofa
  - 0.676 · furniture · mixed · L-shaped sofa 6 seater Lusail للبيع
  - 0.654 · furniture · en · Ashley 3-seater sofa linen black gd cond

**شقة غرفتين للإيجار في لوسيل**

- 0.804 · apartments · mixed · 2br apt for sale lusail للبيع
- 0.803 · apartments · en · 2br apt for rent lusail
- 0.787 · apartments · ar · للبيع شقة 2 غرف نص فرش لوسيل
- *other language only:*
  - 0.804 · apartments · mixed · 2br apt for sale lusail للبيع
  - 0.803 · apartments · en · 2br apt for rent lusail
  - 0.786 · apartments · en · 2BR Penthouse in Lusail 20th Floor Pool

**فيلا مع مسبح خاص في الوعب**

- 0.797 · villas · en · Spacious 3BR Villa with Private Pool in Al Waab
- 0.789 · villas · en · Spacious 5BR Villa for Rent in Al Waab 🏡✨
- 0.788 · villas · en · 3BR unfurnished villa in Al Waab w/ pool
- *other language only:*
  - 0.797 · villas · en · Spacious 3BR Villa with Private Pool in Al Waab
  - 0.789 · villas · en · Spacious 5BR Villa for Rent in Al Waab 🏡✨
  - 0.788 · villas · en · 3BR unfurnished villa in Al Waab w/ pool
