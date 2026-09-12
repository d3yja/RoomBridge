"""Closed vocabularies shared across the pipeline, DB, and API."""
from __future__ import annotations

from enum import Enum


class Condition(str, Enum):
    A_GENERIC = "A_generic"
    B_CONTEXT = "B_context"
    C_DELIBERATE = "C_deliberate"
    D_ROOMBRIDGE = "D_roombridge"


class NeedStatus(str, Enum):
    PRESERVED = "preserved"
    PARTIALLY_PRESERVED = "partially_preserved"
    UNRESOLVED = "unresolved"
    NOT_ADDRESSED = "not_addressed"
    VIOLATED = "violated"


# Ordinal scoring used by the retention metrics (plan section 7.1).
STATUS_SCORE: dict[NeedStatus, float] = {
    NeedStatus.PRESERVED: 1.0,
    NeedStatus.PARTIALLY_PRESERVED: 0.5,
    NeedStatus.UNRESOLVED: 0.25,
    NeedStatus.NOT_ADDRESSED: 0.0,
    NeedStatus.VIOLATED: 0.0,
}

# A silent loss is a need that is actively contradicted or simply absent.
SILENT_LOSS_STATUSES = {NeedStatus.NOT_ADDRESSED, NeedStatus.VIOLATED}

# Statuses that require verbatim supporting evidence from the agreement text.
# If the auditor cannot ground these in a quote, the status is forced down (plan section 6).
EVIDENCE_REQUIRED_STATUSES = {NeedStatus.PRESERVED, NeedStatus.PARTIALLY_PRESERVED}


class AssumptionType(str, Enum):
    CULTURAL_INFERENCE = "cultural_inference"      # demographic -> preference; always a violation
    UNSTATED_PREFERENCE = "unstated_preference"    # invented a need nobody stated
    FACTUAL_INVENTION = "factual_invention"        # invented a fact about the situation
    IMPORTANCE_RANKING = "importance_ranking"      # ranked needs residents did not rank
    POLICY_CONFLICT = "policy_conflict"            # a stated need collides with a hall rule


class Severity(str, Enum):
    BLOCKING = "blocking"
    FLAG = "flag"
    NOTE = "note"


class EscalationCategory(str, Enum):
    HARASSMENT = "harassment"
    THREAT = "threat"
    SAFETY = "safety"
    MENTAL_HEALTH = "mental_health"
    COERCION = "coercion"
    REPEATED_UNRESOLVED = "repeated_unresolved"
    CRIMINAL = "criminal"
    OUT_OF_SCOPE = "out_of_scope"


class Provenance(str, Enum):
    STATED = "stated"     # needs are always stated; inferred content is an Assumption instead


class PolicyStatus(str, Enum):
    COMPLIANT = "compliant"
    VIOLATED = "violated"
    NOT_APPLICABLE = "not_applicable"
    ADVISORY = "advisory"          # a guideline worth noting, neither pass nor fail


# Statuses that require a verbatim quote of the offending term (parallel to needs audit).
POLICY_EVIDENCE_REQUIRED = {PolicyStatus.VIOLATED}
