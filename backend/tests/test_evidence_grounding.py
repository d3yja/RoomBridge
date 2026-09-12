"""A preserved/partial verdict whose evidence_quote is absent from the agreement is forced
down to unresolved -- the anti-rationalization guard (plan sections 6, 10 failure mode 5)."""
from roombridge.domain.contracts import AuditVerdict
from roombridge.domain.enums import NeedStatus
from roombridge.pipeline.audit import _grounded


def test_preserved_without_quote_is_forced_down():
    v = AuditVerdict(status=NeedStatus.PRESERVED, evidence_quote=None, rationale="trust me")
    assert _grounded(v, "1. Some agreement text.").status == NeedStatus.UNRESOLVED


def test_preserved_with_absent_quote_is_forced_down():
    v = AuditVerdict(status=NeedStatus.PRESERVED,
                     evidence_quote="quiet hours from 22:00", rationale="x")
    assert _grounded(v, "1. The room stays warm.").status == NeedStatus.UNRESOLVED


def test_preserved_with_real_quote_is_kept():
    agreement = "1. Quiet hours apply from 22:00 to 05:00."
    v = AuditVerdict(status=NeedStatus.PRESERVED,
                     evidence_quote="Quiet hours apply from 22:00", rationale="x")
    assert _grounded(v, agreement).status == NeedStatus.PRESERVED


def test_not_addressed_is_untouched():
    v = AuditVerdict(status=NeedStatus.NOT_ADDRESSED, evidence_quote=None)
    assert _grounded(v, "anything").status == NeedStatus.NOT_ADDRESSED
