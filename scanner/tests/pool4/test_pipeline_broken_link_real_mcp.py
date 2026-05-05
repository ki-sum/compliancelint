"""Pool 4 — pipeline-broken-link via real MCP transport.

The first Pool 4 cell that exercises the full broken_link cross-system
flow through real MCP subprocess. Existing coverage:
  - scanner/tests/test_broken_link.py — unit (no HTTP, no DB)
  - The internal scanner-tests e2e suite calls _run_broken_link_check()
    IN-PROCESS, bypassing the real MCP stdin/stdout transport
  - The internal dashboard Playwright v6-epochs broken_link-transition
    spec is a UI test, seeds DB directly via INSERT, doesn't go through
    cl_sync at all

What this cell adds (audit-first, 3-layer real):
  - Layer 1: real MCP subprocess invokes cl_sync via JSON-RPC over stdio
  - Layer 2: cl_sync's STEP 11c automatically runs broken_link sweep
    against the dashboard (real curl GET evidence rows + POST status
    transitions)
  - Layer 3: dashboard's DB write — evidence_items.health_status flips
    from 'ok' to 'broken_link' when the file disappears from the working
    tree between syncs

Setup pattern:
  1. tmp_path with a real file at controls/risk-assessment.md
  2. cl_sync first time → repo created + initial scan
  3. Pre-seed: find any finding the scan produced, INSERT a
     finding_response + evidence_items row pointing at the file with
     health_status='ok'. Mirrors what cl_update_finding(provide_evidence)
     would do via the dashboard UI; we INSERT directly to keep the
     test focused on the SWEEP behavior, not the upload flow (the
     upload flow is covered by other cells / the broader e2e suite).
  4. Delete the file from the working tree
  5. cl_sync second time → triggers STEP 11c sweep
  6. Query DB → assert health_status == 'broken_link' for that row
  7. Cleanup: purge_repo cascades all child rows; tmp_path auto-cleaned

Per Pool 4 hard constraints:
  - C1: real MCP subprocess (one client across the chain)
  - C2: live :3000 prod server
  - C3: real seeded test-business persona
  - C7: tmp_path Pattern B (no manual-fixture drift)
  - C8: purge_repo + tmp_path

Verified-via: scanner/server.py STEP 11c (_run_broken_link_check) +
scanner/core/broken_link.py (run_broken_link_check orchestrator) +
the SaaS POST /api/v1/repos/<id>/evidence-health route.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from .cell_loader import ToolCell
from .cleanup import CleanupError, purge_repo
from .dispatcher import invoke_tool
from .fixtures import PERSONAS
from .mcp_client import McpStdioClient, parse_first_json
from .saas_introspection import (
    DB_PATH_ENV,
    fetch_repo_by_name,
    open_readonly,
)


SAAS_URL = "http://localhost:3000"
EVIDENCE_REL_PATH = "controls/risk-assessment.md"


def _git_init(project_dir: Path) -> str:
    """Init a real git repo in `project_dir` with one initial commit so
    cl_sync can derive a head_commit_sha. Returns the initial sha.
    Pool 4 cells avoid faking git state — derive from a real repo so
    the broken_link sweep's checked_at_sha matches what cl_sync sends.
    """
    flags = {"cwd": str(project_dir), "capture_output": True, "text": True, "check": True}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags["creationflags"] = subprocess.CREATE_NO_WINDOW
    subprocess.run(["git", "init", "-q"], **flags)
    subprocess.run(["git", "config", "user.email", "pool4@test.invalid"], **flags)
    subprocess.run(["git", "config", "user.name", "Pool 4 Test"], **flags)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], **flags)
    # Initial commit so HEAD exists.
    (project_dir / ".gitignore").write_text(".compliancelint/\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], **flags)
    subprocess.run(
        ["git", "commit", "-q", "-m", "Pool 4 broken_link initial"],
        **flags,
    )
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(project_dir), capture_output=True, text=True, check=True,
    )
    return r.stdout.strip()


def _build_synthetic_context(client: McpStdioClient, project_path: Path) -> str:
    raw = client.call_tool(
        "cl_analyze_project", {"project_path": str(project_path)},
    )
    analyze = parse_first_json(raw)
    template = analyze.get("compliance_answers_template")
    if not template:
        raise RuntimeError("cl_analyze_project did not return template")
    answers = dict(template)
    answers["_scope"] = {
        **answers.get("_scope", {}),
        "risk_classification": "high-risk",
        "risk_classification_confidence": "high",
        "is_ai_system": True,
        "operator_role": ["provider"],
        "annex_iii_category": "annex_iii_pt5_essential_services",
        "is_annex_i_product": False,
        "uses_training_data": True,
        "is_gpai": False,
        "is_gpai_provider": False,
        "eu_established": True,
        "territorial_scope_applies": True,
        "is_open_source": False,
        "is_military_defense": False,
        "is_research_only": False,
        "is_biometric_system": False,
        "is_financial_institution": False,
        "is_distributor": False,
        "is_importer": False,
        "is_authorised_representative": False,
    }
    return json.dumps({
        "framework": "python",
        "stack": ["python"],
        "compliance_answers": answers,
    })


def _seed_evidence_row(
    *,
    db_path: str,
    repo_id: str,
    scan_id: str,
    repo_path: str,
    head_sha: str,
) -> tuple[str, str]:
    """Insert a finding + finding_response + evidence_items row pointing
    at `repo_path` with health_status='ok'. Returns (finding_id, evidence_id).

    We INSERT a fresh finding row (rather than reusing one of cl_sync's
    findings) to keep the test self-contained — the cl_sync's synthetic
    context may not produce a stable finding to attach to.
    """
    conn = sqlite3.connect(db_path)
    try:
        finding_id = str(uuid.uuid4())
        response_id = str(uuid.uuid4())
        evidence_id = str(uuid.uuid4())
        # Use a known OID; the schema doesn't FK obligation_id to a
        # registry, so any string works.
        conn.execute(
            """INSERT INTO findings
                 (id, scan_id, article, obligation_id, status,
                  title, evidence_summary)
               VALUES (?, ?, 'art9', 'ART09-OBL-1', 'compliant',
                       'Pool 4 broken_link seed finding',
                       'Synthetic evidence anchor for broken_link sweep cell')""",
            (finding_id, scan_id),
        )
        conn.execute(
            """INSERT INTO finding_responses
                 (id, finding_id, action, note, submitted_at, created_at)
               VALUES (?, ?, 'provide_evidence', 'pool4 broken_link seed',
                       strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                       strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))""",
            (response_id, finding_id),
        )
        # storage_kind='git_path' is REQUIRED — the broken_link sweep
        # filters by `storage_kind=git_path` (see scanner/core/broken_link.py
        # line 195: query = "storage_kind=git_path&limit=500"). Rows with
        # other storage_kinds (repo_file, text, url_reference) are NOT
        # checked by the sweep. The Playwright v6-epochs spec uses
        # 'repo_file' because it tests UI rendering of pre-seeded rows
        # without exercising the sweep itself.
        # commit_status='committed' + health_status='ok' is the starting
        # state — the sweep should flip health_status to 'broken_link'
        # after the file disappears.
        conn.execute(
            """INSERT INTO evidence_items
                 (id, finding_response_id, source, evidence_value,
                  evidence_name, dedup_hash, commit_status, storage_kind,
                  repo_path, committed_at_sha, health_status,
                  uploaded_at, created_at)
               VALUES (?, ?, 'dashboard', ?, 'risk-assessment.md',
                       ?, 'committed', 'git_path', ?, ?, 'ok',
                       strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                       strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))""",
            (
                evidence_id,
                response_id,
                repo_path,                  # evidence_value (display path)
                f"dedup-{evidence_id}",     # dedup_hash
                repo_path,                  # repo_path (sweep checks this)
                head_sha,                   # committed_at_sha
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return finding_id, evidence_id


def _read_health_status(db_path: str, evidence_id: str) -> str | None:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT health_status FROM evidence_items WHERE id = ?",
            (evidence_id,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_pipeline_broken_link_via_real_mcp(
    tmp_path: Path,
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end pipeline: real MCP cl_sync detects a missing evidence
    file via STEP 11c broken_link sweep and updates DB health_status."""
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    db_path = os.environ.get(DB_PATH_ENV)
    if not db_path:
        pytest.skip(f"{DB_PATH_ENV} not set")

    persona = PERSONAS["business"]
    suffix = str(int(time.time() * 1000) % 1_000_000_000)
    repo_name = f"test-business/pool4-broken-link-{suffix}"

    project_dir = tmp_path / "fixture"
    project_dir.mkdir()

    # Real evidence file in the working tree.
    evidence_full_path = project_dir / EVIDENCE_REL_PATH
    evidence_full_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_full_path.write_text(
        "# Risk Assessment\n\n(Pool 4 broken_link test artifact)\n",
        encoding="utf-8",
    )

    # Real git repo so cl_sync derives head_commit_sha properly.
    head_sha = _git_init(project_dir)
    # Stage + commit the evidence file so the sweep sees it as
    # committed at this sha.
    flags = {"cwd": str(project_dir), "capture_output": True, "text": True, "check": True}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags["creationflags"] = subprocess.CREATE_NO_WINDOW
    subprocess.run(["git", "add", EVIDENCE_REL_PATH], **flags)
    subprocess.run(
        ["git", "commit", "-q", "-m", "add risk-assessment evidence"], **flags,
    )
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"], **flags,
    )
    head_sha = r.stdout.strip()

    (project_dir / ".compliancelintrc").write_text(
        json.dumps({
            "purpose": "Pool 4 broken_link real-MCP fixture",
            "repo_name": repo_name,
            "saas_url": SAAS_URL,
            "saas_api_key": persona.api_key,
            "scope": {
                "operator_role": ["provider"],
                "risk_classification": "high-risk",
            },
            "attester_name": "Pool 4 Broken-Link Test",
            "attester_email": "pool4-broken-link@test.invalid",
        }, indent=2),
        encoding="utf-8",
    )

    repo_id_for_cleanup: str | None = None
    # IMPORTANT: do NOT pass cwd=project_dir here. MCP spawn() defaults
    # to REPO_ROOT so `python -m scanner.server` resolves to THIS repo's
    # editable scanner package. With cwd=project_dir, the subprocess
    # falls back to whatever scanner version is in site-packages (likely
    # an older pip-installed copy that lacks STEP 11c broken_link sweep).
    # cl_sync takes project_path as an arg; cwd doesn't need to match.
    client = McpStdioClient.spawn()
    try:
        # ── Step 1: cl_scan to produce a state.json then cl_sync to
        #    create the dashboard repo + scan rows. Use synthetic
        #    context so we don't need an AI provider.
        project_context_json = _build_synthetic_context(client, project_dir)
        scan_raw = client.call_tool("cl_scan", {
            "project_path": str(project_dir),
            "project_context": project_context_json,
            "articles": "9",
            "ai_provider": "Pool4 broken_link Synthetic",
        })
        scan_resp = parse_first_json(scan_raw)
        if "error" in scan_resp:
            pytest.skip(f"cl_scan rejected synthetic context: {scan_resp.get('error')}")

        sync1_raw = client.call_tool("cl_sync", {"project_path": str(project_dir)})
        sync1_resp = parse_first_json(sync1_raw)
        assert "error" not in sync1_resp, f"cl_sync 1 errored: {sync1_resp}"
        scan_id = sync1_resp.get("scan_id")
        assert scan_id, "cl_sync 1 returned no scan_id"

        # Resolve repo_id via DB lookup (sync1's response repo_id may not
        # be the dashboard's row id depending on transport; the lookup
        # by name is authoritative).
        with open_readonly() as conn:
            repo_row = fetch_repo_by_name(conn, repo_name)
            assert repo_row is not None, (
                f"DB has no repos row for {repo_name!r} after cl_sync 1"
            )
            repo_id_for_cleanup = repo_row["id"]

        # Resolve dashboard's actual scan_id (same as repo lookup).
        with open_readonly() as conn:
            scan_row = conn.execute(
                "SELECT id FROM scans WHERE repo_id = ? "
                "ORDER BY scanned_at DESC LIMIT 1",
                (repo_id_for_cleanup,),
            ).fetchone()
            assert scan_row is not None, "no scan row for the new repo"
            dashboard_scan_id = scan_row["id"]

        # ── Step 2: pre-seed an evidence_items row pointing at the
        #    real file (health_status='ok'). The sweep next sync should
        #    flip it to 'broken_link' after we delete the file.
        _, evidence_id = _seed_evidence_row(
            db_path=db_path,
            repo_id=repo_id_for_cleanup,
            scan_id=dashboard_scan_id,
            repo_path=EVIDENCE_REL_PATH,
            head_sha=head_sha,
        )

        # Sanity: pre-seed wrote 'ok'.
        assert _read_health_status(db_path, evidence_id) == "ok"

        # ── Step 3: delete the file from working tree. Sweep should
        #    detect this on next sync.
        evidence_full_path.unlink()
        assert not evidence_full_path.exists()

        # ── Step 4: cl_sync 2 — triggers STEP 11c broken_link sweep.
        sync2_raw = client.call_tool("cl_sync", {"project_path": str(project_dir)})
        sync2_resp = parse_first_json(sync2_raw)
        assert "error" not in sync2_resp, f"cl_sync 2 errored: {sync2_resp}"

        # The sweep summary should indicate the row was checked AND
        # transitioned. Field name per scanner/server.py STEP 11d log.
        broken_link_summary = sync2_resp.get("broken_link_check") or {}
        # Best-effort: if the summary is present, it should report at
        # least 1 checked. Even without a summary, the DB-level
        # assertion below is the load-bearing one.
        if broken_link_summary:
            assert broken_link_summary.get("checked", 0) >= 1, (
                f"sweep summary should report checked >= 1; got {broken_link_summary}"
            )
    finally:
        client.close()

    # ── Step 5: Layer 3 verification — DB health_status flipped.
    final_status = _read_health_status(db_path, evidence_id)
    assert final_status == "broken_link", (
        f"After file deletion + cl_sync, evidence_items.health_status "
        f"should be 'broken_link' but got {final_status!r}. The "
        f"broken_link sweep failed to detect the missing file OR the "
        f"POST /evidence-health round-trip didn't update the DB."
    )

    # ── Cleanup: purge cascades to evidence_items + finding_responses.
    if repo_id_for_cleanup is not None:
        try:
            purge_repo(
                SAAS_URL, persona.api_key, repo_id_for_cleanup,
                confirm_name=repo_name,
            )
        except CleanupError as e:
            pytest.fail(
                f"broken_link cleanup purge failed: {e}; orphan repo "
                f"id={repo_id_for_cleanup}"
            )
