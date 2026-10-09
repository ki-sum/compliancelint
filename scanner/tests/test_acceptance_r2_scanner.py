"""Acceptance round 2 (2026-10-09) — scanner fixes, founder: fix before release.

- Overall verdict: a scan whose articles are all not_applicable, or compliant + not_applicable with nothing undecided,
  was summarised "unable_to_determine" (cl_scan_all else branch).
- Art. 82 (manual obligation): the AI's "false" became NON_COMPLIANT and fed the dashboard's Penalty Exposure; the
  sync post-process reset only partial (hybrid) obligations to UNABLE_TO_DETERMINE.
- The Art. 2(12) reason always read "Licence: unknown" — open_source_license was read but not in the template.
- cl_scan_all fell back silently to the unscoped scan when the dashboard settings could not be fetched (5 s timeout,
  hit on a cold dev server): neither the AI nor the user learnt that the Profiling Wizard answers were not applied.
"""
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402
from core.context import _FIELD_DESCRIPTIONS, _build_answers_template  # noqa: E402


@pytest.mark.parametrize("levels,failed,expected", [
    (["not_applicable"] * 44, [], "not_applicable"),
    (["compliant", "not_applicable", "compliant"], [], "compliant"),
    (["compliant", "unable_to_determine", "not_applicable"], [], "unable_to_determine"),
    (["compliant", "partial"], [], "partial"),
    (["compliant", "non_compliant", "not_applicable"], [], "non_compliant"),
    (["compliant", "not_applicable"], [9], "partial"),
])
def test_overall_verdict(levels, failed, expected):
    assert server._overall_verdict(levels, failed) == expected


def test_manual_obligation_answer_does_not_become_non_compliant():
    findings = [{"obligation_id": "ART82-OBL-2", "level": "non_compliant", "description": "No corrective action procedure found."}]
    out = server._apply_approach_b_post_process(findings)
    assert out[0]["level"] == "unable_to_determine"
    assert out[0]["description"].startswith("[COVERAGE GAP — manual]")


def test_manual_obligation_not_applicable_stays():
    findings = [{"obligation_id": "ART82-OBL-2", "level": "not_applicable", "description": "x"}]
    assert server._apply_approach_b_post_process(findings)[0]["level"] == "not_applicable"


def test_open_source_license_is_a_template_field():
    assert "open_source_license" in _build_answers_template()["_scope"]
    assert "SPDX" in _FIELD_DESCRIPTIONS["_scope"]["open_source_license"]


def test_dashboard_settings_unavailable_is_reported(monkeypatch, tmp_path):
    class Cfg:
        saas_api_key = "cl_key"
        saas_url = "http://localhost:3000"

    class Ctx:
        compliance_answers = {"_scope": {}}

    monkeypatch.setattr(server, "_fetch_saas_scan_settings", lambda *a, **k: None)
    assert server._apply_saas_scan_settings(Ctx(), Cfg(), str(tmp_path), "cl_scan_all") == "unavailable"
    assert "Profiling Wizard" in server._DASHBOARD_SETTINGS_UNAVAILABLE


def test_not_connected_is_reported(tmp_path):
    class Cfg:
        saas_api_key = None

    class Ctx:
        compliance_answers = {"_scope": {}}

    assert server._apply_saas_scan_settings(Ctx(), Cfg(), str(tmp_path), "cl_scan_all") == "not_connected"
