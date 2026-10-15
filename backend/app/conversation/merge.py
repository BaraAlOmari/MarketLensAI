"""Merging a follow-up into the conversation's filters (Stage 8).

The LLM only reads the new message (a context-free "delta", so its cache entry is valid in
any conversation). These rules, in code, decide how the delta changes the saved filters:

- a different category starts a new search (only the delta is kept);
- a field the delta sets replaces the old value ("actually under 25000" overrides 20000);
  fields it does not mention are kept ("under 2000 riyals" keeps phone + model + used);
- attributes are merged key by key; keywords are combined;
- a new brand drops models of other brands ("what about Samsung?" drops "iPhone 15 Pro Max");
  new models drop a brand they do not belong to;
- "cheaper" sets the price ceiling just below the median price of everything that matched
  the previous search (computed in SQL, see `median_price`);
- "start over" (or an Arabic equivalent) clears the conversation.
"""

import re
from decimal import Decimal

import asyncpg

from app.models.filters import SearchFilters
from app.models.listing import PROPERTY_CATEGORIES, ListingType, PricePeriod
from app.retrieval.catalog import Catalog
from app.retrieval.filters_sql import build_where

# Only at the start of a message: "factory reset iPhone" is a product search, not a reset.
RESET = re.compile(
    r"^\s*(?:(?:ok(?:ay)?|please|let'?s|lets)[\s,]+)*"
    r"(?:start over|start again|new search|reset|clear (?:the )?(?:filters|search)"
    r"|ابدأ من جديد|ابدا من جديد|نبدأ من جديد|بحث جديد|امسح البحث)\b[\s,.;:!?،-]*",
    re.IGNORECASE,
)
CHEAPER = re.compile(
    r"\b(?:cheaper|less expensive|lower price[sd]?|more affordable|budget options?)\b"
    r"|أرخص|ارخص|اقل سعر|أقل سعر",
    re.IGNORECASE,
)
MAX_KEYWORDS = 8
JUST_BELOW = Decimal("0.001")  # prices have 2 decimals, so <= median - 0.001 means < median


def split_reset(message: str) -> tuple[bool, str]:
    """(reset?, what is left of the message after the reset phrase)."""
    if not RESET.search(message):
        return False, message
    rest = RESET.sub(" ", message)
    rest = re.sub(r"^[\s,.;:!?،-]+|[\s,.;:!?،-]+$", "", rest)
    rest = re.sub(r"^(?:and|then|now|و)\s+", "", rest, flags=re.IGNORECASE)
    return True, rest.strip()


def wants_cheaper(message: str) -> bool:
    return bool(CHEAPER.search(message))


COMPARABLE_PRICE = "(case when price_period = 'year' then price_qar / 12 else price_qar end)"


async def median_price(
    conn: asyncpg.Connection, filters: SearchFilters, rates: dict[str, Decimal]
) -> Decimal | None:
    """Median comparable price (QAR; yearly rent / 12) of everything matching `filters`."""
    clauses, params = build_where(filters, rates, first_param=1)
    where = " and ".join(clauses) or "true"
    value = await conn.fetchval(
        f"select percentile_cont(0.5) within group (order by {COMPARABLE_PRICE}) "
        f"from listings where {where}",
        *params,
    )
    return Decimal(str(value)) if value is not None else None


def merge(
    prev: SearchFilters | None,
    delta: SearchFilters | None,
    catalog: Catalog | None,
    cheaper_than: Decimal | None = None,
) -> tuple[SearchFilters | None, list[str]]:
    """Combine the saved filters with a follow-up. Returns (filters, notes on what changed)."""
    notes: list[str] = []
    brand_by_model = catalog.brand_by_model if catalog is not None else {}
    if prev is None or prev.is_empty():
        merged = delta
        if merged is not None:
            notes.append("new search")
    elif delta is None:
        merged = prev  # extraction failed: keep the conversation's filters
        notes.append("kept previous filters (no extraction)")
    elif delta.category and delta.category != prev.category:
        merged = delta
        notes.append(f"new category: {delta.category}")
    else:
        update: dict = {}
        if delta.min_price is not None or delta.max_price is not None:
            update.update(min_price=delta.min_price, max_price=delta.max_price,
                          currency=delta.currency, price_period=delta.price_period)  # fmt: skip
            notes.append("price replaced")
        for field in ("listing_type", "location"):
            if getattr(delta, field):
                update[field] = getattr(delta, field)
                notes.append(f"{field} set")
        if delta.conditions:
            update["conditions"] = delta.conditions
            notes.append("condition set")
        if delta.brands:
            update["brands"] = delta.brands
            if not delta.models:
                kept = [m for m in prev.models if brand_by_model.get(m) in delta.brands]
                if kept != prev.models:
                    notes.append("models of other brands dropped")
                update["models"] = kept
            notes.append("brand set")
        if delta.models:
            update["models"] = delta.models
            brands = {brand_by_model.get(m) for m in delta.models}
            if not delta.brands and prev.brands and not brands & set(prev.brands):
                update["brands"] = []
            notes.append("models set")
        if delta.attributes:
            update["attributes"] = {**prev.attributes, **delta.attributes}
            notes.append("attributes: " + ", ".join(sorted(delta.attributes)))
        if delta.keywords:
            combined = list(dict.fromkeys([*prev.keywords, *delta.keywords]))[:MAX_KEYWORDS]
            update["keywords"] = combined
        merged = prev.model_copy(update=update)
        # A rent price without a period is per month (same rule as parse_to_filters).
        if (
            merged.listing_type == ListingType.rent
            and merged.category in PROPERTY_CATEGORIES
            and merged.max_price is not None
            and merged.price_period in (None, PricePeriod.total)
        ):
            merged = merged.model_copy(update={"price_period": PricePeriod.month})
        if not update:
            notes.append("nothing new to merge")

    explicit_price = delta is not None and (
        delta.min_price is not None or delta.max_price is not None
    )
    if cheaper_than is not None and merged is not None and explicit_price:
        notes.append("cheaper: explicit price used instead of the median")
    elif cheaper_than is not None and merged is not None:
        rent = merged.listing_type == ListingType.rent and merged.category in PROPERTY_CATEGORIES
        merged = merged.model_copy(
            update={
                "max_price": cheaper_than - JUST_BELOW,
                "currency": "QAR",
                "price_period": PricePeriod.month if rent else None,
            }
        )
        notes.append(f"cheaper: below median {cheaper_than:.0f} QAR")
    return merged, notes


def describe(filters: SearchFilters) -> str:
    """Retrieval text for filters the person edited by hand: only what is still asked for.

    The old message would keep ranking by what was removed ("iPhone 17" pulls 17 Pro/Max to
    the top after the model token is gone), so an edit searches with the remaining filters.
    Prices are left out: they are SQL bounds and carry no meaning for embeddings.
    """
    parts: list[str] = []
    if filters.conditions:
        parts.append(" or ".join(c.value.replace("_", " ") for c in filters.conditions))
    parts += [" or ".join(filters.brands), " or ".join(filters.models)]
    if filters.category:
        parts.append(filters.category)
    if filters.listing_type:
        parts.append(f"for {filters.listing_type.value}")
    if filters.location:
        parts.append(f"in {filters.location}")
    for key, rule in filters.attributes.items():
        name = key.replace("_", " ")
        if rule.eq is not None:
            value = str(rule.eq)
            parts.append(name if rule.eq is True else value if name in value else f"{value} {name}")
        elif rule.any_of or rule.contains:
            parts.append(f"{name} {' '.join(rule.any_of or rule.contains or [])}")
        elif rule.min is not None or rule.max is not None:
            parts.append(f"{name} {rule.min or ''}-{rule.max or ''}".strip())
    return " ".join(p for p in parts if p)


def drop_removed_keywords(previous: SearchFilters | None, edited: SearchFilters) -> SearchFilters:
    """Keyword search terms that belonged to a removed brand or model go with it."""
    if previous is None or not edited.keywords:
        return edited
    kept = {t.lower() for t in edited.brands + edited.models}
    removed = [t.lower() for t in previous.brands + previous.models if t.lower() not in kept]
    keywords = [k for k in edited.keywords
                if not any(k.lower() in r or r in k.lower() for r in removed)]  # fmt: skip
    return edited.model_copy(update={"keywords": keywords})
