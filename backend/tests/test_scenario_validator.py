"""The validator rejects the conditions that would invalidate the metrics (plan section 11)."""
import pytest

from roombridge.scenarios.loader import _ScenarioYAML, validate_scenario, ScenarioValidationError

BASE = {
    "scenario_id": "t", "participants": [
        {"participant_id": "p_A", "display_name": "A"},
        {"participant_id": "p_B", "display_name": "B"}],
}


def _needs(counts):
    out, i = [], 0
    for owner, c in counts.items():
        for _ in range(c):
            i += 1
            out.append({"need_id": f"need_{i:03d}", "owner_id": owner, "verbatim": "x"})
    return out


def test_rejects_unbalanced_need_counts():
    data = _ScenarioYAML(**BASE, needs=_needs({"p_A": 3, "p_B": 1}),
                         gold_audit={f"need_{i:03d}": "preserved" for i in range(1, 5)})
    with pytest.raises(ScenarioValidationError):
        validate_scenario(data)


def test_rejects_missing_gold():
    data = _ScenarioYAML(**BASE, needs=_needs({"p_A": 1, "p_B": 1}),
                         gold_audit={"need_001": "preserved"})  # need_002 missing
    with pytest.raises(ScenarioValidationError):
        validate_scenario(data)


def test_accepts_balanced_covered_scenario():
    data = _ScenarioYAML(**BASE, needs=_needs({"p_A": 2, "p_B": 2}),
                         gold_audit={f"need_{i:03d}": "not_addressed" for i in range(1, 5)})
    validate_scenario(data)  # no raise


def test_escalation_scenario_waives_balance():
    data = _ScenarioYAML(**BASE, should_escalate=True,
                         needs=_needs({"p_A": 1, "p_B": 0}), gold_audit={})
    validate_scenario(data)  # no raise



def test_all_shipped_scenarios_load():
    """Every YAML in the scenarios dir validates and there are at least 22 of them."""
    from roombridge.config import SCENARIO_DIR
    from roombridge.scenarios.loader import load_yaml

    files = sorted(SCENARIO_DIR.glob("*.yaml"))
    assert len(files) >= 22, f"expected >=22 scenarios, found {len(files)}"
    for f in files:
        load_yaml(f)  # raises on any validation error
