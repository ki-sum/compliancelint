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
