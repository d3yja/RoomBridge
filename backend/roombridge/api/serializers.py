"""Read helpers that assemble UI-facing views of a run from the DB."""
from __future__ import annotations

from sqlmodel import select

from ..domain import models as M
from ..domain.db import session_scope


def scenario_view(sid: str) -> dict:
    with session_scope() as s:
        sc = s.get(M.Scenario, sid)
        needs = s.exec(select(M.Need).where(M.Need.scenario_id == sid)).all()
    return {
        "scenario_id": sc.scenario_id, "title": sc.title, "seed": sc.seed,
        "should_escalate": sc.should_escalate, "participants": sc.participants,
        "notes": sc.notes, "expected_observations": sc.expected_observations,
        "needs": [{"need_id": n.need_id, "owner_id": n.owner_id, "verbatim": n.verbatim,
                   "normalized": n.normalized, "category": n.category,
                   "stated_importance": n.stated_importance,
                   "stated_as_boundary": n.stated_as_boundary} for n in needs],
        "gold_audit": sc.gold_audit,
    }


def list_scenarios() -> list[dict]:
    with session_scope() as s:
        scs = s.exec(select(M.Scenario)).all()
    return [{"scenario_id": sc.scenario_id, "title": sc.title,
             "should_escalate": sc.should_escalate,
             "n_participants": len(sc.participants)} for sc in scs]


def run_view(run_id: str) -> dict:
    with session_scope() as s:
        run = s.get(M.Run, run_id)
        if run is None:
            return {}
        audits = s.exec(select(M.NeedAudit).where(M.NeedAudit.run_id == run_id)).all()
        cands = s.exec(select(M.CandidateAgreement).where(M.CandidateAgreement.run_id == run_id)).all()
        assumptions = s.exec(select(M.Assumption).where(M.Assumption.run_id == run_id)).all()
        esc = s.exec(select(M.EscalationEvent).where(M.EscalationEvent.run_id == run_id)).all()
        policy = s.exec(select(M.PolicyAudit).where(M.PolicyAudit.run_id == run_id)).all()
        metrics = s.exec(select(M.MetricResult).where(M.MetricResult.run_id == run_id)).all()
        messages = s.exec(select(M.AgentMessage).where(M.AgentMessage.run_id == run_id)).all()
    chosen = next((c for c in cands if c.chosen), None)
    return {
        "run_id": run.run_id, "scenario_id": run.scenario_id, "condition": run.condition.value,
        "status": run.status, "escalated": run.escalated,
        "final_agreement_text": run.final_agreement_text,
        "culture_diff_rate": run.culture_diff_rate,
        "chosen_agreement": ({"terms": chosen.terms, "rationale": chosen.rationale}
                             if chosen else None),
        "audits": [{"need_id": a.need_id, "phase": a.phase, "status": a.status.value,
                    "evidence_quote": a.evidence_quote, "rationale": a.rationale,
                    "self_consistency": a.self_consistency,
                    "samples": a.samples} for a in audits],
        "assumptions": [{"text": a.text, "type": a.assumption_type,
                         "detected_by": a.detected_by, "severity": a.severity.value}
                        for a in assumptions],
        "policy_audits": [{"rule_id": p.rule_id, "status": p.status, "type": p.type,
                           "title": p.title, "source": p.source,
                           "evidence_quote": p.evidence_quote, "detected_by": p.detected_by}
                          for p in policy],
        "escalation": ({"category": esc[0].category.value if esc[0].category else None,
                        "triggered_by": esc[0].triggered_by, "reason": esc[0].reason,
                        "triggering_span": esc[0].triggering_span,
                        "not_attempted": esc[0].not_attempted,
                        "suggested_support": esc[0].suggested_support} if esc else None),
        "metrics": {m.name: (m.detail if m.value is None else m.value) for m in metrics},
        "messages": [{"round": m.round_idx, "agent": m.agent, "content": m.content}
                     for m in messages],
    }
