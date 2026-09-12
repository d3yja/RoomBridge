"""The auditor must never see the mediator's rationale or the deliberation transcript.
Enforced two ways: the allowlist rejects those fields, and no rendered auditor prompt
shares an 8-word shingle with a mediator rationale / agent message (plan sections 6, 8)."""
from roombridge.prompts.registry import get_prompt
from roombridge.prompts import PromptContext
from roombridge.domain.contracts import Need


def test_auditor_allowlist_excludes_leaky_fields():
    allowed = get_prompt("audit_need").allowed_fields
    assert allowed == frozenset({"need", "agreement_text"})
    for leaky in ["rationale", "messages", "transcript", "condition", "conflicts"]:
        assert leaky not in allowed


def test_auditor_context_rejects_out_of_allowlist_fields():
    import pytest
    with pytest.raises(ValueError):
        PromptContext(get_prompt("audit_need").allowed_fields,
                      need=Need(need_id="need_001", owner_id="p_A", verbatim="x"),
                      agreement_text="y", mediator_rationale="SECRET")


def _shingles(text, k=8):
    words = text.split()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def test_no_rationale_shingle_leaks_into_auditor_prompt():
    need = Need(need_id="need_001", owner_id="p_A",
                verbatim="I need the room quiet from 10pm because I have to be up at 5am.")
    agreement = "1. Quiet hours apply in the room from 22:00 to 05:00 every day of the week."
    mediator_rationale = ("I decided to prioritise the early riser because sleep is a "
                          "non negotiable boundary and the guest need is only a mild preference.")
    spec = get_prompt("audit_need")
    ctx = PromptContext(spec.allowed_fields, need=need, agreement_text=agreement)
    rendered = ctx.format(spec.system) + "\n" + ctx.format(spec.user)
    assert not (_shingles(rendered) & _shingles(mediator_rationale))
