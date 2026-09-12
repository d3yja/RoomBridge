"""The whole pipeline runs on the mock provider and produces the research phenomenon:
baselines silently drop >=1 need, RoomBridge (D) drops none; escalation scenarios halt."""
from sqlmodel import select

from roombridge.domain import models as M
from roombridge.domain.db import session_scope
from roombridge.domain.enums import Condition
from roombridge.providers import get_provider
from roombridge.conditions.registry import run_condition
from roombridge.metrics.compute import compute_run_metrics


def _run(sid, cond):
    rid = run_condition(sid, cond, get_provider("mock"), model="mock", auditor_model="mock")
    return rid, compute_run_metrics(rid)


def test_baselines_lose_needs_and_d_preserves():
    sid = "sc_001_quiet_vs_social"
    _, a = _run(sid, Condition.A_GENERIC)
    _, d = _run(sid, Condition.D_ROOMBRIDGE)
    assert a["silent_loss_count"] >= 1, "baseline should silently drop at least one need"
    assert d["silent_loss_count"] == 0, "RoomBridge should preserve every need"
    assert d["nrr"] > a["nrr"]


def test_d_revision_recovers_a_dropped_need():
    rid, _ = _run("sc_001_quiet_vs_social", Condition.D_ROOMBRIDGE)
    with session_scope() as s:
        pre = s.exec(select(M.NeedAudit).where(
            M.NeedAudit.run_id == rid, M.NeedAudit.phase == "pre_revision")).all()
        fin = s.exec(select(M.NeedAudit).where(
            M.NeedAudit.run_id == rid, M.NeedAudit.phase == "final")).all()
    pre_lost = {a.need_id for a in pre if a.status.value in ("not_addressed", "violated")}
    fin_lost = {a.need_id for a in fin if a.status.value in ("not_addressed", "violated")}
    assert pre_lost, "expected the pre-revision audit to catch a dropped need"
    assert not fin_lost, "revision should have recovered the dropped need(s)"


def test_escalation_halts_all_conditions():
    for cond in Condition:
        rid, m = _run("sc_005_escalation_threat", cond)
        with session_scope() as s:
            run = s.get(M.Run, rid)
            esc = s.exec(select(M.EscalationEvent).where(M.EscalationEvent.run_id == rid)).all()
        assert run.escalated and run.status == "escalated"
        assert run.final_agreement_text is None
        assert len(esc) == 1
