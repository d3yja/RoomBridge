"""ContextNote structurally cannot originate a preference: need_id required, no high
confidence, no preference field (plan section 5)."""
import pytest
from pydantic import ValidationError

from roombridge.domain.contracts import ContextNote


def test_context_note_requires_need_id():
    with pytest.raises(ValidationError):
        ContextNote(possible_reasons=["x"])  # no need_id


def test_context_note_rejects_high_confidence():
    with pytest.raises(ValidationError):
        ContextNote(need_id="need_001", confidence="high")


def test_context_note_has_no_preference_field():
    fields = set(ContextNote.model_fields)
    for forbidden in ["preference", "predicted_preference", "prefers", "wants"]:
        assert forbidden not in fields
    assert ContextNote(need_id="need_001", confidence="low").need_id == "need_001"
