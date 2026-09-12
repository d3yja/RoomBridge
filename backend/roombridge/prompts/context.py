"""PromptContext: an allowlisted field carrier.

The only way a step gets data into a prompt. Rendering raises if a template references
any field outside the step's declared allowlist. This is how leakage prevention is
enforced structurally rather than by review convention (plan sections 5, 6, 8): the
auditor's context, for example, simply has no reachable path to the mediator's rationale.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    return value


class PromptContext:
    def __init__(self, allowed_fields: frozenset[str], **fields: Any):
        illegal = set(fields) - set(allowed_fields)
        if illegal:
            raise ValueError(
                f"PromptContext received fields outside the allowlist: {sorted(illegal)}. "
                f"Allowed: {sorted(allowed_fields)}. This is a leakage guard, not a typo check."
            )
        self.allowed_fields = allowed_fields
        self._fields = fields

    def get(self, name: str) -> Any:
        if name not in self.allowed_fields:
            raise KeyError(
                f"Field {name!r} is not in this step's allowlist {sorted(self.allowed_fields)}."
            )
        return self._fields.get(name)

    def render_json(self, name: str) -> str:
        return json.dumps(_to_jsonable(self.get(name)), ensure_ascii=False, indent=2)

    def format(self, template: str) -> str:
        """Fill {field} and {field:json} placeholders, enforcing the allowlist."""
        import re

        def repl(match: "re.Match[str]") -> str:
            token = match.group(1)
            if token.endswith(":json"):
                return self.render_json(token[:-5])
            value = self.get(token)
            return value if isinstance(value, str) else json.dumps(_to_jsonable(value))

        return re.sub(r"\{([a-zA-Z_][\w]*(?::json)?)\}", repl, template)
