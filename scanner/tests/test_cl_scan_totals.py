"""cl_scan reports the same totals as cl_scan_all (series-2 recording, 2026-10-25, QA #34).

After a single-article rescan the assistant told the user on screen that "the scan result has no
findings_as_recorded_on_dashboard field, so I can't give the counts": cl_scan returned no totals at all, while
cl_scan_all always does. Now cl_scan — one article or several — carries `totals` built the same way, and, when the
project is connected, the dashboard's current numbers (findings_on_dashboard_now) as cl_scan_all does.
"""
import json
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)
sys.path.insert(0, os.path.dirname(__file__))

import server  # noqa: E402
from test_cl_scan_saved_levels import _context, _first_json, _project  # noqa: E402

KEYS = {"explanation", "articles_by_ai_assessment", "findings_by_ai_assessment", "findings_as_recorded_on_dashboard"}


def test_single_article_scan_has_totals(tmp_path):
    out = _first_json(server.cl_scan(_project(tmp_path), project_context=_context(), articles="50"))
    totals = out["totals"]
    assert KEYS <= set(totals)
    assert totals["articles_by_ai_assessment"]["total"] == 1
    assert totals["findings_by_ai_assessment"]["total"] == len(out["findings"])


def test_several_articles_scan_has_totals(tmp_path):
    out = _first_json(server.cl_scan(_project(tmp_path), project_context=_context("art4"), articles="50,4"))
    totals = out["totals"]
    assert KEYS <= set(totals)
    assert totals["articles_by_ai_assessment"]["total"] == 2


def test_connected_scan_has_the_dashboard_numbers(tmp_path, monkeypatch):
    project = _project(tmp_path)
    monkeypatch.setattr(server, "_fetch_effective_status_from_saas",
                        lambda _p: {"ART50-OBL-1": "COMPLIANT", "ART50-OBL-2": "PARTIAL", "ART04-OBL-1": "COMPLIANT"})
    out = _first_json(server.cl_scan(project, project_context=_context(), articles="50"))
    now = out["totals"]["findings_on_dashboard_now"]
    assert (now["compliant"], now["non_compliant"], now["needs_review"]) == (2, 0, 1)
