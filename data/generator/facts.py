"""Deterministic listing facts. Python decides every structured field; an LLM (or the
template writer) only writes title + description. That keeps ground truth reliable.
"""

import random
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.currency import from_qar
from generator import catalog as cat
from generator.locales import Locale

ANCHOR = datetime(2026, 10, 1, tzinfo=UTC)  # fixed, so reruns are reproducible

DEFAULT_CATEGORY_COUNTS = {
    "phones": 420,
    "laptops": 330,
    "cars": 360,
    "furniture": 320,
    "apartments": 420,
    "villas": 250,
}

CONDITION_WEIGHTS = {"new": 0.14, "like_new": 0.30, "good": 0.31, "fair": 0.18, "poor": 0.07}
CONDITION_VALUE = {"new": 1.0, "like_new": 0.84, "good": 0.71, "fair": 0.56, "poor": 0.36}
FURNITURE_CONDITION_VALUE = {"new": 0.95, "like_new": 0.65, "good": 0.5, "fair": 0.35, "poor": 0.2}

# Messiness hints for the text writer; each listing gets one or two.
STYLES = ("terse", "typos", "abbrev", "caps", "detailed", "emoji", "partial", "casual")
STYLE_WEIGHTS = (0.18, 0.16, 0.18, 0.08, 0.12, 0.08, 0.12, 0.08)

NEAR_DUPLICATE_RATE = 0.05
OUTLIER_RATE = 0.03


@dataclass
class ListingFacts:
    external_id: str
    category: str
    item_label: str  # short human name, e.g. "iPhone 17 Pro 256GB"
    brand: str | None
    model: str | None
    condition: str | None
    listing_type: str
    price_period: str
    price_qar: Decimal
    price: Decimal
    currency: str
    attributes: dict[str, Any]
    location: str
    seller_name: str
    seller_kind: str  # individual / dealer / agency
    language: str
    styles: list[str]
    omit: list[str]  # attribute keys the text should not mention (partial specs)
    created_at: datetime
    near_duplicate_of: str | None = None
    tags: list[str] = field(default_factory=list)  # e.g. "underpriced", "overpriced"


def weighted(rng: random.Random, weights: dict[str, float]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def nice_price(x: float, rng: random.Random, retail_style: bool = False) -> Decimal:
    """Round like a human seller would: 2,450 / 87,000 / 1,250,000, sometimes 2,499."""
    steps = ((100, 5), (1_000, 25), (10_000, 50), (100_000, 500), (1_000_000, 1_000))
    step = next((s for limit, s in steps if x < limit), 10_000)
    value = max(step, round(x / step) * step)
    if retail_style and value >= 200 and rng.random() < 0.15:
        value -= 1  # 2,500 -> 2,499
    return Decimal(value)


def condition_for(rng: random.Random) -> str:
    return weighted(rng, CONDITION_WEIGHTS)


def price_noise(rng: random.Random) -> float:
    return rng.uniform(0.88, 1.12)


def maybe_outlier(rng: random.Random, value: float, tags: list[str]) -> float:
    roll = rng.random()
    if roll < OUTLIER_RATE / 2:
        tags.append("underpriced")
        return value * rng.uniform(0.55, 0.7)
    if roll < OUTLIER_RATE:
        tags.append("overpriced")
        return value * rng.uniform(1.3, 1.5)
    return value


def seller(rng: random.Random, locale: Locale, business_kind: str | None) -> tuple[str, str]:
    if business_kind:
        a, b = (rng.choice(words) for words in locale.business_words)
        return f"{a} {b} {business_kind}", "dealer" if business_kind == "Motors" else "agency"
    return f"{rng.choice(locale.first_names)} {rng.choice(locale.last_initials)}.", "individual"


def drop_some(rng: random.Random, attrs: dict[str, Any], optional: tuple[str, ...]) -> None:
    """Real sellers skip form fields: randomly drop optional attributes."""
    for key in optional:
        if key in attrs and rng.random() < 0.15:
            del attrs[key]


# ---------------------------------------------------------------- per-category builders


def build_phone(rng: random.Random) -> dict[str, Any]:
    p = rng.choice(cat.PHONES)
    storage_idx = rng.randrange(len(p.storages))
    storage = p.storages[storage_idx]
    condition = condition_for(rng)
    age = cat.DATASET_YEAR - p.year
    step = 500 if p.brand == "Apple" else 400
    value = (p.base_qar + step * storage_idx) * (0.8**age) * CONDITION_VALUE[condition]
    attrs: dict[str, Any] = {
        "storage_gb": storage,
        "color": rng.choice(p.colors),
        "year": p.year,
        "sim": rng.choice(("dual sim", "esim only", "nano sim + esim")),
        "box_included": rng.random() < 0.55,
        "warranty": condition in ("new", "like_new") and rng.random() < 0.5,
    }
    if p.brand == "Apple":
        attrs["battery_health"] = 100 if condition == "new" else rng.randint(78, 100 - 3 * age)
    drop_some(rng, attrs, ("color", "sim", "battery_health"))
    label = f"{p.model} {storage // 1024}TB" if storage >= 1024 else f"{p.model} {storage}GB"
    return dict(
        brand=p.brand, model=p.model, condition=condition, value=value, attrs=attrs,
        label=label, retail=True, business=None,
    )  # fmt: skip


def build_laptop(rng: random.Random) -> dict[str, Any]:
    lp = rng.choice(cat.LAPTOPS)
    ram_idx, sto_idx = rng.randrange(len(lp.rams)), rng.randrange(len(lp.storages))
    condition = condition_for(rng)
    age = cat.DATASET_YEAR - lp.year
    value = lp.base_qar * (1 + 0.18 * ram_idx + 0.15 * sto_idx) * (0.82**age)
    value *= CONDITION_VALUE[condition]
    attrs: dict[str, Any] = {
        "cpu": lp.cpu,
        "ram_gb": lp.rams[ram_idx],
        "storage_gb": lp.storages[sto_idx],
        "screen_in": lp.screen_in,
        "year": lp.year,
        "charger_included": rng.random() < 0.85,
    }
    if lp.gpu:
        attrs["gpu"] = lp.gpu
    if condition != "new":
        attrs["battery_cycles"] = rng.randint(5, 120 + 250 * age)
    drop_some(rng, attrs, ("cpu", "battery_cycles", "screen_in"))
    return dict(
        brand=lp.brand, model=lp.model, condition=condition, value=value, attrs=attrs,
        label=f"{lp.brand} {lp.model} {lp.rams[ram_idx]}GB/{lp.storages[sto_idx]}GB",
        retail=True, business=None,
    )  # fmt: skip


def build_car(rng: random.Random) -> dict[str, Any]:
    c = rng.choice(cat.CARS)
    condition = condition_for(rng)
    if condition == "new":
        year, mileage = rng.choice((2025, 2026)), rng.randint(0, 400)
    else:
        year = rng.randint(max(c.first_year, 2012), 2026)
        age = cat.DATASET_YEAR - year
        mileage = int(max(age, 0.3) * rng.uniform(9_000, 28_000))
        if condition in ("fair", "poor"):
            mileage = int(mileage * rng.uniform(1.2, 1.6))
    age = cat.DATASET_YEAR - year
    value = c.new_qar * (0.86**age) * {"new": 1.0, "like_new": 0.95, "good": 0.88,
                                       "fair": 0.75, "poor": 0.55}[condition]  # fmt: skip
    attrs: dict[str, Any] = {
        "year": year,
        "mileage_km": round(mileage, -2) if mileage > 1000 else mileage,
        "transmission": "manual" if rng.random() < 0.06 else "automatic",
        "fuel": c.fuel,
        "color": rng.choice(cat.CAR_COLORS),
        "trim": rng.choice(c.trims),
        "gcc_specs": rng.random() < 0.85,
        "accident_free": condition != "poor" and rng.random() < 0.8,
        "service_history": rng.choice(("agency", "agency", "outside", "unknown")),
    }
    if c.cylinders:
        attrs["cylinders"] = c.cylinders
    drop_some(rng, attrs, ("color", "service_history", "cylinders", "trim"))
    business = "Motors" if rng.random() < 0.25 else None
    return dict(
        brand=c.brand, model=c.model, condition=condition, value=value, attrs=attrs,
        label=f"{year} {c.brand} {c.model}", retail=False, business=business,
    )  # fmt: skip


def build_furniture(rng: random.Random) -> dict[str, Any]:
    f = rng.choice(cat.FURNITURE)
    condition = condition_for(rng)
    lo, hi = f.new_qar_range
    value = rng.uniform(lo, hi) * FURNITURE_CONDITION_VALUE[condition]
    brand = rng.choice(f.brands) or None
    attrs: dict[str, Any] = {
        "item_type": f.item_type,
        "material": rng.choice(f.materials),
        "color": rng.choice(cat.FURNITURE_COLORS),
        "delivery_available": rng.random() < 0.3,
    }
    if f.sizes:
        attrs["size"] = rng.choice(f.sizes)
    drop_some(rng, attrs, ("material", "color", "size"))
    return dict(
        brand=brand, model=None, condition=condition, value=value, attrs=attrs,
        label=f"{brand + ' ' if brand else ''}{f.item_type}", retail=False, business=None,
    )  # fmt: skip


def _property_area(rng: random.Random, locale: Locale, sale: bool) -> tuple[str, str, int]:
    areas = [(n, v) for n, v in locale.property_areas.items() if v[2] or not sale]
    name, (city, tier, _) = rng.choice(areas)
    return name, city, tier


def build_apartment(rng: random.Random, locale: Locale) -> dict[str, Any]:
    sale = rng.random() < 0.25
    area, city, tier = _property_area(rng, locale, sale)
    beds = rng.choices((0, 1, 2, 3, 4), weights=(0.12, 0.3, 0.3, 0.2, 0.08))[0]
    ptype = "studio" if beds == 0 else rng.choices(
        ("apartment", "penthouse", "duplex"), weights=(0.88, 0.06, 0.06))[0]  # fmt: skip
    sqm = int((38 if beds == 0 else 40 + 52 * beds) * rng.uniform(0.85, 1.25))
    if ptype != "apartment" and beds:
        sqm = int(sqm * 1.4)
    attrs: dict[str, Any] = {
        "property_type": ptype,
        "bedrooms": beds,
        "bathrooms": max(1, beds + rng.choice((0, 0, 1))),
        "area_sqm": sqm,
        "furnished": rng.choice(("furnished", "semi-furnished", "unfurnished")),
        "floor": rng.randint(1, 45 if tier >= 3 else 12),
        "neighborhood": area,
        "amenities": rng.sample(("pool", "gym", "parking", "balcony", "sea view",
                                 "security", "kids play area", "maid room"), k=rng.randint(1, 4)),
        "bills_included": not sale and rng.random() < 0.35,
    }  # fmt: skip
    if sale:
        value = sqm * cat.APARTMENT_SALE_PER_SQM[tier] * rng.uniform(0.85, 1.2)
        listing_type, period = "sale", "total"
    else:
        value = cat.APARTMENT_RENT_BY_BEDS[beds] * cat.TIER_RENT_MULTIPLIER[tier] * price_noise(rng)
        if ptype in ("penthouse", "duplex"):
            value *= 1.5
        if attrs["furnished"] == "furnished":
            value *= 1.12
        listing_type, period = "rent", "month"
        if rng.random() < 0.12:
            value, period = value * 12 * 0.95, "year"
    drop_some(rng, attrs, ("floor", "bathrooms", "amenities"))
    business = "Realty" if rng.random() < 0.55 else None
    label = f"{'studio' if beds == 0 else f'{beds}BR {ptype}'} in {area}"
    return dict(
        brand=None, model=None, condition=None, value=value, attrs=attrs, label=label,
        retail=False, business=business, listing_type=listing_type, period=period,
        location=area if area == city else f"{area}, {city}",
    )  # fmt: skip


def build_villa(rng: random.Random, locale: Locale) -> dict[str, Any]:
    sale = rng.random() < 0.3
    area, city, tier = _property_area(rng, locale, sale)
    beds = rng.choices((3, 4, 5, 6, 7), weights=(0.18, 0.3, 0.27, 0.17, 0.08))[0]
    ptype = rng.choices(("villa", "townhouse", "compound villa"), weights=(0.6, 0.15, 0.25))[0]
    sqm = int((150 + 85 * beds) * rng.uniform(0.85, 1.3))
    attrs: dict[str, Any] = {
        "property_type": ptype,
        "bedrooms": beds,
        "bathrooms": beds + rng.choice((0, 1, 1, 2)),
        "area_sqm": sqm,
        "furnished": rng.choice(("furnished", "semi-furnished", "unfurnished", "unfurnished")),
        "neighborhood": area,
        "private_pool": rng.random() < 0.35,
        "maid_room": rng.random() < 0.7,
        "garden": rng.random() < 0.6,
    }
    if sale:
        value = sqm * cat.VILLA_SALE_PER_SQM[tier] * rng.uniform(0.85, 1.25)
        listing_type, period = "sale", "total"
    else:
        value = cat.VILLA_RENT_BY_BEDS[beds] * cat.TIER_RENT_MULTIPLIER[tier] * price_noise(rng)
        if ptype == "compound villa":
            value *= 1.15
        listing_type, period = "rent", "month"
        if rng.random() < 0.2:
            value, period = value * 12 * 0.95, "year"
    drop_some(rng, attrs, ("bathrooms", "garden", "maid_room"))
    business = "Properties" if rng.random() < 0.6 else None
    return dict(
        brand=None, model=None, condition=None, value=value, attrs=attrs,
        label=f"{beds}BR {ptype} in {area}", retail=False, business=business,
        listing_type=listing_type, period=period,
        location=area if area == city else f"{area}, {city}",
    )  # fmt: skip


BUILDERS = {
    "phones": lambda rng, loc: build_phone(rng),
    "laptops": lambda rng, loc: build_laptop(rng),
    "cars": lambda rng, loc: build_car(rng),
    "furniture": lambda rng, loc: build_furniture(rng),
    "apartments": build_apartment,
    "villas": build_villa,
}

PARTIAL_OMIT_CANDIDATES = (
    "storage_gb", "ram_gb", "color", "year", "mileage_km", "battery_health", "trim",
    "area_sqm", "bathrooms", "floor", "material", "size",
)  # fmt: skip


# ---------------------------------------------------------------------------- assembly


def generate_facts(
    locale: Locale,
    seed: int = 42,
    counts: dict[str, int] | None = None,
    rates_to_qar: dict[str, Decimal] | None = None,
) -> list[ListingFacts]:
    """Same (locale, seed, counts) -> identical output, which makes generation resumable."""
    from app.config import DEFAULT_FX_RATES_TO_QAR

    rates = rates_to_qar or DEFAULT_FX_RATES_TO_QAR
    counts = counts or DEFAULT_CATEGORY_COUNTS
    rng = random.Random(seed)
    out: list[ListingFacts] = []

    for category, n in counts.items():
        for _ in range(n):
            built = BUILDERS[category](rng, locale)
            tags: list[str] = []
            value = built["value"]
            if category not in ("apartments", "villas"):  # property builders add their own noise
                value *= price_noise(rng)
            value_qar = maybe_outlier(rng, value, tags)
            currency = weighted(rng, locale.currency_mix)
            raw = float(from_qar(Decimal(str(round(value_qar, 2))), currency, rates))
            price = nice_price(raw, rng, retail_style=built["retail"])
            price_qar = (price * rates[currency]).quantize(Decimal("0.01"))
            seller_name, seller_kind = seller(rng, locale, built["business"])
            styles = rng.choices(STYLES, weights=STYLE_WEIGHTS, k=rng.choice((1, 1, 2)))
            styles = list(dict.fromkeys(styles))
            omit = []
            if "partial" in styles:
                keys = [k for k in PARTIAL_OMIT_CANDIDATES if k in built["attrs"]]
                omit = rng.sample(keys, k=min(len(keys), rng.randint(1, 2)))
            location = built.get("location") or weighted(rng, dict(locale.locations))
            out.append(
                ListingFacts(
                    external_id="",
                    category=category,
                    item_label=built["label"],
                    brand=built["brand"],
                    model=built["model"],
                    condition=built["condition"],
                    listing_type=built.get("listing_type", "sale"),
                    price_period=built.get("period", "total"),
                    price_qar=price_qar,
                    price=price,
                    currency=currency,
                    attributes=built["attrs"],
                    location=location,
                    seller_name=seller_name,
                    seller_kind=seller_kind,
                    language=weighted(rng, locale.languages),
                    styles=styles,
                    omit=omit,
                    created_at=ANCHOR - timedelta(minutes=rng.randint(60, 120 * 24 * 60)),
                    tags=tags,
                )
            )

    # Near-duplicates: the same item reposted, slightly changed.
    originals = list(out)
    pairs: list[tuple[ListingFacts, ListingFacts]] = []
    for orig in rng.sample(originals, k=int(len(originals) * NEAR_DUPLICATE_RATE)):
        factor = Decimal(str(round(rng.uniform(0.94, 1.03), 3)))
        price = nice_price(float(orig.price * factor), rng)
        dup = replace(
            orig,
            attributes=dict(orig.attributes),
            price=price,
            price_qar=(price * rates[orig.currency]).quantize(Decimal("0.01")),
            styles=rng.choices(STYLES, weights=STYLE_WEIGHTS, k=1),
            omit=[],
            created_at=orig.created_at + timedelta(days=rng.randint(1, 14)),
            tags=["near_duplicate"],
        )
        pairs.append((dup, orig))
        out.append(dup)

    rng.shuffle(out)
    for i, f in enumerate(out, start=1):
        f.external_id = f"syn-{locale.code}-{i:05d}"
    for dup, orig in pairs:
        dup.near_duplicate_of = orig.external_id
    return out
