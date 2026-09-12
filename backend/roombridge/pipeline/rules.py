"""Deterministic rule layers. No model, no stochasticity, cannot be argued out of firing.

Two layers (plan sections 5, 9, 10):
  * escalation_rule: safety/threat/coercion patterns on raw statements.
  * stereotype_rule: demographic -> preference constructions in generated text.
"""
from __future__ import annotations

import re

from ..domain.contracts import AssumptionFinding, EscalationVerdict
from ..domain.enums import AssumptionType, EscalationCategory, Severity

# Order matters: the first match wins, so the most specific/serious categories come first.
_ESCALATION_PATTERNS: list[tuple[EscalationCategory, str]] = [
    (EscalationCategory.THREAT, r"\b(threat(en)?|kill|hurt|beat|hit|attack|weapon|knife|gun)\b"),
    (EscalationCategory.MENTAL_HEALTH, r"\b(suicid\w*|self[- ]?harm|kill myself|end my life|hopeless)\b"),
    # Handbook p.27: illicit drugs are a criminal offence "not to be compromised on".
    (EscalationCategory.CRIMINAL, r"\b(illicit drug\w*|drug dealing|dealing drugs|selling drugs|"
                                  r"deals? drugs|cocaine|heroin|methamphetamine|narcotic\w*|"
                                  r"stolen goods)\b"),
    (EscalationCategory.SAFETY, r"\b(unsafe|afraid|scared|danger(ous)?|violence|violent|abuse)\b"),
    (EscalationCategory.HARASSMENT, r"\b(harass\w*|stalk\w*|threaten\w*|slur|racist|sexual\w*)\b"),
    (EscalationCategory.COERCION, r"\b(coerc\w*|forc(e|ed|ing) me|blackmail|threaten\w* to)\b"),
]

# The real PolyU Homantin support structure (handbook p.3, p.27, p.30).
_HALL_SUPPORT = ("the on-duty Hall Tutor, the Warden, or Hall Administration (Homantin Halls)")
_CRIMINAL_SUPPORT = ("campus security or the police (999), and the Warden / Hall Administration")

# Blatant HARD-rule violations in an agreement's text. Each rule has a trigger pattern; a
# match only counts as a violation if the surrounding window has no negation/redirection
# cue -- so a COMPLIANT term that names the topic ("use the SHARED kitchen for cooking",
# "keep smoking OUT of the room") is not falsely flagged. Deterministic; no false negatives
# on the obvious in-room forms (plan addendum).
_POLICY_TRIGGERS: list[tuple[str, "re.Pattern[str]"]] = [
    ("HR_NO_COOKING", re.compile(
        r"\bcook\w*|\bhot ?plate|\bstove|\binduction cooker|\brice cooker|\bdeep[- ]fry\w*", re.I)),
    ("HR_NO_SMOKING_ALCOHOL", re.compile(
        r"\bsmok\w*|\bcigarette\w*|\bvap\w*|\balcohol\w*|\bbeer\b|\bwine\b|\bspirits\b", re.I)),
    ("HR_PRIVACY_HOURS", re.compile(
        r"\bovernight\b|\bstay\w* over\b|\bsleep\w* over\b|\bpartner stays?\b|"
        r"\bopposite[- ]sex (?:guest|visitor)\w*", re.I)),
]

# If any of these appear near a trigger, the term is complying WITH the rule, not breaking it.
_COMPLIANCE_CUES = re.compile(
    r"\bno\b|\bnot\b|\bn't\b|\bavoid\b|\bwithout\b|\bout of\b|\brather than\b|\binstead of\b|"
    r"\bprohibit\w*|\bforbidden\b|\bnot allowed\b|\bfree of\b|\bshared\b|\bcommon\b|"
    r"\bcommunal\b|\bpantry\b|\bcanteen\b|\bper hall rule|\bin line with hall rule|"
    r"\bhall rule", re.I)

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
            criminal = category == EscalationCategory.CRIMINAL
            support = _CRIMINAL_SUPPORT if criminal else _HALL_SUPPORT
            reason = (f"A deterministic rule matched a {category.value} indicator; this is "
                      "beyond AI mediation.")
            if criminal:
                reason += (" The hall handbook states such matters (e.g. illicit drugs) are a "
                           "criminal offence and must not be compromised on.")
            return EscalationVerdict(
                escalate=True, category=category, triggering_span=span, reason=reason,
                not_attempted=["assigning blame", "proposing an agreement", "resolving the dispute"],
                suggested_support=support, confidence="high",
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


def policy_violation_rule(agreement_text: str) -> list[tuple[str, str]]:
    """Blatant HARD-rule violations in an agreement -> [(rule_id, offending sentence)].
    A trigger only counts when the sentence around it has no compliance/redirection cue, so
    a compliant term that names the rule's topic is not falsely flagged (plan addendum)."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    # Split into sentences/lines so the compliance window is local to the trigger.
    for raw in re.split(r"(?<=[.?!])\s+|\n", agreement_text):
        sentence = raw.strip()
        if not sentence:
            continue
        for rule_id, pat in _POLICY_TRIGGERS:
            if rule_id in seen:
                continue
            if pat.search(sentence) and not _COMPLIANCE_CUES.search(sentence):
                out.append((rule_id, sentence))
                seen.add(rule_id)
    return out
