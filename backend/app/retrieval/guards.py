"""Guards against fields the LLM invents (Stage 4, after the first eval run).

gemini-3.5-flash-lite at minimal thinking often fills fields the query never mentions,
sometimes with example values from its instructions: "studio for rent" came back with
storage_gb = 512, and "office chair with delivery" with location = Lusail and min_year = 2020.
Two generic rules remove that without touching the prompt:

1. Category scoping: a field only counts for categories where it means something (storage for
   phones and laptops, bedrooms for property, ...), and models / property types must belong to
   the extracted category.
2. Grounding: a number filter must appear in the query (as digits, "40k", "1TB", "30 الف", or a
   number word such as "غرفتين" = 2). Sizes, areas and mileages also need their unit
   (GB/TB, sqm/متر, km/كم). A location must be named (English, or a known Arabic spelling).
3. Backstops for the two most important explicit constraints, used only when the LLM left the
   field empty: a price limit ("under 15000 a month", "أقل من 1500 ريال") and a bedroom count
   ("2BR", "غرفتين"). On 2026-10-14 the model put "under 15000 a month" into area, mileage,
   storage and RAM but not price, and missed "غرفتين".

Guards run on every parse, cached or fresh, so changing them never needs a new LLM call.
"""

import re
from decimal import Decimal

from app.models.filters import PriceComparator, PriceIntent, QueryParse
from app.models.listing import PROPERTY_CATEGORIES, PricePeriod
from app.retrieval.catalog import Catalog

GENERAL = {"category", "brands", "models", "condition", "price", "location", "keywords"}
SCOPED = {
    "phones": {"storage_gb"},
    "laptops": {"storage_gb", "min_ram_gb"},
    "cars": {"min_year", "max_year", "max_mileage_km", "low_mileage", "gcc_specs", "accident_free"},
    "furniture": {"item_types", "delivery_available"},
    "apartments": {"listing_type", "property_type", "bedrooms", "min_bedrooms", "min_area_sqm",
                   "max_area_sqm", "furnished", "amenities"},
    "villas": {"listing_type", "property_type", "bedrooms", "min_bedrooms", "min_area_sqm",
               "max_area_sqm", "furnished", "private_pool"},
}  # fmt: skip
NUMERIC = ("bedrooms", "min_bedrooms", "min_area_sqm", "max_area_sqm", "min_year", "max_year",
           "max_mileage_km", "storage_gb", "min_ram_gb")  # fmt: skip

ARABIC = re.compile(r"[؀-ۿ]")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
NUMBER = re.compile(r"(\d+(?:[.,]\d+)*)\s*(k|m|tb|million|الف|ألف|مليون)?", re.IGNORECASE)
MULTIPLIER = {"k": 1000, "الف": 1000, "ألف": 1000, "m": 1_000_000, "million": 1_000_000,
              "مليون": 1_000_000, "tb": 1024}  # fmt: skip
WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "واحد": 1, "وحدة": 1, "غرفة": 1, "اثنين": 2, "اثنان": 2, "غرفتين": 2,
    "غرفتان": 2, "ثلاث": 3, "ثلاثة": 3, "اربع": 4, "أربع": 4, "اربعة": 4, "أربعة": 4,
    "خمس": 5, "خمسة": 5, "ست": 6, "ستة": 6, "سبع": 7, "سبعة": 7, "ثمان": 8, "ثمانية": 8,
    "تسع": 9, "تسعة": 9, "عشر": 10, "عشرة": 10,
}  # fmt: skip


def numbers_in(query: str) -> set[float]:
    """Every number the query states, in the forms people write them."""
    text = query.lower().translate(ARABIC_DIGITS)
    found: set[float] = set()
    for digits, suffix in NUMBER.findall(text):
        try:
            value = float(digits.replace(",", ""))
        except ValueError:
            continue
        found.add(value)
        if suffix:
            found.add(value * MULTIPLIER[suffix.lower()])
    for word in re.findall(r"[\w؀-ۿ]+", text):
        if word in WORDS:
            found.add(float(WORDS[word]))
    return found


# A size written with its unit: "256GB", "1 TB", "512 جيجا".
SIZED = re.compile(r"(\d+(?:\.\d+)?)\s*(gb|tb|جيجا|تيرا)", re.IGNORECASE)
MIN_STORAGE_GB = 32  # no phone or laptop in the catalog era ships with less


def sizes_in(query: str) -> set[float]:
    """Sizes in GB that the query writes with a unit (TB counted as 1024 GB)."""
    out = set()
    for digits, unit in SIZED.findall(query.lower().translate(ARABIC_DIGITS)):
        value = float(digits)
        out.add(value * 1024 if unit in ("tb", "تيرا") else value)
    return out


# Arabic names of the catalog's places, so Arabic queries are grounded too.
PLACE_NAMES_AR = {
    "Abu Hamour": ("ابو هامور", "أبو هامور"), "Ain Khaled": ("عين خالد",),
    "Al Duhail": ("الدحيل",), "Al Gharrafa": ("الغرافة", "الغرافه"), "Al Khor": ("الخور",),
    "Al Mansoura": ("المنصورة", "المنصوره"), "Al Qassar": ("القصار",), "Al Rayyan": ("الريان",),
    "Al Sadd": ("السد",), "Al Thumama": ("الثمامة", "الثمامه"), "Al Waab": ("الوعب",),
    "Al Wakrah": ("الوكرة", "الوكره"), "Bin Mahmoud": ("بن محمود",), "Lusail": ("لوسيل",),
    "Madinat Khalifa": ("مدينة خليفة",), "Msheireb": ("مشيرب",), "Muaither": ("معيذر",),
    "Najma": ("نجمة", "نجمه"), "Old Airport": ("المطار القديم",),
    "The Pearl": ("اللؤلؤة", "اللؤلؤه", "البيرل", "بيرل"),
    "Umm Salal": ("ام صلال", "أم صلال"), "West Bay": ("الخليج الغربي", "ويست باي", "الدفنة"),
}  # fmt: skip


NUM = r"(\d+(?:[.,]\d+)*)\s*(k|الف|ألف)?\s*"
AREA_UNITS = r"(?:sqm|sq\.?\s?m|m2|m²|square\s+met(?:er|re)s?|متر|م2)"
DISTANCE_UNITS = r"(?:km|kms|kilomet(?:er|re)s?|كم|كيلو)"
OTHER_UNITS = r"(?:gb|tb|جيجا|تيرا)"


def with_unit(query: str, units: str) -> set[float]:
    """Numbers the query writes directly before one of `units` ("150 sqm", "50,000 km")."""
    out = set()
    text = query.lower().translate(ARABIC_DIGITS)
    for digits, k in re.findall(NUM + units, text):
        value = float(digits.replace(",", ""))
        out.add(value * 1000 if k else value)
    return out


PRICE_LIMIT = re.compile(
    r"(?P<cmp>under|below|less than|cheaper than|max(?:imum)?|up to|budget(?: of)?|"
    r"around|about|approx(?:imately)?|roughly|over|above|more than|"
    r"أقل من|اقل من|تحت|حوالي|تقريبا|أكثر من|اكثر من|فوق)\s*"
    r"(?P<cur>\$|qar|qr|usd)?\s*"
    # (?![.,]?\d): take the whole number, so "50,000 km" can't backtrack to "50".
    r"(?P<num>\d+(?:[.,]\d+)*)(?![.,]?\d)\s*(?P<mult>k|m|million|الف|ألف|مليون)?\b"
    rf"(?!\s*(?:{AREA_UNITS}|{DISTANCE_UNITS}|{OTHER_UNITS}))",
    re.IGNORECASE,
)
COMPARATORS = {
    "around": PriceComparator.around, "about": PriceComparator.around,
    "roughly": PriceComparator.around, "حوالي": PriceComparator.around,
    "تقريبا": PriceComparator.around, "over": PriceComparator.over,
    "above": PriceComparator.over, "more than": PriceComparator.over,
    "أكثر من": PriceComparator.over, "اكثر من": PriceComparator.over, "فوق": PriceComparator.over,
}  # fmt: skip
PER_MONTH = re.compile(r"a month|per month|monthly|/\s*month|شهري|بالشهر|في الشهر", re.I)
PER_YEAR = re.compile(r"a year|per year|yearly|annual|/\s*year|سنوي|بالسنة|في السنة", re.I)
USD = re.compile(r"\$|\busd\b|dollars?", re.I)
BEDROOMS = re.compile(r"(\d+)\s*-?\s*(?:bed(?:room)?s?|br|bhk|غرف|غرفة)\b", re.I)
BEDROOM_WORDS = {"غرفتين": 2, "غرفتان": 2, "غرفة واحدة": 1}


def price_from_query(query: str) -> PriceIntent | None:
    """An explicit price limit, if the query states one in a standard form."""
    text = query.translate(ARABIC_DIGITS)
    match = PRICE_LIMIT.search(text)
    if not match:
        return None
    amount = Decimal(match["num"].replace(",", ""))
    mult = (match["mult"] or "").lower()
    if mult in ("k", "الف", "ألف"):
        amount *= 1000
    elif mult in ("m", "million", "مليون"):
        amount *= 1_000_000
    period = PricePeriod.month if PER_MONTH.search(text) else None
    period = PricePeriod.year if period is None and PER_YEAR.search(text) else period
    word = match["cmp"].lower()
    comparator = PriceComparator.around if word.startswith("approx") else COMPARATORS.get(word)
    return PriceIntent(
        comparator=comparator or PriceComparator.under,
        amount=amount,
        currency="USD" if USD.search(text) else "QAR",
        period=period,
    )


def bedrooms_from_query(query: str) -> int | None:
    text = query.translate(ARABIC_DIGITS)
    if match := BEDROOMS.search(text):
        return int(match[1])
    return next((n for word, n in BEDROOM_WORDS.items() if word in text), None)


def _location_named(location: str, query: str) -> bool:
    name = location.lower()
    q = query.lower()
    if name in q or name.removeprefix("al ") in q:
        return True
    if location in PLACE_NAMES_AR:
        return any(alias in query for alias in PLACE_NAMES_AR[location])
    return bool(ARABIC.search(query))  # unknown Arabic spelling: trust the LLM's mapping


def clean_parse(parse: QueryParse, query: str, catalog: Catalog) -> tuple[QueryParse, list[str]]:
    """Drop fields that are out of scope for the category or not grounded in the query."""
    category = parse.category
    allowed = GENERAL | SCOPED.get(category, set())
    if category in PROPERTY_CATEGORIES:
        allowed = allowed - {"condition"}  # property listings have no condition
    update: dict = {}
    dropped: list[str] = []

    def drop(field: str, reason: str) -> None:
        update[field] = QueryParse.model_fields[field].get_default(call_default_factory=True)
        dropped.append(f"{field}:{reason}")

    for field in QueryParse.model_fields:
        value = getattr(parse, field)
        if value is None or value is False or value == [] or field in allowed:
            continue
        drop(field, f"not for {category or 'unknown category'}")

    if category and parse.models:
        in_category = set(catalog.models_by_category.get(category, ()))
        if not set(parse.models) <= in_category:
            kept = [m for m in parse.models if m in in_category]
            update["models"] = kept
            dropped.append(f"models:{len(parse.models) - len(kept)} not in {category}")
    if (
        category
        and parse.property_type
        and "property_type" in allowed
        and parse.property_type not in catalog.property_types_by_category.get(category, ())
    ):
        drop("property_type", f"not a {category} type")

    stated, sized = numbers_in(query), sizes_in(query)
    areas, distances = with_unit(query, AREA_UNITS), with_unit(query, DISTANCE_UNITS)
    for field in NUMERIC:
        value = getattr(parse, field)
        if field in update or value is None:
            continue
        if field in ("storage_gb", "min_ram_gb"):
            # Sizes need their unit: "Dell XPS 13" is not 13 GB of storage.
            if float(value) not in sized:
                drop(field, "size not written with GB/TB")
            elif field == "storage_gb" and value < MIN_STORAGE_GB:
                drop(field, f"under {MIN_STORAGE_GB} GB is not a storage size")
        elif field in ("min_area_sqm", "max_area_sqm"):
            if float(value) not in areas:
                drop(field, "area not written with sqm/متر")
        elif field == "max_mileage_km":
            if float(value) not in distances:
                drop(field, "mileage not written with km")
        elif float(value) not in stated:
            drop(field, "number not in query")
    if parse.price is not None and "price" not in update:
        amounts = [parse.price.amount, parse.price.amount_max]
        if any(a is not None and float(a) not in stated for a in amounts):
            drop("price", "amount not in query")
    if parse.location and not _location_named(parse.location, query):
        drop("location", "not named in query")

    # Backstops: fill an empty field from an explicit, unambiguous phrase in the query.
    if update.get("price", parse.price) is None and (price := price_from_query(query)):
        update["price"] = price
        dropped.append("price:filled from query")
    if (
        "bedrooms" in allowed
        and update.get("bedrooms", parse.bedrooms) is None
        and parse.min_bedrooms is None
        and (beds := bedrooms_from_query(query)) is not None
    ):
        update["bedrooms"] = beds
        dropped.append("bedrooms:filled from query")

    return parse.model_copy(update=update), dropped
