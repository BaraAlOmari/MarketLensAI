"""Currency normalization. Prices keep their listed currency; price_qar is used for filtering."""

from decimal import ROUND_HALF_UP, Decimal


class UnknownCurrencyError(ValueError):
    pass


def to_qar(amount: Decimal, currency: str, rates_to_qar: dict[str, Decimal]) -> Decimal:
    try:
        rate = rates_to_qar[currency.upper()]
    except KeyError:
        raise UnknownCurrencyError(f"no FX rate configured for {currency!r}") from None
    return (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def from_qar(amount_qar: Decimal, currency: str, rates_to_qar: dict[str, Decimal]) -> Decimal:
    try:
        rate = rates_to_qar[currency.upper()]
    except KeyError:
        raise UnknownCurrencyError(f"no FX rate configured for {currency!r}") from None
    return (amount_qar / rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
