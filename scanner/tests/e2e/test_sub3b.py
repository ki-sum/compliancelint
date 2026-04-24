"""Pytest port of scanner/tests/e2e_sub3b.py manual harness.

Covers Evidence v4 sub-3b deferred-path scenarios end-to-end against a live
dashboard:
  - §3.1 basic pull to working tree
  - §3.2 git status shows Untracked (NO auto-commit)
  - §3.3 PM commits manually → next sync transitions DB to committed
  - §4.4 target exists same hash → skip (idempotent resume)
  - §4.5 target exists different hash → .conflict-{ts}
  - §11.2 no third-party OAuth tokens used (only ComplianceLint API key)

Skips entirely if dashboard or project dir not ready (see conftest).
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time

import pytest

from _e2e_consts import API_KEY, DB_PATH, PROJECT, REPO_NAME, SAAS


pytestmark = pytest.mark.live_dashboard


def test_full_pull_workflow(
    discovered, with_remote, cleanup_pending, reset_working_tree, curl_upload,
    call_pull, sha256_file_fn, run_in_project, db_query,
):
    """§3.1 basic pull → §4.4 idempotent resume → §3.3 commit+push + transition.

    Three phases share working-tree state, so they run as one ordered scenario.
    Phase C now does `git push` after `git commit` because the §4.6 fix
    requires the sha to be on a remote branch before sync-confirm fires.
    See test_46_commit_without_push for the unpushed-commit assertion.
    """
    repo_id = discovered["repo_id"]
    finding_id = discovered["finding_id"]

    cleanup_pending()
    reset_working_tree()

    # ── Phase A: §3.1 basic pull + §3.2 Untracked ───────────────────────
    upload_file = os.path.join(PROJECT, "fixture-evidence.txt")
    with open(upload_file, "w") as f:
        f.write("Risk assessment — pytest fixture content.\n")
    seed = curl_upload(finding_id, upload_file)
    assert seed.get("commit_status") == "pending_commit", \
        f"seed commit_status, got {seed!r}"
    expected_sha = seed["content_sha256"]

    summary, prompt, rid = call_pull()
    assert rid == repo_id, f"resolved repo_id, got {rid!r}"
    assert summary.get("pulled") == 1, f"pulled=1 expected, got {summary!r}"
    assert summary.get("errors") == 0, f"errors=0 expected, got {summary!r}"

    target = os.path.join(
        PROJECT, ".compliancelint", "evidence", finding_id, "fixture-evidence.txt",
    )
    assert os.path.isfile(target), "target file written to working tree"
    assert sha256_file_fn(target) == expected_sha, \
        "target file hash matches server-reported sha"

    git_status = run_in_project([
        "git", "status", "--porcelain", "--",
        ".compliancelint/evidence/" + finding_id + "/fixture-evidence.txt",
    ])
    assert git_status.stdout.startswith("??"), \
        f"§3.2: git status must show Untracked, got: {git_status.stdout!r}"

    cache_path = os.path.join(PROJECT, ".compliancelint", "local", "metadata.json")
    with open(cache_path) as f:
        cache = json.load(f)
    assert cache.get("repo_id") == repo_id, \
        f"metadata.json cache populated, got {cache!r}"
    assert "git add .compliancelint/evidence" in prompt, \
        f"prompt includes git command, got: {prompt!r}"

    status = db_query(
        "SELECT commit_status FROM evidence_items WHERE id = ?",
        (seed["evidence_item_id"],),
    )
    assert status[0][0] == "pending_commit", \
        f"DB commit_status still pending pre-commit, got {status!r}"

    # ── Phase B: §4.4 resume — target exists same hash ──────────────────
    summary2, _, _ = call_pull()
    assert summary2.get("pulled") == 0, \
        f"resume: pulled=0 expected, got {summary2!r}"
    assert summary2.get("skipped_same_hash") == 1, \
        f"resume: skipped_same_hash=1 expected, got {summary2!r}"
    assert summary2.get("errors") == 0, \
        f"resume: errors=0 expected, got {summary2!r}"

    # ── Phase C: §3.3 PM commits + pushes → next sync transitions ───────
    # Push is REQUIRED post-Problem-1-fix: get_committed_sha returns None
    # for local-only commits so sync-confirm wouldn't fire without push.
    run_in_project(["git", "add", ".compliancelint/evidence"])
    commit = run_in_project([
        "git", "commit", "-m", "[ComplianceLint] Evidence sync (pytest)",
    ])
    assert commit.returncode == 0, f"git commit failed: {commit.stderr!r}"
    push = run_in_project(["git", "push", "origin"])
    assert push.returncode == 0, f"git push failed: {push.stderr!r}"
    sha = run_in_project(
        ["git", "log", "-1", "--pretty=format:%H"]
    ).stdout.strip()

    pending_pre = db_query(
        "SELECT COUNT(*) FROM pending_evidence WHERE repo_id = ?", (repo_id,),
    )
    assert pending_pre[0][0] == 1, \
        "pending row still exists post-commit, pre-sync (SaaS not yet notified)"

    summary3, _, _ = call_pull()
    assert summary3.get("confirmed") == 1, \
        f"sync-confirm: confirmed=1 expected, got {summary3!r}"
    assert summary3.get("pulled") == 0, \
        f"sync-confirm: pulled=0 expected (nothing new), got {summary3!r}"

    rows = db_query("""
        SELECT ei.commit_status, ei.committed_at_sha
          FROM evidence_items ei
          JOIN finding_responses fr ON fr.id = ei.finding_response_id
         WHERE fr.finding_id = ?
    """, (finding_id,))
    assert len(rows) > 0, "evidence_items row exists after commit"
    assert rows[0][0] == "committed", \
        f"DB commit_status = committed, got {rows[0][0]!r}"
    assert rows[0][1] == sha, \
        f"DB committed_at_sha = {rows[0][1]!r} should match local git {sha!r}"

    pending_post = db_query(
        "SELECT COUNT(*) FROM pending_evidence WHERE evidence_item_id IN "
        "(SELECT ei.id FROM evidence_items ei JOIN finding_responses fr "
        " ON fr.id = ei.finding_response_id WHERE fr.finding_id = ?)",
        (finding_id,),
    )
    assert pending_post[0][0] == 0, \
        "pending_evidence row deleted after sync-confirm"

    audit = db_query("""
        SELECT action FROM audit_logs
         WHERE action = 'evidence_sync_confirm'
           AND resource LIKE 'evidence_items/%'
         ORDER BY created_at DESC LIMIT 1
    """)
    assert len(audit) > 0 and audit[0][0] == "evidence_sync_confirm", \
        f"audit log row written for sync-confirm, got {audit!r}"


def test_conflict_different_hash(
    discovered, cleanup_pending, reset_working_tree, curl_upload, call_pull,
    sha256_file_fn,
):
    """§4.5 target exists with different hash → write to .conflict-{ts}.

    Hard rule: original local file MUST be preserved bit-identical;
    incoming file MUST land at a sibling path with conflict marker.
    """
    finding_id = discovered["finding_id"]

    cleanup_pending()
    reset_working_tree()

    upload_file = os.path.join(PROJECT, "conflict-fixture.txt")
    with open(upload_file, "w") as f:
        f.write("INCOMING content — server version.\n")
    seed = curl_upload(finding_id, upload_file)

    target_rel = seed["repo_path"]
    target_abs = os.path.join(PROJECT, target_rel)
    os.makedirs(os.path.dirname(target_abs), exist_ok=True)
    with open(target_abs, "w") as f:
        f.write("LOCAL content — user had a different file.\n")
    local_hash = sha256_file_fn(target_abs)

    summary, prompt, _ = call_pull()
    assert summary.get("conflicts") == 1, \
        f"conflicts=1 expected, got {summary!r}"
    assert summary.get("pulled") == 0, \
        f"pulled=0 expected (no overwrite), got {summary!r}"

    assert sha256_file_fn(target_abs) == local_hash, \
        "original local file preserved bit-identical (hard rule #2)"

    conflict_paths = summary.get("conflict_paths", [])
    assert len(conflict_paths) == 1, \
        f"exactly one conflict path expected, got {conflict_paths!r}"
    conflict_abs = os.path.join(
        PROJECT, conflict_paths[0].replace("/", os.sep),
    )
    assert os.path.isfile(conflict_abs), "conflict file exists on disk"
    assert "conflict-" in conflict_paths[0], \
        f"conflict filename has timestamp marker, got {conflict_paths[0]!r}"
    assert sha256_file_fn(conflict_abs) == seed["content_sha256"], \
        "conflict file matches incoming server sha"
    assert "different content" in prompt, \
        f"prompt flags conflict, got {prompt!r}"


def test_no_matching_repo(server_module, log):
    """Repo name that does not exist on SaaS → skip with clear message,
    rid empty, reason recorded. Does not need `discovered` — the whole
    point of this test is to use an intentionally-bad repo_name."""
    cfg_path = os.path.join(PROJECT, ".compliancelintrc")
    with open(cfg_path) as f:
        original = f.read()
    try:
        with open(cfg_path, "w") as f:
            f.write(original.replace(REPO_NAME, "nonexistent/fake-repo"))
        meta = os.path.join(PROJECT, ".compliancelint", "local", "metadata.json")
        if os.path.isfile(meta):
            os.unlink(meta)

        summary, prompt, rid = server_module._run_pending_evidence_pull(
            project_path=PROJECT,
            saas_url=SAAS,
            api_key=API_KEY,
            repo_name="nonexistent/fake-repo",
            slog=log,
        )
        assert summary.get("skipped") is True, \
            f"skipped=True expected, got {summary!r}"
        assert summary.get("reason") == "no_matching_repo", \
            f"reason=no_matching_repo expected, got {summary!r}"
        assert rid == "", f"rid should be empty, got {rid!r}"
        assert "not found" in prompt, \
            f"prompt mentions 'not found', got {prompt!r}"
    finally:
        with open(cfg_path, "w") as f:
            f.write(original)


def test_stale_cache_invalidation(
    discovered, cleanup_pending, reset_working_tree, curl_upload, call_pull,
):
    """Stale metadata.json repo_id → 404 on list URL → cache invalidated
    → retry once with fresh list → succeeds. Cache ends up refreshed."""
    repo_id = discovered["repo_id"]
    finding_id = discovered["finding_id"]

    cleanup_pending()
    reset_working_tree()

    meta_dir = os.path.join(PROJECT, ".compliancelint", "local")
    os.makedirs(meta_dir, exist_ok=True)
    meta_path = os.path.join(meta_dir, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump({"repo_id": "bogus-repo-uuid-that-does-not-exist"}, f)

    upload_file = os.path.join(PROJECT, "stale-cache-fixture.txt")
    with open(upload_file, "w") as f:
        f.write("bytes for stale-cache invalidation test\n")
    curl_upload(finding_id, upload_file)

    summary, _, rid = call_pull()
    assert rid == repo_id, \
        f"rid re-resolved after invalidation, got {rid!r}"
    assert summary.get("pulled") == 1, \
        f"pulled=1 after invalidation, got {summary!r}"

    with open(meta_path) as f:
        cache = json.load(f)
    assert cache.get("repo_id") == repo_id, \
        f"metadata.json cache refreshed to correct rid, got {cache!r}"


def test_46_commit_without_push_blocks_sync_confirm(
    discovered, with_remote, cleanup_pending, reset_working_tree, curl_upload,
    call_pull, run_in_project, db_query,
):
    """§4.6 — Problem 1 / sha-on-remote audit-correctness fix.

    User pulls evidence + commits locally but does NOT push. cl_sync must
    NOT send sync-confirm (sha is local-only, not on remote → audit would
    record a sha that never existed remotely = false-committed). After
    `git push`, cl_sync must then fire sync-confirm normally.
    """
    finding_id = discovered["finding_id"]
    repo_id = discovered["repo_id"]

    cleanup_pending()
    reset_working_tree()

    upload_file = os.path.join(PROJECT, "fixture-46.txt")
    with open(upload_file, "w") as f:
        f.write("§4.6 fixture — commit-no-push then push\n")
    seed = curl_upload(finding_id, upload_file)
    summary, _, _ = call_pull()
    assert summary.get("pulled") == 1, f"initial pull, got {summary!r}"

    # ── Phase 1 — commit but DO NOT push ─────────────────────────────────
    run_in_project(["git", "add", ".compliancelint/evidence"])
    commit = run_in_project([
        "git", "commit", "-m", "[ComplianceLint] §4.6 local-only test",
    ])
    assert commit.returncode == 0, f"git commit failed: {commit.stderr!r}"

    summary2, _, _ = call_pull()
    assert summary2.get("confirmed", 0) == 0, (
        "§4.6: sync-confirm must NOT fire for unpushed commits. "
        f"Got {summary2!r} — local-only sha would write false committed_at_sha to DB."
    )

    rows = db_query(
        "SELECT commit_status, committed_at_sha FROM evidence_items WHERE id = ?",
        (seed["evidence_item_id"],),
    )
    assert rows[0][0] == "pending_commit", (
        f"§4.6: DB commit_status must remain pending_commit pre-push, got {rows!r}"
    )
    assert rows[0][1] is None, (
        f"§4.6: committed_at_sha must remain NULL pre-push, got {rows!r}"
    )

    pending_pre = db_query(
        "SELECT COUNT(*) FROM pending_evidence WHERE repo_id = ?", (repo_id,),
    )
    assert pending_pre[0][0] == 1, (
        "§4.6: pending_evidence row must still exist pre-push (not yet committed-and-pushed)"
    )

    # ── Phase 2 — push, sync-confirm fires normally ──────────────────────
    push = run_in_project(["git", "push", "origin"])
    assert push.returncode == 0, f"git push failed: {push.stderr!r}"
    sha = run_in_project(
        ["git", "log", "-1", "--pretty=format:%H"]
    ).stdout.strip()

    summary3, _, _ = call_pull()
    assert summary3.get("confirmed") == 1, (
        f"after push: sync-confirm must fire, got {summary3!r}"
    )

    rows_post = db_query(
        "SELECT commit_status, committed_at_sha FROM evidence_items WHERE id = ?",
        (seed["evidence_item_id"],),
    )
    assert rows_post[0][0] == "committed", (
        f"after push: DB commit_status must be 'committed', got {rows_post!r}"
    )
    assert rows_post[0][1] == sha, (
        f"after push: committed_at_sha must equal local git sha {sha!r}, got {rows_post!r}"
    )


def test_12_13_fingerprint_round_trip_surfaces_warning_in_result_payload(
    discovered, db_query, server_module,
):
    """§1.2/§1.3 cross-layer round-trip — Problem 2 part B silent-drop guard.

    Unit tests cover `_format_fingerprint_warning` with synthetic input. But
    only a real HTTP round-trip proves the dashboard actually returns the
    shape the scanner's parser expects. This test seeds a mismatched
    `repos.first_commit_sha`, sends a POST /scans with a different value,
    and verifies the full chain: dashboard compares + returns 200 with
    warnings[], parser extracts + formats, and audit log is written.

    Silent-drop scenarios this catches:
      - dashboard renames a warning field → parser's .get() returns None
      - dashboard moves `warnings` to a different response location
      - dashboard issues a different audit action string
      - response shape is wrong in a way unit tests cannot see
    """
    repo_id = discovered["repo_id"]
    bogus_first = "b" * 40
    reported_first = "c" * 40

    def _set_fingerprint(prev_sha, pending_sha):
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "UPDATE repos SET first_commit_sha = ?, "
                "fingerprint_pending_sha = ? WHERE id = ?",
                (prev_sha, pending_sha, repo_id),
            )
            conn.commit()
        finally:
            conn.close()

    # Seed mismatch state: DB has bogus sha, we'll report a different one.
    _set_fingerprint(bogus_first, None)

    try:
        # Match cl_sync's payload shape (scanner/server.py line 2109).
        # `articles: {}` is the minimum that passes the /scans validator
        # without creating a scan with findings (keeps DB noise low).
        payload = {
            "project_id": "git-e2e-fingerprint-rt",
            "repo": REPO_NAME,
            "scanned_at": "2026-04-21T00:00:00Z",
            "scanner_version": "test-fingerprint-rt",
            "regulation": "eu-ai-act",
            "ai_provider": None,
            "changes_summary": None,
            "articles": {},
            "responses": [],
            "commit_sha": "a" * 40,
            "first_commit_sha": reported_first,
        }
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        r = subprocess.run(
            [
                "curl", "-sS", "--max-time", "20",
                "-X", "POST", f"{SAAS}/api/v1/scans",
                "-H", "Content-Type: application/json; charset=utf-8",
                "-H", f"Authorization: Bearer {API_KEY}",
                "--data-binary", "@-",
                "-w", "\n%{http_code}",
            ],
            input=body, capture_output=True, timeout=25,
        )
        raw = r.stdout.decode("utf-8", errors="replace")
        parts = raw.strip().rsplit("\n", 1)
        body_str = parts[0] if len(parts) > 1 else ""
        http_code = int(parts[-1]) if parts[-1].isdigit() else 0

        # POST /scans returns 201 Created (RESTful resource creation). The
        # fingerprint check is ADVISORY — mismatch must not return 4xx/5xx.
        # cl_sync production code accepts anything < 400 (server.py:2185).
        assert http_code in (200, 201), (
            f"POST /scans fingerprint mismatch MUST be advisory (200/201), "
            f"not block — got {http_code}: body={body_str[:300]!r}"
        )

        resp = json.loads(body_str)
        warnings = resp.get("warnings")
        assert isinstance(warnings, list), (
            f"scan response must have top-level warnings list for mismatch, "
            f"got keys: {list(resp.keys()) if isinstance(resp, dict) else type(resp).__name__}"
        )
        assert len(warnings) >= 1, (
            f"mismatch must produce at least one warning entry, got {warnings!r}"
        )

        fp = next(
            (w for w in warnings
             if isinstance(w, dict) and w.get("type") == "fingerprint_changed"),
            None,
        )
        assert fp is not None, (
            f"expected warnings[] entry with type='fingerprint_changed'; "
            f"got types: "
            f"{[w.get('type') for w in warnings if isinstance(w, dict)]}"
        )
        # Silent-drop guard: parser reads these exact field names. If dashboard
        # renamed (e.g., to prev_sha / new_sha), parser returns None silently.
        assert fp.get("previous_first_commit_sha") == bogus_first, (
            f"previous_first_commit_sha: expected DB value {bogus_first!r}, "
            f"got {fp!r}"
        )
        assert fp.get("current_first_commit_sha") == reported_first, (
            f"current_first_commit_sha: expected reported value "
            f"{reported_first!r}, got {fp!r}"
        )

        # Pass the REAL response through the scanner's parser. This is the
        # assertion that catches shape drift between the two layers.
        msg = server_module._format_fingerprint_warning(warnings, SAAS, repo_id)
        assert msg is not None, (
            "Parser returned None on real dashboard response — this is the "
            "exact silent-drop the test was added to catch. Either the "
            "dashboard renamed a field or the parser is reading the wrong one."
        )
        assert "Fingerprint changed" in msg
        assert bogus_first[:12] in msg, \
            f"message must include previous sha, got:\n{msg}"
        assert reported_first[:12] in msg, \
            f"message must include current sha, got:\n{msg}"
        assert f"dashboard/repos/{repo_id}" in msg, \
            f"message must include acknowledge URL with repo_id, got:\n{msg}"

        # Audit log — proves dashboard committed the comparison to DB.
        # Tiny delay accommodates async write commit. Scope by resource so
        # parallel test runs / residual rows from other repos don't pollute
        # the assertion (defense-in-depth per cross-review 2026-04-21).
        time.sleep(0.2)
        audit = db_query(
            "SELECT action FROM audit_logs "
            "WHERE action = 'repo_fingerprint_change' "
            "AND resource = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (f"repos/{repo_id}",),
        )
        assert len(audit) == 1 and audit[0][0] == "repo_fingerprint_change", (
            f"audit_logs must have repo_fingerprint_change row scoped to "
            f"resource='repos/{repo_id}' after mismatch POST; got {audit!r}"
        )
    finally:
        # Restore clean state so subsequent runs don't inherit the mismatch.
        _set_fingerprint(None, None)
