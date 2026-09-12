"""Assumption checking + the CultureSPA-style differential tripwire (plan section 5).

The differential re-runs generation with and without the cultural context block and diffs
the results, following data_process/3.CRQPC.py:37-49 -- but inverted: CultureSPA harvests
the diffs as training data; here every diff is a culture-contingent artifact to surface.
"""
from __future__ import annotations

from ..domain import contracts as C
from ..prompts import PromptContext
from ..prompts.registry import get_prompt
from .executor import StepExecutor
from .rules import stereotype_rule


def check_assumptions(ex: StepExecutor, needs, agreement_text: str) -> list[C.AssumptionFinding]:
    ctx = PromptContext(
        get_prompt("check_assumptions").allowed_fields, needs=needs, agreement_text=agreement_text
    )
    model_findings = ex.run_list(
        "check_assumptions", ctx, C.AssumptionFinding, temperature=0.7
    )
    # The deterministic rule layer has no false negatives on the blatant form.
    rule_findings = stereotype_rule(agreement_text)
    return model_findings + rule_findings


def culture_diff_rate(with_context_terms: set[str], without_context_terms: set[str]) -> float:
    """Fraction of agreement terms that changed when the cultural context block was added.
    A non-zero rate means culture altered the substance, not just the explanation."""
    union = with_context_terms | without_context_terms
    if not union:
        return 0.0
    symmetric_diff = (with_context_terms ^ without_context_terms)
    return len(symmetric_diff) / len(union)
