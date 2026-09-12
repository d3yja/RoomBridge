"""Provider protocol and shared structured-output plumbing.

Rewritten from MultiAgent-Diversity's call_api (sec5_infer_api.py:90), which swallowed
every error into a string and had no retry. Here a call returns a validated Pydantic object
or raises a typed LLMError; a schema-repair retry is attempted before failure.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Protocol, Type, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Any failure to obtain a valid structured response. Recorded on the run, never swallowed."""


@dataclass
class CallResult:
    raw: str
    usage: dict = field(default_factory=dict)
    model: str = ""


Message = dict  # {"role": str, "content": str}


class Provider(Protocol):
    name: str

    def complete_text(
        self, messages: list[Message], *, model: str, seed: int | None, temperature: float
    ) -> CallResult: ...


def _balanced_candidates(text: str):
    """Yield each complete top-level JSON object/array via string-aware bracket balancing,
    so stray braces in prose and braces inside strings don't confuse the scan."""
    start = None
    open_ch = close_ch = ""
    depth = 0
    instr = esc = False
    for i, ch in enumerate(text):
        if start is None:
            if ch in "{[":
                start, open_ch, close_ch, depth = i, ch, ("}" if ch == "{" else "]"), 1
            continue
        if instr:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                instr = False
            continue
        if ch == '"':
            instr = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                yield text[start : i + 1]
                start = None


def extract_json(text: str) -> str:
    """Pull the first PARSEABLE JSON object/array out of a possibly chatty response.
    Replaces MAD's \\boxed{} regex (utils.py:42) with something that survives real models:
    tries each balanced candidate and returns the first that actually json-parses."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).rsplit("```", 1)[0].strip()
    first = None
    for cand in _balanced_candidates(text):
        if first is None:
            first = cand
        try:
            json.loads(cand)
            return cand
        except json.JSONDecodeError:
            continue
    return first if first is not None else text


def parse_into(text: str, schema: Type[T]) -> T:
    payload = extract_json(text)
    data = json.loads(payload)
    return schema.model_validate(data)


class StructuredProvider:
    """Wraps a text provider with schema validation + one repair retry."""

    def __init__(self, backend: Provider):
        self.backend = backend
        self.name = backend.name

    def complete_text(self, messages, *, model, seed, temperature) -> CallResult:
        return self.backend.complete_text(
            messages, model=model, seed=seed, temperature=temperature
        )

    def complete_structured(
        self,
        messages: list[Message],
        schema: Type[T],
        *,
        model: str,
        seed: int | None = None,
        temperature: float = 0.0,
    ) -> tuple[T, CallResult]:
        result = self.backend.complete_text(
            messages, model=model, seed=seed, temperature=temperature
        )
        try:
            return parse_into(result.raw, schema), result
        except (json.JSONDecodeError, ValidationError) as first_err:
            repair = messages + [
                {"role": "assistant", "content": result.raw},
                {
                    "role": "user",
                    "content": (
                        "That did not parse against the required schema. Reply with ONLY valid "
                        f"JSON matching this schema and nothing else:\n{json.dumps(schema.model_json_schema())}\n"
                        f"Error: {first_err}"
                    ),
                },
            ]
            retry = self.backend.complete_text(
                repair, model=model, seed=seed, temperature=0.0
            )
            try:
                return parse_into(retry.raw, schema), retry
            except (json.JSONDecodeError, ValidationError) as second_err:
                raise LLMError(
                    f"structured parse failed after repair for {schema.__name__}: {second_err}"
                ) from second_err


def get_provider(name: str) -> StructuredProvider:
    if name == "mock":
        from .mock import MockProvider

        return StructuredProvider(MockProvider())
    if name == "openrouter":
        from .openrouter import OpenRouterProvider

        return StructuredProvider(OpenRouterProvider())
    raise ValueError(f"unknown provider: {name!r} (expected 'mock' or 'openrouter')")
