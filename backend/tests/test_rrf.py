"""Reciprocal Rank Fusion and the hybrid query around it."""

import pytest

from app.retrieval.hybrid import FIRST_FILTER_PARAM, hybrid_sql, rank_sides
from app.retrieval.rrf import RRF_K, rrf_merge


def test_score_is_sum_of_reciprocal_ranks():
    fused = rrf_merge({"vector": ["a", "b"], "keyword": ["b", "c"]})
    scores = {f.id: f.score for f in fused}
    assert scores["a"] == pytest.approx(1 / 61)
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["c"] == pytest.approx(1 / 62)
    assert [f.id for f in fused] == ["b", "a", "c"]  # in both lists beats top of one
    assert next(f for f in fused if f.id == "b").ranks == {"vector": 2, "keyword": 1}


def test_worked_example_from_the_docs():
    # "MacBook Pro M4 Max 1TB": the exact match is 3rd by meaning but 1st by keywords.
    fused = rrf_merge(
        {"vector": ["max-2tb", "pro-1tb", "max-1tb"], "keyword": ["max-1tb", "x", "y", "max-2tb",
                                                               "z", "pro-1tb"]}
    )  # fmt: skip
    top = [f.id for f in fused[:3]]
    assert top == ["max-1tb", "max-2tb", "pro-1tb"]


def test_one_list_alone_keeps_its_order():
    fused = rrf_merge({"vector": [3, 1, 2], "keyword": []})
    assert [f.id for f in fused] == [3, 1, 2]
    assert all(f.ranks.keys() == {"vector"} for f in fused)


def test_ties_are_deterministic():
    # a: 1st in vector only; b: 1st in keyword only -> equal scores and equal best rank.
    # The list given first wins the tie, every time.
    for _ in range(5):
        fused = rrf_merge({"vector": ["a"], "keyword": ["b"]})
        assert [f.id for f in fused] == ["a", "b"]


def test_a_list_cannot_vote_twice_for_one_item():
    fused = rrf_merge({"vector": ["a", "a", "b"]})
    assert {f.id: f.ranks["vector"] for f in fused} == {"a": 1, "b": 3}
    assert fused[0].score == pytest.approx(1 / 61)


def test_k_controls_how_much_top_ranks_dominate():
    sharp = rrf_merge({"v": ["a", "b"], "k": ["b", "c", "d", "a"]}, k=0)
    flat = rrf_merge({"v": ["a", "b"], "k": ["b", "c", "d", "a"]}, k=RRF_K)
    assert sharp[0].score / sharp[-1].score > flat[0].score / flat[-1].score
    with pytest.raises(ValueError):
        rrf_merge({"v": ["a"]}, k=-1)


def test_empty_input():
    assert rrf_merge({}) == []
    assert rrf_merge({"vector": [], "keyword": []}) == []


# --- hybrid query ------------------------------------------------------------------------


class Row(dict):
    """Stands in for asyncpg.Record (mapping access)."""


def test_rank_sides_orders_each_side_and_breaks_keyword_ties_by_meaning():
    rows = [
        Row(id=5, similarity=0.80, kw_score=None, meaning=0.80),
        Row(id=2, similarity=0.90, kw_score=0.05, meaning=0.90),
        Row(id=9, similarity=None, kw_score=0.08, meaning=0.40),
        Row(id=1, similarity=0.80, kw_score=0.05, meaning=0.80),
        Row(id=7, similarity=None, kw_score=0.05, meaning=0.85),
    ]
    vector_ids, keyword_ids = rank_sides(rows)
    assert vector_ids == [2, 1, 5]  # equal similarity: lower id first
    # 2, 7 and 1 tie on ts_rank; the one closest in meaning goes first.
    assert keyword_ids == [9, 2, 7, 1]


def test_hybrid_sql_applies_filters_to_both_sides():
    sql = hybrid_sql(["category = $5", "price_qar <= $6"])
    vec_part, kw_part = sql.split("tsq as")
    assert "category = $5" in vec_part and "price_qar <= $6" in vec_part
    assert "category = $5" in kw_part and "price_qar <= $6" in kw_part
    assert FIRST_FILTER_PARAM == 5  # $1 vector, $2 model, $3 depth, $4 query text
    assert "to_tsvector('english', $4) || to_tsvector('arabic', $4)" in sql
