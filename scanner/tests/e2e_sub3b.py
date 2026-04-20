"""End-to-end harness for Evidence v4 sub-3b.

NOT a pytest — run manually while a dev dashboard listens on localhost:3000
with EVIDENCE_ENCRYPTION_KEY set. Seeds via the real upload endpoint, runs
the scanner pull logic, inspects working tree + DB to verify expected
transitions.

Env / setup required:
  - Dashboard dev server at http://localhost:3000
  - Test user 'test-pro@compliancelint.dev' (api_key = cl_test_pro_key_for_development)
  - Repo 7beafd0f-5c47-486e-93c0-9285ed602b8b owned by that user
  - Finding 4edc3c6d-22f2-4d53-a27c-72024522979e under that repo
  - Project dir at c:/tmp/cl-sub3b-e2e initialised with git + .compliancelintrc

Usage:
    python scanner/tests/e2e_sub3b.py

Covers:
  - §3.1 basic pull to working tree
  - §3.2 git status shows Untracked (NO auto-commit)
  - §3.3 PM commits manually → next sync transitions commit_status
  - §4.4 target exists same hash → skip (idempotent resume)
  - §4.5 target exists different hash → .conflict-{ts}
  - §11.2 no third-party OAuth tokens stored (verified indirectly — upload
    endpoint only needs ComplianceLint API key)
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import sqlite3
import hashlib

PROJECT = "c:/tmp/cl-sub3b-e2e"
DB_PATH = "c:/AI/ComplianceLint/private/dashboard/data/compliancelint.db"
SAAS = "http://localhost:3000"
API_KEY = "cl_test_pro_key_for_development"
REPO_ID = "7beafd0f-5c47-486e-93c0-9285ed602b8b"
REPO_NAME = "test-pro/demo-highrisk-provider"
FINDING_ID = "4edc3c6d-22f2-4d53-a27c-72024522979e"

SCANNER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SCANNER_ROOT)

# Lazy import — needs sys.path first
import server  # noqa: E402

log = logging.getLogger("e2e_sub3b")
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s",
                    stream=sys.stderr)


# ── Helpers ─────────────────────────────────────────────────────────────────


def run(cmd: list[str], cwd: str = PROJECT, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def curl_upload(finding_id: str, file_path: str) -> dict:
    r = run(["curl", "-sS", "--max-time", "30", "-X", "POST",
             f"{SAAS}/api/v1/findings/{finding_id}/evidence/upload-file",
             "-H", f"Authorization: Bearer {API_KEY}",
             "-F", f"file=@{file_path}"], cwd=PROJECT, timeout=45)
    if not r.stdout.strip():
        raise RuntimeError(f"upload returned empty stdout; stderr={r.stderr[:200]}")
    return json.loads(r.stdout)


def pending_rows_for_repo() -> list:
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute("""
            SELECT pe.id, pe.filename, ei.commit_status, ei.repo_path
              FROM pending_evidence pe
              JOIN evidence_items ei ON ei.id = pe.evidence_item_id
             WHERE pe.repo_id = ?
        """, (REPO_ID,)).fetchall()
    finally:
        conn.close()


def db_query(sql: str, params: tuple = ()) -> list[tuple]:
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_status_untracked(path: str) -> bool:
    r = run(["git", "status", "--porcelain", "--", path])
    return r.stdout.startswith("??")


def call_pull():
    """Invoke _run_pending_evidence_pull with real HTTP to localhost."""
    summary, prompt, rid = server._run_pending_evidence_pull(
        project_path=PROJECT,
        saas_url=SAAS,
        api_key=API_KEY,
        repo_name=REPO_NAME,
        slog=log,
    )
    return summary, prompt, rid


def assert_eq(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")
    print(f"  ✓ {label}: {actual!r}")


def assert_true(cond: bool, label: str) -> None:
    if not cond:
        raise AssertionError(f"{label}: condition false")
    print(f"  ✓ {label}")


def cleanup_pending():
    """Delete all pending_evidence + reset evidence_items to start fresh."""
    conn = sqlite3.connect(DB_PATH)
    try:
        # Collect evidence_item ids from ALL findings under REPO_ID (FK cascade via scan/finding)
        rows = conn.execute("""
            SELECT ei.id FROM evidence_items ei
            JOIN finding_responses fr ON fr.id = ei.finding_response_id
            JOIN findings f ON f.id = fr.finding_id
            JOIN scans s ON s.id = f.scan_id
            WHERE s.repo_id = ?
        """, (REPO_ID,)).fetchall()
        ids = [r[0] for r in rows]
        if ids:
            placeholders = ",".join("?" * len(ids))
            conn.execute(f"DELETE FROM pending_evidence WHERE evidence_item_id IN ({placeholders})", ids)
            conn.execute(f"DELETE FROM evidence_items WHERE id IN ({placeholders})", ids)
            conn.execute("DELETE FROM finding_responses WHERE finding_id = ?", (FINDING_ID,))
            conn.execute("DELETE FROM audit_logs WHERE resource LIKE 'evidence_items/%'")
        conn.commit()
        print(f"cleanup: removed {len(ids)} evidence_items")
    finally:
        conn.close()


def reset_working_tree():
    """Remove any previously-pulled evidence files + reset metadata.json cache."""
    ev_dir = os.path.join(PROJECT, ".compliancelint", "evidence")
    if os.path.isdir(ev_dir):
        import shutil
        shutil.rmtree(ev_dir)
    meta = os.path.join(PROJECT, ".compliancelint", "metadata.json")
    if os.path.isfile(meta):
        os.unlink(meta)
    # Reset git to initial commit (drop any committed evidence files)
    run(["git", "reset", "--hard", "HEAD"])
    # If there were evidence commits beyond initial, drop them
    r = run(["git", "log", "--oneline"])
    commits = r.stdout.strip().split("\n")
    if len(commits) > 1:
        # Reset to the FIRST commit (the `init` one)
        r2 = run(["git", "rev-list", "--max-parents=0", "HEAD"])
        root = r2.stdout.strip()
        run(["git", "reset", "--hard", root])


# ── Cases ───────────────────────────────────────────────────────────────────


def case_basic_pull():
    print("\n=== Case 1: §3.1 basic pull + §3.2 Untracked ===")
    cleanup_pending()
    reset_working_tree()

    upload_file = os.path.join(PROJECT, "fixture-evidence.txt")
    with open(upload_file, "w") as f:
        f.write("Risk assessment — e2e fixture content.\n")

    seed = curl_upload(FINDING_ID, upload_file)
    assert_eq(seed.get("commit_status"), "pending_commit", "seed commit_status")
    expected_sha = seed["content_sha256"]

    # Run pull
    summary, prompt, rid = call_pull()
    print(f"  pull summary: {json.dumps(summary, indent=2)}")
    print(f"  prompt: {prompt!r}")
    print(f"  resolved repo_id: {rid}")

    assert_eq(rid, REPO_ID, "resolved repo_id")
    assert_eq(summary.get("pulled"), 1, "pulled count")
    assert_eq(summary.get("errors"), 0, "errors count")

    # File lands in working tree
    target = os.path.join(
        PROJECT, ".compliancelint", "evidence", FINDING_ID, "fixture-evidence.txt",
    )
    assert_true(os.path.isfile(target), "target file exists on disk")
    assert_eq(sha256_file(target), expected_sha, "target hash matches server sha")

    # git status shows Untracked — MCP did NOT commit
    assert_true(
        git_status_untracked(".compliancelint/evidence/" + FINDING_ID + "/fixture-evidence.txt"),
        "§3.2 git status shows Untracked (no auto-commit)",
    )

    # Cache written
    cache = server.json.load(
        open(os.path.join(PROJECT, ".compliancelint", "metadata.json"), "r"))
    assert_eq(cache.get("repo_id"), REPO_ID, "metadata.json repo_id cache")

    # Prompt mentions git command
    assert_true("git add .compliancelint/evidence" in prompt, "prompt includes git command")

    # DB still shows pending_commit (human hasn't committed yet)
    status = db_query(
        "SELECT commit_status FROM evidence_items WHERE id = ?",
        (seed["evidence_item_id"],),
    )
    assert_eq(status[0][0], "pending_commit", "DB commit_status still pending")


def case_resume_same_hash():
    print("\n=== Case 2: §4.4 target exists same hash (idempotent resume) ===")
    # Run pull again — target file already there with matching hash
    summary, prompt, rid = call_pull()
    print(f"  pull summary: {json.dumps(summary, indent=2)}")
    assert_eq(summary.get("pulled"), 0, "pulled count")
    assert_eq(summary.get("skipped_same_hash"), 1, "skipped_same_hash count")
    assert_eq(summary.get("errors"), 0, "errors count")


def case_commit_then_confirm():
    print("\n=== Case 3: §3.3 human commits → next sync reports + transitions ===")
    # Sanity: DB should still have 1 pending row before we commit
    pre = pending_rows_for_repo()
    print(f"  pre-commit DB pending rows: {pre}")
    assert_true(len(pre) == 1, "pending row still exists pre-commit")

    # Simulate PM commit
    run(["git", "add", ".compliancelint/evidence"])
    commit = run(["git", "commit", "-m", "[ComplianceLint] Evidence sync"])
    assert_true(commit.returncode == 0, "git commit succeeded")

    # Get the commit sha for the file
    sha = run(["git", "log", "-1", "--pretty=format:%H"]).stdout.strip()
    print(f"  commit sha: {sha}")

    # Sanity: pending row should STILL exist (we haven't notified SaaS yet)
    mid = pending_rows_for_repo()
    print(f"  post-commit DB pending rows: {mid}")
    assert_true(len(mid) == 1, "pending row still exists post-commit (SaaS not yet notified)")

    # Run pull
    summary, prompt, rid = call_pull()
    print(f"  pull summary: {json.dumps(summary, indent=2)}")
    assert_eq(summary.get("confirmed"), 1, "confirmed count")
    assert_eq(summary.get("pulled"), 0, "pulled count")

    # DB should now show committed
    rows = db_query("""
        SELECT ei.commit_status, ei.committed_at_sha
          FROM evidence_items ei
          JOIN finding_responses fr ON fr.id = ei.finding_response_id
         WHERE fr.finding_id = ?
    """, (FINDING_ID,))
    assert_true(len(rows) > 0, "evidence_items row exists")
    assert_eq(rows[0][0], "committed", "DB commit_status = committed")
    assert_eq(rows[0][1], sha, "DB committed_at_sha matches local git sha")

    # pending_evidence row should be gone (row deleted on transition per sync-confirm route)
    pending = db_query("SELECT COUNT(*) FROM pending_evidence WHERE evidence_item_id IN "
                        "(SELECT ei.id FROM evidence_items ei JOIN finding_responses fr "
                        "ON fr.id = ei.finding_response_id WHERE fr.finding_id = ?)",
                        (FINDING_ID,))
    assert_eq(pending[0][0], 0, "pending_evidence row deleted after confirm")

    # Audit log written
    audit = db_query("""
        SELECT action, resource FROM audit_logs
         WHERE action = 'evidence_sync_confirm' AND resource LIKE 'evidence_items/%'
         ORDER BY created_at DESC LIMIT 1
    """)
    assert_true(len(audit) > 0, "audit log row written")
    assert_eq(audit[0][0], "evidence_sync_confirm", "audit action")


def case_conflict_different_hash():
    print("\n=== Case 4: §4.5 target exists different hash → .conflict-{ts} ===")
    cleanup_pending()
    reset_working_tree()

    # Upload one file to seed
    upload_file = os.path.join(PROJECT, "conflict-fixture.txt")
    with open(upload_file, "w") as f:
        f.write("INCOMING content — server version.\n")
    seed = curl_upload(FINDING_ID, upload_file)

    # Place a *different* file at the target repo_path BEFORE running pull
    target_rel = seed["repo_path"]
    target_abs = os.path.join(PROJECT, target_rel)
    os.makedirs(os.path.dirname(target_abs), exist_ok=True)
    with open(target_abs, "w") as f:
        f.write("LOCAL content — user had different file.\n")
    local_hash = sha256_file(target_abs)

    summary, prompt, rid = call_pull()
    print(f"  pull summary: {json.dumps(summary, indent=2)}")
    assert_eq(summary.get("conflicts"), 1, "conflicts count")
    assert_eq(summary.get("pulled"), 0, "pulled count (no overwrite)")

    # Original untouched
    assert_eq(sha256_file(target_abs), local_hash, "original file preserved bit-identical")

    # Conflict file exists
    conflict_paths = summary.get("conflict_paths", [])
    assert_true(len(conflict_paths) == 1, "one conflict path recorded")
    conflict_rel = conflict_paths[0]
    conflict_abs = os.path.join(PROJECT, conflict_rel.replace("/", os.sep))
    assert_true(os.path.isfile(conflict_abs), "conflict file exists on disk")
    assert_true("conflict-" in conflict_rel, "conflict filename has timestamp marker")
    assert_eq(sha256_file(conflict_abs), seed["content_sha256"], "conflict file matches incoming sha")

    # Prompt mentions conflict
    assert_true("different content" in prompt, "prompt flags conflict separately")


def case_no_matching_repo():
    print("\n=== Case 5: /repos list returns no match → skip with clear message ===")
    # Temporarily change repo_name to something non-existent
    cfg_path = os.path.join(PROJECT, ".compliancelintrc")
    original = open(cfg_path).read()
    try:
        modified = original.replace(REPO_NAME, "nonexistent/fake-repo")
        open(cfg_path, "w").write(modified)

        # Clear cache to force list lookup
        meta = os.path.join(PROJECT, ".compliancelint", "metadata.json")
        if os.path.isfile(meta):
            os.unlink(meta)

        summary, prompt, rid = server._run_pending_evidence_pull(
            project_path=PROJECT,
            saas_url=SAAS,
            api_key=API_KEY,
            repo_name="nonexistent/fake-repo",
            slog=log,
        )
        print(f"  summary: {json.dumps(summary, indent=2)}")
        print(f"  prompt: {prompt!r}")
        assert_eq(summary.get("skipped"), True, "skipped flag set")
        assert_eq(summary.get("reason"), "no_matching_repo", "reason recorded")
        assert_eq(rid, "", "rid empty")
        assert_true("not found" in prompt, "human prompt mentions not-found")
    finally:
        open(cfg_path, "w").write(original)


def case_stale_cache_invalidation():
    print("\n=== Case 6: stale metadata.json repo_id → invalidated on 404 → retry ===")
    cleanup_pending()
    reset_working_tree()

    # Plant a BOGUS repo_id in the cache — simulates repo having moved/been deleted
    meta_dir = os.path.join(PROJECT, ".compliancelint")
    os.makedirs(meta_dir, exist_ok=True)
    meta_path = os.path.join(meta_dir, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump({"repo_id": "bogus-repo-uuid-that-does-not-exist"}, f)

    # Seed one pending row so the retry path has something to pull
    upload_file = os.path.join(PROJECT, "stale-cache-fixture.txt")
    with open(upload_file, "w") as f:
        f.write("bytes for stale-cache invalidation test\n")
    seed = curl_upload(FINDING_ID, upload_file)

    summary, prompt, rid = call_pull()
    print(f"  pull summary: {json.dumps(summary, indent=2)}")
    print(f"  resolved rid: {rid}")
    assert_eq(rid, REPO_ID, "invalidated cache → re-resolved to correct rid")
    assert_eq(summary.get("pulled"), 1, "bonus: pulled 1 after invalidation")

    # Cache now has the correct rid
    with open(meta_path) as f:
        cache = json.load(f)
    assert_eq(cache.get("repo_id"), REPO_ID, "metadata.json cache refreshed")


# ── Main ────────────────────────────────────────────────────────────────────


def main():
    print("=== Evidence v4 sub-3b e2e — Scanner ↔ Dashboard ===")
    print(f"project: {PROJECT}")
    print(f"saas: {SAAS}")
    print(f"repo_id: {REPO_ID}")
    print(f"finding_id: {FINDING_ID}")

    # Warm routes so Next-dev turbopack compile-on-demand doesn't cause timeouts
    print("warming endpoints...")
    for url in [
        f"{SAAS}/api/v1/repos",
        f"{SAAS}/api/v1/repos/{REPO_ID}/pending-evidence",
    ]:
        r = run(["curl", "-s", "--max-time", "30", "-H", f"Authorization: Bearer {API_KEY}", url],
                timeout=45)
        print(f"  warmed {url}: http (stdout {len(r.stdout)}B)")

    cases = [
        ("basic_pull_and_untracked",          case_basic_pull),
        ("resume_same_hash",                  case_resume_same_hash),
        ("commit_then_confirm",               case_commit_then_confirm),
        ("conflict_different_hash",           case_conflict_different_hash),
        ("no_matching_repo",                  case_no_matching_repo),
        ("stale_cache_invalidation",          case_stale_cache_invalidation),
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

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
