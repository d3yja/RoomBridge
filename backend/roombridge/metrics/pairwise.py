"""Pairwise diversity, adapted from MultiAgent-Diversity evaluate.py:81 compute_pairwise().

Original: agents -> answer vectors over shared questions; distance is normalized Euclidean
mean over all pairs. Here the "agents" are the K candidate agreements in one run and the
"questions" are the shared gold needs, scored by the auditor into [0,1] satisfaction
(plan section 7.2). Reused near-verbatim; the only change is delta=1.0 since scores are
already normalized to [0,1]. NOT relabelled as RoomBridge's own metric.
"""
from __future__ import annotations

import math
from itertools import combinations


def compute_pairwise(vectors: dict[str, dict[str, float]]) -> tuple[float, dict, list]:
    """vectors: {candidate_id: {need_id: score in [0,1]}}.
    Returns (mean_pairwise_distance, pair_dict, sorted_ids)."""
    ids = sorted(vectors.keys())
    pair_dict: dict[tuple[str, str], float] = {}
    scores: list[float] = []
    for a, b in combinations(ids, 2):
        v1, v2 = vectors[a], vectors[b]
        common = set(v1) & set(v2)
        sq = sum((v1[q] - v2[q]) ** 2 for q in common)
        maxsq = float(len(common))  # delta = 1.0 per need; scores already in [0,1]
        if maxsq == 0:
            continue
        d = math.sqrt(sq) / math.sqrt(maxsq)
        pair_dict[(a, b)] = d
        scores.append(d)
    mean = sum(scores) / len(scores) if scores else 0.0
    return mean, pair_dict, ids
