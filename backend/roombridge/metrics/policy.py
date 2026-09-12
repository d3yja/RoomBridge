"""Hall-policy compliance metrics (plan addendum) -- a SECOND outcome axis, independent of
needs retention. Not derived from MAD; reported alongside NRR, never merged with it."""
from __future__ import annotations

from ..domain.enums import PolicyStatus


def policy_metrics(rows: list[dict]) -> dict[str, float | dict]:
    """rows: PolicyAudit dicts {rule_id, type, status, ...}. `not_applicable` is excluded
    from the denominator; a rule is 'applicable' if it is compliant or violated."""
    applicable = [r for r in rows if r["status"] in
                  (PolicyStatus.COMPLIANT.value, PolicyStatus.VIOLATED.value)]
    violated = [r for r in applicable if r["status"] == PolicyStatus.VIOLATED.value]
    hard_violated = [r for r in violated if r.get("type") == "hard"]
    n = len(applicable)
    return {
        "policy_compliance_rate": (1.0 - len(violated) / n) if n else 1.0,
        "policy_violation_count": len(violated),
        "policy_hard_violation_count": len(hard_violated),
        "policy_applicable_rules": n,
        "policy_violated_rules": {r["rule_id"]: r["status"] for r in violated},
    }
