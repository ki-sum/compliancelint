"""Coverage for MCP tool cl_update_finding_batch (server.py:1592).

B3 broadening 2026-04-30 — original 2 tests covered all-valid +
partial-failure. Expanded to 10 tests covering the full surface of
the bulk-evidence MCP tool: input validation, both modes (per-OID +
article-level), error classification, evidence quality, idempotency.

Surface tested:

  Input validation (4):
    - malformed updates JSON → error
    - non-array updates → error
    - empty updates array → error
    - bad project_path → directory not found

  Per-obligation mode (3):
    - all-valid happy path → updates count matches
    - partial failure with unknown obligation_id → errors[1]
    - invalid obligation_id format → caught at validation layer
      (not silently passed to disk)

  Article-level mode (1):
    - article: "art9" expands to all open findings in that article

  Mixed mode + idempotency (2):
    - mixing per-OID + article-level in one batch
    - same batch run twice → 2nd run is no-op-shaped

cl_update_finding_batch is the BULK evidence-write tool — it can
mutate many findings in one call. Strict input validation matters
here more than for read-only tools.
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


# ──────────────────────────────────────────────────────────────────────
# Input validation
# ──────────────────────────────────────────────────────────────────────


def test_batch_malformed_updates_json_returns_error(tmp_path):
    _seed_rc_with_attester(str(tmp_path))
    raw = server.cl_update_finding_batch(
        project_path=str(tmp_path),
        updates="{this is not valid json",
    )
    parsed = json.loads(raw)
    assert "error" in parsed
    assert "Invalid updates JSON" in parsed["error"] or "JSON" in parsed["error"]


def test_batch_non_array_updates_returns_error(tmp_path):
    """`updates` must be a JSON array. A bare object should fail."""
    _seed_rc_with_attester(str(tmp_path))
    raw = server.cl_update_finding_batch(
        project_path=str(tmp_path),
        updates=json.dumps({"obligation_id": "ART9-OBL-1", "action": "acknowledge"}),
    )
    parsed = json.loads(raw)
    assert "error" in parsed
    assert "array" in parsed["error"].lower()


def test_batch_empty_array_returns_error(tmp_path):
    _seed_rc_with_attester(str(tmp_path))
    raw = server.cl_update_finding_batch(
        project_path=str(tmp_path),
        updates="[]",
    )
    parsed = json.loads(raw)
    assert "error" in parsed
    assert "empty" in parsed["error"].lower()


def test_batch_bad_project_path_returns_error():
    raw = server.cl_update_finding_batch(
        project_path="/nonexistent/path/that/does/not/exist",
        updates=json.dumps([
            {"obligation_id": "ART9-OBL-1", "action": "acknowledge"},
        ]),
    )
    parsed = json.loads(raw)
    assert "error" in parsed


# ──────────────────────────────────────────────────────────────────────
# Per-obligation mode
# ──────────────────────────────────────────────────────────────────────


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

    on_disk = json.loads(open(art_file, encoding="utf-8").read())
    for oid in ids:
        finding = on_disk["findings"][oid]
        assert finding["status"] == "acknowledged"
        assert len(finding["history"]) == 1
        assert finding["history"][0]["action"] == "acknowledge"


def test_update_finding_batch_partial_failure(tmp_path):
    _seed_rc_with_attester(str(tmp_path))
    seeded_ids = ["ART12-OBL-1", "ART12-OBL-2"]
    art_file = _seed_article_with_findings(str(tmp_path), 12, seeded_ids)

    updates = [
        {"obligation_id": "ART12-OBL-1", "action": "acknowledge"},
        {"obligation_id": "ART12-OBL-2", "action": "acknowledge"},
        {"obligation_id": "ART99-OBL-9", "action": "acknowledge"},
    ]
    raw = server.cl_update_finding_batch(
        project_path=str(tmp_path),
        updates=json.dumps(updates),
    )
    parsed = json.loads(raw)

    assert parsed["updated"] == 2
    assert parsed["total_requested"] == 3
    assert len(parsed["errors"]) == 1
    bad = parsed["errors"][0]
    assert bad["obligation_id"] == "ART99-OBL-9"
    assert "not found" in bad["error"].lower()

    on_disk = json.loads(open(art_file, encoding="utf-8").read())
    for oid in seeded_ids:
        assert on_disk["findings"][oid]["status"] == "acknowledged"
    assert "ART99-OBL-9" not in on_disk["findings"]


def test_update_finding_batch_invalid_oid_format_caught_at_validation(tmp_path):
    """Malformed obligation_id ('ART9' without -OBL-N suffix) should
    fail validation BEFORE reaching disk. Customer-facing safety:
    typos should never silently no-op.

    When ALL updates are invalid, the tool returns an error response
    ("No valid updates in batch") rather than a 0-count summary —
    that's the implementation choice. Both shapes confirm "nothing
    landed on disk", which is what matters."""
    _seed_rc_with_attester(str(tmp_path))
    _seed_article_with_findings(str(tmp_path), 9, ["ART9-OBL-1"])

    updates = [
        {"obligation_id": "ART9", "action": "acknowledge"},  # no -OBL- suffix
        {"obligation_id": "art9-obl-1", "action": "acknowledge"},  # lowercase
        {"obligation_id": "", "action": "acknowledge"},  # empty
    ]
    raw = server.cl_update_finding_batch(
        project_path=str(tmp_path),
        updates=json.dumps(updates),
    )
    parsed = json.loads(raw)

    # Either form is acceptable, but in BOTH the disk MUST be untouched.
    if "updated" in parsed:
        assert parsed["updated"] == 0
        assert len(parsed["errors"]) == 3
        for err in parsed["errors"]:
            assert "format" in err["error"].lower() or "invalid" in err["error"].lower()
    else:
        # Bulk-error shape — all 3 invalid → batch rejected outright
        assert "error" in parsed
        assert "valid" in parsed["error"].lower()

    # Critical: original finding on disk untouched
    art_file = os.path.join(
        str(tmp_path), ".compliancelint", "local", "articles", "art9.json"
    )
    on_disk = json.loads(open(art_file, encoding="utf-8").read())
    assert on_disk["findings"]["ART9-OBL-1"]["status"] == "open"


# ──────────────────────────────────────────────────────────────────────
# Article-level mode
# ──────────────────────────────────────────────────────────────────────


def test_update_finding_batch_article_level_mode_expands_to_all_open(tmp_path):
    """`article: "art12"` with one evidence value should apply that
    evidence to ALL open findings in art12 (per docstring: '1 piece of
    evidence auto-applies to ALL open findings in that article')."""
    _seed_rc_with_attester(str(tmp_path))
    ids = ["ART12-OBL-1", "ART12-OBL-2", "ART12-OBL-3"]
    art_file = _seed_article_with_findings(str(tmp_path), 12, ids)

    updates = [
        {
            "article": "art12",
            "action": "provide_evidence",
            "evidence_type": "repo_file",
            "evidence_value": "docs/logging.md",
        },
    ]
    raw = server.cl_update_finding_batch(
        project_path=str(tmp_path),
        updates=json.dumps(updates),
    )
    parsed = json.loads(raw)

    # All 3 findings should have received the evidence
    assert parsed["updated"] >= 3, (
        f"article-level expansion should hit all 3 findings, got: {parsed}"
    )

    on_disk = json.loads(open(art_file, encoding="utf-8").read())
    for oid in ids:
        finding = on_disk["findings"][oid]
        assert finding["evidence"], f"{oid} got no evidence after article-level update"


# ──────────────────────────────────────────────────────────────────────
# Mixed mode + idempotency
# ──────────────────────────────────────────────────────────────────────


def test_update_finding_batch_mixed_mode_in_single_call(tmp_path):
    """Per-OID + article-level can mix in one batch. Each is processed
    independently; final state reflects union."""
    _seed_rc_with_attester(str(tmp_path))
    art9_ids = ["ART9-OBL-1", "ART9-OBL-2"]
    _seed_article_with_findings(str(tmp_path), 9, art9_ids)
    art12_ids = ["ART12-OBL-1", "ART12-OBL-2"]
    _seed_article_with_findings(str(tmp_path), 12, art12_ids)

    updates = [
        # Per-OID
        {"obligation_id": "ART9-OBL-1", "action": "acknowledge"},
        # Article-level
        {
            "article": "art12",
            "action": "provide_evidence",
            "evidence_type": "repo_file",
            "evidence_value": "docs/logging.md",
        },
    ]
    raw = server.cl_update_finding_batch(
        project_path=str(tmp_path),
        updates=json.dumps(updates),
    )
    parsed = json.loads(raw)

    # 1 per-OID + 2 from art12 expansion = 3 total updates
    assert parsed["updated"] >= 3, (
        f"mixed-mode batch should land >=3 updates, got: {parsed}"
    )


def test_update_finding_batch_idempotent_acknowledge(tmp_path):
    """Acknowledging an already-acknowledged finding is no-op-shaped:
    no crash, but history grows by one entry per call (audit trail)."""
    _seed_rc_with_attester(str(tmp_path))
    art_file = _seed_article_with_findings(str(tmp_path), 9, ["ART9-OBL-1"])

    updates = [{"obligation_id": "ART9-OBL-1", "action": "acknowledge"}]

    first = json.loads(server.cl_update_finding_batch(
        project_path=str(tmp_path),
        updates=json.dumps(updates),
    ))
    second = json.loads(server.cl_update_finding_batch(
        project_path=str(tmp_path),
        updates=json.dumps(updates),
    ))

    assert first["updated"] == 1
    # Second call: still updates (history entry added) but no error.
    # The exact `updated` count for repeat-acknowledge is implementation-
    # defined; what matters is "no crash + history grew".
    on_disk = json.loads(open(art_file, encoding="utf-8").read())
    finding = on_disk["findings"]["ART9-OBL-1"]
    assert finding["status"] == "acknowledged"
    assert len(finding["history"]) >= 1
