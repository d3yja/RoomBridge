"""Recorder + RunContext: the persistence and shared-state layer for a single run.

The Recorder captures every LLMCall, message, candidate, audit, assumption, and escalation
so a run is fully reconstructable (plan section 6). It can also collect events into an
in-memory list for SSE streaming to the UI.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from ..domain import models as M
from ..domain.contracts import Need
from sqlmodel import select

from ..domain.db import session_scope
from ..domain.enums import Condition


def new_run_id() -> str:
    return "run_" + uuid.uuid4().hex[:12]


@dataclass
class RunContext:
    run_id: str
    scenario_id: str
    condition: Condition
    seed: int
    model: str
    auditor_model: str
    needs: list[Need]                       # the SHARED gold need set (plan section 2.3)
    participants: list[dict]
    statements_by_owner: dict[str, str]
    all_statements: str


class Recorder:
    """Persists run artifacts and optionally emits streaming events."""

    def __init__(self, run_id: str, on_event: Callable[[dict], None] | None = None):
        self.run_id = run_id
        self._on_event = on_event

    def emit(self, kind: str, payload: dict) -> None:
        if self._on_event:
            self._on_event({"kind": kind, **payload})

    def record_call(self, **kw) -> None:
        with session_scope() as s:
            s.add(M.LLMCall(run_id=self.run_id, **kw))
        self.emit("llm_call", {"step": kw.get("step", "")})

    def record_message(self, round_idx: int, agent: str, content: str) -> None:
        with session_scope() as s:
            s.add(M.AgentMessage(run_id=self.run_id, round_idx=round_idx, agent=agent, content=content))
        self.emit("message", {"round": round_idx, "agent": agent, "content": content})

    def record_candidate(self, idx: int, seed, agreement, chosen: bool = False) -> None:
        with session_scope() as s:
            s.add(M.CandidateAgreement(
                run_id=self.run_id, candidate_idx=idx, seed=seed,
                terms=[t.model_dump(mode="json") for t in agreement.terms],
                rationale=agreement.rationale, chosen=chosen,
            ))

    def set_final_agreement(self, agreement) -> None:
        """Record the final (possibly revised) agreement as THE chosen candidate, so the UI
        shows the same agreement the final audit scored -- not the pre-revision candidate."""
        with session_scope() as s:
            for c in s.exec(
                select(M.CandidateAgreement).where(M.CandidateAgreement.run_id == self.run_id)
            ).all():
                if c.chosen:
                    c.chosen = False
                    s.add(c)
            idx = len(s.exec(
                select(M.CandidateAgreement).where(M.CandidateAgreement.run_id == self.run_id)
            ).all())
            s.add(M.CandidateAgreement(
                run_id=self.run_id, candidate_idx=idx, seed=None,
                terms=[t.model_dump(mode="json") for t in agreement.terms],
                rationale=agreement.rationale, chosen=True,
            ))

    def record_audit(self, audit: dict, phase: str = "final") -> None:
        with session_scope() as s:
            s.add(M.NeedAudit(run_id=self.run_id, phase=phase, **audit))
        self.emit("audit", {"phase": phase, "need_id": audit["need_id"],
                            "status": audit["status"].value if hasattr(audit["status"], "value") else audit["status"]})

    def record_assumptions(self, findings, detected_by: str) -> None:
        with session_scope() as s:
            for f in findings:
                s.add(M.Assumption(
                    run_id=self.run_id, text=f.text,
                    assumption_type=f.assumption_type.value, grounded_in_need_id=f.grounded_in_need_id,
                    detected_by=detected_by, severity=f.severity,
                ))
        if findings:
            self.emit("assumptions", {"count": len(findings), "detected_by": detected_by})

    def record_escalation(self, verdict, triggered_by: str) -> None:
        with session_scope() as s:
            s.add(M.EscalationEvent(
                run_id=self.run_id, triggered_by=triggered_by,
                category=verdict.category, triggering_span=verdict.triggering_span,
                reason=verdict.reason, not_attempted=verdict.not_attempted,
                suggested_support=verdict.suggested_support,
            ))
        self.emit("escalation", {"category": verdict.category.value if verdict.category else None})

    def finalize(self, *, status: str, agreement_text: str | None,
                 escalated: bool, culture_diff_rate=None, error=None) -> None:
        with session_scope() as s:
            run = s.get(M.Run, self.run_id)
            run.status = status
            run.final_agreement_text = agreement_text
            run.escalated = escalated
            run.culture_diff_rate = culture_diff_rate
            run.error = error
            run.finished_at = datetime.now(timezone.utc)
            s.add(run)
        self.emit("done", {"status": status, "escalated": escalated})
