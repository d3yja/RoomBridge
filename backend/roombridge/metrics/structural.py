"""Structural diversity (MST span), adapted from MultiAgent-Diversity evaluate.py:124
compute_mst_span(). Answers whether candidate spread is even or driven by one outlier
(plan section 7.3). Reused near-verbatim. Secondary metric; meaningful only for K>=3."""
from __future__ import annotations

import numpy as np
from scipy.sparse.csgraph import minimum_spanning_tree


def compute_mst_span(pair_dict: dict, ids: list) -> tuple[float, list]:
    n = len(ids)
    if n < 2 or not pair_dict:
        return 0.0, []
    M = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            a, b = ids[i], ids[j]
            d = pair_dict.get((a, b), pair_dict.get((b, a), 0.0))
            M[i, j] = M[j, i] = d
    mst = minimum_spanning_tree(M).toarray()
    span = float(mst.sum()) / (n - 1)
    edges = [(ids[i], ids[j], float(mst[i, j]))
             for i in range(n) for j in range(n) if mst[i, j] > 0]
    return span, edges
