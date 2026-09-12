"""Condition dispatch + the single entry point to execute one run end-to-end."""
from __future__ import annotations

from typing import Callable

from ..config import settings
from ..domain import models as M
from ..domain.contracts import Need
from ..domain.db import session_scope
from sqlmodel import select
from ..domain.enums import Condition
from ..pipeline.executor import StepExecutor
from ..policies.loader import load_rules
from ..providers.base import LLMError, StructuredProvider
from .base import Recorder, RunContext, new_run_id
from .pipelines import condition_a, condition_b, condition_c, condition_d

CONDITIONS: dict[Condition, Callable] = {
    Condition.A_GENERIC: condition_a,
    Condition.B_CONTEXT: condition_b,
    Condition.C_DELIBERATE: condition_c,
    Condition.D_ROOMBRIDGE: condition_d,
}


def build_run_context(scenario: M.Scenario, needs: list[M.Need], condition: Condition,
                      *, seed: int, model: str, auditor_model: str, run_id: str) -> RunContext:
    contract_needs = [
        Need(need_id=n.need_id, owner_id=n.owner_id, verbatim=n.verbatim, normalized=n.normalized,
             category=n.category, constraints=n.constraints, stated_importance=n.stated_importance,
             stated_as_boundary=n.stated_as_boundary)
        for n in needs
    ]
    statements_by_owner: dict[str, str] = {}
    for p in scenario.participants:
        pid = p["participant_id"]
        owned = [n.verbatim for n in contract_needs if n.owner_id == pid]
        bg = p.get("background_context", "")
        statements_by_owner[pid] = (bg + "\n" if bg else "") + "\n".join(owned)
    all_statements = "\n\n".join(
        f"{p['display_name']} ({p['participant_id']}):\n{statements_by_owner[p['participant_id']]}"
        for p in scenario.participants
    )
    return RunContext(
        run_id=run_id, scenario_id=scenario.scenario_id, condition=condition, seed=seed,
        model=model, auditor_model=auditor_model, needs=contract_needs,
        participants=scenario.participants, statements_by_owner=statements_by_owner,
        all_statements=all_statements, hall_rules=load_rules(),
    )


def run_condition(
    scenario_id: str, condition: Condition, provider: StructuredProvider,
    *, seed: int | None = None, model: str | None = None, auditor_model: str | None = None,
    on_event=None,
) -> str:
    model = model or settings.default_model
    auditor_model = auditor_model or settings.auditor_model
    run_id = new_run_id()

    # Load scenario + needs inside one session and build the RunContext from plain data,
    # so nothing depends on live ORM instances once the session closes.
    with session_scope() as s:
        scenario = s.get(M.Scenario, scenario_id)
        if scenario is None:
            raise ValueError(f"unknown scenario {scenario_id!r}")
        needs = list(s.exec(select(M.Need).where(M.Need.scenario_id == scenario_id)).all())
        run_seed = scenario.seed if seed is None else seed
        ctx = build_run_context(scenario, needs, condition, seed=run_seed, model=model,
                                auditor_model=auditor_model, run_id=run_id)
        s.add(M.Run(run_id=run_id, scenario_id=scenario_id, condition=condition,
                    seed=run_seed, model=model, auditor_model=auditor_model, status="running"))

    rec = Recorder(run_id, on_event=on_event)
    ex = StepExecutor(provider, rec, model=model)
    try:
        CONDITIONS[condition](ctx, ex, rec)
    except LLMError as e:
        rec.finalize(status="failed", agreement_text=None, escalated=False, error=str(e))
    return run_id
