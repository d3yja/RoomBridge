"""Escalation gate: deterministic rule OR classifier, any-fires. Halts the pipeline."""
from __future__ import annotations

from ..config import settings
from ..domain import contracts as C
from ..prompts import PromptContext
from ..prompts.registry import get_prompt
from .executor import StepExecutor
from .rules import escalation_rule


def assess_escalation(ex: StepExecutor, statements: str) -> tuple[bool, C.EscalationVerdict, str]:
    """Return (should_escalate, verdict, triggered_by)."""
    rule_verdict = escalation_rule(statements)

    classifier_fired = False
    classifier_verdict: C.EscalationVerdict | None = None
    for i in range(settings.escalation_samples):
        ctx = PromptContext(get_prompt("assess_escalation").allowed_fields, statements=statements)
        v = ex.run_object(
            "assess_escalation", ctx, C.EscalationVerdict, seed=2000 + i, temperature=0.5
        )
        if v.escalate:                      # any positive fires (under-escalation is the danger)
            classifier_fired = True
            classifier_verdict = v
            break

    if rule_verdict and classifier_fired:
        merged = rule_verdict.model_copy()
        return True, merged, "both"
    if rule_verdict:
        return True, rule_verdict, "rule"
    if classifier_fired and classifier_verdict:
        return True, classifier_verdict, "classifier"
    return False, C.EscalationVerdict(escalate=False), ""
