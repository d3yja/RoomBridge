"""Pydantic contracts for structured LLM I/O and in-memory pipeline objects.

These are NOT database tables (see models.py). They are the validated shapes that
cross the boundary to and from the model, and the objects the pipeline passes between
steps. Every field constraint here is a research safeguard, not incidental validation.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .enums import (
    AssumptionType,
    EscalationCategory,
    NeedStatus,
    Provenance,
    Severity,
)


class Constraint(BaseModel):
    dimension: str                      # e.g. "time", "day", "temperature", "frequency"
    operator: str                       # e.g. "within", "equals", "max", "min"
    value: str                          # e.g. "22:00-05:00", "Sunday", "20C"


class Need(BaseModel):
    """A stated requirement. Needs are ALWAYS stated; inferred content is an Assumption."""

    need_id: str
    owner_id: str
    verbatim: str                       # EXACT source text; never paraphrased or regenerated
    normalized: str = ""                # one-sentence canonical restatement (model-written)
    category: str = "other"
    constraints: list[Constraint] = Field(default_factory=list)
    stated_importance: int | None = None   # 1-5, ONLY if the person stated it
    stated_as_boundary: bool = False       # ONLY if the person said non-negotiable
    provenance: Provenance = Provenance.STATED
    source_span: tuple[int, int] | None = None


class ContextNote(BaseModel):
    """Explanatory cultural/contextual note. Structurally cannot originate a preference.

    Notes attach to a STATED need (need_id required). There is no field for a predicted
    preference, so the model cannot emit 'this person probably wants X' through this shape.
    """

    need_id: str                        # required: notes explain stated needs only
    possible_reasons: list[str] = Field(default_factory=list)
    communication_considerations: list[str] = Field(default_factory=list)
    confidence: str = "low"             # "low" | "medium" only; "high" is rejected

    @field_validator("confidence")
    @classmethod
    def _no_high_confidence(cls, v: str) -> str:
        if v not in {"low", "medium"}:
            raise ValueError(
                "ContextNote.confidence must be 'low' or 'medium'; culture is explanatory, "
                "never a high-confidence predictor of a person's preference."
            )
        return v


class Conflict(BaseModel):
    conflict_id: str
    need_ids: list[str]
    conflict_type: str                  # "direct" | "resource" | "schedule" | "value"
    negotiable: bool
    missing_info: list[str] = Field(default_factory=list)


class AgreementTerm(BaseModel):
    text: str
    addresses_need_ids: list[str] = Field(default_factory=list)


class Agreement(BaseModel):
    terms: list[AgreementTerm] = Field(default_factory=list)
    rationale: str = ""                 # WHY this agreement; never shown to the auditor

    def to_text(self) -> str:
        """Render terms to the plain text the auditor scores. The auditor never sees
        addresses_need_ids or the rationale, only this prose (plan sections 2.3, 6)."""
        if not self.terms:
            return ""
        return "\n".join(f"{i + 1}. {t.text}" for i, t in enumerate(self.terms))


class AuditVerdict(BaseModel):
    """One auditor sample's verdict on one need against one agreement text."""

    status: NeedStatus
    evidence_quote: str | None = None   # must be a verbatim substring of the agreement text
    rationale: str = ""


class AssumptionFinding(BaseModel):
    text: str
    assumption_type: AssumptionType
    grounded_in_need_id: str | None = None
    severity: Severity = Severity.FLAG


class EscalationVerdict(BaseModel):
    escalate: bool
    category: EscalationCategory | None = None
    triggering_span: str = ""
    reason: str = ""
    not_attempted: list[str] = Field(default_factory=list)
    suggested_support: str = ""
    confidence: str = "low"


class PriorityVector(BaseModel):
    """A perspective agent's self-reported priority over ITS OWN principal's needs.
    Used to measure position drift across deliberation rounds (plan section 7.4)."""

    owner_id: str
    weights: dict[str, float] = Field(default_factory=dict)  # need_id -> weight in [0,1]
