"""SearchFilters -> SQL WHERE clauses. Every value is a bind parameter; nothing is formatted
into the SQL text except fixed column names and operators chosen here."""

import json
from decimal import Decimal

from app.currency import UnknownCurrencyError
from app.models.filters import AttributeFilter, SearchFilters
from app.models.listing import PricePeriod

# Rents compared per month (yearly rents count as yearly / 12) or per year.
MONTHLY_PRICE = "(case price_period when 'year' then price_qar / 12 else price_qar end)"
YEARLY_PRICE = "(case price_period when 'month' then price_qar * 12 else price_qar end)"


def escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class WhereBuilder:
    def __init__(self, first_param: int) -> None:
        self.first_param = first_param
        self.clauses: list[str] = []
        self.params: list = []

    def param(self, value) -> str:
        self.params.append(value)
        return f"${self.first_param + len(self.params) - 1}"

    def add(self, clause: str) -> None:
        self.clauses.append(clause)


def _attribute_clause(w: WhereBuilder, key: str, rule: AttributeFilter) -> str:
    k = w.param(key)
    if rule.eq is not None:
        # jsonb equality handles numbers, strings and booleans alike: 2 = 2, "x" = "x".
        return f"attributes -> {k} = {w.param(json.dumps(rule.eq))}::jsonb"
    if rule.any_of is not None:
        return f"attributes ->> {k} = any({w.param(rule.any_of)}::text[])"
    if rule.contains is not None:
        return f"attributes -> {k} ?& {w.param(rule.contains)}::text[]"
    # min / max: compare only real numbers, so a stray string never raises a cast error.
    number = (
        f"(case when jsonb_typeof(attributes -> {k}) = 'number' "
        f"then (attributes ->> {k})::numeric end)"
    )
    parts = []
    if rule.min is not None:
        parts.append(f"{number} >= {w.param(rule.min)}")
    if rule.max is not None:
        parts.append(f"{number} <= {w.param(rule.max)}")
    return " and ".join(parts)


def build_where(
    filters: SearchFilters, rates_to_qar: dict[str, Decimal], first_param: int
) -> tuple[list[str], list]:
    """Clauses (to AND together) and their parameters, numbered from `first_param`.

    A row missing a filtered attribute never matches: unknown is not a yes.
    """
    w = WhereBuilder(first_param)
    if filters.category:
        w.add(f"category = {w.param(filters.category)}")
    if filters.brands:
        w.add(f"brand = any({w.param(filters.brands)}::text[])")
    if filters.models:
        w.add(f"model = any({w.param(filters.models)}::text[])")
    if filters.conditions:
        values = [c.value for c in filters.conditions]
        w.add(f"condition = any({w.param(values)}::listing_condition[])")
    if filters.listing_type:
        w.add(f"listing_type = {w.param(filters.listing_type.value)}::listing_type")
    if filters.location:
        pattern = w.param(f"%{escape_like(filters.location)}%")
        w.add(f"(location ilike {pattern} or attributes ->> 'neighborhood' ilike {pattern})")

    if filters.min_price is not None or filters.max_price is not None:
        rate = rates_to_qar.get(filters.currency.upper())
        if rate is None:
            raise UnknownCurrencyError(f"no FX rate configured for {filters.currency!r}")
        price = {PricePeriod.month: MONTHLY_PRICE, PricePeriod.year: YEARLY_PRICE}.get(
            filters.price_period, "price_qar"
        )
        if filters.min_price is not None:
            w.add(f"{price} >= {w.param(filters.min_price * rate)}")
        if filters.max_price is not None:
            w.add(f"{price} <= {w.param(filters.max_price * rate)}")

    for key, rule in sorted(filters.attributes.items()):
        w.add(_attribute_clause(w, key, rule))
    return w.clauses, w.params
