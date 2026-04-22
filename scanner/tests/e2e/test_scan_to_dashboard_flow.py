"""Cross-system flow: synthetic cl_scan output → cl_sync → dashboard DB.

Workflow 1 from private/docs/memory/project_cross_system_test_design.md:
  "MCP cl_scan → cl_sync → SaaS Findings page shows new findings"

Why synthetic scan (not real cl_scan): cl_scan invokes an AI provider
(Claude API), which is non-deterministic and costs money per run. We
write a deterministic article JSON directly to .compliancelint/articles/
— the same file shape cl_scan writes — and then exercise the real
cl_sync → HTTP → dashboard DB path end-to-end.

What this tests (MCP + SaaS + git):
  - cl_sync reads state.json from project_path
  - cl_sync derives head_commit_sha + first_commit_sha from git (real
    subprocess calls into the test project's .git dir)
  - cl_sync POSTs JSON to /api/v1/scans (real HTTP to localhost:3000)
  - Dashboard writes a scan row + findings rows + audit log (real DB)
  - /api/v1/repos/{id}/scans/{scan_id} returns those findings (real HTTP)
  - repos.first_commit_sha moves from NULL → derived first commit sha

Skips if live dashboard or test project dir missing (conftest._live_env_check).
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import uuid
from pathlib import Path

import pytest

from _e2e_consts import API_KEY, DB_PATH, PROJECT, REPO_NAME, SAAS

pytestmark = pytest.mark.live_dashboard


def _write_synthetic_art9(project_path: str, scan_findings: list[dict]) -> None:
    """Write .compliancelint/articles/art9.json in the exact shape that
    save_article_result emits, skipping the derogation + evidence-preserve
    logic (we seed a fresh article file per test)."""
    art_dir = os.path.join(project_path, ".compliancelint", "articles")
    Path(art_dir).mkdir(parents=True, exist_ok=True)

    findings_dict: dict[str, dict] = {}
    for f in scan_findings:
        oid = f["obligation_id"]
        findings_dict[oid] = {
            "obligation_id": oid,
            "level": f["level"],
            "description": f["description"],
            "source_quote": f.get("source_quote", ""),
            "status": "open",
            "history": [],
            "evidence": [],
        }

    article_payload = {
        "article": 9,
        "last_scan": "2026-04-22T12:00:00+00:00",
        "findings": findings_dict,
        "regulation": "eu-ai-act",
    }
    art_path = os.path.join(art_dir, "art9.json")
    with open(art_path, "w", encoding="utf-8") as fh:
        json.dump(article_payload, fh, indent=2)


def _reset_article_files(project_path: str) -> None:
    art_dir = os.path.join(project_path, ".compliancelint", "articles")
    if os.path.isdir(art_dir):
        for name in os.listdir(art_dir):
            if name.endswith(".json"):
                os.unlink(os.path.join(art_dir, name))


def _delete_specific_scan(scan_id: str) -> None:
    """Targeted cleanup: only remove the scan this test created.

    Session-scoped fixture `discovered` needs at least one seed-demo scan
    to remain on the repo — a blanket delete by repo_id would break
    subsequent tests in the same session.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM findings WHERE scan_id = ?", (scan_id,))
        conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
        conn.commit()
    finally:
        conn.close()


def _reset_fingerprint(repo_id: str) -> None:
    """Clear fingerprint + project_id so synthetic sync observes a fresh baseline.

    Also resets project_id → NULL because cl_sync POSTs the test project's
    project_id ("git-e2e-sub3b-fixture"), and the scans route binds it onto
    the repo row. Without resetting, test_sub3b's later test_12_13 rejects
    the match-by-name step (different project_id) and creates a suffixed
    repo, which invalidates its fingerprint-mismatch precondition.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE repos SET first_commit_sha = NULL, "
            "fingerprint_pending_sha = NULL, project_id = NULL "
            "WHERE id = ?",
            (repo_id,),
        )
        conn.commit()
    finally:
        conn.close()


def _curl_json(method: str, url: str) -> dict | list:
    r = subprocess.run(
        [
            "curl",
            "-sS",
            "-X",
            method,
            url,
            "-H",
            f"Authorization: Bearer {API_KEY}",
            "--max-time",
            "15",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert r.returncode == 0, f"curl failed: {r.stderr[:200]!r}"
    return json.loads(r.stdout.strip())


def test_cl_sync_pushes_synthetic_scan_to_dashboard_end_to_end(
    server_module, log, discovered, with_remote
):
    """Synthetic art9 scan → cl_sync → /api/v1/scans → DB rows + GET visible."""
    repo_id = discovered["repo_id"]
    _reset_fingerprint(repo_id)
    _reset_article_files(PROJECT)

    # Seed two art9 findings — one NC, one compliant — with unique obligation
    # ids so we can assert exactly-these-two landed on the dashboard.
    marker = uuid.uuid4().hex[:8]
    synthetic = [
        {
            "obligation_id": f"ART09-TEST-NC-{marker}",
            "level": "non_compliant",
            "description": f"Synthetic NC finding {marker} for cross-system flow test",
            "source_quote": "verbatim EUR-Lex quote stub",
        },
        {
            "obligation_id": f"ART09-TEST-OK-{marker}",
            "level": "compliant",
            "description": f"Synthetic COMPLIANT finding {marker}",
            "source_quote": "verbatim EUR-Lex quote stub",
        },
    ]
    _write_synthetic_art9(PROJECT, synthetic)

    # Derive what cl_sync will derive so we can assert equality in the DB.
    expected_head = server_module._derive_head_commit_sha(PROJECT)
    expected_first = server_module._derive_first_commit_sha(PROJECT)
    assert expected_head, "precondition: PROJECT must be a git repo with commits"
    assert expected_first, "precondition: PROJECT must be a git repo with at least one commit"

    # Real call through MCP layer — subprocess-based HTTP to localhost:3000.
    result_str = server_module.cl_sync(PROJECT, regulation="")
    result = json.loads(result_str)
    log.info("cl_sync result: %s", result)
    assert "error" not in result, f"cl_sync surfaced error: {result}"
    # Sync response carries scan_id used by /scans/{id} route.
    dashboard_scan_id = result.get("scan_id") or result.get("scanId")
    assert dashboard_scan_id, (
        f"cl_sync response missing scan_id field: {result}"
    )

    # DB assertions — scan row + findings rows written with the derived shas.
    conn = sqlite3.connect(DB_PATH)
    try:
        scan_row = conn.execute(
            "SELECT id, repo_id FROM scans WHERE id = ?",
            (dashboard_scan_id,),
        ).fetchone()
        assert scan_row is not None, (
            f"cl_sync returned scan_id {dashboard_scan_id} but no row in scans table"
        )
        assert scan_row[1] == repo_id, (
            f"scan repo_id mismatch: {scan_row[1]} != {repo_id}"
        )

        repo_row = conn.execute(
            "SELECT first_commit_sha FROM repos WHERE id = ?", (repo_id,)
        ).fetchone()
        assert repo_row is not None
        assert repo_row[0] == expected_first, (
            f"repos.first_commit_sha not derived from git root: {repo_row[0]} != {expected_first}"
        )

        # Each finding gets its last_scan_commit_sha stamped from payload.commit_sha
        # (findings.last_scan_commit_sha column — Track 4a stale-detection anchor).
        finding_rows = conn.execute(
            "SELECT obligation_id, status, last_scan_commit_sha FROM findings "
            "WHERE scan_id = ? AND obligation_id LIKE ?",
            (dashboard_scan_id, f"ART09-TEST-%-{marker}"),
        ).fetchall()
        # Synthetic seeded exactly two with this marker; both must land.
        assert len(finding_rows) == 2, (
            f"expected 2 synthetic findings in DB, got {len(finding_rows)}: {finding_rows}"
        )
        oids = {r[0] for r in finding_rows}
        assert oids == {
            f"ART09-TEST-NC-{marker}",
            f"ART09-TEST-OK-{marker}",
        }
        # Git HEAD sha landed on each finding as the stale-detection anchor.
        shas = {r[2] for r in finding_rows}
        assert shas == {expected_head}, (
            f"findings.last_scan_commit_sha not derived from git HEAD: {shas} != {{{expected_head}}}"
        )

        # Audit row for the fingerprint-set action (first_commit_sha was NULL
        # before this sync — _delete_scans_for_repo reset it).
        fp_set_count = conn.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE resource = ? AND action = ?",
            (f"repos/{repo_id}", "repo_fingerprint_set"),
        ).fetchone()[0]
        assert fp_set_count >= 1, (
            "cl_sync did not write a repo_fingerprint_set audit on fresh baseline"
        )
    finally:
        conn.close()

    # Browser-path assertion: GET /api/v1/repos/{id}/scans/{scan_id} returns
    # the findings. This catches regression in the shape the dashboard UI
    # consumes, not just the raw DB row.
    scan_detail = _curl_json(
        "GET", f"{SAAS}/api/v1/repos/{repo_id}/scans/{dashboard_scan_id}"
    )
    assert isinstance(scan_detail, dict)
    findings = scan_detail.get("findings") or []
    marked = [f for f in findings if marker in (f.get("obligationId") or "")]
    assert len(marked) == 2, (
        f"GET /scans/{dashboard_scan_id} returned {len(marked)} synthetic findings "
        f"(expected 2). Full list: {[f.get('obligationId') for f in findings]}"
    )

    # Cleanup: delete the synthetic scan + findings we seeded; leave other
    # scans alone (session-scoped `discovered` fixture still needs them).
    # Also clear the fingerprint so the next test starts on a fresh baseline.
    _delete_specific_scan(dashboard_scan_id)
    _reset_fingerprint(repo_id)


def test_second_cl_sync_with_different_first_commit_sha_parks_pending(
    server_module, log, discovered, with_remote
):
    """Simulate a force-push-to-root scenario across TWO cl_sync calls.

    After the first sync records first_commit_sha, mutating the DB baseline
    to a different value (as if a force-push to root happened between
    syncs) should cause the second cl_sync to see a mismatch — baseline
    stays, fingerprint_pending_sha gets the incoming value, and an audit
    row records the change. This mirrors the §1.3 parallel-session
    round-trip test but exercises it from the PUSH side.
    """
    repo_id = discovered["repo_id"]
    _reset_fingerprint(repo_id)
    _reset_article_files(PROJECT)

    marker = uuid.uuid4().hex[:8]
    _write_synthetic_art9(
        PROJECT,
        [
            {
                "obligation_id": f"ART09-FP-{marker}",
                "level": "compliant",
                "description": f"fp-flow {marker}",
                "source_quote": "stub",
            }
        ],
    )
    # First sync records baseline.
    r1 = json.loads(server_module.cl_sync(PROJECT, regulation=""))
    assert "error" not in r1, r1
    log.info("first sync ok: %s", r1)
    first_scan_id = r1.get("scan_id") or r1.get("scanId")

    # Verify baseline recorded.
    conn = sqlite3.connect(DB_PATH)
    try:
        baseline_after_first = conn.execute(
            "SELECT first_commit_sha FROM repos WHERE id = ?", (repo_id,)
        ).fetchone()[0]
        assert baseline_after_first == server_module._derive_first_commit_sha(PROJECT)

        # Simulate divergence — mutate baseline to a different 40-hex value.
        # This is what a real force-push-to-root on the remote would make
        # the NEXT cl_sync observe: scanner reports current first_commit_sha,
        # dashboard compares against the stored (now different) baseline.
        rogue = "b" * 40
        conn.execute(
            "UPDATE repos SET first_commit_sha = ? WHERE id = ?",
            (rogue, repo_id),
        )
        conn.commit()
    finally:
        conn.close()

    # Second sync — should park the real first_commit_sha as pending,
    # NOT overwrite the (divergent) baseline.
    r2 = json.loads(server_module.cl_sync(PROJECT, regulation=""))
    assert "error" not in r2, r2
    second_scan_id = r2.get("scan_id") or r2.get("scanId")

    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT first_commit_sha, fingerprint_pending_sha FROM repos WHERE id = ?",
            (repo_id,),
        ).fetchone()
        # Baseline MUST stay at the rogue value (no auto-update, advisory only).
        assert row[0] == "b" * 40, (
            f"baseline was auto-updated on mismatch — baseline={row[0]}"
        )
        # Pending MUST be the scanner-derived first_commit_sha.
        assert row[1] == server_module._derive_first_commit_sha(PROJECT), (
            f"pending_sha={row[1]} is not the scanner-derived first_commit_sha"
        )

        # A repo_fingerprint_change audit row was written.
        change_count = conn.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE resource = ? AND action = ?",
            (f"repos/{repo_id}", "repo_fingerprint_change"),
        ).fetchone()[0]
        assert change_count >= 1, (
            "second cl_sync didn't write repo_fingerprint_change audit on mismatch"
        )
    finally:
        conn.close()

    # Cleanup: remove both scans we created; leave seed-demo scans intact.
    if first_scan_id:
        _delete_specific_scan(first_scan_id)
    if second_scan_id:
        _delete_specific_scan(second_scan_id)
    _reset_fingerprint(repo_id)
