"""Thin coverage for MCP tool cl_update_finding (server.py:1178).

Covers:
  - happy path: acknowledge an existing finding writes status + audit history
  - error path: invalid action returns error listing valid actions
  - error path: unknown obligation_id (valid format, not seeded) returns not-found error
"""
import json
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def _seed_rc_with_attester(project_path):
    rc = os.path.join(project_path, ".compliancelintrc")
    with open(rc, "w", encoding="utf-8") as f:
        json.dump({
            "attester_name": "Grace Hopper",
            "attester_email": "grace@example.com",
            "attester_role": "Engineer",
        }, f)


def _seed_finding(project_path, article_num, obligation_id):
    art_dir = os.path.join(project_path, ".compliancelint", "articles")
    os.makedirs(art_dir, exist_ok=True)
    art_file = os.path.join(art_dir, f"art{article_num}.json")
    payload = {
        "article": article_num,
        "findings": {
            obligation_id: {
                "obligation_id": obligation_id,
                "level": "non_compliant",
                "description": "Seeded for cl_update_finding thin test",
                "source_quote": "verbatim EUR-Lex stub",
                "status": "open",
                "history": [],
                "evidence": [],
            },
        },
        "regulation": "eu-ai-act",
    }
    with open(art_file, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return art_file


def test_update_finding_acknowledge_succeeds(tmp_path):
    _seed_rc_with_attester(str(tmp_path))
    obligation_id = "ART12-OBL-1"
    art_file = _seed_finding(str(tmp_path), 12, obligation_id)

    raw = server.cl_update_finding(
        project_path=str(tmp_path),
        obligation_id=obligation_id,
        action="acknowledge",
    )
    parsed = json.loads(raw)

    assert parsed.get("status") == "updated", f"expected status=updated, got: {parsed}"
    assert parsed["finding"]["status"] == "acknowledged"

    # Article file on disk reflects the change + audit trail
    on_disk = json.loads(open(art_file, encoding="utf-8").read())
    seeded = on_disk["findings"][obligation_id]
    assert seeded["status"] == "acknowledged"
    assert len(seeded["history"]) == 1
    history_entry = seeded["history"][0]
    assert history_entry["action"] == "acknowledge"
    assert history_entry["by"]["email"] == "grace@example.com"
    assert history_entry["by"]["source"] == "compliancelintrc"


def test_update_finding_invalid_action_returns_error(tmp_path):
    raw = server.cl_update_finding(
        project_path=str(tmp_path),
        obligation_id="ART12-OBL-1",
        action="invalid_action",
    )
    parsed = json.loads(raw)

    assert "error" in parsed, f"expected error, got: {parsed}"
    assert "invalid_action" in parsed["error"].lower() or "invalid" in parsed["error"].lower()
    assert "fix" in parsed
    for legal in ("provide_evidence", "acknowledge", "rebut", "defer", "resolve"):
        assert legal in parsed["fix"], f"fix hint must list legal action '{legal}'"


def test_update_finding_unknown_obligation_id_returns_error(tmp_path):
    _seed_rc_with_attester(str(tmp_path))
    # Seed an articles dir with a DIFFERENT obligation so the directory exists
    # but the requested id is missing — exercises the "Finding not found" branch.
    _seed_finding(str(tmp_path), 12, "ART12-OBL-1")

    raw = server.cl_update_finding(
        project_path=str(tmp_path),
        obligation_id="ART99-OBL-999",
        action="acknowledge",
    )
    parsed = json.loads(raw)

    assert "error" in parsed, f"expected error, got: {parsed}"
    assert "ART99-OBL-999" in parsed["error"]
    assert "not found" in parsed["error"].lower()
