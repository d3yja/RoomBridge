"""Individual pipeline steps. Each is a typed function over a StepExecutor."""
from __future__ import annotations

from ..config import settings
from ..domain import contracts as C
from ..prompts import PromptContext
from ..prompts.registry import get_prompt
from .executor import StepExecutor


def _ctx(prompt_name: str, **fields) -> PromptContext:
    return PromptContext(get_prompt(prompt_name).allowed_fields, **fields)


def extract_needs(ex: StepExecutor, owner_id: str, statements: str) -> list[C.Need]:
    ctx = _ctx("extract_needs", owner_id=owner_id, statements=statements)
    return ex.run_list("extract_needs", ctx, C.Need, temperature=0.0)


def context_note(ex: StepExecutor, need: C.Need) -> C.ContextNote:
    ctx = _ctx("context_note", need=need)
    return ex.run_object("context_note", ctx, C.ContextNote, temperature=0.3)


def identify_conflicts(ex: StepExecutor, needs: list[C.Need]) -> list[C.Conflict]:
    ctx = _ctx("identify_conflicts", needs=needs)
    return ex.run_list("identify_conflicts", ctx, C.Conflict, temperature=0.0)


def generate_agreement(
    ex: StepExecutor, needs, conflicts, context_notes, *, seed=None, failing_need_ids=None,
) -> C.Agreement:
    banner = ""
    if failing_need_ids:
        banner = ("REVISION: the following needs were found NOT preserved and MUST be "
                  f"addressed now. FAILING_NEED_IDS: {list(failing_need_ids)}\n")
    ctx = _ctx("generate_agreement", needs=needs, conflicts=conflicts,
               context_notes=context_notes, revision_banner=banner)
    return ex.run_object("generate_agreement", ctx, C.Agreement, seed=seed, temperature=1.0)


def generate_generic(ex: StepExecutor, statements: str, *, seed=None) -> C.Agreement:
    ctx = _ctx("generate_generic", statements=statements)
    return ex.run_object("generate_generic", ctx, C.Agreement, seed=seed, temperature=1.0)


def select_agreement(ex: StepExecutor, needs, candidates: list[dict]) -> int:
    ctx = _ctx("select_agreement", needs=needs, candidates=candidates)
    from pydantic import BaseModel

    class _Sel(BaseModel):
        chosen_index: int = 0
        reason: str = ""

    sel = ex.run_object("select_agreement", ctx, _Sel, temperature=0.0)
    return max(0, min(sel.chosen_index, len(candidates) - 1))


def priority_vector(ex: StepExecutor, owner_id: str, needs, peer_context: str = "") -> C.PriorityVector:
    ctx = _ctx("priority_vector", owner_id=owner_id, needs=needs, peer_context=peer_context)
    return ex.run_object("priority_vector", ctx, C.PriorityVector, temperature=0.5)
