"""Hall-policy layer (plan addendum): isolation, evidence grounding, deterministic rule,
metrics, and the end-to-end A-violates / D-complies demonstration."""
import math

import pytest
from sqlmodel import select

from roombridge.domain import contracts as C
from roombridge.domain import models as M
from roombridge.domain.db import session_scope
from roombridge.domain.enums import Condition, PolicyStatus
from roombridge.metrics.compute import compute_run_metrics
from roombridge.metrics.policy import policy_metrics
from roombridge.pipeline.policy import _grounded, hard_rule_violations
from roombridge.pipeline.rules import policy_violation_rule, escalation_rule
from roombridge.policies.loader import load_rules
from roombridge.prompts.registry import get_prompt
from roombridge.providers import get_provider
from roombridge.conditions.registry import run_condition


# --- rules load + isolation ---------------------------------------------------
def test_rules_load_with_hard_and_guideline():
    rules = load_rules()
    assert any(r.rule_id == "HR_NO_COOKING" and r.type == "hard" for r in rules)
    assert any(r.type == "guideline" for r in rules)
    assert all(r.source for r in rules)  # every rule is cited


def test_policy_auditor_allowlist_is_isolated():
    allowed = get_prompt("check_policy").allowed_fields
    assert allowed == frozenset({"agreement_text", "rules"})
    for leaky in ["rationale", "messages", "needs", "condition"]:
        assert leaky not in allowed


# --- evidence grounding -------------------------------------------------------
def test_violation_without_quote_is_downgraded():
    f = C.PolicyFinding(rule_id="HR_NO_COOKING", status=PolicyStatus.VIOLATED,
                        evidence_quote=None, rationale="trust me")
    assert _grounded(f, "1. Keep the room tidy.").status == PolicyStatus.COMPLIANT


def test_violation_with_absent_quote_is_downgraded():
    f = C.PolicyFinding(rule_id="HR_NO_COOKING", status=PolicyStatus.VIOLATED,
                        evidence_quote="fry chicken in the room", rationale="x")
    assert _grounded(f, "1. Share the fridge fairly.").status == PolicyStatus.COMPLIANT


def test_violation_with_real_quote_is_kept():
    text = "1. Priya may cook dinner in the room on weeknights."
    f = C.PolicyFinding(rule_id="HR_NO_COOKING", status=PolicyStatus.VIOLATED,
                        evidence_quote="cook dinner in the room", rationale="x")
    assert _grounded(f, text).status == PolicyStatus.VIOLATED


# --- deterministic layer: fires on in-room, not on compliant reframing ---------
def test_rule_fires_on_in_room_cooking():
    hits = dict(policy_violation_rule("I need to cook dinner in our room most weeknights."))
    assert "HR_NO_COOKING" in hits


def test_rule_ignores_compliant_reframe():
    assert policy_violation_rule(
        "Use the shared pantry / common kitchen for cooking rather than the room.") == []
    assert policy_violation_rule(
        "Keep smoking and alcohol out of the room, in line with hall rules.") == []


# --- escalation enrichment ----------------------------------------------------
def test_criminal_escalation_routes_to_police():
    v = escalation_rule("My roommate is selling drugs from our room.")
    assert v is not None and v.category.value == "criminal"
    assert "police" in v.suggested_support.lower()


@pytest.mark.parametrize("benign", [
    "agree on a quiet-notification method rather than texting the group",
    "I use methodical study methods",
    "we share a method for cleaning",
])
def test_criminal_pattern_does_not_match_ordinary_words(benign):
    # regression: 'meth\\w*' used to match 'method' and falsely escalate a normal scenario.
    assert escalation_rule(benign) is None


# --- metric -------------------------------------------------------------------
def test_policy_compliance_rate():
    rows = [
        {"rule_id": "a", "type": "hard", "status": "violated"},
        {"rule_id": "b", "type": "hard", "status": "compliant"},
        {"rule_id": "c", "type": "guideline", "status": "compliant"},
        {"rule_id": "d", "type": "hard", "status": "not_applicable"},  # excluded
    ]
    m = policy_metrics(rows)
    assert math.isclose(m["policy_compliance_rate"], 2 / 3)
    assert m["policy_violation_count"] == 1
    assert m["policy_applicable_rules"] == 3


# --- end-to-end demonstration -------------------------------------------------
def _run(cond):
    rid = run_condition("sc_007_policy_conflict", cond, get_provider("mock"),
                        model="mock", auditor_model="mock")
    return rid, compute_run_metrics(rid)


def test_baseline_breaks_rule_and_workflow_complies():
    _, a = _run(Condition.A_GENERIC)
    _, d = _run(Condition.D_ROOMBRIDGE)
    assert a["policy_hard_violation_count"] >= 1, "generic baseline should break a hall rule"
    assert d["policy_hard_violation_count"] == 0, "RoomBridge should comply with hall rules"
    assert d["policy_compliance_rate"] > a["policy_compliance_rate"]


def test_policy_conflict_is_surfaced_not_dropped():
    rid, _ = _run(Condition.D_ROOMBRIDGE)
    with session_scope() as s:
        conflicts = s.exec(select(M.Assumption).where(
            M.Assumption.run_id == rid, M.Assumption.detected_by == "policy_conflict")).all()
    assert conflicts, "a need colliding with a hard rule must be surfaced as a policy conflict"
    assert any(c.grounded_in_need_id == "need_001" for c in conflicts)
