# Eval run: Stage 4 attempt 2 (Interactions API + guards, cached)

2026-10-13 15:53 UTC · 45 queries · k = 10

| Recall@10 | MRR | Wrong in top 10 | Zero-hit | Pages < 10 results | Server latency mean / p95 | Est. cost/query |
|---|---|---|---|---|---|---|
| 0.834 | 0.894 | 23% | 3 | 5 (2 empty) | 3147 / 2049 ms | $0.000392 |

Cached query embeddings: 45/45. LLM extraction: used on 45, cached 44, failed 0; uncached extraction mean 83508 ms.

## By language and tag

| group | n | Recall@10 | MRR |
|---|---|---|---|
| lang:ar | 12 | 0.894 | 1.000 |
| lang:en | 29 | 0.826 | 0.871 |
| lang:mixed | 4 | 0.708 | 0.750 |
| tag:attribute | 19 | 0.702 | 0.829 |
| tag:brand | 1 | 1.000 | 1.000 |
| tag:condition | 11 | 0.835 | 0.864 |
| tag:currency | 1 | 1.000 | 1.000 |
| tag:item | 6 | 0.793 | 0.750 |
| tag:location | 6 | 0.806 | 1.000 |
| tag:model | 18 | 0.842 | 0.889 |
| tag:price | 11 | 0.926 | 0.909 |
| tag:rent_sale | 10 | 0.793 | 0.950 |
| tag:vague | 9 | 0.881 | 0.917 |

## Why wrong results were wrong

96 of 410 top-10 results were not relevant. A result can break several constraints.

| broken constraint | wrong results | queries affected |
|---|---|---|
| attr:bedrooms | 36 | 5 |
| condition | 18 | 4 |
| attr:mileage_km | 12 | 2 |
| attr:amenities | 7 | 1 |
| price | 7 | 1 |
| attr:storage_gb | 4 | 1 |
| attr:furnished | 3 | 1 |
| model | 2 | 1 |
| attr:year | 2 | 1 |
| attr:accident_free | 1 | 1 |
| attr:gcc_specs | 1 | 1 |
| attr:item_type | 1 | 1 |
| attr:delivery_available | 1 | 1 |
| attr:private_pool | 1 | 1 |

## Per query

| id | lang | query | relevant | returned | hits@10 | Recall@10 | RR | main reasons | filters |
|---|---|---|---|---|---|---|---|---|---|
| ph01 | en | used iPhone 15 Pro Max | 16 | 10 | 10 | 1.00 | 1.00 | - | category=phones; models=iPhone 15 Pro Max |
| ph02 | en | iPhone 16 Pro under 3000 QAR | 13 | 10 | 10 | 1.00 | 1.00 | - | category=phones; models=iPhone 16 Pro; max_price=3000 |
| ph03 | en | Samsung Galaxy S24 Ultra 512GB | 6 | 10 | 6 | 1.00 | 1.00 | attr:storage_gb ×4 | brands=Samsung; models=Galaxy S24 Ultra |
| ph04 | en | cheap android phone under 1000 riyals | 25 | 10 | 10 | 1.00 | 1.00 | - | category=phones; brands=Samsung/Google/Huawei/OnePlus/Xiaomi; max_price=1000 |
| ph05 | en | brand new iPhone 15 Pro Max | 6 | 6 | 6 | 1.00 | 1.00 | - | category=phones; models=iPhone 15 Pro Max; conditions=new |
| ph06 | en | foldable phone in like new condition | 21 | 10 | 10 | 1.00 | 1.00 | - | category=phones; conditions=new/like_new; keywords=foldable |
| ph07 | en | iPhone 17 Pro around $1000 | 14 | 10 | 10 | 1.00 | 1.00 | - | category=phones; models=iPhone 17 Pro; min_price=850.00; max_price=1150.00; currency=USD |
| ph08 | ar | ايفون 16 بحالة ممتازة | 8 | 10 | 5 | 0.62 | 1.00 | condition ×5 | category=phones; models=iPhone 16 |
| ph09 | ar | سامسونج جالكسي S25 الترا جديد | 2 | 10 | 2 | 1.00 | 1.00 | condition ×8 | category=phones; models=Galaxy S25 Ultra |
| ph10 | mixed | iPhone 14 نظيف أقل من 1500 ريال | 16 | 10 | 10 | 1.00 | 1.00 | - | category=phones; models=iPhone 14; max_price=1500 |
| lp01 | en | MacBook Air M4 with 16GB RAM | 33 | 0 | 0 | 0.00 | 0.00 | - | category=laptops; models=MacBook Air 13 M4/MacBook Air 15 M4; storage_gb:16 |
| lp02 | en | gaming laptop under 4000 QAR | 82 | 10 | 10 | 1.00 | 1.00 | - | category=laptops; max_price=4000; keywords=gaming |
| lp03 | en | lightweight laptop for a university student in good condition | 118 | 10 | 8 | 0.80 | 1.00 | model ×2 | category=laptops; conditions=new/like_new/good |
| lp04 | en | Dell XPS 13 like new | 10 | 0 | 0 | 0.00 | 0.00 | - | category=laptops; models=XPS 13; storage_gb:13 |
| lp05 | en | MacBook Pro M4 Max 1TB | 10 | 10 | 10 | 1.00 | 1.00 | - | category=laptops; models=MacBook Pro 16 M4 Max; storage_gb:1024 |
| lp06 | ar | لابتوب قيمنق مستعمل | 84 | 10 | 10 | 1.00 | 1.00 | - | category=laptops; conditions=like_new/good/fair/poor |
| lp07 | ar | ماك بوك اير للبيع | 54 | 10 | 10 | 1.00 | 1.00 | - | category=laptops; models=MacBook Air 13 M2/MacBook Air 13 M4/MacBook Air 15 M4 |
| car01 | en | Toyota Land Cruiser 2020 or newer | 9 | 10 | 8 | 0.89 | 1.00 | attr:year ×2 | brands=Toyota; models=Land Cruiser |
| car02 | en | used Nissan Patrol under 150,000 QAR | 3 | 3 | 3 | 1.00 | 1.00 | - | category=cars; models=Patrol; conditions=like_new/good/fair/poor; max_price=150000 |
| car03 | en | SUV with less than 50,000 km | 91 | 10 | 3 | 0.30 | 0.25 | attr:mileage_km ×7 | - |
| car04 | en | cheap sedan for daily commute under 40k | 54 | 10 | 10 | 1.00 | 1.00 | - | category=cars; max_price=40000 |
| car05 | en | Tesla Model Y | 11 | 10 | 10 | 1.00 | 1.00 | - | category=cars; models=Model Y |
| car06 | en | Range Rover Sport GCC specs accident free | 11 | 10 | 8 | 0.80 | 1.00 | attr:accident_free ×1, attr:gcc_specs ×1 | category=cars; models=Range Rover Sport |
| car07 | ar | لاندكروزر برادو للبيع | 13 | 10 | 10 | 1.00 | 1.00 | - | category=cars; models=Land Cruiser Prado |
| car08 | ar | سيارة سيدان اقتصادية اقل من 30 الف | 47 | 10 | 10 | 1.00 | 1.00 | - | category=cars; max_price=30000 |
| car09 | mixed | G63 AMG ممشى قليل | 6 | 10 | 5 | 0.83 | 1.00 | attr:mileage_km ×5 | category=cars; models=G 63 AMG |
| fu01 | en | IKEA bookshelf | 9 | 10 | 9 | 1.00 | 1.00 | attr:item_type ×1 | brands=IKEA |
| fu02 | en | L-shaped sofa in good condition under 2500 QAR | 7 | 10 | 6 | 0.86 | 0.50 | condition ×4 | category=furniture; max_price=2500; item_type:['L-shaped sofa'] |
| fu03 | en | majlis set | 18 | 10 | 10 | 1.00 | 1.00 | - | category=furniture; item_type:['majlis set'] |
| fu04 | mixed | office chair مع توصيل | 5 | 1 | 0 | 0.00 | 0.00 | attr:delivery_available ×1 | category=furniture; location=Lusail; item_type:['office chair'] |
| fu05 | ar | كنب ثلاثي مستعمل | 16 | 10 | 9 | 0.90 | 1.00 | condition ×1 | category=furniture; item_type:['3-seater sofa'] |
| fu06 | ar | سرير كوين مع مرتبة | 25 | 10 | 10 | 1.00 | 1.00 | - | category=furniture; item_type:['queen bed with mattress'] |
| ap01 | en | 2 bedroom apartment for rent in Lusail | 2 | 10 | 1 | 0.50 | 1.00 | attr:bedrooms ×9 | category=apartments; listing_type=rent; location=Lusail; property_type:apartment |
| ap02 | en | studio for rent under 5000 a month | 33 | 10 | 10 | 1.00 | 1.00 | - | category=apartments; listing_type=rent; property_type:studio |
| ap03 | en | furnished 1BR in The Pearl | 6 | 10 | 5 | 0.83 | 1.00 | attr:bedrooms ×5 | category=apartments; location=The Pearl; property_type:apartment; furnished:furnished |
| ap04 | en | 3 bedroom apartment for sale in West Bay | 3 | 10 | 3 | 1.00 | 1.00 | attr:bedrooms ×7 | category=apartments; listing_type=sale; location=West Bay; property_type:apartment |
| ap05 | en | penthouse with sea view | 4 | 10 | 3 | 0.75 | 1.00 | attr:amenities ×7 | category=apartments; property_type:penthouse |
| ap06 | ar | شقة غرفتين للإيجار في لوسيل | 2 | 10 | 1 | 0.50 | 1.00 | attr:bedrooms ×9 | category=apartments; listing_type=rent; location=Lusail; property_type:apartment |
| ap07 | ar | استوديو مفروش للإيجار | 14 | 10 | 7 | 0.70 | 1.00 | attr:furnished ×3 | category=apartments; listing_type=rent; property_type:studio |
| ap08 | mixed | 2BR شقة للبيع in The Pearl | 4 | 10 | 4 | 1.00 | 1.00 | attr:bedrooms ×6 | category=apartments; listing_type=sale; location=The Pearl; property_type:apartment |
| vi01 | en | 5 bedroom villa with private pool for rent | 20 | 10 | 9 | 0.90 | 1.00 | attr:private_pool ×1 | category=villas; listing_type=rent; property_type:villa |
| vi02 | en | compound villa for rent under 15000 a month | 9 | 10 | 3 | 0.33 | 0.50 | price ×7 | category=villas; listing_type=rent; property_type:compound villa |
| vi03 | en | townhouse for sale | 14 | 10 | 10 | 1.00 | 1.00 | - | category=villas; listing_type=sale; property_type:townhouse |
| vi04 | ar | فيلا للبيع في لوسيل | 23 | 10 | 10 | 1.00 | 1.00 | - | category=villas; listing_type=sale; location=Lusail |
| vi05 | ar | فيلا 6 غرف مع مسبح | 13 | 10 | 10 | 1.00 | 1.00 | - | category=villas; bedrooms:6; private_pool:True |
