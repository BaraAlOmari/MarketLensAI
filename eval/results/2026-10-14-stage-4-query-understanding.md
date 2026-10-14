# Eval run: Stage 4 query understanding

2026-10-14 08:56 UTC · 45 queries · k = 10

| Recall@10 | MRR | Wrong in top 10 | Zero-hit | Pages < 10 results | Server latency mean / p95 | Est. cost/query |
|---|---|---|---|---|---|---|
| 0.996 | 1.000 | 1% | 0 | 17 (0 empty) | 1168 / 1146 ms | $0.000402 |

Cached query embeddings: 45/45. LLM extraction: used on 45, cached 45, failed 0.

## By language and tag

| group | n | Recall@10 | MRR |
|---|---|---|---|
| lang:ar | 12 | 1.000 | 1.000 |
| lang:en | 29 | 0.993 | 1.000 |
| lang:mixed | 4 | 1.000 | 1.000 |
| tag:attribute | 19 | 1.000 | 1.000 |
| tag:brand | 1 | 1.000 | 1.000 |
| tag:condition | 11 | 0.982 | 1.000 |
| tag:currency | 1 | 1.000 | 1.000 |
| tag:item | 6 | 1.000 | 1.000 |
| tag:location | 6 | 1.000 | 1.000 |
| tag:model | 18 | 1.000 | 1.000 |
| tag:price | 11 | 1.000 | 1.000 |
| tag:rent_sale | 10 | 1.000 | 1.000 |
| tag:vague | 9 | 0.978 | 1.000 |

## Why wrong results were wrong

2 of 371 top-10 results were not relevant. A result can break several constraints.

| broken constraint | wrong results | queries affected |
|---|---|---|
| model | 2 | 1 |

## Per query

| id | lang | query | relevant | returned | hits@10 | Recall@10 | RR | main reasons | filters |
|---|---|---|---|---|---|---|---|---|---|
| ph01 | en | used iPhone 15 Pro Max | 16 | 10 | 10 | 1.00 | 1.00 | - | category=phones; brands=Apple; models=iPhone 15 Pro Max; conditions=like_new/good/fair/poor |
| ph02 | en | iPhone 16 Pro under 3000 QAR | 13 | 10 | 10 | 1.00 | 1.00 | - | category=phones; brands=Apple; models=iPhone 16 Pro; max_price=3000 |
| ph03 | en | Samsung Galaxy S24 Ultra 512GB | 6 | 6 | 6 | 1.00 | 1.00 | - | category=phones; brands=Samsung; models=Galaxy S24 Ultra; storage_gb:512; keywords=512GB |
| ph04 | en | cheap android phone under 1000 riyals | 25 | 10 | 10 | 1.00 | 1.00 | - | brands=Google/Huawei/OnePlus/Samsung/Xiaomi; max_price=1000 |
| ph05 | en | brand new iPhone 15 Pro Max | 6 | 6 | 6 | 1.00 | 1.00 | - | category=phones; brands=Apple; models=iPhone 15 Pro Max; conditions=new |
| ph06 | en | foldable phone in like new condition | 21 | 10 | 10 | 1.00 | 1.00 | - | category=phones; conditions=new/like_new; keywords=foldable |
| ph07 | en | iPhone 17 Pro around $1000 | 14 | 10 | 10 | 1.00 | 1.00 | - | brands=Apple; models=iPhone 17 Pro; min_price=850.00; max_price=1150.00; currency=USD |
| ph08 | ar | ايفون 16 بحالة ممتازة | 8 | 8 | 8 | 1.00 | 1.00 | - | category=phones; brands=Apple; models=iPhone 16; conditions=like_new/good |
| ph09 | ar | سامسونج جالكسي S25 الترا جديد | 2 | 2 | 2 | 1.00 | 1.00 | - | category=phones; brands=Samsung; models=Galaxy S25 Ultra; conditions=new; keywords=Ultra |
| ph10 | mixed | iPhone 14 نظيف أقل من 1500 ريال | 16 | 10 | 10 | 1.00 | 1.00 | - | category=phones; brands=Apple; models=iPhone 14; max_price=1500 |
| lp01 | en | MacBook Air M4 with 16GB RAM | 33 | 10 | 10 | 1.00 | 1.00 | - | category=laptops; brands=Apple; models=MacBook Air 13 M4/MacBook Air 15 M4; ram_gb:16; keywords=16GB/M4 |
| lp02 | en | gaming laptop under 4000 QAR | 82 | 10 | 10 | 1.00 | 1.00 | - | category=laptops; max_price=4000 |
| lp03 | en | lightweight laptop for a university student in good condition | 118 | 10 | 8 | 0.80 | 1.00 | model ×2 | category=laptops; conditions=new/like_new/good |
| lp04 | en | Dell XPS 13 like new | 10 | 10 | 10 | 1.00 | 1.00 | - | category=laptops; brands=Dell; models=XPS 13; conditions=new/like_new |
| lp05 | en | MacBook Pro M4 Max 1TB | 10 | 10 | 10 | 1.00 | 1.00 | - | category=laptops; brands=Apple; models=MacBook Pro 16 M4 Max; storage_gb:1024; keywords=1TB |
| lp06 | ar | لابتوب قيمنق مستعمل | 84 | 10 | 10 | 1.00 | 1.00 | - | category=laptops; conditions=like_new/good/fair/poor |
| lp07 | ar | ماك بوك اير للبيع | 54 | 10 | 10 | 1.00 | 1.00 | - | category=laptops; brands=Apple; models=MacBook Air 13 M2/MacBook Air 13 M4/MacBook Air 15 M4 |
| car01 | en | Toyota Land Cruiser 2020 or newer | 9 | 9 | 9 | 1.00 | 1.00 | - | category=cars; brands=Toyota; models=Land Cruiser; year:2020 |
| car02 | en | used Nissan Patrol under 150,000 QAR | 3 | 3 | 3 | 1.00 | 1.00 | - | category=cars; brands=Nissan; models=Patrol; conditions=like_new/good/fair/poor; max_price=150000 |
| car03 | en | SUV with less than 50,000 km | 91 | 10 | 10 | 1.00 | 1.00 | - | category=cars; mileage_km:50000 |
| car04 | en | cheap sedan for daily commute under 40k | 54 | 10 | 10 | 1.00 | 1.00 | - | category=cars; max_price=40000 |
| car05 | en | Tesla Model Y | 11 | 10 | 10 | 1.00 | 1.00 | - | models=Model Y |
| car06 | en | Range Rover Sport GCC specs accident free | 11 | 10 | 10 | 1.00 | 1.00 | - | category=cars; models=Range Rover Sport; gcc_specs:True; accident_free:True |
| car07 | ar | لاندكروزر برادو للبيع | 13 | 10 | 10 | 1.00 | 1.00 | - | category=cars; models=Land Cruiser Prado |
| car08 | ar | سيارة سيدان اقتصادية اقل من 30 الف | 47 | 10 | 10 | 1.00 | 1.00 | - | category=cars; max_price=30000 |
| car09 | mixed | G63 AMG ممشى قليل | 6 | 6 | 6 | 1.00 | 1.00 | - | category=cars; models=G 63 AMG; mileage_km:50000 |
| fu01 | en | IKEA bookshelf | 9 | 9 | 9 | 1.00 | 1.00 | - | category=furniture; brands=IKEA; item_type:['bookshelf'] |
| fu02 | en | L-shaped sofa in good condition under 2500 QAR | 7 | 7 | 7 | 1.00 | 1.00 | - | category=furniture; conditions=new/like_new/good; max_price=2500; item_type:['L-shaped sofa'] |
| fu03 | en | majlis set | 18 | 10 | 10 | 1.00 | 1.00 | - | category=furniture; item_type:['majlis set'] |
| fu04 | mixed | office chair مع توصيل | 5 | 5 | 5 | 1.00 | 1.00 | - | category=furniture; item_type:['office chair']; delivery_available:True |
| fu05 | ar | كنب ثلاثي مستعمل | 16 | 10 | 10 | 1.00 | 1.00 | - | category=furniture; conditions=like_new/good/fair/poor; item_type:['3-seater sofa'] |
| fu06 | ar | سرير كوين مع مرتبة | 25 | 10 | 10 | 1.00 | 1.00 | - | category=furniture; item_type:['queen bed with mattress'] |
| ap01 | en | 2 bedroom apartment for rent in Lusail | 2 | 2 | 2 | 1.00 | 1.00 | - | category=apartments; listing_type=rent; location=Lusail; bedrooms:2 |
| ap02 | en | studio for rent under 5000 a month | 33 | 10 | 10 | 1.00 | 1.00 | - | category=apartments; max_price=5000; price_period=month; listing_type=rent; property_type:studio |
| ap03 | en | furnished 1BR in The Pearl | 6 | 6 | 6 | 1.00 | 1.00 | - | category=apartments; location=The Pearl; bedrooms:1; furnished:furnished |
| ap04 | en | 3 bedroom apartment for sale in West Bay | 3 | 3 | 3 | 1.00 | 1.00 | - | category=apartments; listing_type=sale; location=West Bay; bedrooms:3 |
| ap05 | en | penthouse with sea view | 4 | 4 | 4 | 1.00 | 1.00 | - | category=apartments; property_type:penthouse; amenities:['sea view'] |
| ap06 | ar | شقة غرفتين للإيجار في لوسيل | 2 | 2 | 2 | 1.00 | 1.00 | - | category=apartments; listing_type=rent; location=Lusail; bedrooms:2; keywords=شقة |
| ap07 | ar | استوديو مفروش للإيجار | 14 | 10 | 10 | 1.00 | 1.00 | - | category=apartments; property_type:studio; furnished:furnished; keywords=مفروش |
| ap08 | mixed | 2BR شقة للبيع in The Pearl | 4 | 4 | 4 | 1.00 | 1.00 | - | category=apartments; listing_type=sale; location=The Pearl; bedrooms:2 |
| vi01 | en | 5 bedroom villa with private pool for rent | 20 | 10 | 10 | 1.00 | 1.00 | - | category=villas; listing_type=rent; bedrooms:5; private_pool:True |
| vi02 | en | compound villa for rent under 15000 a month | 9 | 9 | 9 | 1.00 | 1.00 | - | category=villas; max_price=15000; price_period=month; listing_type=rent; property_type:compound villa; keywords=15000 |
| vi03 | en | townhouse for sale | 14 | 10 | 10 | 1.00 | 1.00 | - | category=villas; property_type:townhouse; keywords=townhouse |
| vi04 | ar | فيلا للبيع في لوسيل | 23 | 10 | 10 | 1.00 | 1.00 | - | category=villas; listing_type=sale; location=Lusail |
| vi05 | ar | فيلا 6 غرف مع مسبح | 13 | 10 | 10 | 1.00 | 1.00 | - | category=villas; bedrooms:6; private_pool:True |
