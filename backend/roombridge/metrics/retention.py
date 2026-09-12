"""Needs-Retention Rate and companions (plan section 7.1). PRIMARY metric.

Derived from the STRUCTURE of MAD's normalized-distance construction (per-item scoring,
averaging over a fixed item set) but NOT MAD's metric -- reported under its own name.
Retention_Asymmetry is the degenerate 1-D case of pairwise distance over a single scalar
per person; noted here, never called Pairwise Diversity.
"""
from __future__ import annotations

from ..domain.enums import SILENT_LOSS_STATUSES, STATUS_SCORE, NeedStatus


def retention_metrics(
    statuses: dict[str, NeedStatus], owners: dict[str, str]
) -> dict[str, float | dict]:
    """statuses: {need_id: NeedStatus}. owners: {need_id: owner_id}."""
    if not statuses:
        return {"nrr": 0.0, "silent_loss_count": 0, "silent_loss_rate": 0.0,
                "retention_asymmetry": 0.0, "nrr_by_person": {}}

    nrr = sum(STATUS_SCORE[s] for s in statuses.values()) / len(statuses)
    silent = sum(1 for s in statuses.values() if s in SILENT_LOSS_STATUSES)

    by_person: dict[str, list[float]] = {}
    for nid, status in statuses.items():
        by_person.setdefault(owners.get(nid, "?"), []).append(STATUS_SCORE[status])
    nrr_by_person = {p: sum(v) / len(v) for p, v in by_person.items()}
    asymmetry = (max(nrr_by_person.values()) - min(nrr_by_person.values())
                 if len(nrr_by_person) > 1 else 0.0)

    return {
        "nrr": nrr,
        "silent_loss_count": silent,
        "silent_loss_rate": silent / len(statuses),
        "retention_asymmetry": asymmetry,
        "nrr_by_person": nrr_by_person,
    }
