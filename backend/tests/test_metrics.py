"""Metric adaptations reproduce hand-computed values, including the N=2 degenerate case
where MST span equals mean-pairwise (plan section 7)."""
import math

from roombridge.metrics.pairwise import compute_pairwise
from roombridge.metrics.structural import compute_mst_span
from roombridge.metrics.retention import retention_metrics
from roombridge.domain.enums import NeedStatus


def test_pairwise_hand_computed():
    vectors = {"c0": {"n1": 1.0, "n2": 0.0}, "c1": {"n1": 0.0, "n2": 0.0},
               "c2": {"n1": 1.0, "n2": 1.0}}
    mean, pair, ids = compute_pairwise(vectors)
    # d(c0,c1)=sqrt(1)/sqrt(2)=.7071; d(c0,c2)=.7071; d(c1,c2)=sqrt(2)/sqrt(2)=1.0
    # mean = (.7071 + .7071 + 1.0) / 3 = .80474
    assert math.isclose(mean, (2 ** 0.5 + 1.0) / 3, rel_tol=1e-6)


def test_mst_n2_equals_pairwise():
    vectors = {"c0": {"n1": 1.0}, "c1": {"n1": 0.0}}
    mean, pair, ids = compute_pairwise(vectors)
    span, edges = compute_mst_span(pair, ids)
    assert math.isclose(span, mean, rel_tol=1e-9)  # degenerate: single edge


def test_retention_and_asymmetry():
    statuses = {"n1": NeedStatus.PRESERVED, "n2": NeedStatus.NOT_ADDRESSED,
                "n3": NeedStatus.PRESERVED, "n4": NeedStatus.PRESERVED}
    owners = {"n1": "A", "n2": "A", "n3": "B", "n4": "B"}
    m = retention_metrics(statuses, owners)
    assert math.isclose(m["nrr"], 0.75)
    assert m["silent_loss_count"] == 1
    # A: (1+0)/2=0.5 ; B: (1+1)/2=1.0 ; asymmetry 0.5
    assert math.isclose(m["retention_asymmetry"], 0.5)
