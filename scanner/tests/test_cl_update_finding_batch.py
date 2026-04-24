"""Thin coverage for MCP tool cl_update_finding_batch (server.py:1288).

Covers:
  - happy path: 3 valid per-obligation updates all succeed
  - partial-failure path: 2 valid + 1 unknown obligation_id → updated=2, errors[1]
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
            "attester_name": "Ada Lovelace",
            "attester_email": "ada@example.com",
            "attester_role": "Compliance Lead",
        }, f)


def _seed_article_with_findings(project_path, article_num, obligation_ids):
    art_dir = os.path.join(project_path, ".compliancelint", "local", "articles")
    os.makedirs(art_dir, exist_ok=True)
    art_file = os.path.join(art_dir, f"art{article_num}.json")
    findings = {
        oid: {
            "obligation_id": oid,
            "level": "non_compliant",
            "description": f"Seeded {oid} for batch test",
            "source_quote": "verbatim stub",
            "status": "open",
            "history": [],
            "evidence": [],
        }
        for oid in obligation_ids
    }
    with open(art_file, "w", encoding="utf-8") as f:
        json.dump({
            "article": article_num,
            "findings": findings,
            "regulation": "eu-ai-act",
        }, f)
    return art_file


def test_update_finding_batch_all_valid(tmp_path):
    _seed_rc_with_attester(str(tmp_path))
    ids = ["ART12-OBL-1", "ART12-OBL-2", "ART12-OBL-3"]
    art_file = _seed_article_with_findings(str(tmp_path), 12, ids)

    updates = [
        {"obligation_id": oid, "action": "acknowledge"} for oid in ids
    ]
    raw = server.cl_update_finding_batch(
        project_path=str(tmp_path),
        updates=json.dumps(updates),
    )
    parsed = json.loads(raw)

    assert parsed["updated"] == 3, f"expected all 3 updated, got: {parsed}"
    assert parsed["errors"] == [], f"expected no errors, got: {parsed['errors']}"
    assert parsed["total_requested"] == 3

    # All three findings on disk now have status=acknowledged and a history entry
    on_disk = json.loads(open(art_file, encoding="utf-8").read())
    for oid in ids:
        finding = on_disk["findings"][oid]
        assert finding["status"] == "acknowledged", f"{oid} not acknowledged on disk"
        assert len(finding["history"]) == 1
        assert finding["history"][0]["action"] == "acknowledge"


def test_update_finding_batch_partial_failure(tmp_path):
    _seed_rc_with_attester(str(tmp_path))
    seeded_ids = ["ART12-OBL-1", "ART12-OBL-2"]
    art_file = _seed_article_with_findings(str(tmp_path), 12, seeded_ids)

    updates = [
        {"obligation_id": "ART12-OBL-1", "action": "acknowledge"},
        {"obligation_id": "ART12-OBL-2", "action": "acknowledge"},
        {"obligation_id": "ART99-OBL-9", "action": "acknowledge"},  # not seeded
    ]
    raw = server.cl_update_finding_batch(
        project_path=str(tmp_path),
        updates=json.dumps(updates),
    )
    parsed = json.loads(raw)

    assert parsed["updated"] == 2, f"expected 2 succeeded, got: {parsed}"
    assert parsed["total_requested"] == 3
    assert len(parsed["errors"]) == 1, f"expected 1 error, got: {parsed['errors']}"
    bad = parsed["errors"][0]
    assert bad["obligation_id"] == "ART99-OBL-9"
    assert "not found" in bad["error"].lower()

    # Valid updates landed on disk; the unseeded one left no trace
    on_disk = json.loads(open(art_file, encoding="utf-8").read())
    for oid in seeded_ids:
        assert on_disk["findings"][oid]["status"] == "acknowledged"
    assert "ART99-OBL-9" not in on_disk["findings"]
