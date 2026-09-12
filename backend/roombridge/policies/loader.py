"""Load the structured hall rules. The raw handbook PDF is never used at runtime; only this
curated, cited YAML is (plan addendum). Cached so every run reuses one parsed copy."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from ..domain.contracts import PolicyRule

_RULES_PATH = Path(__file__).resolve().parent / "hall_rules.yaml"


@lru_cache(maxsize=1)
def load_rules() -> list[PolicyRule]:
    data = yaml.safe_load(_RULES_PATH.read_text(encoding="utf-8"))
    rules = [PolicyRule.model_validate(r) for r in data.get("rules", [])]
    ids = [r.rule_id for r in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate rule_id in hall_rules.yaml")
    for r in rules:
        if r.type not in {"hard", "guideline"}:
            raise ValueError(f"{r.rule_id}: type must be 'hard' or 'guideline'")
    return rules


def rules_for_prompt(rules: list[PolicyRule] | None = None) -> list[dict]:
    """Compact rule dicts for a prompt block: no internals the model doesn't need."""
    rules = rules or load_rules()
    return [{"rule_id": r.rule_id, "type": r.type, "title": r.title,
             "rule_text": r.rule_text, "source": r.source} for r in rules]
