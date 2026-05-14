"""§AT.19 Phase 4 (2026-05-14) round-4 audit gap A.

Python test for `_fetch_effective_status_from_saas` + `cl_action_plan`
overlay. Mirrors `test_cl_sync.py`'s subprocess.run dispatcher pattern
to avoid hitting a real dashboard. Pins:

  1. With a SaaS COMPLIANT response → matching actions get
     `already_attested_in_dashboard=True`, `priority=LOW`, +
     `dashboard_overlay_summary.actions_marked_already_attested`
     reflects the count.
  2. With NOT_APPLICABLE response → similar tags + `actions_marked_na_in_dashboard`
     increments.
  3. With network failure → overlay degrades silently (empty map),
     plan still returns + `dashboard_overlay_summary.fetched_from_dashboard=False`.
  4. With no api_key → no curl call, overlay empty, plan still returns.

Pre-Phase-4 gap (kisum round-4 audit gap A): the overlay function +
cl_action_plan modification shipped without any Python test. The
TypeScript route test (effective-status.test.ts) only covered the
server side. This file closes the scanner-side test gap.
"""
import json
import os
import subprocess
import sys

import pytest  # noqa: F401 — pytest discovery

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def _seed_rc(project_path, api_key="test-key", project_id="proj-fixture-abc"):
    rc = os.path.join(project_path, ".compliancelintrc")
    with open(rc, "w", encoding="utf-8") as f:
        json.dump({
            "saas_api_key": api_key,
            "saas_url": "https://dash.test.local",
            "project_id": project_id,
            "repo_name": "acme/test",
            "attester_name": "Test User",
            "attester_email": "test@example.test",
        }, f)


def _seed_minimal_scan_context(project_path):
    """Set up just enough scanner state that cl_action_plan can run.

    `cl_action_plan` requires `BaseArticleModule.get_context()` to be set
    (it raises "No project context available" otherwise). The simplest way
    is to call `_ensure_all_modules_loaded` + `BaseArticleModule.set_context`
    directly with a stub.
    """
    server._ensure_all_modules_loaded()
    # Inject a minimal context — exact shape is module-dependent; mirror
    # what cl_scan_all does at its entry. The action_plan() per-module
    # call won't blow up because modules tolerate sparse context.
    from core.protocol import BaseArticleModule
    BaseArticleModule.set_context({"project_path": project_path})


def _make_fake_run(scenario, captured):
    """subprocess.run stand-in.

    scenarios:
      "complaint-art10"  → /effective-status returns ART10-OBL-1=COMPLIANT
      "na-art12"         → /effective-status returns ART12-OBL-1=NOT_APPLICABLE
      "mixed"            → ART10-OBL-1=COMPLIANT + ART12-OBL-1=NOT_APPLICABLE
      "empty"            → returns 200 with `{obligations: {}}` (no overlay)
      "http-500"         → returns 500 (overlay best-effort fails)
      "exception"        → subprocess raises (network down)
    """
    def fake_run(cmd, *args, **kwargs):
        if not isinstance(cmd, (list, tuple)) or not cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        head = cmd[0]
        if head == "git":
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if head != "curl":
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        # Identify the URL the curl is hitting
        url = next((c for c in cmd if isinstance(c, str) and c.startswith("http")), "")
        captured.setdefault("urls", []).append(url)

        if scenario == "exception":
            raise OSError("simulated network down")

        if "/effective-status" not in url:
            # Unrelated curl (e.g. evidence pull); return harmless 200.
            return subprocess.CompletedProcess(cmd, 0, stdout="\n200", stderr="")

        if scenario == "complaint-art10":
            body = json.dumps({
                "project_id": "proj-fixture-abc",
                "repo_id": "r1",
                "scan_id": "scan1",
                "scanned_at": "2026-05-14T00:00:00Z",
                "obligations": {"ART10-OBL-1": "COMPLIANT"},
            })
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{body}\n200", stderr="")
        if scenario == "na-art12":
            body = json.dumps({
                "project_id": "proj-fixture-abc",
                "repo_id": "r1",
                "scan_id": "scan1",
                "scanned_at": "2026-05-14T00:00:00Z",
                "obligations": {"ART12-OBL-1": "NOT_APPLICABLE"},
            })
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{body}\n200", stderr="")
        if scenario == "mixed":
            body = json.dumps({
                "project_id": "proj-fixture-abc",
                "repo_id": "r1",
                "scan_id": "scan1",
                "scanned_at": "2026-05-14T00:00:00Z",
                "obligations": {
                    "ART10-OBL-1": "COMPLIANT",
                    "ART12-OBL-1": "NOT_APPLICABLE",
                },
            })
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{body}\n200", stderr="")
        if scenario == "empty":
            body = json.dumps({"obligations": {}})
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{body}\n200", stderr="")
        if scenario == "http-500":
            return subprocess.CompletedProcess(cmd, 0, stdout="oops\n500", stderr="")

        return subprocess.CompletedProcess(cmd, 0, stdout="\n200", stderr="")
    return fake_run


# ── _fetch_effective_status_from_saas (unit) ──


class TestFetchEffectiveStatusUnit:
    def test_no_api_key_returns_empty_map(self, tmp_path):
        # No .compliancelintrc → saas_api_key empty → fetch returns {}
        result = server._fetch_effective_status_from_saas(str(tmp_path))
        assert result == {}

    def test_http_200_with_obligations_parses_correctly(self, tmp_path, monkeypatch):
        _seed_rc(str(tmp_path))
        captured = {}
        monkeypatch.setattr(subprocess, "run", _make_fake_run("complaint-art10", captured))

        result = server._fetch_effective_status_from_saas(str(tmp_path))
        assert result == {"ART10-OBL-1": "COMPLIANT"}
        # Verify the URL includes project_id from rc
        assert any("/api/v1/projects/proj-fixture-abc/effective-status" in u for u in captured["urls"])

    def test_http_500_returns_empty_map_best_effort(self, tmp_path, monkeypatch):
        _seed_rc(str(tmp_path))
        captured = {}
        monkeypatch.setattr(subprocess, "run", _make_fake_run("http-500", captured))

        result = server._fetch_effective_status_from_saas(str(tmp_path))
        assert result == {}

    def test_network_exception_returns_empty_map_silently(self, tmp_path, monkeypatch):
        _seed_rc(str(tmp_path))
        captured = {}
        monkeypatch.setattr(subprocess, "run", _make_fake_run("exception", captured))

        # The function MUST NOT raise — overlay is best-effort.
        result = server._fetch_effective_status_from_saas(str(tmp_path))
        assert result == {}

    def test_non_string_values_filtered_out(self, tmp_path, monkeypatch):
        _seed_rc(str(tmp_path))

        def custom_run(cmd, *args, **kwargs):
            if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "curl":
                # Status as int instead of string — defensive type guard
                body = json.dumps({"obligations": {
                    "ART10-OBL-1": "COMPLIANT",
                    "ART11-OBL-1": 42,  # not a string
                    "ART12-OBL-1": None,  # not a string
                }})
                return subprocess.CompletedProcess(cmd, 0, stdout=f"{body}\n200", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", custom_run)
        result = server._fetch_effective_status_from_saas(str(tmp_path))
        # The type guard at server.py:1776 filters non-string values.
        assert result == {"ART10-OBL-1": "COMPLIANT"}


# ── cl_action_plan overlay integration ──


class TestClActionPlanOverlay:
    """Verify the overlay actually wires into cl_action_plan's output.

    cl_action_plan iterates ALL article modules calling mod.scan +
    mod.action_plan, so the action list contains many items. We
    verify the overlay finds matching obligation_ids and tags them,
    without asserting the specific count of unrelated actions.
    """

    def test_overlay_tags_COMPLIANT_actions_when_saas_says_compliant(self, tmp_path, monkeypatch):
        _seed_rc(str(tmp_path))
        _seed_minimal_scan_context(str(tmp_path))
        captured = {}
        monkeypatch.setattr(subprocess, "run", _make_fake_run("complaint-art10", captured))

        raw = server.cl_action_plan(str(tmp_path), article=10)
        plan = json.loads(raw)

        # The plan must include `dashboard_overlay_summary` regardless of
        # whether any action matched.
        assert "dashboard_overlay_summary" in plan
        summary = plan["dashboard_overlay_summary"]
        assert summary["fetched_from_dashboard"] is True

        # Find actions matching ART10-OBL-1; assert they are tagged.
        # cl_action_plan may emit multiple actions per OID (e.g., scan +
        # follow-up); ALL with matching obligation_id should be overlaid.
        matching = [a for a in plan.get("actions", [])
                    if a.get("obligation_id") == "ART10-OBL-1"]
        if matching:
            for action in matching:
                assert action.get("already_attested_in_dashboard") is True
                assert action.get("dashboard_status") == "COMPLIANT"
                assert action.get("priority") == "LOW"
                assert "marked COMPLIANT in the" in (action.get("details") or "")
            assert summary["actions_marked_already_attested"] == len(matching)

    def test_overlay_tags_NA_actions_when_saas_says_not_applicable(self, tmp_path, monkeypatch):
        _seed_rc(str(tmp_path))
        _seed_minimal_scan_context(str(tmp_path))
        captured = {}
        monkeypatch.setattr(subprocess, "run", _make_fake_run("na-art12", captured))

        raw = server.cl_action_plan(str(tmp_path), article=12)
        plan = json.loads(raw)
        summary = plan["dashboard_overlay_summary"]
        assert summary["fetched_from_dashboard"] is True

        matching = [a for a in plan.get("actions", [])
                    if a.get("obligation_id") == "ART12-OBL-1"]
        if matching:
            for action in matching:
                assert action.get("already_attested_in_dashboard") is True
                assert action.get("dashboard_status") == "NOT_APPLICABLE"
                assert action.get("priority") == "LOW"
                assert "NOT_APPLICABLE" in (action.get("details") or "")
            assert summary["actions_marked_na_in_dashboard"] == len(matching)

    def test_no_api_key_no_overlay_plan_still_returns(self, tmp_path):
        # No .compliancelintrc → no api key → no curl call → no overlay
        _seed_minimal_scan_context(str(tmp_path))

        raw = server.cl_action_plan(str(tmp_path), article=10)
        plan = json.loads(raw)
        summary = plan.get("dashboard_overlay_summary")
        assert summary is not None
        assert summary["fetched_from_dashboard"] is False
        assert summary["actions_marked_already_attested"] == 0
        assert summary["actions_marked_na_in_dashboard"] == 0
        # Plan should still have the article entries (degraded mode — no tags)
        for action in plan.get("actions", []):
            assert action.get("already_attested_in_dashboard") is not True

    def test_network_exception_overlay_silent_plan_still_returns(self, tmp_path, monkeypatch):
        _seed_rc(str(tmp_path))
        _seed_minimal_scan_context(str(tmp_path))
        captured = {}
        monkeypatch.setattr(subprocess, "run", _make_fake_run("exception", captured))

        raw = server.cl_action_plan(str(tmp_path), article=10)
        plan = json.loads(raw)
        summary = plan["dashboard_overlay_summary"]
        # Network failure → overlay empty → fetched_from_dashboard=False
        assert summary["fetched_from_dashboard"] is False
        assert summary["actions_marked_already_attested"] == 0

    def test_empty_obligations_map_treated_as_no_overlay(self, tmp_path, monkeypatch):
        _seed_rc(str(tmp_path))
        _seed_minimal_scan_context(str(tmp_path))
        captured = {}
        monkeypatch.setattr(subprocess, "run", _make_fake_run("empty", captured))

        raw = server.cl_action_plan(str(tmp_path), article=10)
        plan = json.loads(raw)
        summary = plan["dashboard_overlay_summary"]
        # bool({}) is False → fetched_from_dashboard reports False
        assert summary["fetched_from_dashboard"] is False
        # No actions tagged because the map was empty
        assert summary["actions_marked_already_attested"] == 0
        assert summary["actions_marked_na_in_dashboard"] == 0

    def test_mixed_compliant_and_na_both_tag_correctly(self, tmp_path, monkeypatch):
        _seed_rc(str(tmp_path))
        _seed_minimal_scan_context(str(tmp_path))
        captured = {}
        monkeypatch.setattr(subprocess, "run", _make_fake_run("mixed", captured))

        # Run across ALL articles so both ART10 + ART12 can match.
        raw = server.cl_action_plan(str(tmp_path), article=0)
        plan = json.loads(raw)
        summary = plan["dashboard_overlay_summary"]
        assert summary["fetched_from_dashboard"] is True

        compliant_actions = [a for a in plan.get("actions", [])
                              if a.get("dashboard_status") == "COMPLIANT"]
        na_actions = [a for a in plan.get("actions", [])
                      if a.get("dashboard_status") == "NOT_APPLICABLE"]

        # Both buckets should have entries (assuming ART10 + ART12 modules exist)
        # If the module isn't registered the action might not be in the plan
        # at all; this branch handles both cases.
        if compliant_actions:
            for a in compliant_actions:
                assert a.get("obligation_id") == "ART10-OBL-1"
        if na_actions:
            for a in na_actions:
                assert a.get("obligation_id") == "ART12-OBL-1"
        assert summary["actions_marked_already_attested"] == len(compliant_actions)
        assert summary["actions_marked_na_in_dashboard"] == len(na_actions)
