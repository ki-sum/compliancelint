"""Coverage for MCP tool cl_disconnect (server.py:3455).

B3 broadening 2026-04-30 — original 2 tests covered only happy path
+ no-rc. Expanded to 8 tests covering:

  Happy paths:
    - bound project clears saas_* fields, preserves local config
    - non-ASCII attester values stay readable after rewrite (ensure_ascii)
    - extra fields (project_id, attester_name, scan_strategy) preserved
    - idempotency: 2nd call after disconnect returns not_connected

  Empty / not-connected paths:
    - no .compliancelintrc → not_connected
    - .compliancelintrc exists but no saas_* fields → not_connected

  Error paths:
    - bad project_path → Directory not found
    - malformed .compliancelintrc JSON → readable error (no crash)

These are the customer-facing surface of cl_disconnect — every
behavior the MCP tool exposes has at least one assertion.
"""
import json
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


# ──────────────────────────────────────────────────────────────────────
# Happy paths
# ──────────────────────────────────────────────────────────────────────


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


def test_disconnect_preserves_extra_local_fields(tmp_path):
    """attester_name / scan_strategy / risk_classification_override etc.
    are local config fields that MUST survive a disconnect."""
    rc_path = tmp_path / ".compliancelintrc"
    rc_path.write_text(json.dumps({
        "project_id": "proj-456",
        "saas_api_key": "key",
        "attester_name": "Alice",
        "attester_email": "alice@example.com",
        "scan_strategy": "deep",
        "risk_classification_override": "limited-risk",
    }), encoding="utf-8")

    server.cl_disconnect(str(tmp_path))

    rewritten = json.loads(rc_path.read_text(encoding="utf-8"))
    assert rewritten["project_id"] == "proj-456"
    assert rewritten["attester_name"] == "Alice"
    assert rewritten["attester_email"] == "alice@example.com"
    assert rewritten["scan_strategy"] == "deep"
    assert rewritten["risk_classification_override"] == "limited-risk"


def test_disconnect_uses_ensure_ascii_for_non_ascii_attester(tmp_path):
    """Per `memory/feedback_encoding_mojibake.md`: scanner writes to
    .compliancelintrc must use ensure_ascii=True so re-read on a
    Windows host with cp1252 default encoding doesn't garble the
    non-ASCII content. The .write_text path uses utf-8, but the
    rewrite by cl_disconnect must produce ASCII-safe JSON."""
    rc_path = tmp_path / ".compliancelintrc"
    rc_path.write_text(json.dumps({
        "project_id": "proj-zh",
        "saas_api_key": "key",
        "attester_name": "張三",  # CJK characters
        "attester_email": "張@example.com",
    }, ensure_ascii=False), encoding="utf-8")

    server.cl_disconnect(str(tmp_path))

    raw_bytes = rc_path.read_bytes()
    # ensure_ascii=True means \uXXXX escapes — all bytes must be
    # ASCII-printable (no high-byte UTF-8 sequences).
    assert all(b < 128 for b in raw_bytes), (
        "Disconnect rewrote .compliancelintrc with raw UTF-8 — should "
        "use ensure_ascii=True per feedback_encoding_mojibake.md"
    )

    # And the values round-trip correctly when read with utf-8
    rewritten = json.loads(raw_bytes.decode("ascii"))
    assert rewritten["attester_name"] == "張三"


def test_disconnect_is_idempotent(tmp_path):
    """Two consecutive disconnects: first removes the fields, second
    sees no saas_* fields and returns not_connected. No crash, no
    accidental local-config wipe."""
    rc_path = tmp_path / ".compliancelintrc"
    rc_path.write_text(json.dumps({
        "project_id": "proj-x",
        "saas_api_key": "key",
        "saas_url": "https://dash.example.com",
    }), encoding="utf-8")

    first = json.loads(server.cl_disconnect(str(tmp_path)))
    assert first["status"] == "disconnected"

    second = json.loads(server.cl_disconnect(str(tmp_path)))
    assert second["status"] == "not_connected"
    # Local config still intact
    rewritten = json.loads(rc_path.read_text(encoding="utf-8"))
    assert rewritten["project_id"] == "proj-x"


# ──────────────────────────────────────────────────────────────────────
# Empty / not-connected paths
# ──────────────────────────────────────────────────────────────────────


def test_disconnect_unbound_project_returns_not_connected(tmp_path):
    raw = server.cl_disconnect(str(tmp_path))
    parsed = json.loads(raw)

    assert parsed["status"] == "not_connected"
    assert "No .compliancelintrc" in parsed["message"]


def test_disconnect_rc_present_but_no_saas_fields(tmp_path):
    """User has .compliancelintrc with only local config — cl_disconnect
    should return not_connected (different message from no-file case)."""
    rc_path = tmp_path / ".compliancelintrc"
    rc_path.write_text(json.dumps({
        "project_id": "proj-local-only",
        "attester_name": "Bob",
    }), encoding="utf-8")

    raw = server.cl_disconnect(str(tmp_path))
    parsed = json.loads(raw)

    assert parsed["status"] == "not_connected"
    assert "No dashboard connection" in parsed["message"]
    # Local fields untouched
    rewritten = json.loads(rc_path.read_text(encoding="utf-8"))
    assert rewritten["project_id"] == "proj-local-only"
    assert rewritten["attester_name"] == "Bob"


# ──────────────────────────────────────────────────────────────────────
# Error paths
# ──────────────────────────────────────────────────────────────────────


def test_disconnect_bad_project_path_returns_directory_not_found():
    raw = server.cl_disconnect("/nonexistent/path/that/does/not/exist")
    parsed = json.loads(raw)

    assert "error" in parsed
    assert "not found" in parsed["error"].lower() or "directory" in parsed["error"].lower()


def test_disconnect_malformed_json_returns_readable_error(tmp_path):
    """If .compliancelintrc is corrupted JSON, return a clean error
    (not a Python traceback). User can fix the file by hand."""
    rc_path = tmp_path / ".compliancelintrc"
    rc_path.write_text("{ this is not valid json }}}", encoding="utf-8")

    raw = server.cl_disconnect(str(tmp_path))
    parsed = json.loads(raw)

    assert "error" in parsed
    assert "Could not read" in parsed["error"] or "valid JSON" in parsed.get("fix", "")
