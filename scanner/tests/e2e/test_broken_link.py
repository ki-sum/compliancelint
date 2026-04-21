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


def test_48_file_removed_transitions_to_broken_link(
    discovered, clear_git_path_rows, seed_git_path_row, db_query,
    server_module, log,
):
    """§4.8 (revised spec) — evidence was committed+pushed (present on disk
    at scan time) then force-push rewrites history to erase the commit, so
    the file is no longer in the working tree at the next cl_sync.
    broken_link sweep must flag it. This mirrors the scanner view of §4.8
    now that the spec change (07c0e59) points §4.8 step 4 at broken_link
    rather than fingerprint warning."""
    repo_id = discovered["repo_id"]
    clear_git_path_rows()
    rel_path = ".compliancelint/evidence/e2e-48/erased.txt"
    abs_path = os.path.join(PROJECT, rel_path)

    # ── Phase 1 — simulate committed-and-pushed state: file on disk ─────
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w") as f:
        f.write("evidence that was committed and pushed\n")
    eid = seed_git_path_row(rel_path)

    summary1 = _broken_link(server_module, log, repo_id, "a" * 40)
    assert summary1["checked"] == 1, f"phase 1 checked=1, got {summary1!r}"
    assert summary1["ok"] == 1, f"phase 1 ok=1, got {summary1!r}"
    # No transition expected in phase 1 (seed='ok' + file present → stays ok).
    # broken_link writes audit rows only on transitions, so phase 1 must be
    # silent. Phase 2 will produce the single fail audit row.
    assert summary1["transitioned"] == 0, \
        f"phase 1 transitioned=0 (no state change), got {summary1!r}"
    row1 = _read_health(db_query, eid)
    assert row1["health_status"] == "ok", \
        f"phase 1: DB stays ok while file present, got {row1!r}"
    audit1 = _audit_counts(db_query, eid)
    assert audit1 == {} or sum(audit1.values()) == 0, \
        f"phase 1: no audit rows (no transition), got {audit1!r}"

    # ── Phase 2 — simulate force-push erasing the commit: file disappears ──
    try:
        os.unlink(abs_path)
        summary2 = _broken_link(server_module, log, repo_id, "b" * 40)
        assert summary2["checked"] == 1, f"phase 2 checked=1, got {summary2!r}"
        assert summary2["broken"] == 1, f"phase 2 broken=1, got {summary2!r}"
        assert summary2["transitioned"] == 1, \
            f"§4.8: phase 2 transitioned=1 (ok → broken_link), got {summary2!r}"

        row2 = _read_health(db_query, eid)
        assert row2["health_status"] == "broken_link", \
            f"§4.8: DB transitions to broken_link after file erased, got {row2!r}"
        assert row2["last_checked_at_sha"] == "b" * 40, \
            f"phase 2: sha updated to b*40, got {row2!r}"

        audit2 = _audit_counts(db_query, eid)
        assert audit2.get("evidence_health_check_fail", 0) == 1, \
            f"§4.8: phase 2 fail audit row (force-push narrative), got {audit2!r}"
        assert audit2.get("evidence_health_check_pass", 0) == 0, \
            f"§4.8: no pass audit row (phase 1 didn't transition), got {audit2!r}"
    finally:
        # Defensive cleanup — if a later test needs this path, it re-creates.
        try:
            if os.path.exists(abs_path):
                os.unlink(abs_path)
        except OSError:
            pass
