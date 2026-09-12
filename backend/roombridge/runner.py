"""Headless experiment runner: scenario x condition x seed, resumable.

Runner idiom follows MAD's sec5_infer_api.py:158 (resume by skipping already-done work,
append-only), but over the run DB rather than JSONL files. Runs entirely on the mock
provider by default, so a full sweep costs nothing until you switch to --provider openrouter.
"""
from __future__ import annotations

import argparse

from sqlmodel import select

from .config import settings
from .domain import models as M
from .domain.db import init_db, session_scope
from .domain.enums import Condition
from .metrics.compute import compute_run_metrics
from .providers import get_provider
from .scenarios.loader import load_all


def _already_done(scenario_id: str, condition: Condition, seed: int, model: str) -> bool:
    with session_scope() as s:
        existing = s.exec(select(M.Run).where(
            M.Run.scenario_id == scenario_id, M.Run.condition == condition,
            M.Run.seed == seed, M.Run.model == model,
            M.Run.status.in_(["complete", "escalated"]))).first()
    return existing is not None


def run_sweep(scenario_ids, conditions, seeds, provider_name, model, auditor_model, *, resume=True):
    from .conditions.registry import run_condition

    provider = get_provider(provider_name)
    done = 0
    for sid in scenario_ids:
        for cond in conditions:
            for seed in seeds:
                if resume and _already_done(sid, cond, seed, model):
                    print(f"skip (done): {sid} {cond.value} seed={seed}")
                    continue
                rid = run_condition(sid, cond, provider, seed=seed, model=model,
                                    auditor_model=auditor_model)
                metrics = compute_run_metrics(rid)
                nrr = metrics.get("nrr")
                print(f"ran {sid} {cond.value:14s} seed={seed} -> {rid} "
                      f"NRR={nrr if nrr is None else round(nrr,3)} "
                      f"{'ESCALATED' if metrics.get('escalated') else ''}")
                done += 1
    return done


def main():
    ap = argparse.ArgumentParser(description="RoomBridge experiment runner")
    ap.add_argument("--scenario", default="all", help="scenario id, comma-list, or 'all'")
    ap.add_argument("--conditions", default="A,B,C,D")
    ap.add_argument("--seeds", default="")
    ap.add_argument("--provider", default="mock", choices=["mock", "openrouter"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--auditor-model", default=None)
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args()

    init_db()
    loaded = load_all()
    model = args.model or (settings.default_model if args.provider == "openrouter" else "mock")
    auditor = args.auditor_model or (settings.auditor_model if args.provider == "openrouter" else "mock")

    scenario_ids = loaded if args.scenario == "all" else args.scenario.split(",")
    cond_map = {"A": Condition.A_GENERIC, "B": Condition.B_CONTEXT,
                "C": Condition.C_DELIBERATE, "D": Condition.D_ROOMBRIDGE}
    conditions = [cond_map[c.strip().upper()] for c in args.conditions.split(",")]
    seeds = [int(x) for x in args.seeds.split(",")] if args.seeds else None
    if seeds is None:
        seeds = [None]  # use each scenario's own seed

    total = 0
    for sid in scenario_ids:
        used_seeds = seeds if seeds != [None] else [_scenario_seed(sid)]
        total += run_sweep([sid], conditions, used_seeds, args.provider, model, auditor,
                           resume=not args.no_resume)
    print(f"\nDone. {total} runs executed.")


def _scenario_seed(scenario_id: str) -> int:
    with session_scope() as s:
        sc = s.get(M.Scenario, scenario_id)
        return sc.seed if sc else 42


if __name__ == "__main__":
    main()
