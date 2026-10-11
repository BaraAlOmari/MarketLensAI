import json
from decimal import Decimal

import pytest

from app.config import DEFAULT_FX_RATES_TO_QAR
from app.currency import UnknownCurrencyError, from_qar, to_qar
from app.ingestion.source import SyntheticListingSource, build_search_text
from app.models.listing import NormalizedListing

PHONE = {
    "source": "synthetic",
    "external_id": "syn-qa-00001",
    "title": "iphone 17 pro 256gb like new",
    "description": "barely used, comes w/ box. battery 98%",
    "category": "phones",
    "brand": "Apple",
    "model": "iPhone 17 Pro",
    "price": "3900",
    "currency": "QAR",
    "condition": "like_new",
    "attributes": {"storage_gb": 256, "color": "blue"},
    "location": "Lusail",
    "seller_name": "Ahmed K.",
    "language": "en",
    "created_at": "2026-09-01T10:00:00Z",
    "meta": {"near_duplicate_of": None},
}


def test_currency_conversion_round_trip():
    rates = DEFAULT_FX_RATES_TO_QAR
    assert to_qar(Decimal("900"), "USD", rates) == Decimal("3276.00")
    assert to_qar(Decimal("3276"), "qar", rates) == Decimal("3276.00")
    assert from_qar(Decimal("3276"), "USD", rates) == Decimal("900.00")
    with pytest.raises(UnknownCurrencyError):
        to_qar(Decimal("1"), "EUR", rates)


def test_search_text_contains_title_description_and_facts():
    listing = NormalizedListing.model_validate({k: v for k, v in PHONE.items() if k != "meta"})
    text = build_search_text(listing)
    assert "iphone 17 pro 256gb like new" in text
    assert "comes w/ box" in text
    assert "storage gb: 256" in text and "condition: like new" in text and "Lusail" in text


def test_rent_requires_period():
    data = {**PHONE, "category": "apartments", "condition": None, "listing_type": "rent"}
    data.pop("meta")
    with pytest.raises(ValueError, match="price_period"):
        NormalizedListing.model_validate(data)  # rent with default price_period=total


def test_condition_required_outside_property():
    data = {**PHONE, "condition": None}
    data.pop("meta")
    with pytest.raises(ValueError, match="condition"):
        NormalizedListing.model_validate(data)


def test_synthetic_source_reads_jsonl_and_strips_meta(tmp_path):
    path = tmp_path / "listings.jsonl"
    path.write_text(json.dumps(PHONE) + "\n\n", encoding="utf-8")
    items = list(SyntheticListingSource(path).iter_listings())
    assert len(items) == 1 and items[0].external_id == "syn-qa-00001"


def test_synthetic_source_reports_line_number(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps({**PHONE, "currency": "qar!"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bad.jsonl:1"):
        list(SyntheticListingSource(path).iter_listings())
