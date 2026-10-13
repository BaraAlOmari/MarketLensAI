"""The eval's own logic: metrics and the ground-truth matcher must be right before any score
means anything."""

import pytest

from ground_truth import build, load_facts, load_queries, violations
from run import p95, recall_at_k, reciprocal_rank

PHONE = {
    "external_id": "x1",
    "category": "phones",
    "brand": "Apple",
    "model": "iPhone 15 Pro",
    "condition": "good",
    "listing_type": "sale",
    "price_period": "total",
    "location": "Lusail",
    "attributes": {"storage_gb": 256, "color": "black"},
    "meta": {"price_qar": "2800.00"},
}
FLAT = {
    "external_id": "x2",
    "category": "apartments",
    "brand": None,
    "model": None,
    "condition": None,
    "listing_type": "rent",
    "price_period": "year",
    "location": "The Pearl, Doha",
    "attributes": {"bedrooms": 2, "neighborhood": "The Pearl", "amenities": ["gym"]},
    "meta": {"price_qar": "96000.00"},
}


def test_recall_denominator_is_capped_at_k():
    relevant = {f"r{i}" for i in range(40)}
    assert recall_at_k([f"r{i}" for i in range(10)], relevant) == 1.0
    assert recall_at_k(["r1", "x", "r2"], {"r1", "r2", "r3", "r4"}) == 0.5
    assert recall_at_k(["x"], set()) == 0.0


def test_reciprocal_rank_uses_first_hit_within_k():
    assert reciprocal_rank(["x", "y", "r"], {"r"}) == pytest.approx(1 / 3)
    assert reciprocal_rank(["x"] * 10 + ["r"], {"r"}) == 0.0


def test_p95():
    assert p95([float(i) for i in range(1, 101)]) == 95.0


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ({"category": "phones", "models": ["iPhone 15 Pro"]}, []),
        ({"category": "laptops"}, ["category"]),
        ({"category": "phones", "conditions": ["new", "like_new"]}, ["condition"]),
        ({"category": "phones", "price": {"max": 3000}}, []),
        ({"category": "phones", "price": {"max": 700, "currency": "USD"}}, ["price"]),  # 2548
        ({"category": "phones", "price": {"around": 800, "currency": "USD"}}, []),  # 2912 +-15%
        ({"category": "phones", "attrs": {"storage_gb": {"min": 512}}}, ["attr:storage_gb"]),
        ({"category": "phones", "attrs": {"sim": "dual"}}, ["attr:sim"]),  # unknown != match
        ({"category": "phones", "brands": ["Samsung"], "location": "West Bay"},
         ["brand", "location"]),
    ],
)  # fmt: skip
def test_violations_for_a_phone(spec, expected):
    assert violations(PHONE, spec) == expected


def test_property_rules_use_neighborhood_and_monthly_rent():
    spec = {"category": "apartments", "listing_type": "rent", "location": "the pearl",
            "attrs": {"bedrooms": 2, "amenities": {"contains": "gym"}}}  # fmt: skip
    assert violations(FLAT, spec) == []
    # 96,000 a year is 8,000 a month.
    month = {"category": "apartments", "price": {"max": 8000, "basis": "month"}}
    assert violations(FLAT, month) == []
    assert violations(FLAT, {**month, "price": {"max": 7999, "basis": "month"}}) == ["price"]
    assert violations(FLAT, {"category": "apartments", "listing_type": "sale"}) == ["rent_sale"]


def test_committed_query_set_has_answers_for_every_query():
    queries = load_queries()
    truth = build(queries, load_facts())
    assert 30 <= len(queries) <= 50
    assert len({q["id"] for q in queries}) == len(queries)
    assert all(1 <= len(truth[q["id"]]) <= 150 for q in queries)
    assert {q["lang"] for q in queries} == {"en", "ar", "mixed"}
