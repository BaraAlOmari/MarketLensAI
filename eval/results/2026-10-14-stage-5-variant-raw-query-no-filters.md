# Eval run: Stage 5 variant: hybrid on the raw query, no LLM filters

2026-10-14 12:54 UTC · 45 queries · k = 10

| Recall@10 | MRR | Wrong in top 10 | Zero-hit | Pages < 10 results | Server latency mean / p95 | Est. cost/query |
|---|---|---|---|---|---|---|
| 0.689 | 0.907 | 43% | 1 | 0 (0 empty) | 851 / 976 ms | $0.000005 |

Cached query embeddings: 45/45. LLM extraction: used on 0, cached 0, failed 0.

## By language and tag

| group | n | Recall@10 | MRR |
|---|---|---|---|
| lang:ar | 12 | 0.552 | 0.875 |
| lang:en | 29 | 0.733 | 0.937 |
| lang:mixed | 4 | 0.783 | 0.792 |
| tag:attribute | 19 | 0.589 | 0.842 |
| tag:brand | 1 | 1.000 | 1.000 |
| tag:condition | 11 | 0.785 | 0.939 |
| tag:currency | 1 | 0.600 | 1.000 |
| tag:item | 6 | 0.852 | 0.889 |
| tag:location | 6 | 0.528 | 0.833 |
| tag:model | 18 | 0.771 | 0.954 |
| tag:price | 11 | 0.685 | 0.894 |
| tag:rent_sale | 10 | 0.549 | 0.900 |
| tag:vague | 9 | 0.593 | 0.778 |

## Why wrong results were wrong

193 of 450 top-10 results were not relevant. A result can break several constraints.

| broken constraint | wrong results | queries affected |
|---|---|---|
| model | 43 | 15 |
| price | 38 | 9 |
| attr:bedrooms | 26 | 7 |
| condition | 23 | 9 |
| location | 18 | 3 |
| attr:mileage_km | 12 | 2 |
| rent_sale | 7 | 3 |
| attr:private_pool | 7 | 2 |
| attr:storage_gb | 6 | 2 |
| attr:delivery_available | 6 | 1 |
| attr:furnished | 5 | 2 |
| attr:property_type | 5 | 1 |
| attr:item_type | 3 | 1 |
| attr:amenities | 3 | 1 |
| category | 2 | 2 |
| attr:year | 1 | 1 |
| attr:accident_free | 1 | 1 |
| attr:gcc_specs | 1 | 1 |
| brand | 1 | 1 |

## Per query

| id | lang | query | relevant | returned | hits@10 | Recall@10 | RR | main reasons | filters |
|---|---|---|---|---|---|---|---|---|---|
| ph01 | en | used iPhone 15 Pro Max | 16 | 10 | 8 | 0.80 | 1.00 | condition ×1, model ×1 | - |
| ph02 | en | iPhone 16 Pro under 3000 QAR | 13 | 10 | 8 | 0.80 | 1.00 | price ×2 | - |
| ph03 | en | Samsung Galaxy S24 Ultra 512GB | 6 | 10 | 5 | 0.83 | 1.00 | attr:storage_gb ×4, model ×1 | - |
| ph04 | en | cheap android phone under 1000 riyals | 25 | 10 | 3 | 0.30 | 0.50 | price ×7 | - |
| ph05 | en | brand new iPhone 15 Pro Max | 6 | 10 | 6 | 1.00 | 1.00 | condition ×4 | - |
| ph06 | en | foldable phone in like new condition | 21 | 10 | 6 | 0.60 | 1.00 | model ×3, condition ×1 | - |
| ph07 | en | iPhone 17 Pro around $1000 | 14 | 10 | 6 | 0.60 | 1.00 | price ×4, model ×2 | - |
| ph08 | ar | ايفون 16 بحالة ممتازة | 8 | 10 | 1 | 0.12 | 1.00 | model ×8, condition ×2 | - |
| ph09 | ar | سامسونج جالكسي S25 الترا جديد | 2 | 10 | 2 | 1.00 | 1.00 | condition ×8, model ×1 | - |
| ph10 | mixed | iPhone 14 نظيف أقل من 1500 ريال | 16 | 10 | 10 | 1.00 | 1.00 | - | - |
| lp01 | en | MacBook Air M4 with 16GB RAM | 33 | 10 | 10 | 1.00 | 1.00 | - | - |
| lp02 | en | gaming laptop under 4000 QAR | 82 | 10 | 10 | 1.00 | 1.00 | - | - |
| lp03 | en | lightweight laptop for a university student in good condition | 118 | 10 | 9 | 0.90 | 1.00 | model ×1 | - |
| lp04 | en | Dell XPS 13 like new | 10 | 10 | 10 | 1.00 | 1.00 | - | - |
| lp05 | en | MacBook Pro M4 Max 1TB | 10 | 10 | 8 | 0.80 | 1.00 | attr:storage_gb ×2 | - |
| lp06 | ar | لابتوب قيمنق مستعمل | 84 | 10 | 9 | 0.90 | 1.00 | condition ×1 | - |
| lp07 | ar | ماك بوك اير للبيع | 54 | 10 | 9 | 0.90 | 1.00 | model ×1 | - |
| car01 | en | Toyota Land Cruiser 2020 or newer | 9 | 10 | 7 | 0.78 | 1.00 | model ×2, attr:year ×1 | - |
| car02 | en | used Nissan Patrol under 150,000 QAR | 3 | 10 | 3 | 1.00 | 1.00 | price ×5, model ×2, condition ×2 | - |
| car03 | en | SUV with less than 50,000 km | 91 | 10 | 2 | 0.20 | 0.33 | attr:mileage_km ×8 | - |
| car04 | en | cheap sedan for daily commute under 40k | 54 | 10 | 6 | 0.60 | 1.00 | price ×4, model ×3 | - |
| car05 | en | Tesla Model Y | 11 | 10 | 10 | 1.00 | 1.00 | - | - |
| car06 | en | Range Rover Sport GCC specs accident free | 11 | 10 | 7 | 0.70 | 1.00 | attr:accident_free ×1, attr:gcc_specs ×1, model ×1 | - |
| car07 | ar | لاندكروزر برادو للبيع | 13 | 10 | 2 | 0.20 | 1.00 | model ×8 | - |
| car08 | ar | سيارة سيدان اقتصادية اقل من 30 الف | 47 | 10 | 5 | 0.50 | 1.00 | model ×4, price ×4, category ×1 | - |
| car09 | mixed | G63 AMG ممشى قليل | 6 | 10 | 2 | 0.33 | 0.17 | model ×5, attr:mileage_km ×4 | - |
| fu01 | en | IKEA bookshelf | 9 | 10 | 9 | 1.00 | 1.00 | brand ×1 | - |
| fu02 | en | L-shaped sofa in good condition under 2500 QAR | 7 | 10 | 5 | 0.71 | 0.33 | condition ×3, price ×2 | - |
| fu03 | en | majlis set | 18 | 10 | 10 | 1.00 | 1.00 | - | - |
| fu04 | mixed | office chair مع توصيل | 5 | 10 | 4 | 0.80 | 1.00 | attr:delivery_available ×6 | - |
| fu05 | ar | كنب ثلاثي مستعمل | 16 | 10 | 6 | 0.60 | 1.00 | attr:item_type ×3, condition ×1 | - |
| fu06 | ar | سرير كوين مع مرتبة | 25 | 10 | 10 | 1.00 | 1.00 | - | - |
| ap01 | en | 2 bedroom apartment for rent in Lusail | 2 | 10 | 1 | 0.50 | 1.00 | attr:bedrooms ×4, location ×4, rent_sale ×1 | - |
| ap02 | en | studio for rent under 5000 a month | 33 | 10 | 8 | 0.80 | 1.00 | price ×2 | - |
| ap03 | en | furnished 1BR in The Pearl | 6 | 10 | 3 | 0.50 | 1.00 | attr:bedrooms ×6, attr:furnished ×1 | - |
| ap04 | en | 3 bedroom apartment for sale in West Bay | 3 | 10 | 2 | 0.67 | 1.00 | attr:bedrooms ×6, rent_sale ×1, category ×1 | - |
| ap05 | en | penthouse with sea view | 4 | 10 | 3 | 0.75 | 1.00 | attr:property_type ×5, attr:amenities ×3 | - |
| ap06 | ar | شقة غرفتين للإيجار في لوسيل | 2 | 10 | 0 | 0.00 | 0.00 | location ×9, attr:bedrooms ×1 | - |
| ap07 | ar | استوديو مفروش للإيجار | 14 | 10 | 6 | 0.60 | 1.00 | attr:furnished ×4 | - |
| ap08 | mixed | 2BR شقة للبيع in The Pearl | 4 | 10 | 4 | 1.00 | 1.00 | attr:bedrooms ×6 | - |
| vi01 | en | 5 bedroom villa with private pool for rent | 20 | 10 | 7 | 0.70 | 1.00 | attr:private_pool ×2, attr:bedrooms ×1 | - |
| vi02 | en | compound villa for rent under 15000 a month | 9 | 10 | 2 | 0.22 | 1.00 | price ×8 | - |
| vi03 | en | townhouse for sale | 14 | 10 | 5 | 0.50 | 1.00 | rent_sale ×5 | - |
| vi04 | ar | فيلا للبيع في لوسيل | 23 | 10 | 5 | 0.50 | 1.00 | location ×5 | - |
| vi05 | ar | فيلا 6 غرف مع مسبح | 13 | 10 | 3 | 0.30 | 0.50 | attr:private_pool ×5, attr:bedrooms ×2 | - |
