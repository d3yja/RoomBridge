"""Position drift under social exposure (plan section 7.4).

Adapted from MAD's multi-round social exposure (sec6_social_exposure_api.py / sec6_fig4.py
ΔD): does a perspective agent abandon its principal's priorities after seeing peers?
Drift = normalized Euclidean distance between a perspective agent's round-1 and round-R
priority vectors over its OWN principal's needs. Elicited without showing the agent its
previous vector, so we do not merely measure copy-paste.
"""
from __future__ import annotations

import json
import math

from sqlmodel import select

from ..domain import models as M
from ..domain.db import session_scope


def _dist(v1: dict[str, float], v2: dict[str, float]) -> float:
    keys = set(v1) & set(v2)
    if not keys:
        return 0.0
    sq = sum((v1[k] - v2[k]) ** 2 for k in keys)
    return math.sqrt(sq) / math.sqrt(len(keys))  # weights in [0,1] -> delta 1 per need


def position_drift(run_id: str) -> dict:
    with session_scope() as s:
        msgs = s.exec(select(M.AgentMessage).where(
            M.AgentMessage.run_id == run_id,
            M.AgentMessage.agent.like("perspective:%"))).all()
    by_owner: dict[str, dict[int, dict]] = {}
    for m in msgs:
        owner = m.agent.split(":", 1)[1]
        try:
            weights = json.loads(m.content)
        except (json.JSONDecodeError, TypeError):
            continue
        by_owner.setdefault(owner, {})[m.round_idx] = weights

    per_owner_drift = {}
    for owner, rounds in by_owner.items():
        if len(rounds) < 2:
            continue
        r_first, r_last = min(rounds), max(rounds)
        per_owner_drift[owner] = _dist(rounds[r_first], rounds[r_last])
    mean = sum(per_owner_drift.values()) / len(per_owner_drift) if per_owner_drift else 0.0
    return {"mean_drift": mean, "by_owner": per_owner_drift}
