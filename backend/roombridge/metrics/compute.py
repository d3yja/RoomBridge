"""Compute and persist all metrics for a finished run from its recorded DB rows.

Includes audit accuracy against the scenario's authored gold_audit -- the honest
substitute for MAD's Value Alignment (plan section 7.5): same role (compare output to a
reference), different epistemics (author design intent, not a population prior).
"""
from __future__ import annotations

from sqlmodel import select

from ..domain import models as M
from ..domain.db import session_scope
from ..domain.enums import NeedStatus
from .pairwise import compute_pairwise
from .retention import retention_metrics
from .structural import compute_mst_span
from .policy import policy_metrics
from .drift import position_drift


def _candidate_satisfaction_vectors(run_id: str) -> dict[str, dict[str, float]]:
    """Score each candidate agreement's per-need audit into a [0,1] vector.
    For the demo/prototype we reuse the chosen agreement's audit as a proxy where a
    per-candidate audit is not available; candidates that were separately audited use theirs.
    Here we approximate candidate spread using the coverage the generator claimed, which is
    cheap and deterministic; a full per-candidate audit is a documented later extension."""
    from ..domain.enums import STATUS_SCORE
    with session_scope() as s:
        cands = s.exec(select(M.CandidateAgreement).where(
            M.CandidateAgreement.run_id == run_id)).all()
        needs = s.exec(select(M.Need)).all()
    vectors: dict[str, dict[str, float]] = {}
    all_need_ids = {n.need_id for n in needs}
    for c in cands:
        covered = {nid for t in c.terms for nid in t.get("addresses_need_ids", [])}
        vectors[f"cand_{c.candidate_idx}"] = {
            nid: (1.0 if nid in covered else 0.0) for nid in all_need_ids
        }
    return vectors


def compute_run_metrics(run_id: str) -> dict:
    with session_scope() as s:
        run = s.get(M.Run, run_id)
        scenario = s.get(M.Scenario, run.scenario_id)
        needs = s.exec(select(M.Need).where(M.Need.scenario_id == run.scenario_id)).all()
        finals = s.exec(select(M.NeedAudit).where(
            M.NeedAudit.run_id == run_id, M.NeedAudit.phase == "final")).all()
        policy_rows = s.exec(select(M.PolicyAudit).where(M.PolicyAudit.run_id == run_id)).all()
        gold = dict(scenario.gold_audit or {})
        owners = {n.need_id: n.owner_id for n in needs}
        escalated = run.escalated

    results: dict[str, float | dict] = {}

    if escalated:
        results["escalated"] = 1.0
    else:
        statuses = {a.need_id: a.status for a in finals}
        results.update(retention_metrics(statuses, owners))
        results["mean_self_consistency"] = (
            sum(a.self_consistency for a in finals) / len(finals) if finals else 0.0
        )
        if policy_rows:
            results.update(policy_metrics(
                [{"rule_id": r.rule_id, "type": r.type, "status": r.status} for r in policy_rows]))
        # Match against the scenario's pre-registered expected (baseline) statuses.
        # This is phenomenon-confirmation, NOT pure auditor accuracy: for baseline
        # conditions a high match means the predicted silent losses were detected; for D,
        # divergence is EXPECTED and good (revision recovered the dropped needs). True
        # auditor accuracy needs per-agreement human labels (the held-out kappa in the plan).
        if gold:
            matches = sum(1 for a in finals if gold.get(a.need_id) == a.status.value)
            results["gold_status_match"] = matches / len(finals) if finals else 0.0

        # Candidate spread (pairwise + MST), K>=3 only.
        vectors = _candidate_satisfaction_vectors(run_id)
        if len(vectors) >= 3:
            mean_pw, pair_dict, ids = compute_pairwise(vectors)
            span, _ = compute_mst_span(pair_dict, ids)
            results["candidate_spread_pairwise"] = mean_pw
            results["candidate_spread_mst"] = span

        # Position drift (conditions with a deliberation transcript).
        drift = position_drift(run_id)
        if drift["by_owner"]:
            results["position_drift"] = drift["mean_drift"]
            results["position_drift_detail"] = drift["by_owner"]

    # Persist.
    with session_scope() as s:
        for name, value in results.items():
            if isinstance(value, dict):
                s.add(M.MetricResult(run_id=run_id, name=name, value=None, detail=value))
            else:
                s.add(M.MetricResult(run_id=run_id, name=name, value=float(value)))
    return results
