"""cl_scan_all agrees with the dashboard once Human Gates answers and evidence are applied (found on the production
site, 2026-10-21).

After the obligations of a limited-risk system were confirmed in Human Gates (dashboard: Compliant, 100 %), a rescan
still said overall "partial" and listed ART04-OBL-1, ART50-OBL-4b and ART50-OBL-5 under `pending_evidence` — all
answered with evidence on the dashboard. The scanner reads the dashboard's effective statuses (the endpoint
cl_action_plan already uses) and: drops pending items that are compliant there, and reports the dashboard's current
counts as `totals.findings_on_dashboard_now` with `dashboard_overall`.
"""
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def _report(pending_oids):
    return {
        "overall_compliance": "partial",
        "pending_evidence": {
            "count": len(pending_oids),
            "obligations": [{"obligation_id": o, "expected": 1, "actual": 0, "missing": "evidence"} for o in pending_oids],
            "note": "x",
        },
        "totals": {"explanation": "Three counts …"},
    }


DASHBOARD = {
    "ART04-OBL-1": "COMPLIANT",
    "ART50-OBL-1": "COMPLIANT",
    "ART50-OBL-4b": "COMPLIANT",
    "ART50-OBL-5": "COMPLIANT",
    "ART06-CLS-2": "UNABLE_TO_DETERMINE",
}


def test_pending_items_compliant_on_the_dashboard_are_dropped():
    r = _report(["ART04-OBL-1", "ART50-OBL-4b", "ART50-OBL-5", "ART06-CLS-2"])
    server._apply_dashboard_overlay(r, DASHBOARD)
    assert [p["obligation_id"] for p in r["pending_evidence"]["obligations"]] == ["ART06-CLS-2"]
    assert r["pending_evidence"]["count"] == 1


def test_no_pending_left_removes_the_block():
    r = _report(["ART04-OBL-1"])
    server._apply_dashboard_overlay(r, DASHBOARD)
    assert "pending_evidence" not in r


def test_the_dashboard_counts_are_reported():
    r = _report([])
    server._apply_dashboard_overlay(r, DASHBOARD)
    now = r["totals"]["findings_on_dashboard_now"]
    assert now == {"unit": "findings (one per obligation, not-applicable ones not listed)", "compliant": 4,
                   "non_compliant": 0, "needs_review": 1}
    assert r["dashboard_overall"] == "needs_review"
    assert "findings_on_dashboard_now" in r["totals"]["explanation"]


def test_all_compliant_on_the_dashboard():
    r = _report([])
    server._apply_dashboard_overlay(r, {"ART04-OBL-1": "COMPLIANT", "ART50-OBL-1": "COMPLIANT"})
    assert r["dashboard_overall"] == "compliant"


def test_a_non_compliant_one_decides():
    r = _report([])
    server._apply_dashboard_overlay(r, {"ART04-OBL-1": "COMPLIANT", "ART50-OBL-2": "NON_COMPLIANT"})
    assert r["dashboard_overall"] == "non_compliant"


def test_without_dashboard_data_nothing_changes():
    r = _report(["ART04-OBL-1"])
    before = repr(r)
    server._apply_dashboard_overlay(r, {})
    assert repr(r) == before
