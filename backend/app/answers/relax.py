"""Honest "no matches" (Stage 7): which single constraint to relax, from real counts.

When a search finds nothing, every filter is dropped one at a time and the matches are
counted, all in one SQL round trip (`count(*) filter (where ...)` per variant). The reply is
then built from those counts, so the suggestion is a fact, not an LLM guess.
"""

import re
from dataclasses import dataclass
from decimal import Decimal

import asyncpg

from app.models.filters import SearchFilters
from app.retrieval.filters_sql import build_where

ARABIC = re.compile(r"[؀-ۿ]")

# Constraint -> (English, Arabic) phrase for "without ...".
LABELS = {
    "price": ("the price limit", "حد السعر"),
    "location": ("the location", "الموقع"),
    "conditions": ("the condition", "شرط الحالة"),
    "models": ("the model", "الموديل"),
    "brands": ("the brand", "الماركة"),
    "listing_type": ("sale or rent", "نوع العرض (بيع أو إيجار)"),
    "attr:bedrooms": ("the bedroom count", "عدد الغرف"),
    "attr:mileage_km": ("the mileage limit", "حد الممشى"),
    "attr:year": ("the model year", "سنة الصنع"),
    "attr:storage_gb": ("the storage size", "سعة التخزين"),
    "attr:ram_gb": ("the RAM size", "حجم الرام"),
    "attr:furnished": ("the furnishing", "الفرش"),
    "attr:amenities": ("the amenities", "المرافق"),
    "attr:private_pool": ("the private pool", "المسبح الخاص"),
    "attr:property_type": ("the property type", "نوع العقار"),
    "attr:item_type": ("the item type", "نوع القطعة"),
    "attr:area_sqm": ("the area", "المساحة"),
    "attr:gcc_specs": ("GCC specs", "المواصفات الخليجية"),
    "attr:accident_free": ("accident-free", "بدون حوادث"),
    "attr:delivery_available": ("delivery", "التوصيل"),
}


@dataclass(frozen=True)
class Relaxation:
    constraint: str
    count: int


def relaxed_variants(filters: SearchFilters) -> list[tuple[str, SearchFilters]]:
    """Each applied constraint removed once. Category is never relaxed."""
    out: list[tuple[str, SearchFilters]] = []
    if filters.min_price is not None or filters.max_price is not None:
        out.append(("price", filters.model_copy(update={"min_price": None, "max_price": None})))
    for field, empty in (("location", None), ("conditions", []), ("models", []),
                         ("brands", []), ("listing_type", None)):  # fmt: skip
        if getattr(filters, field):
            out.append((field, filters.model_copy(update={field: empty})))
    for key in sorted(filters.attributes):
        rest = {k: v for k, v in filters.attributes.items() if k != key}
        out.append((f"attr:{key}", filters.model_copy(update={"attributes": rest})))
    return out


async def relax_counts(
    conn: asyncpg.Connection, filters: SearchFilters, rates: dict[str, Decimal]
) -> list[Relaxation]:
    variants = relaxed_variants(filters)
    if not variants:
        return []
    columns, params = [], []
    for i, (_, relaxed) in enumerate(variants):
        clauses, p = build_where(relaxed, rates, first_param=len(params) + 1)
        params += p
        where = " and ".join(clauses) or "true"
        columns.append(f"count(*) filter (where {where}) as v{i}")
    row = await conn.fetchrow(f"select {', '.join(columns)} from listings", *params)
    return [Relaxation(name, row[f"v{i}"]) for i, (name, _) in enumerate(variants)]


def no_match_message(query: str, relaxations: list[Relaxation], limit: int = 2) -> str:
    """Grounded reply for an empty result: up to `limit` relaxations that would find listings."""
    arabic = bool(ARABIC.search(query))
    useful = sorted((r for r in relaxations if r.count > 0), key=lambda r: -r.count)[:limit]
    if arabic:
        head = "لا يوجد إعلان يطابق كل الشروط المطلوبة."
        if not useful:
            return head + " جرّب تخفيف أكثر من شرط أو تغيير الفئة."
        parts = [f"بدون {LABELS.get(r.constraint, (r.constraint,) * 2)[1]} يوجد {r.count}"
                 for r in useful]  # fmt: skip
        return head + " " + "، و".join(parts) + "."
    head = "Nothing matches all of your filters."
    if not useful:
        return head + " Try relaxing more than one constraint, or a different category."
    parts = [
        f"without {LABELS.get(r.constraint, (r.constraint,))[0]} there "
        f"{'is' if r.count == 1 else 'are'} {r.count}"
        for r in useful
    ]
    return head + " " + "; ".join(parts).capitalize() + "."
