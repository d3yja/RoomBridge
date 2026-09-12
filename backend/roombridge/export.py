"""Structured export for research analysis: one JSONL row per run (full nested record)
plus a flat CSV of per-run metrics (plan section 6). Avoids free-form-only text."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime

from sqlmodel import select

from .config import EXPORT_DIR
from .domain import models as M
from .domain.db import init_db, session_scope


def run_record(run_id: str) -> dict:
    with session_scope() as s:
        run = s.get(M.Run, run_id)
        scenario = s.get(M.Scenario, run.scenario_id)
        needs = s.exec(select(M.Need).where(M.Need.scenario_id == run.scenario_id)).all()
        calls = s.exec(select(M.LLMCall).where(M.LLMCall.run_id == run_id)).all()
        messages = s.exec(select(M.AgentMessage).where(M.AgentMessage.run_id == run_id)).all()
        candidates = s.exec(select(M.CandidateAgreement).where(M.CandidateAgreement.run_id == run_id)).all()
        audits = s.exec(select(M.NeedAudit).where(M.NeedAudit.run_id == run_id)).all()
        assumptions = s.exec(select(M.Assumption).where(M.Assumption.run_id == run_id)).all()
        policy_audits = s.exec(select(M.PolicyAudit).where(M.PolicyAudit.run_id == run_id)).all()
        escalations = s.exec(select(M.EscalationEvent).where(M.EscalationEvent.run_id == run_id)).all()
        metrics = s.exec(select(M.MetricResult).where(M.MetricResult.run_id == run_id)).all()

        return {
            "run_id": run.run_id,
            "scenario_id": run.scenario_id,
            "condition": run.condition.value,
            "seed": run.seed,
            "model": run.model,
            "auditor_model": run.auditor_model,
            "status": run.status,
            "escalated": run.escalated,
            "culture_diff_rate": run.culture_diff_rate,
            "final_agreement_text": run.final_agreement_text,
            "scenario": {
                "title": scenario.title, "should_escalate": scenario.should_escalate,
                "gold_audit": scenario.gold_audit, "participants": scenario.participants,
            },
            "needs": [{"need_id": n.need_id, "owner_id": n.owner_id, "verbatim": n.verbatim,
                       "normalized": n.normalized, "category": n.category,
                       "stated_importance": n.stated_importance,
                       "stated_as_boundary": n.stated_as_boundary} for n in needs],
            "candidate_agreements": [{"idx": c.candidate_idx, "chosen": c.chosen,
                                      "terms": c.terms, "rationale": c.rationale} for c in candidates],
            "need_audits": [{"need_id": a.need_id, "phase": a.phase, "status": a.status.value,
                             "evidence_quote": a.evidence_quote, "self_consistency": a.self_consistency,
                             "with_rationale": a.with_rationale, "rationale": a.rationale,
                             "samples": a.samples} for a in audits],
            "assumptions": [{"text": a.text, "type": a.assumption_type,
                             "detected_by": a.detected_by, "severity": a.severity.value}
                            for a in assumptions],
            "policy_audits": [{"rule_id": p.rule_id, "status": p.status, "type": p.type,
                               "title": p.title, "source": p.source,
                               "evidence_quote": p.evidence_quote, "detected_by": p.detected_by}
                              for p in policy_audits],
            "escalation_events": [{"triggered_by": e.triggered_by,
                                   "category": e.category.value if e.category else None,
                                   "triggering_span": e.triggering_span, "reason": e.reason,
                                   "not_attempted": e.not_attempted,
                                   "suggested_support": e.suggested_support} for e in escalations],
            "metrics": {m.name: (m.detail if m.value is None else m.value) for m in metrics},
            "agent_messages": [{"round": m.round_idx, "agent": m.agent, "content": m.content}
                               for m in messages],
            "llm_calls": [{"step": c.step, "prompt_name": c.prompt_name,
                           "prompt_version": c.prompt_version, "model": c.model, "seed": c.seed,
                           "temperature": c.temperature, "messages": c.messages,
                           "raw_response": c.raw_response, "usage": c.usage} for c in calls],
        }


_FLAT_METRICS = ["nrr", "silent_loss_count", "silent_loss_rate", "retention_asymmetry",
                 "mean_self_consistency", "gold_status_match", "candidate_spread_pairwise",
                 "candidate_spread_mst", "position_drift",
                 "policy_compliance_rate", "policy_violation_count", "policy_hard_violation_count",
                 "escalated"]


def export_all(tag: str | None = None) -> tuple[str, str]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = tag or datetime.now().strftime("%Y%m%d_%H%M%S")
    jsonl_path = EXPORT_DIR / f"runs_{stamp}.jsonl"
    csv_path = EXPORT_DIR / f"metrics_{stamp}.csv"

    with session_scope() as s:
        run_ids = [r.run_id for r in s.exec(select(M.Run)).all()]

    with open(jsonl_path, "w", encoding="utf-8") as jf, open(csv_path, "w", newline="") as cf:
        writer = csv.writer(cf)
        writer.writerow(["run_id", "scenario_id", "condition", "seed", "model", "status",
                         "escalated", "culture_diff_rate", *_FLAT_METRICS])
        for rid in run_ids:
            rec = run_record(rid)
            jf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            m = rec["metrics"]
            writer.writerow([
                rec["run_id"], rec["scenario_id"], rec["condition"], rec["seed"], rec["model"],
                rec["status"], rec["escalated"], rec["culture_diff_rate"],
                *[m.get(k, "") if not isinstance(m.get(k), dict) else "" for k in _FLAT_METRICS],
            ])
    return str(jsonl_path), str(csv_path)


def main():
    ap = argparse.ArgumentParser(description="Export RoomBridge runs")
    ap.add_argument("--tag", default=None)
    args = ap.parse_args()
    init_db()
    jsonl, csvp = export_all(args.tag)
    print(f"wrote:\n  {jsonl}\n  {csvp}")


if __name__ == "__main__":
    main()
