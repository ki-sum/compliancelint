"""Thin coverage for MCP tool cl_delete (server.py:2753).

Covers:
  - safety gate: confirm=False does NOT delete, returns confirmation_required
  - happy path: confirm=True, target="local" removes .compliancelint/ dir
  - error path: invalid target returns error listing legal values
"""
import json
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def _seed_cl_dir(project_path):
    cl_dir = os.path.join(project_path, ".compliancelint")
    os.makedirs(os.path.join(cl_dir, "articles"), exist_ok=True)
    with open(os.path.join(cl_dir, "articles", "art12.json"), "w", encoding="utf-8") as f:
        json.dump({"article": 12, "findings": {}}, f)
    return cl_dir


def test_delete_without_confirm_is_safety_abort(tmp_path):
    cl_dir = _seed_cl_dir(str(tmp_path))

    raw = server.cl_delete(str(tmp_path), target="local", confirm=False)
    parsed = json.loads(raw)

    assert parsed["status"] == "confirmation_required", f"expected safety gate, got: {parsed}"
    assert "confirm=true" in parsed["action"]
    assert os.path.isdir(cl_dir), "safety gate must NOT delete data"


def test_delete_local_with_confirm_removes_state(tmp_path, monkeypatch):
    # Isolate from scanner_log's RotatingFileHandler — on Windows the open
    # handle on .compliancelint/logs/scanner.log blocks shutil.rmtree. This
    # latent cl_delete behaviour is tracked in scanner/tests/G1_BUGS.md; the
    # test uses a stderr-only logger to verify the core delete semantics.
    import logging
    from core import scanner_log
    monkeypatch.setattr(
        scanner_log,
        "get_scanner_logger",
        lambda path="": logging.getLogger("test_cl_delete_isolated"),
    )
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
