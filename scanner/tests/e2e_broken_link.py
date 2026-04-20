"""End-to-end harness for Evidence v4 Track 4c-2 (scanner broken_link).

NOT a pytest — run manually against a live dashboard dev server with
seeded git_path evidence.

Setup required:
  - Dashboard dev server at http://localhost:3000
  - test-pro user (api_key cl_test_pro_key_for_development)
  - Repo 7beafd0f (demo-highrisk-provider)
  - Finding 4edc3c6d

Usage:
    python scanner/tests/e2e_broken_link.py

Covers:
  - Seed git_path evidence via direct SQL (scanner doesn't produce them
    during cl_scan; this harness simulates a scan result)
  - Scanner broken_link sweep against real dashboard
  - Verify health_status transitions (ok → broken_link on missing file,
    broken_link → ok on file restore)
  - Verify audit log rows written in evidence_health_check_pass/fail
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import sys
import uuid

PROJECT = "c:/tmp/cl-sub3b-e2e"  # reuse the same dir as sub-3b
DB_PATH = "c:/AI/ComplianceLint/private/dashboard/data/compliancelint.db"
SAAS = "http://localhost:3000"
API_KEY = "cl_test_pro_key_for_development"
REPO_ID = "7beafd0f-5c47-486e-93c0-9285ed602b8b"
FINDING_ID = "4edc3c6d-22f2-4d53-a27c-72024522979e"

SCANNER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402

log = logging.getLogger("e2e_broken_link")
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s",
                    stream=sys.stderr)


def run(cmd: list[str], cwd: str = PROJECT, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def seed_git_path_row(repo_path: str, content_sha: str = "a" * 64) -> str:
    """Insert a finding_response + evidence_items (git_path) row directly.

    Returns evidence_item_id. Simulates a cl_scan_all result without
    running the full scanner pipeline.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        fr_id = str(uuid.uuid4())
        ei_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO finding_responses (id, finding_id, action, submitted_by) "
            "VALUES (?, ?, 'acknowledge', NULL)",
            (fr_id, FINDING_ID),
        )
        conn.execute(
            "INSERT INTO evidence_items "
            "(id, finding_response_id, source, storage_kind, repo_path, "
            " content_sha256, commit_status, health_status, uploaded_at, created_at) "
            "VALUES (?, ?, 'scanner', 'git_path', ?, ?, 'committed', 'ok', "
            "       datetime('now'), datetime('now'))",
            (ei_id, fr_id, repo_path, content_sha),
        )
        conn.commit()
        return ei_id
    finally:
        conn.close()


def clear_git_path_rows() -> None:
    """Delete all scanner-sourced git_path evidence under this finding."""
    conn = sqlite3.connect(DB_PATH)
    try:
        eids = [r[0] for r in conn.execute(
            "SELECT ei.id FROM evidence_items ei "
            "JOIN finding_responses fr ON fr.id = ei.finding_response_id "
            "WHERE fr.finding_id = ? AND ei.storage_kind = 'git_path'",
            (FINDING_ID,),
        ).fetchall()]
        if eids:
            ph = ",".join("?" * len(eids))
            conn.execute(f"DELETE FROM audit_logs WHERE resource IN ({','.join([repr(f'evidence_items/{e}') for e in eids])})")
            conn.execute(f"DELETE FROM evidence_items WHERE id IN ({ph})", eids)
        conn.execute(
            "DELETE FROM finding_responses WHERE finding_id = ? AND submitted_by IS NULL",
            (FINDING_ID,),
        )
        conn.commit()
        print(f"  cleanup: removed {len(eids)} git_path rows")
    finally:
        conn.close()


def read_health_status(evidence_item_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        r = conn.execute(
            "SELECT health_status, last_health_check_at, last_checked_at_sha "
            "FROM evidence_items WHERE id = ?",
            (evidence_item_id,),
        ).fetchone()
        if not r:
            return {}
        return {
            "health_status": r[0],
            "last_health_check_at": r[1],
            "last_checked_at_sha": r[2],
        }
    finally:
        conn.close()


def count_audit_rows(evidence_item_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT action, COUNT(*) FROM audit_logs "
            "WHERE resource = ? AND action LIKE 'evidence_health%' GROUP BY action",
            (f"evidence_items/{evidence_item_id}",),
        ).fetchall()
        return {action: n for action, n in rows}
    finally:
        conn.close()


def assert_eq(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")
    print(f"  PASS {label}: {actual!r}")


def assert_true(cond: bool, label: str) -> None:
    if not cond:
        raise AssertionError(f"{label}: condition false")
    print(f"  PASS {label}")


def case_broken_link_transition():
    print("\n=== Case 1: file missing → broken_link transition + audit fail ===")
    clear_git_path_rows()

    # Seed a row pointing at a path that does NOT exist in the working tree
    rel_path = ".compliancelint/evidence/e2e-4c2/nonexistent.txt"
    eid = seed_git_path_row(rel_path)
    print(f"  seeded evidence_item: {eid} repo_path={rel_path}")

    # Run the broken_link check
    summary = server._run_broken_link_check(
        project_path=PROJECT,
        saas_url=SAAS,
        api_key=API_KEY,
        repo_id=REPO_ID,
        checked_at_sha="d" * 40,
        slog=log,
    )
    print(f"  summary: {json.dumps(summary, indent=2)}")

    assert_eq(summary["checked"], 1, "checked")
    assert_eq(summary["broken"], 1, "broken count")
    assert_eq(summary["transitioned"], 1, "transitioned (ok → broken_link)")
    assert_eq(summary["unchanged"], 0, "unchanged")

    row = read_health_status(eid)
    assert_eq(row["health_status"], "broken_link", "DB health_status")
    assert_true(row["last_health_check_at"] is not None, "DB last_health_check_at populated")
    assert_eq(row["last_checked_at_sha"], "d" * 40, "DB last_checked_at_sha populated")

    audit = count_audit_rows(eid)
    assert_eq(audit.get("evidence_health_check_fail", 0), 1, "audit log fail row written")


def case_file_restore_transitions_back_to_ok():
    print("\n=== Case 2: file restored → broken_link → ok transition + audit pass ===")
    # Clear rows from case 1 so this case's state assertions are focused on
    # the single row we seed below (otherwise case 1's item inflates counts).
    clear_git_path_rows()

    rel_path = ".compliancelint/evidence/e2e-4c2/restored.txt"
    abs_path = os.path.join(PROJECT, rel_path)
    # Prior test run may have left this file — pre-delete so pass 1 actually
    # sees file-missing state (otherwise health stays ok, no transition).
    if os.path.exists(abs_path):
        os.unlink(abs_path)
    eid = seed_git_path_row(rel_path)
    print(f"  seeded evidence_item: {eid} repo_path={rel_path}")

    # First pass: file missing → broken_link
    summary1 = server._run_broken_link_check(
        project_path=PROJECT, saas_url=SAAS, api_key=API_KEY,
        repo_id=REPO_ID, checked_at_sha="e" * 40, slog=log,
    )
    print(f"  pass 1 summary: {json.dumps(summary1, indent=2)}")
    assert_eq(read_health_status(eid)["health_status"], "broken_link",
              "after pass 1: broken_link")

    # Now create the file
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w") as f:
        f.write("restored evidence content\n")

    # Second pass: file present → transition back to ok
    summary = server._run_broken_link_check(
        project_path=PROJECT, saas_url=SAAS, api_key=API_KEY,
        repo_id=REPO_ID, checked_at_sha="f" * 40, slog=log,
    )
    print(f"  pass 2 summary: {json.dumps(summary, indent=2)}")
    assert_eq(summary["checked"], 1, "checked (exactly the 1 row under test)")
    assert_eq(summary["ok"], 1, "ok count")
    assert_eq(summary["transitioned"], 1, "transitioned (broken_link → ok)")

    row = read_health_status(eid)
    assert_eq(row["health_status"], "ok", "DB health_status ok")
    assert_eq(row["last_checked_at_sha"], "f" * 40, "DB last_checked_at_sha updated")

    audit = count_audit_rows(eid)
    assert_eq(audit.get("evidence_health_check_fail", 0), 1, "audit fail row (from pass 1)")
    assert_eq(audit.get("evidence_health_check_pass", 0), 1, "audit pass row (from pass 2)")

    # Cleanup created file
    try:
        os.unlink(abs_path)
    except OSError:
        pass


def case_idempotent_no_double_audit():
    print("\n=== Case 3: idempotent — repeating same check does not double-audit ===")
    clear_git_path_rows()

    rel_path = ".compliancelint/evidence/e2e-4c2/idempotent.txt"
    eid = seed_git_path_row(rel_path)

    # Two successive checks, same state (file missing both times)
    server._run_broken_link_check(
        project_path=PROJECT, saas_url=SAAS, api_key=API_KEY,
        repo_id=REPO_ID, checked_at_sha="1" * 40, slog=log,
    )
    # After first: 1 fail audit row
    audit1 = count_audit_rows(eid)
    assert_eq(audit1.get("evidence_health_check_fail", 0), 1,
              "after first check: 1 fail audit row")

    # Second pass — same file-check result, no transition
    summary = server._run_broken_link_check(
        project_path=PROJECT, saas_url=SAAS, api_key=API_KEY,
        repo_id=REPO_ID, checked_at_sha="2" * 40, slog=log,
    )
    assert_eq(summary["unchanged"], 1, "second pass: unchanged=1")
    assert_eq(summary["transitioned"], 0, "second pass: transitioned=0")

    # Audit row count should NOT have increased
    audit2 = count_audit_rows(eid)
    assert_eq(audit2.get("evidence_health_check_fail", 0), 1,
              "after second check: STILL 1 fail audit row (idempotent)")


def main():
    print("=== Evidence v4 Track 4c-2 e2e — scanner broken_link check ===")
    print(f"project: {PROJECT}")
    print(f"saas: {SAAS}")
    print(f"repo_id: {REPO_ID}")
    print(f"finding_id: {FINDING_ID}")

    cases = [
        ("broken_link_transition", case_broken_link_transition),
        ("file_restore_transitions_back_to_ok", case_file_restore_transitions_back_to_ok),
        ("idempotent_no_double_audit", case_idempotent_no_double_audit),
    ]

    passed = 0
    failed = 0
    for name, fn in cases:
        try:
            fn()
            passed += 1
            print(f"PASS: {name}")
        except Exception as e:
            failed += 1
            print(f"FAIL: {name}: {e}")
            import traceback
            traceback.print_exc()

    # Final cleanup
    clear_git_path_rows()
    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
