"""The four experimental conditions (plan section 2.2 + policy addendum).

All four share invariants that make the comparison valid (plan section 2.3):
  1. the gold need set (ctx.needs) is fixed outside the condition;
  2. the needs auditor is identical for all four and sees only (need, agreement_text);
  3. the hall-policy compliance auditor is likewise identical and sees only
     (agreement_text, rules) -- so policy compliance is a second, independently measured
     outcome. The hall-rules BLOCK is fed to generation only in the workflow conditions
     (B/C/D); A stays a rules-free baseline. Every condition's agreement is still audited.
The escalation gate runs first for every condition; a positive halts before any agreement.
"""
from __future__ import annotations

from ..config import settings
from ..domain import contracts as C
from ..domain.enums import (
    SILENT_LOSS_STATUSES, STATUS_SCORE, AssumptionType, NeedStatus, Severity,
)
from ..pipeline import assumptions as A
from ..pipeline import steps as S
from ..pipeline.audit import audit_all
from ..pipeline.executor import StepExecutor
from ..pipeline.policy import check_policy, hard_rule_violations
from ..pipeline.rules import policy_violation_rule
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


def _policy_rows(ctx: RunContext, ex: StepExecutor, agreement: C.Agreement) -> list[dict]:
    """Independent compliance audit of one agreement (no recording)."""
    if not ctx.hall_rules:
        return []
    return check_policy(ex, agreement.to_text(), ctx.hall_rules, auditor_model=ctx.auditor_model)


def _finalize_policy(ctx: RunContext, ex: StepExecutor, rec: Recorder,
                     agreement: C.Agreement) -> list[dict]:
    rows = _policy_rows(ctx, ex, agreement)
    if rows:
        rec.record_policy_audit(rows)
    return rows


def _record_policy_conflicts(ctx: RunContext, rec: Recorder) -> None:
    """Surface (never silently drop) any STATED need that collides with a hard hall rule.
    Scenario-level and condition-independent: the tension exists regardless of the
    agreement, so every run shows it; the policy audit then shows whether the condition's
    agreement actually broke the rule."""
    if not ctx.hall_rules:
        return
    findings: list[C.AssumptionFinding] = []
    for n in ctx.needs:
        for rule_id, _ in policy_violation_rule(n.verbatim):
            rule = next((r for r in ctx.hall_rules if r.rule_id == rule_id and r.type == "hard"), None)
            if rule:
                findings.append(C.AssumptionFinding(
                    text=(f'Stated need {n.need_id} ("{n.verbatim}") conflicts with hall rule '
                          f"{rule.rule_id}: {rule.title} ({rule.source})."),
                    assumption_type=AssumptionType.POLICY_CONFLICT,
                    grounded_in_need_id=n.need_id, severity=Severity.FLAG))
    if findings:
        rec.record_assumptions(findings, detected_by="policy_conflict")


def _rules_block(ctx: RunContext) -> str:
    """Compact hall-rules text appended to the statements for B/C (which use generate_generic)."""
    if not ctx.hall_rules:
        return ""
    lines = [f"- [{r.type}] {r.title}: {r.rule_text} ({r.source})" for r in ctx.hall_rules]
    return ("\n\nHall rules the agreement MUST comply with (hard rules are absolute):\n"
            + "\n".join(lines))


def _run_assumptions(ctx, ex, rec, agreement: C.Agreement) -> None:
    findings = A.check_assumptions(ex, ctx.needs, agreement.to_text())
    rec.record_assumptions(findings, detected_by="assumption_checker")


# --- Condition A: generic LLM (no rules fed; still audited) --------------------
def condition_a(ctx: RunContext, ex: StepExecutor, rec: Recorder) -> None:
    if _escalated(ctx, ex, rec):
        return
    agreement = S.generate_generic(ex, ctx.all_statements, seed=ctx.seed)
    rec.record_candidate(0, ctx.seed, agreement, chosen=True)
    _finalize_with_audit(ctx, ex, rec, agreement)
    _finalize_policy(ctx, ex, rec, agreement)
    _record_policy_conflicts(ctx, rec)
    rec.finalize(status="complete", agreement_text=agreement.to_text(), escalated=False)


# --- Condition B: context-informed (rules fed as text) ------------------------
def condition_b(ctx: RunContext, ex: StepExecutor, rec: Recorder) -> None:
    if _escalated(ctx, ex, rec):
        return
    notes = [S.context_note(ex, n) for n in ctx.needs]
    context_block = "\n".join(
        f"- context for {nt.need_id}: " + "; ".join(nt.possible_reasons) for nt in notes
    )
    statements_plus = (ctx.all_statements
                       + "\n\nContextual considerations (explanatory only):\n" + context_block
                       + _rules_block(ctx))
    agreement = S.generate_generic(ex, statements_plus, seed=ctx.seed)
    rec.record_candidate(0, ctx.seed, agreement, chosen=True)
    _finalize_with_audit(ctx, ex, rec, agreement)
    _finalize_policy(ctx, ex, rec, agreement)
    _record_policy_conflicts(ctx, rec)
    _run_assumptions(ctx, ex, rec, agreement)
    rec.finalize(status="complete", agreement_text=agreement.to_text(), escalated=False)


# --- Condition C: ordinary multi-agent deliberation (rules fed as text) -------
def condition_c(ctx: RunContext, ex: StepExecutor, rec: Recorder, rounds: int = 2) -> None:
    if _escalated(ctx, ex, rec):
        return
    owners = [p["participant_id"] for p in ctx.participants]
    needs_by_owner = {o: [n for n in ctx.needs if n.owner_id == o] for o in owners}

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

    transcript = "\n".join(f"{k}: {v.weights}" for k, v in prev_vectors.items())
    mediator_input = (ctx.all_statements + "\n\nDeliberation notes:\n" + transcript
                      + _rules_block(ctx))
    agreement = S.generate_generic(ex, mediator_input, seed=ctx.seed)
    rec.record_message(rounds + 1, "mediator", agreement.to_text())
    rec.record_candidate(0, ctx.seed, agreement, chosen=True)
    _finalize_with_audit(ctx, ex, rec, agreement)
    _finalize_policy(ctx, ex, rec, agreement)
    _record_policy_conflicts(ctx, rec)
    rec.finalize(status="complete", agreement_text=agreement.to_text(), escalated=False)


# --- Condition D: RoomBridge needs-preserving + policy-aware workflow ----------
def condition_d(ctx: RunContext, ex: StepExecutor, rec: Recorder) -> None:
    if _escalated(ctx, ex, rec):
        return

    notes = [S.context_note(ex, n) for n in ctx.needs]
    conflicts = S.identify_conflicts(ex, ctx.needs)

    # K independently-sampled candidate agreements, each drafted under the hall rules.
    candidates: list[C.Agreement] = []
    for k in range(settings.generation_k):
        cand = S.generate_agreement(ex, ctx.needs, conflicts, notes,
                                    seed=ctx.seed + 100 + k, hall_rules=ctx.hall_rules)
        candidates.append(cand)

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

    # Pre-revision: needs audit (recorded) + policy audit (computed). Revision is triggered
    # by BOTH a dropped need AND any hard-rule violation, so a rule-breaking term is fixed
    # exactly like a lost need. Only failing need ids and violated rule ids are passed back
    # -- never the auditor's rationale.
    audits = _finalize_with_audit(ctx, ex, rec, agreement, phase="pre_revision")
    policy_rows = _policy_rows(ctx, ex, agreement)
    failing_needs = _failing(audits)
    failing_rules = set(hard_rule_violations(policy_rows))
    revised = False
    for _ in range(settings.max_revision_iterations):
        if not failing_needs and not failing_rules:
            break
        agreement = S.generate_agreement(
            ex, ctx.needs, conflicts, notes, seed=ctx.seed + 200,
            failing_need_ids=failing_needs, failing_rule_ids=failing_rules,
            hall_rules=ctx.hall_rules,
        )
        audits = audit_all(ex, ctx.needs, agreement.to_text(), auditor_model=ctx.auditor_model)
        policy_rows = _policy_rows(ctx, ex, agreement)
        revised = True
        failing_needs = _failing(audits)
        failing_rules = set(hard_rule_violations(policy_rows))

    for a in audits:
        rec.record_audit(a, phase="final")
    if policy_rows:
        rec.record_policy_audit(policy_rows)
    _record_policy_conflicts(ctx, rec)

    if revised:
        rec.set_final_agreement(agreement)

    _run_assumptions(ctx, ex, rec, agreement)

    # CultureSPA differential tripwire: generate without context, diff the terms.
    plain = S.generate_agreement(ex, ctx.needs, conflicts, [], seed=ctx.seed + 300,
                                 hall_rules=ctx.hall_rules)
    with_terms = {t.text for t in candidates[chosen_idx].terms}
    without_terms = {t.text for t in plain.terms}
    diff_rate = A.culture_diff_rate(with_terms, without_terms)

    rec.finalize(status="complete", agreement_text=agreement.to_text(),
                 escalated=False, culture_diff_rate=diff_rate)
