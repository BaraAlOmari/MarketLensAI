"""The values that actually exist in `listings`: categories, brands, models, locations, ...

They become `enum`s in the LLM's response schema, so the model can only name things a
filter can match ("G63" must come back as the catalog's "G 63 AMG", "لوسيل" as "Lusail").
Loaded once at startup; reload the app after loading a new dataset.
"""

import hashlib
import json
from dataclasses import asdict, dataclass

import asyncpg


@dataclass(frozen=True)
class Catalog:
    categories: tuple[str, ...]
    brands: tuple[str, ...]
    models_by_category: dict[str, tuple[str, ...]]
    item_types: tuple[str, ...]
    property_types_by_category: dict[str, tuple[str, ...]]
    locations: tuple[str, ...]
    furnished: tuple[str, ...]
    amenities: tuple[str, ...]

    @property
    def models(self) -> tuple[str, ...]:
        return tuple(sorted({m for ms in self.models_by_category.values() for m in ms}))

    @property
    def property_types(self) -> tuple[str, ...]:
        return tuple(sorted({t for ts in self.property_types_by_category.values() for t in ts}))

    def fingerprint(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


async def load_catalog(conn: asyncpg.Connection) -> Catalog:
    async def values(sql: str) -> tuple[str, ...]:
        return tuple(sorted(r[0] for r in await conn.fetch(sql) if r[0]))

    async def by_category(expr: str) -> dict[str, tuple[str, ...]]:
        grouped: dict[str, list[str]] = {}
        sql = f"select distinct category, {expr} as v from listings order by 1, 2"
        for r in await conn.fetch(sql):
            if r["v"]:
                grouped.setdefault(r["category"], []).append(r["v"])
        return {c: tuple(vs) for c, vs in grouped.items()}

    return Catalog(
        categories=await values("select distinct category from listings"),
        brands=await values("select distinct brand from listings"),
        models_by_category=await by_category("model"),
        item_types=await values("select distinct attributes ->> 'item_type' from listings"),
        property_types_by_category=await by_category("attributes ->> 'property_type'"),
        # Neighbourhoods plus the first part of every location ("West Bay" of "West Bay, Doha").
        locations=await values(
            """select distinct attributes ->> 'neighborhood' from listings
               union select distinct split_part(location, ',', 1) from listings"""
        ),
        furnished=await values("select distinct attributes ->> 'furnished' from listings"),
        amenities=await values(
            """select distinct jsonb_array_elements_text(attributes -> 'amenities')
               from listings where jsonb_typeof(attributes -> 'amenities') = 'array'"""
        ),
    )
