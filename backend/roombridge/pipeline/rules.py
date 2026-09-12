"""Deterministic rule layers. No model, no stochasticity, cannot be argued out of firing.

Two layers (plan sections 5, 9, 10):
  * escalation_rule: safety/threat/coercion patterns on raw statements.
  * stereotype_rule: demographic -> preference constructions in generated text.
"""
from __future__ import annotations

import re

from ..domain.contracts import AssumptionFinding, EscalationVerdict
from ..domain.enums import AssumptionType, EscalationCategory, Severity

_ESCALATION_PATTERNS: list[tuple[EscalationCategory, str]] = [
    (EscalationCategory.THREAT, r"\b(threat(en)?|kill|hurt|beat|hit|attack|weapon|knife|gun)\b"),
    (EscalationCategory.SAFETY, r"\b(unsafe|afraid|scared|danger(ous)?|violence|violent|abuse)\b"),
    (EscalationCategory.MENTAL_HEALTH, r"\b(suicid\w*|self[- ]?harm|kill myself|end my life|hopeless)\b"),
    (EscalationCategory.HARASSMENT, r"\b(harass\w*|stalk\w*|threaten\w*|slur|racist|sexual\w*)\b"),
    (EscalationCategory.COERCION, r"\b(coerc\w*|forc(e|ed|ing) me|blackmail|threaten\w* to)\b"),
]

# demographic term ... connective ... preference verb
_STEREOTYPE = re.compile(
    r"\b(nationality|national|culture|cultural|religion|religious|country|ethnic\w*|"
    r"[A-Z][a-z]+(?:ian|ese|ish|an))\b"
    r"[^.?!]{0,60}?\b(therefore|so|thus|hence|because|since|tend to|tends to|typically|"
    r"usually|probably|likely|generally)\b"
    r"[^.?!]{0,40}?\b(prefer\w*|value\w*|want\w*|need\w*|expect\w*|like\w*|enjoy\w*)\b",
    re.IGNORECASE,
)


def escalation_rule(statements: str) -> EscalationVerdict | None:
    low = statements.lower()
    for category, pattern in _ESCALATION_PATTERNS:
        m = re.search(pattern, low)
        if m:
            span = statements[max(0, m.start() - 20): m.end() + 20].strip()
            return EscalationVerdict(
                escalate=True, category=category, triggering_span=span,
                reason=f"A deterministic rule matched a {category.value} indicator; this is "
                       "beyond AI mediation.",
                not_attempted=["assigning blame", "proposing an agreement", "resolving the dispute"],
                suggested_support="hall tutor / warden / university counselling or wellbeing service",
                confidence="high",
            )
    return None


def stereotype_rule(text: str) -> list[AssumptionFinding]:
    findings: list[AssumptionFinding] = []
    for m in _STEREOTYPE.finditer(text):
        findings.append(AssumptionFinding(
            text=m.group(0).strip(),
            assumption_type=AssumptionType.CULTURAL_INFERENCE,
            severity=Severity.BLOCKING,
        ))
    return findings
