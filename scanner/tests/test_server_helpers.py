"""Unit tests for scanner/server.py helpers introduced with Evidence v4
fingerprint client (Problem 2 part B, 2026-04-21).

Covers:
  - _derive_first_commit_sha (git rev-list --max-parents=0)
  - _format_fingerprint_warning (POST /scans response → user message)
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

SCANNER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SCANNER_ROOT not in sys.path:
    sys.path.insert(0, SCANNER_ROOT)

from server import (  # noqa: E402
    _derive_first_commit_sha,
    _format_fingerprint_warning,
)


def _git(cwd: str, *args: str) -> str:
    r = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    )
    return r.stdout


class TestDeriveFirstCommitSha:
    def test_returns_none_for_non_git_directory(self, tmp_path):
        assert _derive_first_commit_sha(str(tmp_path)) is None

    def test_returns_sha_for_single_commit_repo(self, tmp_path):
        repo = str(tmp_path)
        _git(repo, "init")
        _git(repo, "symbolic-ref", "HEAD", "refs/heads/master")
        _git(repo, "config", "user.email", "test@example.com")
        _git(repo, "config", "user.name", "Test")
        (tmp_path / "README").write_text("init\n")
        _git(repo, "add", "README")
        _git(repo, "commit", "-m", "init")

        sha = _derive_first_commit_sha(repo)
        assert sha is not None
        assert len(sha) == 40
        assert all(c in "0123456789abcdef" for c in sha)

        # Sanity: equals the HEAD sha in single-commit repo
        head = _git(repo, "rev-parse", "HEAD").strip()
        assert sha == head

    def test_returns_root_sha_unchanged_after_new_commits(self, tmp_path):
        repo = str(tmp_path)
        _git(repo, "init")
        _git(repo, "symbolic-ref", "HEAD", "refs/heads/master")
        _git(repo, "config", "user.email", "test@example.com")
        _git(repo, "config", "user.name", "Test")
        (tmp_path / "a").write_text("one")
        _git(repo, "add", "a")
        _git(repo, "commit", "-m", "first")
        root = _derive_first_commit_sha(repo)

        # Add more commits — first_commit_sha must stay the same
        (tmp_path / "b").write_text("two")
        _git(repo, "add", "b")
        _git(repo, "commit", "-m", "second")
        (tmp_path / "c").write_text("three")
        _git(repo, "add", "c")
        _git(repo, "commit", "-m", "third")

        assert _derive_first_commit_sha(repo) == root, \
            "first_commit_sha must be stable across new commits (project identity)"


class TestFormatFingerprintWarning:
    _SAAS = "http://localhost:3000"
    _REPO = "repo-abc"

    def test_returns_none_for_none_input(self):
        assert _format_fingerprint_warning(None, self._SAAS, self._REPO) is None

    def test_returns_none_for_empty_list(self):
        assert _format_fingerprint_warning([], self._SAAS, self._REPO) is None

    def test_returns_none_for_non_list(self):
        assert _format_fingerprint_warning(  # type: ignore[arg-type]
            {"type": "fingerprint_changed"}, self._SAAS, self._REPO,
        ) is None
        assert _format_fingerprint_warning(  # type: ignore[arg-type]
            "not a list", self._SAAS, self._REPO,
        ) is None

    def test_returns_none_when_no_fingerprint_type(self):
        warnings = [
            {"type": "unrelated", "note": "x"},
            {"type": "other"},
        ]
        assert _format_fingerprint_warning(warnings, self._SAAS, self._REPO) is None

    def test_returns_formatted_string_for_fingerprint_changed(self):
        warnings = [{
            "type": "fingerprint_changed",
            "previous_first_commit_sha": "abc123" + "0" * 34,
            "current_first_commit_sha": "def456" + "0" * 34,
            "note": "Repo history may have been rewritten",
        }]
        msg = _format_fingerprint_warning(warnings, self._SAAS, self._REPO)
        assert msg is not None
        assert "Fingerprint changed" in msg
        assert "abc123" in msg
        assert "def456" in msg
        assert "Repo history may have been rewritten" in msg
        assert "http://localhost:3000/dashboard/repos/repo-abc" in msg

    def test_handles_missing_optional_fields(self):
        warnings = [{"type": "fingerprint_changed"}]
        msg = _format_fingerprint_warning(warnings, self._SAAS, self._REPO)
        assert msg is not None
        assert "Fingerprint changed" in msg
        # Default note still present
        assert "Repo fingerprint changed" in msg or "may have been rewritten" in msg

    def test_skips_non_dict_entries(self):
        warnings = ["string-entry", None, {"type": "fingerprint_changed",
                                           "previous_first_commit_sha": "a" * 40,
                                           "current_first_commit_sha": "b" * 40}]
        msg = _format_fingerprint_warning(warnings, self._SAAS, self._REPO)
        assert msg is not None  # the one valid dict is still picked up

    def test_returns_first_matching_warning_when_multiple(self):
        warnings = [
            {"type": "fingerprint_changed",
             "previous_first_commit_sha": "a" * 40,
             "current_first_commit_sha": "b" * 40,
             "note": "first"},
            {"type": "fingerprint_changed",
             "previous_first_commit_sha": "c" * 40,
             "current_first_commit_sha": "d" * 40,
             "note": "second"},
        ]
        msg = _format_fingerprint_warning(warnings, self._SAAS, self._REPO)
        assert msg is not None
        assert "first" in msg
        assert "second" not in msg

    def test_trailing_slash_on_saas_url_does_not_duplicate(self):
        warnings = [{"type": "fingerprint_changed",
                     "previous_first_commit_sha": "a" * 40,
                     "current_first_commit_sha": "b" * 40}]
        msg = _format_fingerprint_warning(
            warnings, "http://localhost:3000/", self._REPO,
        )
        assert msg is not None
        assert "http://localhost:3000/dashboard/repos" in msg
        assert "http://localhost:3000//dashboard" not in msg


class TestClSyncFingerprintWiringSource:
    """Source-level contract test catching silent-drop bugs in cl_sync's
    fingerprint glue code. The round-trip e2e test covers HTTP contract +
    parser correctness; this test covers the *glue between them* — the
    code that extracts warnings from the response and writes them into
    result_payload. A typo in the result_payload dict key would be a
    silent-drop bug (MCP clients would never see the warning), and a
    typo is exactly the kind of issue that doesn't fail unit tests.
    """

    @pytest.fixture(scope="class")
    def server_source(self):
        server_py = os.path.join(SCANNER_ROOT, "server.py")
        with open(server_py, "r", encoding="utf-8") as f:
            return f.read()

    def test_cl_sync_extracts_warnings_from_scan_response(self, server_source):
        assert 'resp_data.get("warnings")' in server_source, (
            "cl_sync must read the 'warnings' field from the POST /scans "
            "response. If renamed, the fingerprint warning is silent-dropped."
        )

    def test_cl_sync_calls_format_fingerprint_warning(self, server_source):
        assert "_format_fingerprint_warning(" in server_source, (
            "cl_sync must call _format_fingerprint_warning to format the "
            "parsed warnings. Missing call = silent drop."
        )

    def test_cl_sync_writes_fingerprint_warning_to_result_payload(self, server_source):
        # Exact-key match — any typo like 'fingerprintWarning' or
        # 'fingerprint-warning' would be a silent drop because MCP clients
        # look for this specific key. Keep test brittle ON PURPOSE.
        assert 'result_payload["fingerprint_warning"] = fingerprint_msg' in server_source, (
            "cl_sync must write the formatted message under the exact key "
            "'fingerprint_warning' in result_payload. ANY typo here is a "
            "silent-drop bug — MCP clients (Claude Code, Cursor) render "
            "this key and will show no warning if it's renamed."
        )

    def test_cl_sync_appends_fingerprint_to_top_level_message(self, server_source):
        # Matches the one-line-UI pattern already in cl_sync for human_prompt
        # (line 2283). Without this, terminal-style MCP clients that only
        # render `message` would miss the warning.
        assert "fingerprint_msg" in server_source and \
               "result_payload['message']" in server_source, (
            "cl_sync must append fingerprint_msg to result_payload['message'] "
            "so one-line MCP UIs render the warning. Pattern must match "
            "human_prompt appending (line ~2283)."
        )

    def test_first_commit_sha_in_scan_payload(self, server_source):
        # Guards against the payload builder forgetting to send the field.
        assert '"first_commit_sha": first_commit_sha' in server_source, (
            "cl_sync must include first_commit_sha in POST /scans payload. "
            "Without it the dashboard has no basis for comparison and the "
            "fingerprint check silently no-ops on every sync."
        )
