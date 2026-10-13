# Eval run: Stage 3 baseline (vector only)

2026-10-13 13:44 UTC · 45 queries · k = 10

| Recall@10 | MRR | Zero-hit queries | Server latency mean / p95 | Est. cost/query |
|---|---|---|---|---|
| 0.853 | 0.919 | 0 | 891 / 921 ms | $0.0000046 |

Cached query embeddings: 45/45.

## By language and tag

| group | n | Recall@10 | MRR |
|---|---|---|---|
| lang:ar | 12 | 0.885 | 0.958 |
| lang:en | 29 | 0.831 | 0.908 |
| lang:mixed | 4 | 0.908 | 0.875 |
| tag:attribute | 19 | 0.814 | 0.882 |
| tag:brand | 1 | 1.000 | 1.000 |
| tag:condition | 11 | 0.854 | 0.932 |
| tag:currency | 1 | 0.600 | 1.000 |
| tag:item | 6 | 0.862 | 0.792 |
| tag:location | 6 | 0.944 | 0.917 |
| tag:model | 18 | 0.886 | 1.000 |
| tag:price | 11 | 0.773 | 0.826 |
| tag:rent_sale | 10 | 0.893 | 0.900 |
| tag:vague | 9 | 0.770 | 0.843 |

## Why wrong results were wrong

138 of 450 top-10 results were not relevant. A result can break several constraints.

| broken constraint | wrong results | queries affected |
|---|---|---|
| price | 30 | 7 |
| condition | 28 | 9 |
| attr:bedrooms | 25 | 6 |
| attr:mileage_km | 12 | 2 |
| model | 10 | 7 |
| attr:amenities | 7 | 1 |
| attr:delivery_available | 6 | 1 |
| rent_sale | 6 | 2 |
| attr:storage_gb | 5 | 2 |
| attr:furnished | 4 | 2 |
| location | 3 | 2 |
| attr:private_pool | 2 | 2 |
| attr:accident_free | 1 | 1 |
| attr:gcc_specs | 1 | 1 |
| brand | 1 | 1 |
| attr:item_type | 1 | 1 |
| category | 1 | 1 |

## Per query

| id | lang | query | relevant | hits@10 | Recall@10 | RR | main reasons |
|---|---|---|---|---|---|---|---|
| ph01 | en | used iPhone 15 Pro Max | 16 | 10 | 1.00 | 1.00 | - |
| ph02 | en | iPhone 16 Pro under 3000 QAR | 13 | 8 | 0.80 | 1.00 | price ×2 |
| ph03 | en | Samsung Galaxy S24 Ultra 512GB | 6 | 6 | 1.00 | 1.00 | attr:storage_gb ×3, model ×1 |
| ph04 | en | cheap android phone under 1000 riyals | 25 | 4 | 0.40 | 0.33 | price ×6 |
| ph05 | en | brand new iPhone 15 Pro Max | 6 | 6 | 1.00 | 1.00 | condition ×3, model ×1 |
| ph06 | en | foldable phone in like new condition | 21 | 8 | 0.80 | 1.00 | condition ×2 |
| ph07 | en | iPhone 17 Pro around $1000 | 14 | 6 | 0.60 | 1.00 | model ×3, price ×3 |
| ph08 | ar | ايفون 16 بحالة ممتازة | 8 | 5 | 0.62 | 1.00 | condition ×5 |
| ph09 | ar | سامسونج جالكسي S25 الترا جديد | 2 | 2 | 1.00 | 1.00 | condition ×8 |
| ph10 | mixed | iPhone 14 نظيف أقل من 1500 ريال | 16 | 10 | 1.00 | 1.00 | - |
| lp01 | en | MacBook Air M4 with 16GB RAM | 33 | 10 | 1.00 | 1.00 | - |
| lp02 | en | gaming laptop under 4000 QAR | 82 | 10 | 1.00 | 1.00 | - |
| lp03 | en | lightweight laptop for a university student in good condition | 118 | 8 | 0.80 | 1.00 | model ×1, condition ×1 |
| lp04 | en | Dell XPS 13 like new | 10 | 8 | 0.80 | 1.00 | condition ×2 |
| lp05 | en | MacBook Pro M4 Max 1TB | 10 | 7 | 0.70 | 1.00 | attr:storage_gb ×2, model ×1 |
| lp06 | ar | لابتوب قيمنق مستعمل | 84 | 10 | 1.00 | 1.00 | - |
| lp07 | ar | ماك بوك اير للبيع | 54 | 10 | 1.00 | 1.00 | - |
| car01 | en | Toyota Land Cruiser 2020 or newer | 9 | 8 | 0.89 | 1.00 | model ×2 |
| car02 | en | used Nissan Patrol under 150,000 QAR | 3 | 3 | 1.00 | 1.00 | price ×7, condition ×3 |
| car03 | en | SUV with less than 50,000 km | 91 | 3 | 0.30 | 0.25 | attr:mileage_km ×7 |
| car04 | en | cheap sedan for daily commute under 40k | 54 | 10 | 1.00 | 1.00 | - |
| car05 | en | Tesla Model Y | 11 | 10 | 1.00 | 1.00 | - |
| car06 | en | Range Rover Sport GCC specs accident free | 11 | 8 | 0.80 | 1.00 | attr:accident_free ×1, attr:gcc_specs ×1 |
| car07 | ar | لاندكروزر برادو للبيع | 13 | 9 | 0.90 | 1.00 | model ×1 |
| car08 | ar | سيارة سيدان اقتصادية اقل من 30 الف | 47 | 8 | 0.80 | 1.00 | price ×2 |
| car09 | mixed | G63 AMG ممشى قليل | 6 | 5 | 0.83 | 1.00 | attr:mileage_km ×5 |
| fu01 | en | IKEA bookshelf | 9 | 9 | 1.00 | 1.00 | brand ×1 |
| fu02 | en | L-shaped sofa in good condition under 2500 QAR | 7 | 4 | 0.57 | 0.25 | condition ×3, price ×3 |
| fu03 | en | majlis set | 18 | 10 | 1.00 | 1.00 | - |
| fu04 | mixed | office chair مع توصيل | 5 | 4 | 0.80 | 0.50 | attr:delivery_available ×6 |
| fu05 | ar | كنب ثلاثي مستعمل | 16 | 8 | 0.80 | 1.00 | condition ×1, attr:item_type ×1 |
| fu06 | ar | سرير كوين مع مرتبة | 25 | 10 | 1.00 | 1.00 | - |
| ap01 | en | 2 bedroom apartment for rent in Lusail | 2 | 2 | 1.00 | 1.00 | attr:bedrooms ×6, rent_sale ×2 |
| ap02 | en | studio for rent under 5000 a month | 33 | 10 | 1.00 | 1.00 | - |
| ap03 | en | furnished 1BR in The Pearl | 6 | 4 | 0.67 | 1.00 | attr:bedrooms ×5, attr:furnished ×1 |
| ap04 | en | 3 bedroom apartment for sale in West Bay | 3 | 3 | 1.00 | 1.00 | attr:bedrooms ×6, category ×1 |
| ap05 | en | penthouse with sea view | 4 | 3 | 0.75 | 1.00 | attr:amenities ×7 |
| ap06 | ar | شقة غرفتين للإيجار في لوسيل | 2 | 2 | 1.00 | 0.50 | rent_sale ×4, attr:bedrooms ×2, location ×2 |
| ap07 | ar | استوديو مفروش للإيجار | 14 | 7 | 0.70 | 1.00 | attr:furnished ×3 |
| ap08 | mixed | 2BR شقة للبيع in The Pearl | 4 | 4 | 1.00 | 1.00 | attr:bedrooms ×5, location ×1 |
| vi01 | en | 5 bedroom villa with private pool for rent | 20 | 9 | 0.90 | 1.00 | attr:private_pool ×1 |
| vi02 | en | compound villa for rent under 15000 a month | 9 | 3 | 0.33 | 0.50 | price ×7 |
| vi03 | en | townhouse for sale | 14 | 10 | 1.00 | 1.00 | - |
| vi04 | ar | فيلا للبيع في لوسيل | 23 | 10 | 1.00 | 1.00 | - |
| vi05 | ar | فيلا 6 غرف مع مسبح | 13 | 8 | 0.80 | 1.00 | attr:private_pool ×1, attr:bedrooms ×1 |
