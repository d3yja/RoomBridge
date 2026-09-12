"""FastAPI app. Local-only, no auth, synthetic scenarios by default (plan sections 13-15).

Two ways to run a condition:
  * POST /runs         -> run synchronously, return the full run view (used for cached demo).
  * GET  /runs/stream  -> SSE: pipeline steps stream as they happen (the live workbench).
"""
from __future__ import annotations

import json
import queue
import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import select

from ..config import settings
from ..domain import models as M
from ..domain.db import init_db, session_scope
from ..domain.enums import Condition
from ..providers import get_provider
from ..providers.base import LLMError
from ..scenarios.loader import load_all
from .serializers import list_scenarios, run_view, scenario_view

app = FastAPI(title="RoomBridge API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_COND_MAP = {"A": Condition.A_GENERIC, "B": Condition.B_CONTEXT,
             "C": Condition.C_DELIBERATE, "D": Condition.D_ROOMBRIDGE,
             **{c.value: c for c in Condition}}


@app.on_event("startup")
def _startup() -> None:
    init_db()
    load_all()


@app.get("/health")
def health() -> dict:
    return {"ok": True, "live_input_enabled": settings.live_input_enabled}


@app.get("/scenarios")
def scenarios() -> list[dict]:
    return list_scenarios()


@app.get("/scenarios/{sid}")
def scenario(sid: str) -> dict:
    view = scenario_view(sid)
    if not view.get("scenario_id"):
        raise HTTPException(404, "unknown scenario")
    return view


class RunRequest(BaseModel):
    scenario_id: str
    condition: str
    provider: str = "mock"
    seed: int | None = None
    model: str | None = None
    auditor_model: str | None = None


def _resolve_condition(name: str) -> Condition:
    if name not in _COND_MAP:
        raise HTTPException(400, f"unknown condition {name!r}")
    return _COND_MAP[name]


def _cached_run(req: RunRequest) -> str | None:
    """Return an existing complete run id for this exact config (demo replay from cache)."""
    cond = _resolve_condition(req.condition)
    model = req.model or ("mock" if req.provider == "mock" else settings.default_model)
    with session_scope() as s:
        stmt = select(M.Run).where(
            M.Run.scenario_id == req.scenario_id, M.Run.condition == cond,
            M.Run.model == model, M.Run.status.in_(["complete", "escalated"]))
        if req.seed is not None:
            stmt = stmt.where(M.Run.seed == req.seed)
        existing = s.exec(stmt.order_by(M.Run.started_at.desc())).first()
    return existing.run_id if existing else None


@app.post("/runs")
def create_run(req: RunRequest, use_cache: bool = True) -> dict:
    from ..conditions.registry import run_condition
    from ..metrics.compute import compute_run_metrics

    if use_cache:
        cached = _cached_run(req)
        if cached:
            return {"cached": True, **run_view(cached)}

    cond = _resolve_condition(req.condition)
    try:
        provider = get_provider(req.provider)
    except LLMError as e:
        raise HTTPException(400, str(e))
    rid = run_condition(req.scenario_id, cond, provider, seed=req.seed,
                        model=req.model, auditor_model=req.auditor_model)
    compute_run_metrics(rid)
    return {"cached": False, **run_view(rid)}


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    view = run_view(run_id)
    if not view:
        raise HTTPException(404, "unknown run")
    return view


@app.get("/runs/stream/{scenario_id}/{condition}")
def stream_run(scenario_id: str, condition: str, provider: str = "mock",
               seed: int | None = None) -> StreamingResponse:
    """Server-Sent Events: emit each pipeline step as it happens, then the final run view."""
    from ..conditions.registry import run_condition
    from ..metrics.compute import compute_run_metrics

    cond = _resolve_condition(condition)
    events: "queue.Queue[dict | None]" = queue.Queue()

    def on_event(ev: dict) -> None:
        events.put(ev)

    def worker() -> None:
        try:
            prov = get_provider(provider)
            rid = run_condition(scenario_id, cond, prov, seed=seed, on_event=on_event)
            compute_run_metrics(rid)
            events.put({"kind": "final", "run": run_view(rid)})
        except Exception as e:  # noqa: BLE001 - surface any failure to the client stream
            events.put({"kind": "error", "message": str(e)})
        finally:
            events.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def gen():
        while True:
            ev = events.get()
            if ev is None:
                break
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


class DemoRequest(BaseModel):
    scenario_id: str
    provider: str = "mock"
    seed: int | None = None


@app.post("/demo")
def demo(req: DemoRequest) -> dict:
    """Run all four conditions (from cache when available) for the side-by-side compare."""
    out = {}
    for letter in ["A", "B", "C", "D"]:
        out[letter] = create_run(
            RunRequest(scenario_id=req.scenario_id, condition=letter,
                       provider=req.provider, seed=req.seed), use_cache=True)
    return {"scenario": scenario_view(req.scenario_id), "conditions": out}
