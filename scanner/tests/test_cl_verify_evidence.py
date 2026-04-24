"""Thin coverage for MCP tool cl_verify_evidence (server.py:1418).

Tool semantics (see core/evidence.py): loads compliance-evidence.json from
project root and returns a structured summary the AI client then uses to
verify each item. It does NOT crawl .compliancelint/state.json — that's
cl_scan's broken_link path.

Covers:
  - happy path: declared evidence items returned with verification instructions
  - empty path: no compliance-evidence.json returns found=false + schema hint
  - error path: invalid project_path returns Directory not found error
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
                "type": "url",
                "location": "https://example.com/terms",
                "description": "Terms of Service with AI disclosure",
                "provided_by": "Legal Team",
            },
            "ART12-OBL-3": {
                "type": "attestation",
                "description": "Log retention set to 12 months; screenshot on file",
                "provided_by": "DevOps",
            },
        },
    }), encoding="utf-8")

    raw = server.cl_verify_evidence(str(tmp_path))
    parsed = json.loads(raw)

    assert parsed.get("found") is True, f"expected found=true, got: {parsed}"
    assert parsed["total_items"] == 2
    assert parsed["needs_ai_verification"] == 1, (
        "the URL item must need AI verification, the attestation must not"
    )
    assert parsed["attestation_only"] == 1
    assert "verification_instructions" in parsed
    obligation_ids = {item["obligation_id"] for item in parsed["items"]}
    assert obligation_ids == {"ART13", "ART12-OBL-3"}


def test_verify_evidence_with_no_declaration_returns_schema_hint(tmp_path):
    # Empty tmp_path — no compliance-evidence.json
    raw = server.cl_verify_evidence(str(tmp_path))
    parsed = json.loads(raw)

    assert parsed.get("found") is False, f"expected found=false, got: {parsed}"
    assert "fix" in parsed, "missing-evidence response must include fix hint"
    assert "compliance-evidence.json" in parsed["fix"]
    assert "schema_example" in parsed, "response must teach users the file shape"


def test_verify_evidence_with_invalid_project_path_errors(tmp_path):
    nonexistent = tmp_path / "does-not-exist"
    raw = server.cl_verify_evidence(str(nonexistent))
    parsed = json.loads(raw)

    assert "error" in parsed, f"expected error payload, got: {parsed}"
    assert "Directory not found" in parsed["error"]
    assert str(nonexistent) in parsed["error"]
