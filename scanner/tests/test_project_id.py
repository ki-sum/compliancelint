"""Tests for project identity — zero-friction git fingerprint + UUID fallback."""
import json
import os
import subprocess
import tempfile

import pytest

from core.state import get_project_id


class TestGitFingerprint:
    """Git-based fingerprint: deterministic, zero config."""

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a minimal git repo with one commit."""
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "README.md").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", "git@github.com:test/my-project.git"], cwd=str(tmp_path), capture_output=True)
        return tmp_path

    def test_returns_git_prefixed_id(self, git_repo):
        pid = get_project_id(str(git_repo))
        assert pid.startswith("git-")
        assert len(pid) == 20  # "git-" + 16 hex chars

    def test_same_repo_same_id(self, git_repo):
        pid1 = get_project_id(str(git_repo))
        pid2 = get_project_id(str(git_repo))
        assert pid1 == pid2

    def test_no_project_json_created(self, git_repo):
        """Git repos should NOT create project.json — zero friction."""
        get_project_id(str(git_repo))
        project_file = git_repo / ".compliancelint" / "project.json"
        assert not project_file.exists()

    def test_different_remote_different_id(self, git_repo):
        pid1 = get_project_id(str(git_repo))
        subprocess.run(["git", "remote", "set-url", "origin", "git@github.com:other/repo.git"], cwd=str(git_repo), capture_output=True)
        pid2 = get_project_id(str(git_repo))
        assert pid1 != pid2


class TestNonGitFallback:
    """Non-git projects fall back to cached UUID."""

    def test_generates_uuid(self, tmp_path):
        pid = get_project_id(str(tmp_path))
        assert pid
        assert len(pid) == 36  # UUID format
        assert "-" in pid

    def test_caches_in_project_json(self, tmp_path):
        pid = get_project_id(str(tmp_path))
        project_file = tmp_path / ".compliancelint" / "project.json"
        assert project_file.exists()
        data = json.loads(project_file.read_text())
        assert data["project_id"] == pid

    def test_returns_same_uuid_on_second_call(self, tmp_path):
        pid1 = get_project_id(str(tmp_path))
        pid2 = get_project_id(str(tmp_path))
        assert pid1 == pid2

    def test_different_dirs_different_uuids(self, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        assert get_project_id(str(a)) != get_project_id(str(b))

    def test_survives_corrupted_json(self, tmp_path):
        cl = tmp_path / ".compliancelint"
        cl.mkdir()
        (cl / "project.json").write_text("{bad json")
        pid = get_project_id(str(tmp_path))
        assert pid and len(pid) == 36

    def test_preserves_existing_uuid(self, tmp_path):
        cl = tmp_path / ".compliancelint"
        cl.mkdir()
        existing = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        (cl / "project.json").write_text(json.dumps({"project_id": existing}))
        assert get_project_id(str(tmp_path)) == existing
