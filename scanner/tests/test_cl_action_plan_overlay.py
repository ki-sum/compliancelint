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

class TestFetchEffectiveStatusByRepoName:
    """Acceptance run A5b (2026-10-07): project_id is written only by `npx compliancelint init` for git repos; a project
    connected through cl_connect alone has just its repo_name, and the overlay used to return {} silently."""

    def test_without_project_id_falls_back_to_repo_name(self, tmp_path, monkeypatch):
        _seed_rc(str(tmp_path), project_id="")
        captured = {}
        monkeypatch.setattr(subprocess, "run", _make_fake_run("complaint-art10", captured))

        result = server._fetch_effective_status_from_saas(str(tmp_path))
        assert result == {"ART10-OBL-1": "COMPLIANT"}
        assert any(u == "https://dash.test.local/api/v1/repos/effective-status?repo=acme%2Ftest" for u in captured["urls"]), captured["urls"]

    def test_project_id_still_wins(self, tmp_path, monkeypatch):
        _seed_rc(str(tmp_path))
        captured = {}
        monkeypatch.setattr(subprocess, "run", _make_fake_run("complaint-art10", captured))

        server._fetch_effective_status_from_saas(str(tmp_path))
        assert all("/api/v1/repos/effective-status" not in u for u in captured["urls"])


def _real_context():
    """The full answers template (the scan asks for every applicable article), scope filled. Under it the Art 12
    plan has exactly two actions: "Art. 12(2)(a)" and "Art. 12(2)(c)"."""
    from core.context import ProjectContext, _build_answers_template
    from core.protocol import BaseArticleModule
    server._ensure_all_modules_loaded()
    answers = _build_answers_template()
    answers["_scope"].update({"is_ai_system": True, "risk_classification": "high-risk", "risk_classification_confidence": "high"})
    BaseArticleModule.set_context(ProjectContext(
        primary_language="python", risk_classification="high-risk", risk_classification_confidence="high",
        compliance_answers=answers,
    ))


def _plan_with_dashboard(tmp_path, monkeypatch, statuses):
    _real_context()
    monkeypatch.setattr(server, "_fetch_effective_status_from_saas", lambda _p: dict(statuses))
    plan = json.loads(server.cl_action_plan(str(tmp_path), article=12))
    return {a["article"]: a for a in plan["actions"]}, plan["dashboard_overlay_summary"]


class TestOverlayMapsActionsToObligations:
    """Acceptance run A6 (2026-10-07, founder: "用條文編號對應"): ActionItems carry no obligation_id, so the overlay —
    which matched on action.obligation_id — never marked anything; the old tests asserted only inside `if matching:`
    (always empty). Actions now map to obligations by their article reference: an exact `source` match
    ("Art. 12(2)(a)" → ART12-OBL-2a), else every obligation of the cited article(s)."""

    def test_answered_yes_on_the_dashboard_marks_that_action(self, tmp_path, monkeypatch):
        # The acceptance-run case: Art 12(2)(a) attested yes in the Human Gates questionnaire, (2)(c) still open.
        actions, summary = _plan_with_dashboard(
            tmp_path, monkeypatch, {"ART12-OBL-2a": "COMPLIANT", "ART12-OBL-2c": "NON_COMPLIANT"})
        assert set(actions) == {"Art. 12(2)(a)", "Art. 12(2)(c)"}
        done = actions["Art. 12(2)(a)"]
        assert done["already_attested_in_dashboard"] is True
        assert done["dashboard_status"] == "COMPLIANT"
        assert done["priority"] == "LOW"
        assert done["obligation_ids"] == ["ART12-OBL-2a"]
        assert "marked COMPLIANT in the" in done["details"]
        assert "already_attested_in_dashboard" not in actions["Art. 12(2)(c)"]
        assert summary == {"fetched_from_dashboard": True, "actions_marked_already_attested": 1,
                           "actions_marked_na_in_dashboard": 0}

    def test_not_applicable_on_the_dashboard_marks_that_action(self, tmp_path, monkeypatch):
        actions, summary = _plan_with_dashboard(tmp_path, monkeypatch, {"ART12-OBL-2c": "NOT_APPLICABLE"})
        na = actions["Art. 12(2)(c)"]
        assert na["dashboard_status"] == "NOT_APPLICABLE"
        assert na["priority"] == "LOW"
        assert "already_attested_in_dashboard" not in actions["Art. 12(2)(a)"]
        assert summary["actions_marked_na_in_dashboard"] == 1
        assert summary["actions_marked_already_attested"] == 0

    def test_both_marked(self, tmp_path, monkeypatch):
        actions, summary = _plan_with_dashboard(
            tmp_path, monkeypatch, {"ART12-OBL-2a": "COMPLIANT", "ART12-OBL-2c": "NOT_APPLICABLE"})
        assert actions["Art. 12(2)(a)"]["dashboard_status"] == "COMPLIANT"
        assert actions["Art. 12(2)(c)"]["dashboard_status"] == "NOT_APPLICABLE"
        assert (summary["actions_marked_already_attested"], summary["actions_marked_na_in_dashboard"]) == (1, 1)


class TestActionObligationIds:
    def test_exact_source(self):
        assert server._action_obligation_ids({"article": "Art. 12(2)(a)"}) == ["ART12-OBL-2a"]

    def test_explicit_obligation_id_wins(self):
        assert server._action_obligation_ids({"article": "Art. 12", "obligation_id": "ART12-OBL-1"}) == ["ART12-OBL-1"]

    def test_whole_article_and_ranges_map_to_every_obligation_of_the_article(self):
        art4 = server._action_obligation_ids({"article": "Art. 4"})
        assert art4 and all(o.startswith("ART04-") for o in art4)
        art9 = server._action_obligation_ids({"article": "Art. 9(1)-(2)"})
        assert "ART09-OBL-1" in art9 and all(o.startswith("ART09-") for o in art9)
        arts = server._action_obligation_ids({"article": "Arts. 8-15"})
        assert {o.split("-")[0] for o in arts} == {f"ART{n:02d}" for n in range(8, 16)}

    def test_whole_article_marked_only_when_every_listed_obligation_is_compliant(self):
        ids = server._action_obligation_ids({"article": "Art. 12"})
        assert len(ids) > 1
        assert server._dashboard_status_for(ids, {o: "COMPLIANT" for o in ids}) == "COMPLIANT"
        assert server._dashboard_status_for(ids, {**{o: "COMPLIANT" for o in ids}, ids[-1]: "NON_COMPLIANT"}) is None
        # an obligation the dashboard does not list (not applicable, or not in the scan) does not block
        assert server._dashboard_status_for(ids, {ids[0]: "COMPLIANT"}) == "COMPLIANT"
        assert server._dashboard_status_for(["ART12-OBL-2a"], {}) is None

