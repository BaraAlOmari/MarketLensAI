# Eval run: Stage 4 attempt 1 (Interactions API, no guards)

2026-10-13 14:47 UTC · 45 queries · k = 10

| Recall@10 | MRR | Wrong in top 10 | Zero-hit | Pages < 10 results | Server latency mean / p95 | Est. cost/query |
|---|---|---|---|---|---|---|
| 0.734 | 0.811 | 27% | 7 | 11 (7 empty) | 114837 / 229764 ms | $0.000193 |

Cached query embeddings: 45/45. LLM extraction: used on 45, cached 0, failed 22; uncached extraction mean 100917 ms.

## By language and tag

| group | n | Recall@10 | MRR |
|---|---|---|---|
| lang:ar | 12 | 0.669 | 0.750 |
| lang:en | 29 | 0.764 | 0.845 |
| lang:mixed | 4 | 0.708 | 0.750 |
| tag:attribute | 19 | 0.592 | 0.645 |
| tag:brand | 1 | 1.000 | 1.000 |
| tag:condition | 11 | 0.751 | 0.932 |
| tag:currency | 1 | 0.600 | 1.000 |
| tag:item | 6 | 0.762 | 0.708 |
| tag:location | 6 | 0.778 | 0.833 |
| tag:model | 18 | 0.779 | 0.944 |
| tag:price | 11 | 0.743 | 0.750 |
| tag:rent_sale | 10 | 0.590 | 0.600 |
| tag:vague | 9 | 0.881 | 0.917 |

## Why wrong results were wrong

99 of 373 top-10 results were not relevant. A result can break several constraints.

| broken constraint | wrong results | queries affected |
|---|---|---|
| condition | 33 | 8 |
| attr:bedrooms | 22 | 4 |
| price | 13 | 3 |
| attr:mileage_km | 12 | 2 |
| attr:amenities | 7 | 1 |
| model | 6 | 4 |
| attr:storage_gb | 3 | 1 |
| rent_sale | 2 | 1 |
| attr:accident_free | 1 | 1 |
| attr:gcc_specs | 1 | 1 |
| attr:furnished | 1 | 1 |
| category | 1 | 1 |
| location | 1 | 1 |
| attr:private_pool | 1 | 1 |

## Per query

| id | lang | query | relevant | returned | hits@10 | Recall@10 | RR | main reasons | filters |
|---|---|---|---|---|---|---|---|---|---|
| ph01 | en | used iPhone 15 Pro Max | 16 | 9 | 5 | 0.50 | 1.00 | condition ×4 | category=phones; models=iPhone 15 Pro Max; storage_gb:1024 |
| ph02 | en | iPhone 16 Pro under 3000 QAR | 13 | 10 | 10 | 1.00 | 1.00 | - | category=phones; models=iPhone 16 Pro; max_price=3000 |
| ph03 | en | Samsung Galaxy S24 Ultra 512GB | 6 | 10 | 6 | 1.00 | 1.00 | attr:storage_gb ×3, model ×1 | FAILED: extraction call failed: InternalServerError |
| ph04 | en | cheap android phone under 1000 riyals | 25 | 10 | 10 | 1.00 | 1.00 | - | category=phones; max_price=1000 |
| ph05 | en | brand new iPhone 15 Pro Max | 6 | 9 | 4 | 0.67 | 1.00 | condition ×5 | category=phones; models=iPhone 15 Pro Max; storage_gb:1024 |
| ph06 | en | foldable phone in like new condition | 21 | 10 | 10 | 1.00 | 1.00 | - | category=phones; conditions=new/like_new |
| ph07 | en | iPhone 17 Pro around $1000 | 14 | 10 | 6 | 0.60 | 1.00 | model ×3, price ×3 | FAILED: extraction call failed: InternalServerError |
| ph08 | ar | ايفون 16 بحالة ممتازة | 8 | 6 | 1 | 0.12 | 1.00 | condition ×5 | category=phones; models=iPhone 16; storage_gb:128 |
| ph09 | ar | سامسونج جالكسي S25 الترا جديد | 2 | 10 | 2 | 1.00 | 1.00 | condition ×8 | FAILED: extraction call failed: APITimeoutError |
| ph10 | mixed | iPhone 14 نظيف أقل من 1500 ريال | 16 | 10 | 10 | 1.00 | 1.00 | - | FAILED: extraction call failed: InternalServerError |
| lp01 | en | MacBook Air M4 with 16GB RAM | 33 | 10 | 10 | 1.00 | 1.00 | - | FAILED: invalid extraction: 1 errors |
| lp02 | en | gaming laptop under 4000 QAR | 82 | 10 | 10 | 1.00 | 1.00 | - | category=laptops; max_price=4000; storage_gb:512 |
| lp03 | en | lightweight laptop for a university student in good condition | 118 | 10 | 8 | 0.80 | 1.00 | model ×1, condition ×1 | FAILED: extraction call failed: InternalServerError |
| lp04 | en | Dell XPS 13 like new | 10 | 10 | 6 | 0.60 | 1.00 | condition ×4 | category=laptops; models=XPS 13; storage_gb:512 |
| lp05 | en | MacBook Pro M4 Max 1TB | 10 | 10 | 10 | 1.00 | 1.00 | - | category=laptops; models=MacBook Pro 16 M4 Max; storage_gb:1024 |
| lp06 | ar | لابتوب قيمنق مستعمل | 84 | 10 | 10 | 1.00 | 1.00 | - | FAILED: extraction call failed: InternalServerError |
| lp07 | ar | ماك بوك اير للبيع | 54 | 10 | 10 | 1.00 | 1.00 | - | FAILED: extraction call failed: TimeoutError |
| car01 | en | Toyota Land Cruiser 2020 or newer | 9 | 0 | 0 | 0.00 | 0.00 | - | category=cars; models=Land Cruiser; min_price=850.00; max_price=1150.00; currency=USD; year:2020 |
| car02 | en | used Nissan Patrol under 150,000 QAR | 3 | 10 | 3 | 1.00 | 1.00 | price ×7, condition ×3 | FAILED: extraction call failed: InternalServerError |
| car03 | en | SUV with less than 50,000 km | 91 | 10 | 3 | 0.30 | 0.25 | attr:mileage_km ×7 | FAILED: extraction call failed: InternalServerError |
| car04 | en | cheap sedan for daily commute under 40k | 54 | 10 | 10 | 1.00 | 1.00 | - | category=cars; max_price=40000 |
| car05 | en | Tesla Model Y | 11 | 10 | 10 | 1.00 | 1.00 | - | category=cars; models=Model Y |
| car06 | en | Range Rover Sport GCC specs accident free | 11 | 10 | 8 | 0.80 | 1.00 | attr:accident_free ×1, attr:gcc_specs ×1 | FAILED: invalid extraction: 1 errors |
| car07 | ar | لاندكروزر برادو للبيع | 13 | 10 | 9 | 0.90 | 1.00 | model ×1 | FAILED: invalid extraction: 1 errors |
| car08 | ar | سيارة سيدان اقتصادية اقل من 30 الف | 47 | 10 | 10 | 1.00 | 1.00 | - | category=cars; max_price=30000 |
| car09 | mixed | G63 AMG ممشى قليل | 6 | 10 | 5 | 0.83 | 1.00 | attr:mileage_km ×5 | FAILED: extraction call failed: InternalServerError |
| fu01 | en | IKEA bookshelf | 9 | 9 | 9 | 1.00 | 1.00 | - | brands=IKEA; item_type:['bookshelf'] |
| fu02 | en | L-shaped sofa in good condition under 2500 QAR | 7 | 10 | 4 | 0.57 | 0.25 | condition ×3, price ×3 | FAILED: extraction call failed: InternalServerError |
| fu03 | en | majlis set | 18 | 10 | 10 | 1.00 | 1.00 | - | category=furniture; item_type:['majlis set'] |
| fu04 | mixed | office chair مع توصيل | 5 | 0 | 0 | 0.00 | 0.00 | - | category=furniture; location=Lusail; item_type:['office chair']; property_type:apartment; year:2020; storage_gb:512 |
| fu05 | ar | كنب ثلاثي مستعمل | 16 | 10 | 10 | 1.00 | 1.00 | - | category=furniture; conditions=like_new/good/fair/poor; item_type:['3-seater sofa'] |
| fu06 | ar | سرير كوين مع مرتبة | 25 | 10 | 10 | 1.00 | 1.00 | - | FAILED: extraction call failed: InternalServerError |
| ap01 | en | 2 bedroom apartment for rent in Lusail | 2 | 10 | 2 | 1.00 | 1.00 | attr:bedrooms ×6, rent_sale ×2 | FAILED: invalid extraction: 1 errors |
| ap02 | en | studio for rent under 5000 a month | 33 | 0 | 0 | 0.00 | 0.00 | - | category=apartments; property_type:studio; storage_gb:512 |
| ap03 | en | furnished 1BR in The Pearl | 6 | 10 | 4 | 0.67 | 1.00 | attr:bedrooms ×5, attr:furnished ×1 | FAILED: extraction call failed: InternalServerError |
| ap04 | en | 3 bedroom apartment for sale in West Bay | 3 | 10 | 3 | 1.00 | 1.00 | attr:bedrooms ×6, category ×1 | FAILED: extraction call failed: InternalServerError |
| ap05 | en | penthouse with sea view | 4 | 10 | 3 | 0.75 | 1.00 | attr:amenities ×7 | FAILED: invalid extraction: 1 errors |
| ap06 | ar | شقة غرفتين للإيجار في لوسيل | 2 | 0 | 0 | 0.00 | 0.00 | - | category=apartments; listing_type=rent; location=Lusail; property_type:apartment; storage_gb:2 |
| ap07 | ar | استوديو مفروش للإيجار | 14 | 0 | 0 | 0.00 | 0.00 | - | category=apartments; listing_type=rent; property_type:studio; storage_gb:1024 |
| ap08 | mixed | 2BR شقة للبيع in The Pearl | 4 | 10 | 4 | 1.00 | 1.00 | attr:bedrooms ×5, location ×1 | FAILED: extraction call failed: InternalServerError |
| vi01 | en | 5 bedroom villa with private pool for rent | 20 | 10 | 9 | 0.90 | 1.00 | attr:private_pool ×1 | FAILED: extraction call failed: InternalServerError |
| vi02 | en | compound villa for rent under 15000 a month | 9 | 0 | 0 | 0.00 | 0.00 | - | category=villas; property_type:compound villa; storage_gb:15000 |
| vi03 | en | townhouse for sale | 14 | 10 | 10 | 1.00 | 1.00 | - | FAILED: extraction call failed: InternalServerError |
| vi04 | ar | فيلا للبيع في لوسيل | 23 | 10 | 10 | 1.00 | 1.00 | - | category=villas; listing_type=sale; location=Lusail |
| vi05 | ar | فيلا 6 غرف مع مسبح | 13 | 0 | 0 | 0.00 | 0.00 | - | category=villas; property_type:villa; storage_gb:6 |
