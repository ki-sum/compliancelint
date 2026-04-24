"""Coverage for MCP tool cl_delete (server.py:2753).

Covers:
  - safety gate: confirm=False does NOT delete, returns confirmation_required
  - happy path: confirm=True, target="local" removes .compliancelint/ dir
  - error path: invalid target returns error listing legal values
  - BUG-1 regression: cl_delete after a real cl_scan-style logger attach
    must succeed (no WinError 32 sharing violation on Windows)
  - BUG-1 regression: scanner.log must live under Path.home(), not inside
    the project tree (so it can't block shutil.rmtree)
"""
import json
import os
import sys
from pathlib import Path

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def _seed_cl_dir(project_path):
    cl_dir = os.path.join(project_path, ".compliancelint")
    local_articles = os.path.join(cl_dir, "local", "articles")
    os.makedirs(local_articles, exist_ok=True)
    with open(os.path.join(local_articles, "art12.json"), "w", encoding="utf-8") as f:
        json.dump({"article": 12, "findings": {}}, f)
    return cl_dir


def test_delete_without_confirm_is_safety_abort(tmp_path):
    cl_dir = _seed_cl_dir(str(tmp_path))

    raw = server.cl_delete(str(tmp_path), target="local", confirm=False)
    parsed = json.loads(raw)

    assert parsed["status"] == "confirmation_required", f"expected safety gate, got: {parsed}"
    assert "confirm=true" in parsed["action"]
    assert os.path.isdir(cl_dir), "safety gate must NOT delete data"


def test_delete_local_with_confirm_removes_state(tmp_path):
    cl_dir = _seed_cl_dir(str(tmp_path))

    raw = server.cl_delete(str(tmp_path), target="local", confirm=True)
    parsed = json.loads(raw)

    assert parsed["status"] == "deleted", f"unexpected status: {parsed}"
    assert parsed["results"]["local"] == "deleted"
    assert not os.path.exists(cl_dir), ".compliancelint/ must be removed after confirmed delete"


def test_delete_invalid_target_returns_error(tmp_path):
    _seed_cl_dir(str(tmp_path))

    raw = server.cl_delete(str(tmp_path), target="invalid", confirm=True)
    parsed = json.loads(raw)

    assert "error" in parsed, f"expected error, got: {parsed}"
    assert "invalid" in parsed["error"].lower()
    for legal in ("local", "remote", "all"):
        assert legal in parsed["error"], f"error must list legal target '{legal}'"


# ── BUG-1 regression tests (see scanner/tests/G1_BUGS.md) ───────────────────

def test_delete_works_after_real_cl_scan_without_monkeypatch(tmp_path):
    """Regression for BUG-1: cl_delete must succeed on Windows even after a
    real RotatingFileHandler has been attached for this project (what every
    prior cl_scan / cl_sync call in the same MCP process does). Pre-fix this
    raises PermissionError: WinError 32 because scanner.log is still open
    inside the very directory rmtree is trying to remove.
    """
    _seed_cl_dir(str(tmp_path))

    # Trigger the real get_scanner_logger path — no monkeypatch. Mirrors what
    # happens in a long-running MCP process after any earlier scan.
    from core.scanner_log import get_scanner_logger
    log = get_scanner_logger(str(tmp_path))
    log.info("simulating a prior cl_scan writing to scanner.log for %s", tmp_path)

    raw = server.cl_delete(str(tmp_path), target="local", confirm=True)
    parsed = json.loads(raw)

    assert parsed["status"] == "deleted", f"cl_delete failed post-scan: {parsed}"
    assert parsed["results"]["local"] == "deleted"
    assert not (tmp_path / ".compliancelint").exists(), (
        "project .compliancelint/ must be gone after confirmed delete"
    )


def test_scanner_log_lives_outside_project_tree(tmp_path):
    """BUG-1 fix: scanner.log MUST be written under Path.home() / .compliancelint/,
    not inside {project}/.compliancelint/. Placing log state outside the project
    tree is what makes cl_delete safe on Windows — rmtree of the project dir
    can never hit an open log handle.
    """
    from logging.handlers import RotatingFileHandler
    from core.scanner_log import get_scanner_logger

    log = get_scanner_logger(str(tmp_path))
    log.info("where does this handler's baseFilename land?")

    project_log = tmp_path / ".compliancelint" / "logs" / "scanner.log"
    assert not project_log.exists(), (
        f"scanner.log leaked back into project tree at {project_log}"
    )

    file_handlers = [h for h in log.handlers if isinstance(h, RotatingFileHandler)]
    assert len(file_handlers) >= 1, (
        "expected at least one RotatingFileHandler attached to the project logger"
    )

    home_resolved = Path.home().resolve()
    for h in file_handlers:
        bf = Path(h.baseFilename).resolve()
        assert str(bf).startswith(str(home_resolved)), (
            f"log file at {bf} is not under home {home_resolved}"
        )
        assert ".compliancelint" in bf.parts, (
            f"log file {bf} must live under a .compliancelint directory"
        )
