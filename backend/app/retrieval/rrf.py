"""Reciprocal Rank Fusion: merge ranked lists by position, ignoring their raw scores.

    score(d) = sum over lists L containing d of  1 / (k + rank_L(d))      (ranks start at 1)

Vector similarity (~0.8) and ts_rank (~0.05) are on unrelated scales, so adding them would
let one dominate. RRF only uses positions: an item near the top of both lists beats an item
at the top of one. k = 60 is the value from Cormack, Clarke & Buettcher (SIGIR 2009); larger
k flattens the difference between ranks.
"""

from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass, field

RRF_K = 60


@dataclass(frozen=True)
class Fused:
    id: Hashable
    score: float
    ranks: dict[str, int] = field(default_factory=dict)  # list name -> 1-based rank


def rrf_merge(rankings: Mapping[str, Sequence[Hashable]], k: int = RRF_K) -> list[Fused]:
    """Fuse ranked lists (best first). Ties: best single rank, then list order, then id order
    of first appearance, so the result is deterministic."""
    if k < 0:
        raise ValueError("k must be >= 0")
    scores: dict[Hashable, float] = {}
    ranks: dict[Hashable, dict[str, int]] = {}
    first_seen: dict[Hashable, int] = {}
    for name, ids in rankings.items():
        seen_here: set[Hashable] = set()
        for rank, item in enumerate(ids, 1):
            if item in seen_here:
                continue  # a list should not vote twice for the same item
            seen_here.add(item)
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
            ranks.setdefault(item, {})[name] = rank
            first_seen.setdefault(item, len(first_seen))
    ordered = sorted(scores, key=lambda i: (-scores[i], min(ranks[i].values()), first_seen[i]))
    return [Fused(i, scores[i], ranks[i]) for i in ordered]
