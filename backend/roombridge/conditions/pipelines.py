"""The four experimental conditions (plan section 2.2).

All four share TWO invariants that make the comparison valid (plan section 2.3):
  1. the gold need set (ctx.needs) is fixed outside the condition;
  2. the auditor is identical for all four and sees only (need, agreement_text).
The escalation gate runs first for every condition; a positive halts before any agreement.
"""
from __future__ import annotations

from ..config import settings
from ..domain import contracts as C
from ..domain.enums import SILENT_LOSS_STATUSES, STATUS_SCORE, NeedStatus
from ..pipeline import assumptions as A
from ..pipeline import steps as S
from ..pipeline.audit import audit_all
from ..pipeline.executor import StepExecutor
from ..pipeline.safety import assess_escalation
from .base import Recorder, RunContext


def _escalated(ctx: RunContext, ex: StepExecutor, rec: Recorder) -> bool:
    fire, verdict, by = assess_escalation(ex, ctx.all_statements)
    if fire:
        rec.record_escalation(verdict, by)
        rec.finalize(status="escalated", agreement_text=None, escalated=True)
        return True
    return False


def _finalize_with_audit(
    ctx: RunContext, ex: StepExecutor, rec: Recorder, agreement: C.Agreement, *, phase="final",
) -> list[dict]:
    text = agreement.to_text()
    audits = audit_all(ex, ctx.needs, text, auditor_model=ctx.auditor_model)
    for a in audits:
        rec.record_audit(a, phase=phase)
    return audits


def _run_assumptions(ctx, ex, rec, agreement: C.Agreement) -> None:
    findings = A.check_assumptions(ex, ctx.needs, agreement.to_text())
    rec.record_assumptions(findings, detected_by="assumption_checker")


# --- Condition A: generic LLM -------------------------------------------------
def condition_a(ctx: RunContext, ex: StepExecutor, rec: Recorder) -> None:
    if _escalated(ctx, ex, rec):
        return
    agreement = S.generate_generic(ex, ctx.all_statements, seed=ctx.seed)
    rec.record_candidate(0, ctx.seed, agreement, chosen=True)
    _finalize_with_audit(ctx, ex, rec, agreement)
    rec.finalize(status="complete", agreement_text=agreement.to_text(), escalated=False)


# --- Condition B: context-informed --------------------------------------------
def condition_b(ctx: RunContext, ex: StepExecutor, rec: Recorder) -> None:
    if _escalated(ctx, ex, rec):
        return
    # Context notes explain the stated needs; they are advisory, not a structured ledger.
    notes = [S.context_note(ex, n) for n in ctx.needs]
    context_block = "\n".join(
        f"- context for {nt.need_id}: " + "; ".join(nt.possible_reasons) for nt in notes
    )
    statements_plus = ctx.all_statements + "\n\nContextual considerations (explanatory only):\n" + context_block
    agreement = S.generate_generic(ex, statements_plus, seed=ctx.seed)
    rec.record_candidate(0, ctx.seed, agreement, chosen=True)
    _finalize_with_audit(ctx, ex, rec, agreement)
    _run_assumptions(ctx, ex, rec, agreement)
    rec.finalize(status="complete", agreement_text=agreement.to_text(), escalated=False)


# --- Condition C: ordinary multi-agent deliberation ---------------------------
def condition_c(ctx: RunContext, ex: StepExecutor, rec: Recorder, rounds: int = 2) -> None:
    if _escalated(ctx, ex, rec):
        return
    owners = [p["participant_id"] for p in ctx.participants]
    needs_by_owner = {o: [n for n in ctx.needs if n.owner_id == o] for o in owners}

    # Multi-round priority elicitation (MAD social-exposure shape) -> drift instrumentation.
    prev_vectors: dict[str, C.PriorityVector] = {}
    for r in range(1, rounds + 1):
        for o in owners:
            peer_context = ""
            if r > 1:
                peer_lines = [f"{po} statements: {ctx.statements_by_owner.get(po,'')}"
                              for po in owners if po != o]
                peer_context = "Peers have said:\n" + "\n".join(peer_lines)
            pv = S.priority_vector(ex, o, needs_by_owner[o], peer_context)
            prev_vectors[f"{o}@r{r}"] = pv
            import json as _json
            rec.record_message(r, f"perspective:{o}", _json.dumps(pv.weights))

    # Mediator synthesises an agreement from statements + transcript (no needs objects, no audit loop).
    transcript = "\n".join(f"{k}: {v.weights}" for k, v in prev_vectors.items())
    mediator_input = ctx.all_statements + "\n\nDeliberation notes:\n" + transcript
    agreement = S.generate_generic(ex, mediator_input, seed=ctx.seed)
    rec.record_message(rounds + 1, "mediator", agreement.to_text())
    rec.record_candidate(0, ctx.seed, agreement, chosen=True)
    _finalize_with_audit(ctx, ex, rec, agreement)
    rec.finalize(status="complete", agreement_text=agreement.to_text(), escalated=False)


# --- Condition D: RoomBridge needs-preserving workflow -------------------------
def condition_d(ctx: RunContext, ex: StepExecutor, rec: Recorder) -> None:
    if _escalated(ctx, ex, rec):
        return

    notes = [S.context_note(ex, n) for n in ctx.needs]
    conflicts = S.identify_conflicts(ex, ctx.needs)

    # K independently-sampled candidate agreements (MAD sec7_vote sampling shape).
    candidates: list[C.Agreement] = []
    for k in range(settings.generation_k):
        cand = S.generate_agreement(ex, ctx.needs, conflicts, notes, seed=ctx.seed + 100 + k)
        candidates.append(cand)

    # Selection sees terms + per-need coverage, never the candidates' rationales.
    cand_summaries = [
        {"index": i, "terms": [t.text for t in c.terms],
         "covers_need_ids": sorted({nid for t in c.terms for nid in t.addresses_need_ids})}
        for i, c in enumerate(candidates)
    ]
    chosen_idx = S.select_agreement(ex, ctx.needs, cand_summaries)
    for i, c in enumerate(candidates):
        rec.record_candidate(i, ctx.seed + 100 + i, c, chosen=(i == chosen_idx))
    agreement = candidates[chosen_idx]

    def _failing(audits: list[dict]) -> set[str]:
        return {a["need_id"] for a in audits
                if a["status"] in SILENT_LOSS_STATUSES or a["status"] == NeedStatus.UNRESOLVED}

    # Pre-revision audit (recorded), then bounded revision passing ONLY the failing need
    # ids -- never the auditor's rationale, which would let the generator game the auditor.
    audits = _finalize_with_audit(ctx, ex, rec, agreement, phase="pre_revision")
    failing = _failing(audits)
    revised = False
    for _ in range(settings.max_revision_iterations):
        if not failing:
            break
        agreement = S.generate_agreement(
            ex, ctx.needs, conflicts, notes, seed=ctx.seed + 200, failing_need_ids=failing
        )
        audits = audit_all(ex, ctx.needs, agreement.to_text(), auditor_model=ctx.auditor_model)
        revised = True
        failing = _failing(audits)

    # A final-phase audit always exists: either the revised one, or the pre-revision
    # promoted to final when no revision was needed or allowed.
    for a in audits:
        rec.record_audit(a, phase="final")

    # Show the agreement the final audit actually scored (post-revision if it changed).
    if revised:
        rec.set_final_agreement(agreement)

    _run_assumptions(ctx, ex, rec, agreement)

    # CultureSPA differential tripwire: generate without context, diff the terms.
    plain = S.generate_agreement(ex, ctx.needs, conflicts, [], seed=ctx.seed + 300)
    with_terms = {t.text for t in candidates[chosen_idx].terms}
    without_terms = {t.text for t in plain.terms}
    diff_rate = A.culture_diff_rate(with_terms, without_terms)

    rec.finalize(status="complete", agreement_text=agreement.to_text(),
                 escalated=False, culture_diff_rate=diff_rate)
