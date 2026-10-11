from collections import Counter
from decimal import Decimal

import pytest

from app.config import DEFAULT_FX_RATES_TO_QAR
from generator.facts import generate_facts, nice_price
from generator.locales import QATAR, US


@pytest.fixture(scope="module")
def facts():
    return generate_facts(QATAR, seed=7)


def test_deterministic_for_same_seed():
    small = {"phones": 20, "apartments": 20}
    a = generate_facts(QATAR, seed=1, counts=small)
    b = generate_facts(QATAR, seed=1, counts=small)
    assert [x.__dict__ for x in a] == [x.__dict__ for x in b]


def test_size_and_unique_ids(facts):
    assert len(facts) >= 2000
    assert len({f.external_id for f in facts}) == len(facts)


def test_every_category_present(facts):
    assert set(Counter(f.category for f in facts)) == {
        "phones", "laptops", "cars", "furniture", "apartments", "villas",
    }  # fmt: skip


def test_condition_spread_and_null_only_for_property(facts):
    for f in facts:
        is_property = f.category in ("apartments", "villas")
        assert (f.condition is None) == is_property
    conditions = Counter(f.condition for f in facts if f.condition)
    assert set(conditions) == {"new", "like_new", "good", "fair", "poor"}


def test_price_period_matches_listing_type(facts):
    for f in facts:
        if f.listing_type == "sale":
            assert f.price_period == "total"
        else:
            assert f.price_period in ("month", "year")
    rent = [f for f in facts if f.category in ("apartments", "villas")]
    assert {f.listing_type for f in rent} == {"sale", "rent"}


def test_price_qar_consistent_with_currency(facts):
    for f in facts:
        expected = (f.price * DEFAULT_FX_RATES_TO_QAR[f.currency]).quantize(Decimal("0.01"))
        assert f.price_qar == expected
        assert f.price > 0


def test_qar_is_primary_currency(facts):
    share = Counter(f.currency for f in facts)["QAR"] / len(facts)
    assert 0.8 < share < 0.95


def test_bilingual_mix(facts):
    langs = Counter(f.language for f in facts)
    assert langs["ar"] / len(facts) > 0.2
    assert langs["mixed"] > 0


def test_near_duplicates_point_to_real_listings(facts):
    ids = {f.external_id for f in facts}
    dups = [f for f in facts if f.near_duplicate_of]
    assert len(dups) >= 50
    assert all(d.near_duplicate_of in ids and d.near_duplicate_of != d.external_id for d in dups)


def test_us_locale_uses_usd_and_english():
    us = generate_facts(US, seed=3, counts={"phones": 30, "apartments": 30})
    assert {f.currency for f in us} == {"USD"}
    assert {f.language for f in us} == {"en"}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(87.0, Decimal(85)), (2437.0, Decimal(2450)), (86_740.0, Decimal(86_500)),
     (1_234_567.0, Decimal(1_230_000))],
)  # fmt: skip
def test_nice_price(raw, expected):
    import random

    assert nice_price(raw, random.Random(0)) == expected
