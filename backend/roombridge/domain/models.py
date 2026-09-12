"""SQLModel database tables. JSON-typed columns hold structured content — never
free-form-only text. Every LLM call is persisted for reproducibility (plan section 6, 8)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from .enums import Condition, EscalationCategory, NeedStatus, Severity


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json(default: Any) -> Any:
    return Field(default_factory=lambda: default, sa_column=Column(JSON))


class Scenario(SQLModel, table=True):
    scenario_id: str = Field(primary_key=True)
    version: int = 1
    title: str = ""
    seed: int = 42
    should_escalate: bool = False
    is_synthetic: bool = True
    participants: list = _json([])          # [{participant_id, display_name, background_context}]
    gold_audit: dict = _json({})            # {need_id: NeedStatus}
    expected_observations: list = _json([])
    notes: str = ""
    created_at: datetime = Field(default_factory=_now)


class Need(SQLModel, table=True):
    """Authored gold need. Immutable within a scenario version (plan section 4.1)."""

    pk: int | None = Field(default=None, primary_key=True)
    need_id: str = Field(index=True)
    scenario_id: str = Field(index=True, foreign_key="scenario.scenario_id")
    owner_id: str
    verbatim: str
    normalized: str = ""
    category: str = "other"
    constraints: list = _json([])
    stated_importance: int | None = None
    stated_as_boundary: bool = False
    source_span: list | None = _json(None)


class Run(SQLModel, table=True):
    run_id: str = Field(primary_key=True)
    scenario_id: str = Field(index=True, foreign_key="scenario.scenario_id")
    condition: Condition = Field(index=True)
    seed: int = 42
    model: str = ""
    auditor_model: str = ""
    status: str = "pending"                 # pending | running | complete | escalated | failed
    escalated: bool = False
    final_agreement_text: str | None = None
    error: str | None = None
    culture_diff_rate: float | None = None  # CultureSPA-style tripwire (plan section 5)
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None


class LLMCall(SQLModel, table=True):
    """One request/response. The rendered prompt is stored inline (MAD sec5_infer_api.py)."""

    pk: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="run.run_id")
    step: str
    prompt_name: str = ""
    prompt_version: str = ""
    model: str = ""
    seed: int | None = None
    temperature: float | None = None
    messages: list = _json([])              # rendered [{role, content}]
    raw_response: str = ""
    parsed: dict | None = _json(None)
    usage: dict | None = _json(None)
    ok: bool = True
    error: str | None = None
    created_at: datetime = Field(default_factory=_now)


class AgentMessage(SQLModel, table=True):
    """Deliberation transcript entry (conditions C/D). Never reaches the auditor."""

    pk: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="run.run_id")
    round_idx: int = 0
    agent: str = ""
    content: str = ""
    created_at: datetime = Field(default_factory=_now)


class CandidateAgreement(SQLModel, table=True):
    pk: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="run.run_id")
    candidate_idx: int = 0
    seed: int | None = None
    terms: list = _json([])                 # [{text, addresses_need_ids}]
    rationale: str = ""
    chosen: bool = False


class NeedAudit(SQLModel, table=True):
    """One row per (run, need). Status lives HERE, not on Need (plan section 4.1)."""

    pk: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="run.run_id")
    need_id: str
    phase: str = "final"                    # "pre_revision" | "final"
    status: NeedStatus = NeedStatus.NOT_ADDRESSED
    evidence_quote: str | None = None
    rationale: str = ""
    samples: list = _json([])               # all n verdicts
    self_consistency: float = 0.0
    with_rationale: bool = False            # True for the leakage-control arm
    auditor_model: str = ""
    prompt_version: str = ""


class Assumption(SQLModel, table=True):
    pk: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="run.run_id")
    text: str
    assumption_type: str = ""
    grounded_in_need_id: str | None = None
    detected_by: str = ""                   # assumption_checker | culture_differential | rule
    severity: Severity = Severity.FLAG
    surfaced_in_ui: bool = True


class EscalationEvent(SQLModel, table=True):
    pk: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="run.run_id")
    triggered_by: str = ""                  # rule | classifier | both
    category: EscalationCategory | None = None
    triggering_span: str = ""
    reason: str = ""
    not_attempted: list = _json([])
    suggested_support: str = ""


class PolicyAudit(SQLModel, table=True):
    """One row per (run, applicable rule). Parallel to NeedAudit; compliance is a second,
    independent axis from needs retention (plan addendum)."""

    pk: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="run.run_id")
    rule_id: str
    status: str = "not_applicable"      # PolicyStatus value
    type: str = "hard"                  # rule type at audit time
    title: str = ""
    source: str = ""
    evidence_quote: str | None = None
    rationale: str = ""
    samples: list = _json([])
    self_consistency: float = 0.0
    detected_by: str = "policy_auditor" # policy_auditor | rule
    auditor_model: str = ""
    prompt_version: str = ""


class MetricResult(SQLModel, table=True):
    pk: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="run.run_id")
    name: str
    value: float | None = None
    detail: dict | None = _json(None)
