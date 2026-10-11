# Stage 1 Spot Check

Generated 2026-10-10 10:19 UTC by `backend/scripts/spot_check.py`.

## Acceptance

| Check | Result |
|---|---|
| Listings loaded (>= 2,000) | 2205 ✅ |
| Nulls in required fields | 0 ✅ |
| Condition missing outside property | 0 ✅ |
| Empty title/description | 0 ✅ |
| Overall | PASS ✅ |

## Distributions

**category**

| category | count |
|---|---|
| apartments | 445 |
| phones | 435 |
| cars | 373 |
| laptops | 349 |
| furniture | 340 |
| villas | 263 |

**condition**

| condition | count |
|---|---|
| (null: property) | 708 |
| good | 475 |
| like_new | 456 |
| fair | 277 |
| new | 206 |
| poor | 83 |

**currency**

| currency | count |
|---|---|
| QAR | 1952 |
| USD | 253 |

**language**

| language | count |
|---|---|
| en | 1318 |
| ar | 657 |
| mixed | 230 |

**listing type / period**

| listing type / period | count |
|---|---|
| sale / total | 1680 |
| rent / month | 442 |
| rent / year | 83 |

**text writer** (from the dataset file)

| writer | count |
|---|---|
| template | 1286 |
| gemini | 919 |

Near-duplicates: 105.

## Prices (QAR, normalized)

| category | type/period | n | min | median | max |
|---|---|---|---|---|---|
| apartments | rent/month | 298 | 2,500 | 7,200 | 33,000 |
| apartments | rent/year | 49 | 31,000 | 98,000 | 272,000 |
| apartments | sale/total | 98 | 324,000 | 1,550,000 | 4,340,000 |
| cars | sale/total | 373 | 5,900 | 70,500 | 875,000 |
| furniture | sale/total | 340 | 80 | 1,262 | 14,500 |
| laptops | sale/total | 349 | 475 | 2,899 | 11,500 |
| phones | sale/total | 435 | 350 | 2,100 | 5,950 |
| villas | rent/month | 144 | 7,550 | 18,000 | 49,140 |
| villas | rent/year | 34 | 65,500 | 217,000 | 436,800 |
| villas | sale/total | 85 | 2,960,000 | 5,787,600 | 12,380,000 |

## Full-text search sanity

| query | matches |
|---|---|
| iphone | 205 |
| 256gb | 175 |
| شقة | 129 |
| للإيجار | 213 |
| Land Cruiser | 27 |

## 20 random rows

| id | category | title | price | price_qar | condition | type | location | lang |
|---|---|---|---|---|---|---|---|---|
| 420 | furniture | سرير كينج خشب ابيض 180x200 سم النجمة | 2,350 QAR | 2,350 | good | sale/total | Najma, Doha | ar |
| 1034 | furniture | l-shaped sofa | 2,400 QAR | 2,400 | like_new | sale/total | Al Khor | en |
| 1613 | laptops | Acer Nitro V 15 512GB للبيع | 1,500 QAR | 1,500 | good | sale/total | Madinat Khalifa, Doha | mixed |
| 275 | cars | 2012 Porsche Cayenne Turbo pearl white in West Bay | 45,500 QAR | 45,500 | like_new | sale/total | West Bay, Doha | en |
| 1481 | laptops | HP Spectre x360 14 for sale | 2,700 QAR | 2,700 | good | sale/total | The Pearl, Doha | en |
| 158 | laptops | Lenovo ThinkPad X1 Carbon Gen 13 بحالة ممتازة | 5,250 QAR | 5,250 | like_new | sale/total | Msheireb, Doha | ar |
| 654 | cars | Ford Mustang GT 2026 قير عادي بيج | 55,500 USD | 202,020 | like_new | sale/total | Al Rayyan | ar |
| 526 | laptops | BRAND NEW APPLE MACBOOK AIR 13 M4 24GB 512GB!! | 4,550 QAR | 4,550 | new | sale/total | Al Rayyan | en |
| 1485 | phones | Samsung Galaxy S25 128GB للبيع | 2,000 QAR | 2,000 | good | sale/total | Al Wakrah | mixed |
| 1202 | cars | LEXUS ES 350 2024!!! | 80,500 QAR | 80,500 | like_new | sale/total | Lusail | en |
| 987 | furniture | outdoor patio set - good cond | 425 QAR | 425 | good | sale/total | The Pearl, Doha | mixed |
| 348 | apartments | Unfurnished 1BR Apartment in Al Wakrah 🏊 | 4,950 QAR | 4,950 | - | rent/month | Al Wakrah | en |
| 1579 | phones | 💯 تلفون iPhone 17 Pro استعمال عادي ونظيف | 3,200 QAR | 3,200 | good | sale/total | Umm Salal | ar |
| 2169 | phones | Samsung Galaxy S24 Ultra 256GB | 2,350 QAR | 2,350 | good | sale/total | Lusail | en |
| 1509 | apartments | شقة للبيع في القصار | 1,950,000 QAR | 1,950,000 | - | sale/total | Al Qassar, Doha | ar |
| 1217 | laptops | HP Pavilion 15 for sale | 875 QAR | 875 | good | sale/total | Al Rayyan | en |
| 1877 | villas | للإيجار تاون هاوس 5 غرف مفروشة بالكامل نجمة | 3,550 USD | 12,922 | - | rent/month | Najma, Doha | ar |
| 742 | furniture | مكتب دراسة خشب ايكيا في اللؤلؤة !! | 775 QAR | 775 | fair | sale/total | The Pearl, Doha | ar |
| 83 | laptops | MSI Katana 15 i7 RTX 4060 gd cond | 1,850 QAR | 1,850 | good | sale/total | Najma, Doha | ar |
| 1751 | villas | فيلا 4 غرف للبيع - اللؤلؤة | 6,940,000 QAR | 6,940,000 | - | sale/total | The Pearl, Doha | ar |
