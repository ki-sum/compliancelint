"""Cross-system flow: SaaS evidence upload → cl_sync pull/commit/confirm.

Workflow 2 from private/docs/memory/project_cross_system_test_design.md:
  "SaaS Human Gates questionnaire filled → MCP re-scan picks up evidence
   → status updates"

The canonical evidence-upload path is POST
  /api/v1/findings/{id}/evidence/upload-file
(see respond/route.ts line 131 docstring: "repo_file → upload-file").
This test exercises that endpoint end-to-end through the MCP pull +
commit + sync-confirm lifecycle.

What this tests (MCP + SaaS + git):
  - POST /evidence/upload-file writes finding_responses (action=
    provide_evidence) + evidence_items rows (dashboard contract)
  - pending_evidence row is queued for delivery to the project working tree
  - cl_sync's _run_pending_evidence_pull moves the evidence to .compliancelint/
    evidence/ in the project AND writes a metadata.json entry (real git
    worktree writes, subprocess)
  - sync-confirm lands the committed_at_sha back in the DB
  - evidence_items.commit_status transitions pending_commit → committed
  - evidence_items.committed_at_sha matches the git HEAD after commit

The end-to-end contract: dashboard evidence + local git commit + cl_sync
must converge on `committed` status with the right sha. A regression in
any layer (upload-file route, pending_evidence queue, scanner pull,
sync-confirm) breaks one of these assertions.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import tempfile
import uuid

import pytest

from _e2e_consts import API_KEY, DB_PATH, PROJECT, REPO_NAME, SAAS

pytestmark = pytest.mark.live_dashboard


def _fingerprint_reset(repo_id: str) -> None:
    # See test_scan_to_dashboard_flow note: also clear project_id so a
    # later test (e.g. test_sub3b) that uses a different project_id isn't
    # forced onto a suffixed repo by findRepoForCaller.
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE repos SET fingerprint_pending_sha = NULL, project_id = NULL "
            "WHERE id = ?",
            (repo_id,),
        )
        conn.commit()
    finally:
        conn.close()


def _upload_file_evidence(
    finding_id: str, file_path: str
) -> dict:
    """POST /api/v1/findings/{id}/evidence/upload-file multipart.

    Mirrors conftest.curl_upload but returns raw JSON for local assertion.
    """
    r = subprocess.run(
        [
            "curl",
            "-sS",
            "-X",
            "POST",
            f"{SAAS}/api/v1/findings/{finding_id}/evidence/upload-file",
            "-H",
            f"Authorization: Bearer {API_KEY}",
            "-F",
            f"file=@{file_path}",
            "--max-time",
            "30",
        ],
        capture_output=True,
        text=True,
        timeout=40,
    )
    assert r.returncode == 0, f"curl upload-file failed: {r.stderr[:200]!r}"
    if not r.stdout.strip():
        raise AssertionError(
            f"upload-file returned empty stdout; stderr={r.stderr[:200]!r}"
        )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise AssertionError(
            f"upload-file did not return JSON: stdout={r.stdout[:500]!r}"
        )


def _get_evidence_rows(finding_id: str) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT ei.id, ei.commit_status, ei.committed_at_sha,
                   ei.health_status, ei.storage_kind, ei.evidence_name,
                   ei.source
            FROM evidence_items ei
            JOIN finding_responses fr ON fr.id = ei.finding_response_id
            WHERE fr.finding_id = ?
            ORDER BY ei.uploaded_at DESC
            """,
            (finding_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _delete_evidence_for_finding(finding_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        eids = [
            r[0]
            for r in conn.execute(
                "SELECT ei.id FROM evidence_items ei "
                "JOIN finding_responses fr ON fr.id = ei.finding_response_id "
                "WHERE fr.finding_id = ?",
                (finding_id,),
            ).fetchall()
        ]
        if eids:
            ph = ",".join("?" * len(eids))
            conn.execute(
                f"DELETE FROM pending_evidence WHERE evidence_item_id IN ({ph})",
                eids,
            )
            conn.execute(
                f"DELETE FROM evidence_items WHERE id IN ({ph})", eids
            )
        conn.execute(
            "DELETE FROM finding_responses WHERE finding_id = ?",
            (finding_id,),
        )
        conn.commit()
    finally:
        conn.close()


def test_dashboard_evidence_roundtrips_via_cl_sync_pull_confirm_to_committed(
    server_module,
    discovered,
    reset_working_tree,
    call_pull,
    with_remote,
    log,
    run_in_project,
):
    """End-to-end: POST /respond → pending_evidence → cl_sync pull → commit → confirm.

    Each layer is a real subprocess or HTTP call; no mocks. The DB transition
    pending_commit → committed is the critical cross-system assertion.
    """
    finding_id = discovered["finding_id"]
    repo_id = discovered["repo_id"]

    # Clean state: purge any prior evidence on this finding, reset git
    # working tree to root commit, clear fingerprint pending.
    _delete_evidence_for_finding(finding_id)
    reset_working_tree()
    _fingerprint_reset(repo_id)

    marker = uuid.uuid4().hex[:8]
    evidence_value = f"Risk assessed via automated vuln scan run-{marker}\n"
    evidence_name = f"art09-risk-assessment-{marker}.txt"

    # 1. Dashboard contract: POST /upload-file writes finding_response +
    #    evidence_items. Write a temp file and upload it as multipart form.
    with tempfile.TemporaryDirectory() as td:
        src_path = os.path.join(td, evidence_name)
        with open(src_path, "w", encoding="utf-8") as fh:
            fh.write(evidence_value)
        upload_result = _upload_file_evidence(finding_id, src_path)
    log.info("POST /evidence/upload-file result: %s", upload_result)

    rows = _get_evidence_rows(finding_id)
    assert len(rows) == 1, (
        f"expected exactly 1 evidence row after upload-file, got {len(rows)}: {rows}"
    )
    initial = rows[0]
    assert initial["commit_status"] == "pending_commit", (
        f"new evidence should start pending_commit, got {initial['commit_status']}"
    )
    assert initial["committed_at_sha"] is None, (
        f"new evidence should have no committed_at_sha yet, got {initial['committed_at_sha']}"
    )
    evidence_item_id = initial["id"]

    # 2. cl_sync pull — writes evidence file to working tree + metadata.json.
    #    Uses the test project's real git remote (with_remote fixture).
    #    call_pull returns tuple[summary_dict, human_prompt, repo_id].
    pull_summary, _prompt, _rid = call_pull()
    log.info("cl_sync pull result: %s", pull_summary)
    assert pull_summary.get("pulled", 0) >= 1, (
        f"cl_sync pull returned {pull_summary.get('pulled')} items (expected ≥1): {pull_summary}"
    )

    # Evidence landed on disk. Pull orchestrator nests files under
    # .compliancelint/evidence/{finding_id}/{evidence_name} (see
    # pending_evidence.py — per-finding directory isolates collisions).
    ev_dir = os.path.join(PROJECT, ".compliancelint", "evidence")
    assert os.path.isdir(ev_dir), (
        f"cl_sync should have created {ev_dir}"
    )
    landed = []
    for root, _dirs, files in os.walk(ev_dir):
        for name in files:
            if marker in name and name.endswith(".txt"):
                landed.append(os.path.join(root, name))
    assert len(landed) == 1, (
        f"expected 1 pulled file with marker {marker}, got: {landed}"
    )
    landed_path = landed[0]
    with open(landed_path, "r", encoding="utf-8") as fh:
        content = fh.read()
    assert content == evidence_value, (
        f"pulled file content != uploaded value; got {content!r}"
    )

    # 3. PM commits (real git — this is the cross-system "user commits" step).
    r_add = run_in_project(["git", "add", ".compliancelint"])
    assert r_add.returncode == 0, f"git add failed: {r_add.stderr[:200]!r}"
    r_commit = run_in_project(
        [
            "git",
            "-c",
            "user.name=Cross-System Test",
            "-c",
            "user.email=xst@compliancelint.dev",
            "commit",
            "-m",
            f"evidence: add {evidence_name}",
        ],
    )
    assert r_commit.returncode == 0, f"git commit failed: {r_commit.stderr[:200]!r}"
    r_push = run_in_project(["git", "push", "origin", "HEAD"])
    assert r_push.returncode == 0, f"git push failed: {r_push.stderr[:200]!r}"
    committed_sha = run_in_project(
        ["git", "rev-parse", "HEAD"]
    ).stdout.strip()
    assert len(committed_sha) == 40, f"HEAD sha shape wrong: {committed_sha!r}"

    # 4. cl_sync confirm path — the NEXT pull sends sync-confirm that
    #    transitions the DB row pending_commit → committed with the sha.
    pull_summary_2, _p2, _r2 = call_pull()
    log.info("cl_sync pull (confirm phase) result: %s", pull_summary_2)
    # Confirmations counter lives under "confirmed" in the pull result.
    assert pull_summary_2.get("confirmed", 0) >= 1, (
        f"expected ≥1 sync-confirm on second pull, got {pull_summary_2}"
    )

    # 5. DB transitioned to committed + sha stamped.
    rows_after = _get_evidence_rows(finding_id)
    matching = [r for r in rows_after if r["id"] == evidence_item_id]
    assert len(matching) == 1, (
        f"evidence row disappeared after sync-confirm: {rows_after}"
    )
    final = matching[0]
    assert final["commit_status"] == "committed", (
        f"commit_status did NOT transition to committed — got {final['commit_status']}"
    )
    assert final["committed_at_sha"] == committed_sha, (
        f"committed_at_sha != actual git HEAD: {final['committed_at_sha']} != {committed_sha}"
    )
    assert final["health_status"] == "ok", (
        f"health_status after commit must be 'ok', got {final['health_status']}"
    )

    # Cleanup: the row + file + git commit stay (tests are idempotent via
    # reset_working_tree + _delete_evidence_for_finding at test start).
    _delete_evidence_for_finding(finding_id)
    reset_working_tree()
