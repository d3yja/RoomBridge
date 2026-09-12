"""Prompt registry: binds each versioned template to its field allowlist and output schema.

The allowlists here ARE the leakage-prevention policy (plan section 8). The auditor's
allowlist is {need, agreement_text} and nothing else -- no rationale, no transcript, no
sibling needs -- so isolation is guaranteed by construction, not by discipline.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Type

from pydantic import BaseModel

from ..domain import contracts as C

_DIR = Path(__file__).resolve().parent


def _load(filename: str) -> tuple[str, str]:
    text = (_DIR / filename).read_text(encoding="utf-8")
    _, system, user = text.split("=== SYSTEM ===")[0], "", ""
    parts = text.split("=== SYSTEM ===", 1)[1].split("=== USER ===", 1)
    system, user = parts[0].strip(), parts[1].strip()
    return system, user


@dataclass(frozen=True)
class PromptSpec:
    name: str
    version: str
    step: str                       # marker the mock keys off; label real models ignore
    allowed_fields: frozenset[str]
    system: str
    user: str
    output_schema: Type[BaseModel] | None  # None => the caller parses a list of this item
    item_schema: Type[BaseModel] | None = None


def _spec(name, version, step, allowed, schema, item=None) -> PromptSpec:
    system, user = _load(f"{name}.{version}.md")
    return PromptSpec(name, version, step, frozenset(allowed), system, user, schema, item)


PROMPTS: dict[str, PromptSpec] = {
    "extract_needs": _spec(
        "extract_needs", "v1", "extract_needs",
        {"owner_id", "statements"}, None, item=C.Need),
    "context_note": _spec(
        "context_note", "v1", "context_note",
        {"need"}, C.ContextNote),
    "identify_conflicts": _spec(
        "identify_conflicts", "v1", "identify_conflicts",
        {"needs"}, None, item=C.Conflict),
    "generate_agreement": _spec(
        "generate_agreement", "v1", "generate_agreement",
        {"needs", "conflicts", "context_notes", "revision_banner"}, C.Agreement),
    "generate_generic": _spec(
        "generate_generic", "v1", "generate_agreement",
        {"statements"}, C.Agreement),
    "select_agreement": _spec(
        "select_agreement", "v1", "select_agreement",
        {"needs", "candidates"}, None),
    "audit_need": _spec(
        "audit_need", "v1", "audit_need",
        {"need", "agreement_text"}, C.AuditVerdict),
    "check_assumptions": _spec(
        "check_assumptions", "v1", "check_assumptions",
        {"needs", "agreement_text"}, None, item=C.AssumptionFinding),
    "assess_escalation": _spec(
        "assess_escalation", "v1", "assess_escalation",
        {"statements"}, C.EscalationVerdict),
    "priority_vector": _spec(
        "priority_vector", "v1", "priority_vector",
        {"owner_id", "needs", "peer_context"}, C.PriorityVector),
}


def get_prompt(name: str) -> PromptSpec:
    if name not in PROMPTS:
        raise KeyError(f"unknown prompt {name!r}")
    return PROMPTS[name]
