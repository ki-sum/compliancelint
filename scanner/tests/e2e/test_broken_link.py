"""Pytest port of scanner/tests/e2e_broken_link.py manual harness.

Track 4c-2 broken_link sweep against live dashboard. Verifies:
  - file missing → ok → broken_link transition + audit fail row
  - file restored → broken_link → ok transition + audit pass row
  - identical re-check is idempotent (no double audit)

Skips entirely if dashboard or project dir not ready (see conftest).
"""
from __future__ import annotations

import os

import pytest

from _e2e_consts import API_KEY, PROJECT, SAAS


pytestmark = pytest.mark.live_dashboard


def _broken_link(server_module, log, repo_id: str, sha: str):
    return server_module._run_broken_link_check(
        project_path=PROJECT, saas_url=SAAS, api_key=API_KEY,
        repo_id=repo_id, checked_at_sha=sha, slog=log,
    )


def _read_health(db_query, eid: str) -> dict:
    rows = db_query(
        "SELECT health_status, last_health_check_at, last_checked_at_sha "
        "FROM evidence_items WHERE id = ?",
        (eid,),
    )
    if not rows:
        return {}
    return {
        "health_status": rows[0][0],
        "last_health_check_at": rows[0][1],
        "last_checked_at_sha": rows[0][2],
    }


def _audit_counts(db_query, eid: str) -> dict:
    rows = db_query(
        "SELECT action, COUNT(*) FROM audit_logs "
        "WHERE resource = ? AND action LIKE 'evidence_health%' GROUP BY action",
        (f"evidence_items/{eid}",),
    )
    return {action: n for action, n in rows}


def test_broken_link_transition(
    discovered, clear_git_path_rows, seed_git_path_row, db_query,
    server_module, log,
):
    """File missing → DB transitions ok → broken_link, audit fail row written."""
    clear_git_path_rows()
    rel_path = ".compliancelint/evidence/e2e-4c2/nonexistent.txt"
    eid = seed_git_path_row(rel_path)

    summary = _broken_link(server_module, log, discovered["repo_id"], "d" * 40)
    assert summary["checked"] == 1, f"checked=1, got {summary!r}"
    assert summary["broken"] == 1, f"broken=1, got {summary!r}"
    assert summary["transitioned"] == 1, f"transitioned=1, got {summary!r}"
    assert summary["unchanged"] == 0, f"unchanged=0, got {summary!r}"

    row = _read_health(db_query, eid)
    assert row["health_status"] == "broken_link", \
        f"DB health_status broken_link, got {row!r}"
    assert row["last_health_check_at"] is not None, \
        "DB last_health_check_at populated"
    assert row["last_checked_at_sha"] == "d" * 40, \
        f"DB last_checked_at_sha, got {row!r}"

    audit = _audit_counts(db_query, eid)
    assert audit.get("evidence_health_check_fail", 0) == 1, \
        f"audit fail row written, got {audit!r}"


def test_file_restore_transitions_back_to_ok(
    discovered, clear_git_path_rows, seed_git_path_row, db_query,
    server_module, log,
):
    """First pass: file missing → broken_link. Create file. Second pass:
    file present → ok transition + pass audit row."""
    repo_id = discovered["repo_id"]
    clear_git_path_rows()
    rel_path = ".compliancelint/evidence/e2e-4c2/restored.txt"
    abs_path = os.path.join(PROJECT, rel_path)
    if os.path.exists(abs_path):
        os.unlink(abs_path)

    eid = seed_git_path_row(rel_path)

    _broken_link(server_module, log, repo_id, "e" * 40)
    assert _read_health(db_query, eid)["health_status"] == "broken_link", \
        "after pass 1: DB transitioned to broken_link"

    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w") as f:
        f.write("restored evidence content\n")

    try:
        summary = _broken_link(server_module, log, repo_id, "f" * 40)
        assert summary["checked"] == 1, f"pass 2 checked=1, got {summary!r}"
        assert summary["ok"] == 1, f"pass 2 ok=1, got {summary!r}"
        assert summary["transitioned"] == 1, \
            f"pass 2 transitioned=1, got {summary!r}"

        row = _read_health(db_query, eid)
        assert row["health_status"] == "ok", \
            f"DB health_status ok after restore, got {row!r}"
        assert row["last_checked_at_sha"] == "f" * 40, \
            f"DB sha updated to f*40, got {row!r}"

        audit = _audit_counts(db_query, eid)
        assert audit.get("evidence_health_check_fail", 0) == 1, \
            f"audit fail row from pass 1, got {audit!r}"
        assert audit.get("evidence_health_check_pass", 0) == 1, \
            f"audit pass row from pass 2, got {audit!r}"
    finally:
        try:
            os.unlink(abs_path)
        except OSError:
            pass


def test_idempotent_no_double_audit(
    discovered, clear_git_path_rows, seed_git_path_row, db_query,
    server_module, log,
):
    """Two consecutive checks with identical state → no extra audit row."""
    repo_id = discovered["repo_id"]
    clear_git_path_rows()
    rel_path = ".compliancelint/evidence/e2e-4c2/idempotent.txt"
    eid = seed_git_path_row(rel_path)

    _broken_link(server_module, log, repo_id, "1" * 40)
    audit1 = _audit_counts(db_query, eid)
    assert audit1.get("evidence_health_check_fail", 0) == 1, \
        f"after first check: 1 fail audit row, got {audit1!r}"

    summary = _broken_link(server_module, log, repo_id, "2" * 40)
    assert summary["unchanged"] == 1, \
        f"second pass unchanged=1, got {summary!r}"
    assert summary["transitioned"] == 0, \
        f"second pass transitioned=0, got {summary!r}"

    audit2 = _audit_counts(db_query, eid)
    assert audit2.get("evidence_health_check_fail", 0) == 1, \
        f"after second check: STILL 1 fail audit row (idempotent), got {audit2!r}"
