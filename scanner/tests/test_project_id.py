"""Tests for project identity — config-cached project_id + UUID fallback.

project_id is pre-derived by `npx compliancelint init` (normal terminal)
and cached in .compliancelintrc. get_project_id() reads this cache.
It does NOT call git subprocess (hangs in MCP context).
"""
import json
import os

import pytest

from core.state import get_project_id


class TestConfigCachedId:
    """project_id from .compliancelintrc (pre-derived by npx init)."""

    def test_reads_from_compliancelintrc(self, tmp_path):
        rc = tmp_path / ".compliancelintrc"
        rc.write_text(json.dumps({"project_id": "git-abcdef1234567890"}))
        pid = get_project_id(str(tmp_path))
        assert pid == "git-abcdef1234567890"

    def test_no_git_subprocess_called(self, tmp_path):
        """get_project_id must NOT call git — it hangs in MCP context."""
        # No .compliancelintrc, no .compliancelint/ — should fall back to UUID
        pid = get_project_id(str(tmp_path))
        # Should be a UUID, not a git-prefixed id
        assert not pid.startswith("git-")
        assert len(pid) == 36  # UUID format

    def test_config_takes_priority_over_project_json(self, tmp_path):
        rc = tmp_path / ".compliancelintrc"
        rc.write_text(json.dumps({"project_id": "git-fromconfig12345"}))
        cl = tmp_path / ".compliancelint" / "local"
        cl.mkdir(parents=True)
        (cl / "project.json").write_text(json.dumps({"project_id": "uuid-from-json"}))
        pid = get_project_id(str(tmp_path))
        assert pid == "git-fromconfig12345"


class TestNonGitFallback:
    """Non-git projects fall back to cached UUID."""

    def test_generates_uuid(self, tmp_path):
        pid = get_project_id(str(tmp_path))
        assert pid
        assert len(pid) == 36  # UUID format
        assert "-" in pid

    def test_caches_in_project_json(self, tmp_path):
        pid = get_project_id(str(tmp_path))
        project_file = tmp_path / ".compliancelint" / "local" / "project.json"
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
        cl = tmp_path / ".compliancelint" / "local"
        cl.mkdir(parents=True)
        (cl / "project.json").write_text("{bad json")
        pid = get_project_id(str(tmp_path))
        assert pid and len(pid) == 36

    def test_preserves_existing_uuid(self, tmp_path):
        cl = tmp_path / ".compliancelint" / "local"
        cl.mkdir(parents=True)
        existing = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        (cl / "project.json").write_text(json.dumps({"project_id": existing}))
        assert get_project_id(str(tmp_path)) == existing
