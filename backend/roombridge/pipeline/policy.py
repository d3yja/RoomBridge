"""Independent hall-policy compliance audit (plan addendum).

Mirrors the needs audit (pipeline/audit.py): the auditor's allowlist is {agreement_text,
rules} only -- no rationale, no transcript, no needs, no condition label -- and a `violated`
verdict must quote the offending term verbatim or it is downgraded to compliant (we never
claim a violation we cannot point at). Applied identically to all four conditions, so it
measures the agreement, not the mediator.
"""
from __future__ import annotations

import re

from ..domain import contracts as C
from ..domain.enums import POLICY_EVIDENCE_REQUIRED, PolicyStatus
from ..prompts import PromptContext
from ..prompts.registry import get_prompt
from .executor import StepExecutor
from .rules import policy_violation_rule


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _grounded(finding: C.PolicyFinding, agreement_text: str) -> C.PolicyFinding:
    """A `violated` claim not backed by a real quote is downgraded to compliant."""
    if finding.status not in POLICY_EVIDENCE_REQUIRED:
        return finding
    quote = _normalize(finding.evidence_quote or "")
    if quote and quote in _normalize(agreement_text):
        return finding
    return C.PolicyFinding(
        rule_id=finding.rule_id, status=PolicyStatus.COMPLIANT, evidence_quote=None,
        rationale=("[downgraded] claimed a violation but quoted no verbatim offending term. "
                   f"Model said: {finding.rationale}"),
    )


def check_policy(ex: StepExecutor, agreement_text: str, rules: list[C.PolicyRule],
                 *, auditor_model: str) -> list[dict]:
    """Return rows shaped for PolicyAudit. Combines the model audit with the deterministic
    rule layer, which has no false negatives on the blatant hard-rule violations."""
    from ..policies.loader import rules_for_prompt

    by_id = {r.rule_id: r for r in rules}
    spec = get_prompt("check_policy")
    ctx = PromptContext(spec.allowed_fields, agreement_text=agreement_text,
                        rules=rules_for_prompt(rules))
    model_findings = ex.run_list(
        "check_policy", ctx, C.PolicyFinding, model=auditor_model, temperature=0.0
    )
    grounded = {f.rule_id: _grounded(f, agreement_text) for f in model_findings}

    # Deterministic layer: force a violation for any blatant hard-rule breach it catches,
    # regardless of what the model said (no false negatives on the obvious cases).
    for rule_id, span in policy_violation_rule(agreement_text):
        grounded[rule_id] = C.PolicyFinding(
            rule_id=rule_id, status=PolicyStatus.VIOLATED, evidence_quote=span,
            rationale="Deterministic rule layer matched a blatant hard-rule violation.",
        )

    rows = []
    for rule in rules:
        f = grounded.get(rule.rule_id)
        detected_by = "rule" if (f and "Deterministic" in f.rationale) else "policy_auditor"
        if f is None:
            f = C.PolicyFinding(rule_id=rule.rule_id, status=PolicyStatus.NOT_APPLICABLE)
        rows.append({
            "rule_id": rule.rule_id, "status": f.status.value, "type": rule.type,
            "title": rule.title, "source": rule.source,
            "evidence_quote": f.evidence_quote, "rationale": f.rationale,
            "samples": [f.model_dump(mode="json")], "self_consistency": 1.0,
            "detected_by": detected_by, "auditor_model": auditor_model,
            "prompt_version": spec.version,
        })
    return rows


def hard_rule_violations(policy_rows: list[dict]) -> list[str]:
    """rule_ids of HARD rules that the agreement violates -- fed into D's revision loop."""
    return [r["rule_id"] for r in policy_rows
            if r["type"] == "hard" and r["status"] == PolicyStatus.VIOLATED.value]
