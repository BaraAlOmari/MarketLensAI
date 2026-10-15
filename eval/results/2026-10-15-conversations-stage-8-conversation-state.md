# Multi-turn eval: Stage 8 conversation state

2026-10-15 10:36 UTC · 12 conversations · 18 scored turns

| Conversations passed | Scored turns passed | Recall@10 (all scored) | Recall@10 (final turns) | MRR | Wrong in top 10 |
|---|---|---|---|---|---|
| **12/12** | 18/18 | 1.000 | 1.000 | 1.000 | 0 |

Pass rule: every scored turn has 0 wrong results in its top 10 and Recall@10 >= 0.8.

## c01 (en, add): PASS

| turn | message | scored | relevant | hits@10 | Recall@10 | wrong | filters | notes |
|---|---|---|---|---|---|---|---|---|
| 1 | used iPhone 15 Pro Max | yes | 16 | 10 | 1.00 | - | {"category": "phones", "brands": ["Apple"], "models": ["iPhone 15 Pro Max"], "conditions": ["like_new", "good", "fair", "poor"]} | new search |
| 2 | under 2000 riyals | yes | 8 | 8 | 1.00 | - | {"category": "phones", "brands": ["Apple"], "models": ["iPhone 15 Pro Max"], "conditions": ["like_new", "good", "fair", "poor"], "max_price": "2000"} | price replaced |

## c02 (en, add, add): PASS

| turn | message | scored | relevant | hits@10 | Recall@10 | wrong | filters | notes |
|---|---|---|---|---|---|---|---|---|
| 1 | MacBook Air M4 | - | - | - | - | - | {"category": "laptops", "brands": ["Apple"], "models": ["MacBook Air 13 M4", "MacBook Air 15 M4"]} | new search |
| 2 | with 16GB RAM | - | - | - | - | - | {"category": "laptops", "brands": ["Apple"], "models": ["MacBook Air 13 M4", "MacBook Air 15 M4"], "attributes": {"ram_gb": {"min": "16"}}} | attributes: ram_gb |
| 3 | like new only | yes | 13 | 10 | 1.00 | - | {"category": "laptops", "brands": ["Apple"], "models": ["MacBook Air 13 M4", "MacBook Air 15 M4"], "conditions": ["new", "like_new"], "attributes": {"ram_gb": {"min": "16"}}} | condition set |

## c03 (en, cheaper): PASS

| turn | message | scored | relevant | hits@10 | Recall@10 | wrong | filters | notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Toyota Land Cruiser | yes | 14 | 10 | 1.00 | - | {"category": "cars", "brands": ["Toyota"], "models": ["Land Cruiser"]} | new search |
| 2 | cheaper ones | yes | 7 | 7 | 1.00 | - | {"category": "cars", "brands": ["Toyota"], "models": ["Land Cruiser"], "max_price": "204999.999"} | nothing new to merge, cheaper: below median 205000 QAR |

## c04 (en, brand_switch): PASS

| turn | message | scored | relevant | hits@10 | Recall@10 | wrong | filters | notes |
|---|---|---|---|---|---|---|---|---|
| 1 | used iPhone 15 Pro Max under 3000 QAR | - | - | - | - | - | {"category": "phones", "brands": ["Apple"], "models": ["iPhone 15 Pro Max"], "conditions": ["like_new", "good", "fair", "poor"], "max_price": "3000"} | new search |
| 2 | what about Samsung? | yes | 63 | 10 | 1.00 | - | {"category": "phones", "brands": ["Samsung"], "conditions": ["like_new", "good", "fair", "poor"], "max_price": "3000"} | models of other brands dropped, brand set |

## c05 (en, add, add): PASS

| turn | message | scored | relevant | hits@10 | Recall@10 | wrong | filters | notes |
|---|---|---|---|---|---|---|---|---|
| 1 | 2 bedroom apartment in Lusail | - | - | - | - | - | {"category": "apartments", "location": "Lusail", "attributes": {"bedrooms": {"eq": 2}}} | new search |
| 2 | for rent | yes | 2 | 2 | 1.00 | - | {"category": "apartments", "listing_type": "rent", "location": "Lusail", "attributes": {"bedrooms": {"eq": 2}}} | listing_type set |
| 3 | under 12000 a month | yes | 1 | 1 | 1.00 | - | {"category": "apartments", "max_price": "12000", "price_period": "month", "listing_type": "rent", "location": "Lusail", "attributes": {"bedrooms": {"eq": 2}}} | price replaced, listing_type set |

## c06 (en, reset): PASS

| turn | message | scored | relevant | hits@10 | Recall@10 | wrong | filters | notes |
|---|---|---|---|---|---|---|---|---|
| 1 | MacBook Air | - | - | - | - | - | {"category": "laptops", "models": ["MacBook Air 13 M2", "MacBook Air 13 M4", "MacBook Air 15 M4"]} | new search |
| 2 | start over | - | - | - | - | - | {} | start over |
| 3 | office chair with delivery | yes | 5 | 5 | 1.00 | - | {"category": "furniture", "attributes": {"item_type": {"any_of": ["office chair"]}, "delivery_available": {"eq": true}}} | new search |

## c07 (en, category_switch): PASS

| turn | message | scored | relevant | hits@10 | Recall@10 | wrong | filters | notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Nissan Patrol | - | - | - | - | - | {"category": "cars", "brands": ["Nissan"], "models": ["Patrol"]} | new search |
| 2 | actually I need a villa for rent in Lusail | yes | 4 | 4 | 1.00 | - | {"category": "villas", "listing_type": "rent", "location": "Lusail"} | new category: villas |

## c08 (ar, add, add): PASS

| turn | message | scored | relevant | hits@10 | Recall@10 | wrong | filters | notes |
|---|---|---|---|---|---|---|---|---|
| 1 | شقة للإيجار في لوسيل | - | - | - | - | - | {"category": "apartments", "listing_type": "rent", "location": "Lusail"} | new search |
| 2 | غرفتين | yes | 2 | 2 | 1.00 | - | {"category": "apartments", "listing_type": "rent", "location": "Lusail", "attributes": {"bedrooms": {"eq": 2}}} | attributes: bedrooms |
| 3 | أقل من 12000 ريال بالشهر | yes | 1 | 1 | 1.00 | - | {"category": "apartments", "max_price": "12000", "price_period": "month", "listing_type": "rent", "location": "Lusail", "attributes": {"bedrooms": {"eq": 2}}} | price replaced, listing_type set |

## c09 (en, replace): PASS

| turn | message | scored | relevant | hits@10 | Recall@10 | wrong | filters | notes |
|---|---|---|---|---|---|---|---|---|
| 1 | villa for rent with a private pool | - | - | - | - | - | {"category": "villas", "listing_type": "rent", "attributes": {"private_pool": {"eq": true}}} | new search |
| 2 | under 20000 a month | yes | 40 | 10 | 1.00 | - | {"category": "villas", "max_price": "20000", "price_period": "month", "listing_type": "rent", "attributes": {"private_pool": {"eq": true}}} | price replaced, listing_type set |
| 3 | actually under 25000 | yes | 50 | 10 | 1.00 | - | {"category": "villas", "max_price": "25000", "price_period": "month", "listing_type": "rent", "attributes": {"private_pool": {"eq": true}}} | price replaced, listing_type set |

## c10 (en, add, add): PASS

| turn | message | scored | relevant | hits@10 | Recall@10 | wrong | filters | notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Nissan Patrol under 250,000 QAR | - | - | - | - | - | {"category": "cars", "brands": ["Nissan"], "models": ["Patrol"], "max_price": "250000"} | new search |
| 2 | less than 100,000 km | - | - | - | - | - | {"category": "cars", "brands": ["Nissan"], "models": ["Patrol"], "max_price": "250000", "attributes": {"mileage_km": {"max": "100000"}}} | attributes: mileage_km |
| 3 | GCC specs only | yes | 3 | 3 | 1.00 | - | {"category": "cars", "brands": ["Nissan"], "models": ["Patrol"], "max_price": "250000", "attributes": {"mileage_km": {"max": "100000"}, "gcc_specs": {"eq": true}}} | attributes: gcc_specs |

## c11 (mixed, add, cheaper): PASS

| turn | message | scored | relevant | hits@10 | Recall@10 | wrong | filters | notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Galaxy S24 Ultra | - | - | - | - | - | {"category": "phones", "brands": ["Samsung"], "models": ["Galaxy S24 Ultra"]} | new search |
| 2 | 512GB | yes | 6 | 6 | 1.00 | - | {"category": "phones", "brands": ["Samsung"], "models": ["Galaxy S24 Ultra"], "attributes": {"storage_gb": {"eq": 512}}} | attributes: storage_gb |
| 3 | أرخص | yes | 3 | 3 | 1.00 | - | {"category": "phones", "brands": ["Samsung"], "models": ["Galaxy S24 Ultra"], "max_price": "2474.499", "attributes": {"storage_gb": {"eq": 512}}} | nothing new to merge, cheaper: below median 2474 QAR |

## c12 (en, reset, category_switch): PASS

| turn | message | scored | relevant | hits@10 | Recall@10 | wrong | filters | notes |
|---|---|---|---|---|---|---|---|---|
| 1 | furnished studio for rent | - | - | - | - | - | {"category": "apartments", "listing_type": "rent", "attributes": {"property_type": {"eq": "studio"}, "furnished": {"eq": "furnished"}}} | new search |
| 2 | in Al Qassar | - | - | - | - | - | {"category": "apartments", "listing_type": "rent", "location": "Al Qassar", "attributes": {"furnished": {"eq": "furnished"}, "property_type": {"eq": "studio"}}} | location set |
| 3 | start over | - | - | - | - | - | {} | start over |
| 4 | townhouse for sale | yes | 14 | 10 | 1.00 | - | {"category": "villas", "listing_type": "sale", "attributes": {"property_type": {"eq": "townhouse"}}} | new search |

