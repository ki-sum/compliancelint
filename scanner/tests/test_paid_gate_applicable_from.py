"""Paid strict gate must not require answers for obligations that do not apply yet.

Self-audit A12 (2026-10-02): the questionnaire marks ART05-PRO-1ba/1bb completion_required,
but they apply only from 2026-12-02 (Art. 113, third paragraph, point (a), as amended).
enforce_paid_completion had no date check, so strict paid scans stayed pending until users
answered two not-yet-applicable questions.
"""
import json
import os
import sys
from datetime import date

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.enforce_paid_completion import enforce_paid_completion  # noqa: E402

Q = {
    "ART05-PRO-1a": {"completion_required": True, "evidence_min": 0},
    "ART05-PRO-1ba": {"completion_required": True, "evidence_min": 0},
}
FROM = {"ART05-PRO-1ba": "2026-12-02"}
ANSWERS = {"ART05-PRO-1a": True}  # 1ba unanswered


def _pending(today):
    r = enforce_paid_completion(Q, {}, "strict", ANSWERS, applicable_from=FROM, today=today)
    return r, [p["obligation_id"] for p in r.pending]


def test_before_application_date_not_required():
    r, pending = _pending(date(2026, 12, 1))
    assert r.status == "ok"
    assert pending == []


def test_on_application_date_required():
    r, pending = _pending(date(2026, 12, 2))
    assert r.status == "pending_evidence_needs_sync"
    assert pending == ["ART05-PRO-1ba"]


def test_after_application_date_required():
    _, pending = _pending(date(2027, 3, 1))
    assert pending == ["ART05-PRO-1ba"]


def test_without_dates_behaviour_unchanged():
    r = enforce_paid_completion(Q, {}, "strict", ANSWERS)
    assert [p["obligation_id"] for p in r.pending] == ["ART05-PRO-1ba"]


class _StubCtx:
    def __init__(self, scope, answers):
        self.compliance_answers = {"_scope": scope, "_oid_answers": answers}


def test_wrapper_uses_obligation_json_dates_and_the_clock(tmp_path, monkeypatch):
    import server
    from core import application_dates
    scope = {"_saas_questionnaire": Q, "_saas_enforcement_mode": "strict"}

    monkeypatch.setattr(application_dates, "_today", lambda: date(2026, 11, 30))
    assert server._check_paid_completion_gate(_StubCtx(dict(scope), ANSWERS), str(tmp_path)) is None

    monkeypatch.setattr(application_dates, "_today", lambda: date(2026, 12, 2))
    blocked = json.loads(server._check_paid_completion_gate(_StubCtx(dict(scope), ANSWERS), str(tmp_path)))
    assert [p["obligation_id"] for p in blocked["pending_obligations"]] == ["ART05-PRO-1ba"]
