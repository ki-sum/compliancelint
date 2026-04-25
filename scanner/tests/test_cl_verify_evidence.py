"""Thin coverage for MCP tool cl_verify_evidence (server.py:1420).

Tool semantics (see core/evidence.py): loads compliance-evidence.json from
project root and returns a structured summary the AI client then uses to
verify each item. It does NOT crawl .compliancelint/state.json — that's
cl_scan's broken_link path.

Aligned with v4 evidence architecture (shipped 2026-04-21):
storage_kind ∈ {text, repo_file, git_path, url_reference}.

Covers:
  - happy path: declared evidence items returned with verification instructions
  - empty path: no compliance-evidence.json returns found=false + schema hint
  - error path: invalid project_path returns Directory not found error
  - migration path: pre-v4 storage kinds rejected with migration message
"""
import json
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def test_verify_evidence_with_declared_items_returns_summary(tmp_path):
    evidence_path = tmp_path / "compliance-evidence.json"
    evidence_path.write_text(json.dumps({
        "evidence": {
            "ART13": {
                "storage_kind": "url_reference",
                "location": "https://example.com/terms",
                "description": "Terms of Service with AI disclosure",
                "provided_by": "Legal Team",
            },
            "ART12-OBL-6": {
                "storage_kind": "text",
                "description": "Log retention is configured to 12 months in src/logging/retention.py:12.",
                "provided_by": "DevOps",
            },
        },
    }), encoding="utf-8")

    raw = server.cl_verify_evidence(str(tmp_path))
    parsed = json.loads(raw)

    assert parsed.get("found") is True, f"expected found=true, got: {parsed}"
    assert parsed["total_items"] == 2
    assert "verification_instructions" in parsed
    kinds = {item["storage_kind"] for item in parsed["items"]}
    assert kinds == {"url_reference", "text"}
    obligation_ids = {item["obligation_id"] for item in parsed["items"]}
    assert obligation_ids == {"ART13", "ART12-OBL-6"}
    # Every v4 item carries a verification_instruction the AI client must follow.
    for item in parsed["items"]:
        assert item["requires_ai_verification"] is True
        assert "verification_instruction" in item
        assert len(item["verification_instruction"]) > 20


def test_verify_evidence_with_no_declaration_returns_schema_hint(tmp_path):
    # Empty tmp_path — no compliance-evidence.json
    raw = server.cl_verify_evidence(str(tmp_path))
    parsed = json.loads(raw)

    assert parsed.get("found") is False, f"expected found=false, got: {parsed}"
    assert "fix" in parsed, "missing-evidence response must include fix hint"
    assert "compliance-evidence.json" in parsed["fix"]
    assert "schema_example" in parsed, "response must teach users the file shape"
    # Schema example must use v4 storage kinds, not legacy `type` field
    sample = parsed["schema_example"]["evidence"]
    for entry in sample.values():
        assert "storage_kind" in entry, f"schema example must use storage_kind, got: {entry}"
        assert entry["storage_kind"] in {"text", "repo_file", "git_path", "url_reference"}


def test_verify_evidence_with_invalid_project_path_errors(tmp_path):
    nonexistent = tmp_path / "does-not-exist"
    raw = server.cl_verify_evidence(str(nonexistent))
    parsed = json.loads(raw)

    assert "error" in parsed, f"expected error payload, got: {parsed}"
    assert "Directory not found" in parsed["error"]
    assert str(nonexistent) in parsed["error"]


def test_verify_evidence_rejects_pre_v4_storage_kinds(tmp_path):
    """Pre-v4 kinds (url, file, attestation, screenshot) must be hard-rejected
    with a migration message — not silently accepted.
    """
    evidence_path = tmp_path / "compliance-evidence.json"
    evidence_path.write_text(json.dumps({
        "evidence": {
            "ART13": {
                "type": "url",  # legacy
                "location": "https://example.com/terms",
                "description": "Terms of Service",
            },
            "ART12-OBL-6": {
                "type": "screenshot",  # legacy — must trigger migration message
                "description": "Vercel dashboard log retention setting",
            },
        },
    }), encoding="utf-8")

    raw = server.cl_verify_evidence(str(tmp_path))
    parsed = json.loads(raw)

    assert "error" in parsed, f"expected rejection, got: {parsed}"
    # Error payload should mention v4 kinds and the migration path
    assert "v4" in parsed.get("fix", "") or "v4" in parsed.get("error", "")
    assert "screenshot" in parsed.get("error", "") or "screenshot" in str(parsed)
