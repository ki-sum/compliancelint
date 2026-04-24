"""Thin coverage for MCP tool cl_disconnect (server.py:2869).

Covers:
  - happy path: bound .compliancelintrc has saas_* fields removed, local config preserved
  - error path: project with no .compliancelintrc returns not_connected (no crash)
"""
import json
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def test_disconnect_bound_project_clears_saas_fields(tmp_path):
    rc_path = tmp_path / ".compliancelintrc"
    rc_path.write_text(json.dumps({
        "project_id": "proj-abc-123",
        "saas_api_key": "secret-key-xyz",
        "saas_url": "https://dash.example.com",
        "auto_sync": True,
    }), encoding="utf-8")

    raw = server.cl_disconnect(str(tmp_path))
    parsed = json.loads(raw)

    assert parsed["status"] == "disconnected", f"unexpected status: {parsed}"
    assert set(parsed["removed_fields"]) == {"saas_api_key", "saas_url", "auto_sync"}

    rewritten = json.loads(rc_path.read_text(encoding="utf-8"))
    assert "saas_api_key" not in rewritten
    assert "saas_url" not in rewritten
    assert "auto_sync" not in rewritten
    assert rewritten["project_id"] == "proj-abc-123", (
        "local project_id must be preserved after disconnect"
    )


def test_disconnect_unbound_project_returns_not_connected(tmp_path):
    # tmp_path is a fresh empty dir — no .compliancelintrc exists
    raw = server.cl_disconnect(str(tmp_path))
    parsed = json.loads(raw)

    assert parsed["status"] == "not_connected", f"unexpected status: {parsed}"
    assert "No .compliancelintrc" in parsed["message"]
