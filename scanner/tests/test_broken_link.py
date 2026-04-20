"""Unit tests for core.broken_link — Evidence v4 Track 4c-2.

Covers:
  - File existence check (secure): ok file / missing file / directory /
    symlink inside repo / symlink escaping repo / absolute path / `..`
    traversal / nonexistent subdir
  - Report construction (pure): maps file-check result to health_status
  - Orchestrator with mocked HTTP: pagination, empty response, POST
    dispatch, server-skipped items, error paths
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import pytest

SCANNER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SCANNER_ROOT not in sys.path:
    sys.path.insert(0, SCANNER_ROOT)

from core import broken_link as bl  # noqa: E402


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def project(tmp_path):
    return str(tmp_path)


class FakeHttp:
    """Recorder for injected HTTP callbacks."""

    def __init__(self):
        self.get_responses: dict[str, object] = {}
        self.post_responses: dict[str, object] = {}
        self.gotten: list[str] = []
        self.posted: list[tuple[str, dict]] = []

    def get(self, url: str):
        self.gotten.append(url)
        resp = self.get_responses.get(url)
        if isinstance(resp, Exception):
            raise resp
        return resp

    def post(self, url: str, payload: dict):
        self.posted.append((url, payload))
        resp = self.post_responses.get(url)
        if isinstance(resp, Exception):
            raise resp
        return resp


# ── check_file_exists_secure ────────────────────────────────────────────


class TestCheckFileExistsSecure:
    def test_existing_file_returns_true(self, project):
        path = os.path.join(project, "evidence", "ok.txt")
        os.makedirs(os.path.dirname(path))
        open(path, "w").write("content")
        assert bl.check_file_exists_secure(project, "evidence/ok.txt")

    def test_missing_file_returns_false(self, project):
        assert not bl.check_file_exists_secure(project, "evidence/missing.txt")

    def test_directory_rejected(self, project):
        os.makedirs(os.path.join(project, "evidence", "subdir"))
        assert not bl.check_file_exists_secure(project, "evidence/subdir")

    def test_empty_string_returns_false(self, project):
        assert not bl.check_file_exists_secure(project, "")

    def test_absolute_path_rejected_for_security(self, project):
        # Create a real file somewhere and try to reach it via absolute path
        target_dir = os.path.join(project, "outside")
        os.makedirs(target_dir)
        target = os.path.join(target_dir, "secret.txt")
        open(target, "w").write("secret")
        # Absolute path to the real file — security must reject
        assert not bl.check_file_exists_secure(project, target)

    def test_parent_traversal_rejected(self, project):
        # `..` walking out of the repo root must be refused even if the
        # target exists.
        parent = os.path.dirname(project)
        sibling_file = os.path.join(parent, "sibling.txt")
        open(sibling_file, "w").write("neighbor")
        try:
            assert not bl.check_file_exists_secure(project, "../sibling.txt")
        finally:
            os.unlink(sibling_file)

    def test_leading_dot_dot_slash_rejected(self, project):
        assert not bl.check_file_exists_secure(project, "../etc/passwd")

    def test_bare_dot_dot_rejected(self, project):
        assert not bl.check_file_exists_secure(project, "..")

    @pytest.mark.skipif(
        sys.platform == "win32" and not os.environ.get("CI"),
        reason="Symlink creation requires admin on Windows",
    )
    def test_symlink_inside_repo_ok(self, project):
        os.makedirs(os.path.join(project, "evidence"))
        real = os.path.join(project, "evidence", "real.txt")
        link = os.path.join(project, "evidence", "link.txt")
        open(real, "w").write("content")
        try:
            os.symlink(real, link)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unsupported")
        assert bl.check_file_exists_secure(project, "evidence/link.txt")

    @pytest.mark.skipif(
        sys.platform == "win32" and not os.environ.get("CI"),
        reason="Symlink creation requires admin on Windows",
    )
    def test_symlink_escaping_repo_rejected(self, project):
        # Security-critical: symlink inside repo pointing OUTSIDE the repo.
        # realpath resolves to the outside target → commonpath mismatch →
        # broken_link (not ok).
        parent = os.path.dirname(project)
        outside = os.path.join(parent, "outside-secret.txt")
        open(outside, "w").write("secret")
        os.makedirs(os.path.join(project, "evidence"))
        link = os.path.join(project, "evidence", "escape.txt")
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unsupported")
        try:
            assert not bl.check_file_exists_secure(project, "evidence/escape.txt")
        finally:
            os.unlink(outside)


# ── build_reports ──────────────────────────────────────────────────────


class TestBuildReports:
    def test_ok_and_broken_mix(self, project):
        os.makedirs(os.path.join(project, "evidence"))
        open(os.path.join(project, "evidence", "present.txt"), "w").write("x")

        rows = [
            bl.EvidenceRow(evidence_item_id="e1", finding_id="f1",
                           repo_path="evidence/present.txt"),
            bl.EvidenceRow(evidence_item_id="e2", finding_id="f1",
                           repo_path="evidence/gone.txt"),
        ]
        reports = bl.build_reports(project, rows, checked_at_sha="a" * 40)
        assert len(reports) == 2
        assert reports[0].health_status == "ok"
        assert reports[1].health_status == "broken_link"
        assert all(r.checked_at_sha == "a" * 40 for r in reports)

    def test_checked_at_timestamp_populated(self, project):
        rows = [bl.EvidenceRow(evidence_item_id="e1", finding_id="f1",
                               repo_path="missing.txt")]
        reports = bl.build_reports(project, rows, checked_at_sha=None,
                                    checked_at="2026-04-20T12:00:00Z")
        assert reports[0].checked_at == "2026-04-20T12:00:00Z"

    def test_default_checked_at_is_current_time(self, project):
        rows = [bl.EvidenceRow(evidence_item_id="e1", finding_id="f1",
                               repo_path="x.txt")]
        reports = bl.build_reports(project, rows, checked_at_sha=None)
        # Parse — must be a valid ISO timestamp, recent
        dt = datetime.fromisoformat(reports[0].checked_at.replace("Z", "+00:00"))
        delta = abs((datetime.now(timezone.utc) - dt).total_seconds())
        assert delta < 10

    def test_null_checked_at_sha_allowed(self, project):
        rows = [bl.EvidenceRow(evidence_item_id="e1", finding_id="f1",
                               repo_path="x.txt")]
        reports = bl.build_reports(project, rows, checked_at_sha=None)
        assert reports[0].checked_at_sha is None


# ── run_broken_link_check orchestrator ─────────────────────────────────


SAAS = "http://localhost:3000"
REPO_ID = "repo-uuid"


class TestRunBrokenLinkCheck:
    def test_empty_list_response_is_noop(self, project):
        http = FakeHttp()
        http.get_responses[
            f"{SAAS}/api/v1/repos/{REPO_ID}/evidence?storage_kind=git_path&limit=500"
        ] = {"evidence": [], "next_cursor": None, "total_matched": 0}

        summary = bl.run_broken_link_check(
            project_path=project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            checked_at_sha="b" * 40,
        )
        assert summary.checked == 0
        assert summary.ok == 0
        assert summary.broken == 0
        # Must NOT have POSTed anything — nothing to report
        assert http.posted == []

    def test_full_roundtrip_mixed_ok_and_broken(self, project):
        # Seed one present file, one missing
        os.makedirs(os.path.join(project, ".compliancelint", "evidence", "f1"))
        open(os.path.join(project, ".compliancelint", "evidence", "f1", "present.txt"),
             "w").write("x")

        http = FakeHttp()
        list_url = f"{SAAS}/api/v1/repos/{REPO_ID}/evidence?storage_kind=git_path&limit=500"
        http.get_responses[list_url] = {
            "evidence": [
                {
                    "evidence_item_id": "e1",
                    "finding_id": "f1",
                    "storage_kind": "git_path",
                    "repo_path": ".compliancelint/evidence/f1/present.txt",
                    "health_status": "ok",
                },
                {
                    "evidence_item_id": "e2",
                    "finding_id": "f1",
                    "storage_kind": "git_path",
                    "repo_path": ".compliancelint/evidence/f1/gone.txt",
                    "health_status": "ok",  # server's current belief
                },
            ],
            "next_cursor": None,
            "total_matched": 2,
        }
        post_url = f"{SAAS}/api/v1/repos/{REPO_ID}/evidence-health"
        http.post_responses[post_url] = {
            "transitioned": 1,  # e2 transitioned ok→broken_link
            "unchanged": 1,     # e1 stayed ok
            "skipped": 0,
            "skipped_details": [],
        }

        summary = bl.run_broken_link_check(
            project_path=project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            checked_at_sha="c" * 40,
        )
        assert summary.checked == 2
        assert summary.ok == 1
        assert summary.broken == 1
        assert summary.transitioned == 1
        assert summary.unchanged == 1
        # Verify the POST payload
        assert len(http.posted) == 1
        url, payload = http.posted[0]
        assert url == post_url
        reports = payload["reports"]
        assert len(reports) == 2
        # Map by evidence_item_id for stable assertions
        by_id = {r["evidence_item_id"]: r for r in reports}
        assert by_id["e1"]["health_status"] == "ok"
        assert by_id["e2"]["health_status"] == "broken_link"
        assert all(r["checked_at_sha"] == "c" * 40 for r in reports)

    def test_paginates_across_multiple_pages(self, project):
        http = FakeHttp()
        page1 = f"{SAAS}/api/v1/repos/{REPO_ID}/evidence?storage_kind=git_path&limit=500"
        page2 = f"{SAAS}/api/v1/repos/{REPO_ID}/evidence?storage_kind=git_path&limit=500&cursor=PAGE2"
        http.get_responses[page1] = {
            "evidence": [
                {"evidence_item_id": "e1", "finding_id": "f1", "repo_path": "a.txt"},
            ],
            "next_cursor": "PAGE2",
        }
        http.get_responses[page2] = {
            "evidence": [
                {"evidence_item_id": "e2", "finding_id": "f1", "repo_path": "b.txt"},
            ],
            "next_cursor": None,
        }
        http.post_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/evidence-health"] = {
            "transitioned": 0, "unchanged": 0, "skipped": 2,
            "skipped_details": [],
        }

        summary = bl.run_broken_link_check(
            project_path=project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            checked_at_sha=None,
        )
        assert summary.checked == 2
        # Both files missing → both broken_link
        assert summary.broken == 2
        assert http.gotten == [page1, page2]  # paginated correctly

    def test_skipped_by_server_counted(self, project):
        http = FakeHttp()
        list_url = f"{SAAS}/api/v1/repos/{REPO_ID}/evidence?storage_kind=git_path&limit=500"
        http.get_responses[list_url] = {
            "evidence": [
                {"evidence_item_id": "e1", "finding_id": "f1", "repo_path": "x.txt"},
            ],
            "next_cursor": None,
        }
        http.post_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/evidence-health"] = {
            "transitioned": 0, "unchanged": 0, "skipped": 1,
            "skipped_details": [
                {"evidence_item_id": "e1", "reason": "not found in this repo"},
            ],
        }

        summary = bl.run_broken_link_check(
            project_path=project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            checked_at_sha=None,
        )
        assert summary.skipped_by_server == 1

    def test_list_fetch_failure_is_graceful(self, project):
        http = FakeHttp()
        http.get_responses[
            f"{SAAS}/api/v1/repos/{REPO_ID}/evidence?storage_kind=git_path&limit=500"
        ] = RuntimeError("connection refused")

        summary = bl.run_broken_link_check(
            project_path=project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            checked_at_sha=None,
        )
        assert summary.checked == 0
        assert len(summary.errors) == 1
        assert "connection refused" in summary.errors[0]
        assert http.posted == []

    def test_post_failure_surfaces_in_errors(self, project):
        http = FakeHttp()
        list_url = f"{SAAS}/api/v1/repos/{REPO_ID}/evidence?storage_kind=git_path&limit=500"
        http.get_responses[list_url] = {
            "evidence": [
                {"evidence_item_id": "e1", "finding_id": "f1", "repo_path": "x.txt"},
            ],
            "next_cursor": None,
        }
        http.post_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/evidence-health"] = (
            RuntimeError("service unavailable")
        )

        summary = bl.run_broken_link_check(
            project_path=project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            checked_at_sha=None,
        )
        # File check still ran — 1 item checked as broken (missing).
        # But POST failed — recorded in errors, summary.transitioned stays 0.
        assert summary.checked == 1
        assert summary.broken == 1
        assert summary.transitioned == 0
        assert len(summary.errors) == 1
        assert "service unavailable" in summary.errors[0]

    def test_malformed_row_in_response_skipped_with_warn(self, project):
        http = FakeHttp()
        list_url = f"{SAAS}/api/v1/repos/{REPO_ID}/evidence?storage_kind=git_path&limit=500"
        http.get_responses[list_url] = {
            "evidence": [
                {"evidence_item_id": "good", "finding_id": "f1", "repo_path": "x.txt"},
                {"evidence_item_id": None, "repo_path": "y.txt"},  # missing finding_id
                {"finding_id": "f1", "repo_path": "z.txt"},  # missing evidence_item_id
            ],
            "next_cursor": None,
        }
        http.post_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/evidence-health"] = {
            "transitioned": 0, "unchanged": 0, "skipped": 0, "skipped_details": [],
        }

        summary = bl.run_broken_link_check(
            project_path=project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            checked_at_sha=None,
        )
        # Only the well-formed row is processed
        assert summary.checked == 1
        # POST payload should have 1 report
        _, payload = http.posted[0]
        assert len(payload["reports"]) == 1
        assert payload["reports"][0]["evidence_item_id"] == "good"
