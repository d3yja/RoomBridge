"""The needs-preservation audit -- the research instrument (plan section 6).

Independence is guaranteed by the auditor's prompt allowlist ({need, agreement_text}).
Two further guards live here:
  * evidence grounding: a preserved/partially verdict whose evidence_quote is not a
    verbatim substring of the agreement is forced down to unresolved;
  * n-sample majority: n independent samples, majority status wins, self-consistency stored.
"""
from __future__ import annotations

import re
from collections import Counter

from ..config import settings
from ..domain import contracts as C
from ..domain.enums import EVIDENCE_REQUIRED_STATUSES, NeedStatus
from ..prompts import PromptContext
from ..prompts.registry import get_prompt
from .executor import StepExecutor


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _grounded(verdict: C.AuditVerdict, agreement_text: str) -> C.AuditVerdict:
    """Force the status down when a preserved/partial claim is not backed by a real quote."""
    if verdict.status not in EVIDENCE_REQUIRED_STATUSES:
        return verdict
    quote = _normalize(verdict.evidence_quote or "")
    if quote and quote in _normalize(agreement_text):
        return verdict
    return C.AuditVerdict(
        status=NeedStatus.UNRESOLVED,
        evidence_quote=None,
        rationale=(f"[forced to unresolved] claimed {verdict.status.value} but no supporting "
                   f"verbatim span was found in the agreement. Model said: {verdict.rationale}"),
    )


def audit_one_need(
    ex: StepExecutor, need: C.Need, agreement_text: str, *,
    auditor_model: str, n: int | None = None, with_rationale: bool = False,
) -> dict:
    """Return a dict shaped for the NeedAudit row."""
    n = n or settings.audit_samples
    samples: list[C.AuditVerdict] = []
    for i in range(n):
        ctx = PromptContext(
            get_prompt("audit_need").allowed_fields, need=need, agreement_text=agreement_text
        )
        verdict = ex.run_object(
            "audit_need", ctx, C.AuditVerdict, model=auditor_model, seed=1000 + i, temperature=1.0
        )
        samples.append(_grounded(verdict, agreement_text))

    counts = Counter(s.status for s in samples)
    majority_status, majority_n = counts.most_common(1)[0]
    winner = next(s for s in samples if s.status == majority_status)
    return {
        "need_id": need.need_id,
        "status": majority_status,
        "evidence_quote": winner.evidence_quote,
        "rationale": winner.rationale,
        "samples": [s.model_dump(mode="json") for s in samples],
        "self_consistency": majority_n / len(samples),
        "with_rationale": with_rationale,
        "auditor_model": auditor_model,
        "prompt_version": get_prompt("audit_need").version,
    }


def audit_all(
    ex: StepExecutor, needs: list[C.Need], agreement_text: str, *, auditor_model: str,
) -> list[dict]:
    return [audit_one_need(ex, n, agreement_text, auditor_model=auditor_model) for n in needs]
