"""Scenario loading + validation. Scenarios are git-versioned YAML; the validator enforces
the properties the metrics depend on (plan sections 7.1, 11):
  * balanced need count per participant (else NRR is dominated by whoever has more needs);
  * gold_audit covers every need;
  * unique need ids, valid owners, valid gold statuses.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ..config import SCENARIO_DIR
from ..domain import models as M
from ..domain.db import session_scope
from ..domain.enums import NeedStatus


class ScenarioValidationError(Exception):
    pass


class _Participant(BaseModel):
    participant_id: str
    display_name: str
    background_context: str = ""


class _NeedYAML(BaseModel):
    need_id: str
    owner_id: str
    verbatim: str
    normalized: str = ""
    category: str = "other"
    constraints: list[dict] = Field(default_factory=list)
    stated_importance: int | None = None
    stated_as_boundary: bool = False


class _ScenarioYAML(BaseModel):
    scenario_id: str
    version: int = 1
    title: str = ""
    seed: int = 42
    should_escalate: bool = False
    participants: list[_Participant]
    needs: list[_NeedYAML] = Field(default_factory=list)
    gold_audit: dict[str, str] = Field(default_factory=dict)
    expected_observations: list[str] = Field(default_factory=list)
    notes: str = ""


def validate_scenario(data: _ScenarioYAML) -> None:
    pids = {p.participant_id for p in data.participants}
    if not 2 <= len(pids) <= 3:
        raise ScenarioValidationError(f"{data.scenario_id}: need 2-3 participants, got {len(pids)}")

    need_ids = [n.need_id for n in data.needs]
    if len(need_ids) != len(set(need_ids)):
        raise ScenarioValidationError(f"{data.scenario_id}: duplicate need_id")
    for n in data.needs:
        if n.owner_id not in pids:
            raise ScenarioValidationError(f"{data.scenario_id}: need {n.need_id} owner not a participant")

    # Escalation scenarios need not carry needs; mediation scenarios must be balanced + gold-covered.
    if not data.should_escalate:
        counts = {p: sum(1 for n in data.needs if n.owner_id == p) for p in pids}
        if len(set(counts.values())) != 1:
            raise ScenarioValidationError(
                f"{data.scenario_id}: unbalanced need counts {counts}; NRR requires balance.")
        if min(counts.values()) == 0:
            raise ScenarioValidationError(f"{data.scenario_id}: every participant needs >=1 need")
        missing = set(need_ids) - set(data.gold_audit)
        if missing:
            raise ScenarioValidationError(f"{data.scenario_id}: gold_audit missing {sorted(missing)}")
        valid = {s.value for s in NeedStatus}
        bad = {k: v for k, v in data.gold_audit.items() if v not in valid}
        if bad:
            raise ScenarioValidationError(f"{data.scenario_id}: invalid gold statuses {bad}")


def load_yaml(path: Path) -> _ScenarioYAML:
    data = _ScenarioYAML.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    validate_scenario(data)
    return data


def upsert_scenario(data: _ScenarioYAML) -> None:
    with session_scope() as s:
        existing = s.get(M.Scenario, data.scenario_id)
        if existing:
            for n in s.query(M.Need).filter(M.Need.scenario_id == data.scenario_id).all():
                s.delete(n)
            s.delete(existing)
            s.flush()
        s.add(M.Scenario(
            scenario_id=data.scenario_id, version=data.version, title=data.title, seed=data.seed,
            should_escalate=data.should_escalate, is_synthetic=True,
            participants=[p.model_dump() for p in data.participants],
            gold_audit=data.gold_audit, expected_observations=data.expected_observations,
            notes=data.notes,
        ))
        for n in data.needs:
            s.add(M.Need(scenario_id=data.scenario_id, **n.model_dump()))


def load_all(directory: Path | None = None) -> list[str]:
    directory = directory or SCENARIO_DIR
    loaded = []
    for path in sorted(directory.glob("*.yaml")):
        data = load_yaml(path)
        upsert_scenario(data)
        loaded.append(data.scenario_id)
    return loaded
