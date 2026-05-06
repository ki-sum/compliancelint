"""Pool 4 — pipeline-broken-link force-push variant.

Sister cell to ``test_pipeline_broken_link_real_mcp.py`` (file-missing
variant). This cell exercises the second broken_link trigger introduced
2026-05-06: when ``git push --force`` rewrites history out from under a
previously-committed evidence row, the sweep must flip
``health_status`` from ``ok`` to ``broken_link`` even though the file
itself is still on disk.

Detection path under audit (post-implementation, not aspirational):

  1. ``GET /api/v1/repos/{id}/evidence?storage_kind=git_path`` now
     surfaces ``commit_status`` + ``committed_at_sha`` for every row.
  2. ``scanner/core/broken_link.py:build_reports`` calls the injected
     ``is_sha_orphaned`` hook for each row whose
     ``commit_status == "committed"`` and whose ``committed_at_sha`` is
     non-empty AND whose file is on disk.
  3. The hook (``pending_evidence.is_committed_orphaned``) returns True
     iff the repo has remote-tracking refs AND the sha is not reachable
     via ``git branch -r --contains <sha>``. Force-push rewrites all
     remote-tracking refs to the new tip; the orphaned sha is no longer
     reachable from any ``refs/remotes/<remote>/*`` ref.
  4. The report goes through the existing batch
     ``POST /evidence-health`` path; SaaS flips DB health_status.

Setup:
  1. tmp_path with bare git remote (same pattern as
     ``test_pipeline_evidence_commit_transition``).
  2. Initial commit + push. Add evidence file, commit, push at sha X.
  3. cl_sync 1 — creates dashboard repo + scan rows.
  4. Seed evidence_items row with ``committed_at_sha=X``,
     ``commit_status='committed'``, ``health_status='ok'``,
     ``storage_kind='git_path'``.
  5. cl_sync 2 — sweep runs; X is still on remote; row stays ``ok``
     (sanity check that the new orphan check has no false positives
     in the normal case).
  6. ``git reset --hard <initial>`` + ``git push --force`` to rewrite
     history. Sha X is now orphaned on remote.
  7. cl_sync 3 — sweep runs; ``is_committed_orphaned(project, X)``
     returns True; row flips to ``broken_link``.
  8. Verify DB: ``evidence_items.health_status == 'broken_link'``.

Per Pool 4 hard constraints:
  - C1: real MCP subprocess (default ``cwd=REPO_ROOT``)
  - C2: live :3000 prod server
  - C3: real seeded test-business persona
  - C7: tmp_path Pattern B (one tmp_path = working tree, sibling
    tmp_path = bare remote)
  - C8: ``purge_repo`` cleanup; ``tmp_path`` auto-cleaned

Verified-via: scanner/server.py STEP 11c (``_run_broken_link_check`` —
now passes ``is_committed_orphaned`` to the orchestrator) +
scanner/core/broken_link.py:build_reports (orphaned-commit branch) +
scanner/core/pending_evidence.py:is_committed_orphaned + the SaaS
``POST /api/v1/repos/<id>/evidence-health`` route.
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

from .cleanup import CleanupError, purge_repo
from .fixtures import PERSONAS
from .mcp_client import McpStdioClient, parse_first_json
from .saas_introspection import (
    DB_PATH_ENV,
    fetch_repo_by_name,
    open_readonly,
)


SAAS_URL = "http://localhost:3000"
EVIDENCE_REL_PATH = "controls/audit-trail.md"


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    flags = {
        "cwd": str(cwd),
        "capture_output": True,
        "text": True,
        "check": True,
    }
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(["git"] + args, **flags)


def _init_working_tree_with_remote(
    project_dir: Path, bare_remote: Path,
) -> str:
    """Same pattern as test_pipeline_evidence_commit_transition. Returns
    the initial HEAD sha (the sha we'll later reset back to during the
    force-push)."""
    bare_remote.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q", "--bare"], cwd=bare_remote)

    _git(["init", "-q", "-b", "main"], cwd=project_dir)
    _git(["config", "user.email", "pool4@test.invalid"], cwd=project_dir)
    _git(["config", "user.name", "Pool 4 Test"], cwd=project_dir)
    _git(["config", "commit.gpgsign", "false"], cwd=project_dir)

    (project_dir / ".gitignore").write_text(
        ".compliancelint/local/\n", encoding="utf-8",
    )
    _git(["add", ".gitignore"], cwd=project_dir)
    _git(["commit", "-q", "-m", "initial"], cwd=project_dir)

    _git(["remote", "add", "origin", str(bare_remote)], cwd=project_dir)
    _git(["push", "-q", "origin", "main"], cwd=project_dir)

    return _git(["rev-parse", "HEAD"], cwd=project_dir).stdout.strip()


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


def _seed_committed_evidence_row(
    *,
    db_path: str,
    scan_id: str,
    repo_path: str,
    committed_at_sha: str,
) -> str:
    """Insert finding + finding_response + evidence_items with
    commit_status='committed' and given sha. Returns evidence_item_id.
    Mirrors the file-missing cell's seed but adds committed_at_sha so
    the orphan check has something to validate.
    """
    conn = sqlite3.connect(db_path)
    try:
        finding_id = str(uuid.uuid4())
        response_id = str(uuid.uuid4())
        evidence_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO findings
                 (id, scan_id, article, obligation_id, status,
                  title, evidence_summary)
               VALUES (?, ?, 'art9', 'ART09-OBL-1', 'compliant',
                       'Pool 4 force-push seed finding',
                       'Synthetic anchor for force-push broken_link cell')""",
            (finding_id, scan_id),
        )
        conn.execute(
            """INSERT INTO finding_responses
                 (id, finding_id, action, note, submitted_at, created_at)
               VALUES (?, ?, 'provide_evidence', 'pool4 force-push seed',
                       strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                       strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))""",
            (response_id, finding_id),
        )
        conn.execute(
            """INSERT INTO evidence_items
                 (id, finding_response_id, source, evidence_value,
                  evidence_name, dedup_hash, commit_status, storage_kind,
                  repo_path, committed_at_sha, health_status,
                  uploaded_at, created_at)
               VALUES (?, ?, 'dashboard', ?, 'audit-trail.md',
                       ?, 'committed', 'git_path', ?, ?, 'ok',
                       strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                       strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))""",
            (
                evidence_id,
                response_id,
                repo_path,
                f"dedup-{evidence_id}",
                repo_path,
                committed_at_sha,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return evidence_id


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
def test_pipeline_broken_link_force_push_via_real_mcp(
    tmp_path: Path,
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end force-push pipeline: cl_sync detects orphaned
    committed_at_sha via STEP 11c sweep + commit-reachability hook,
    flips DB health_status from ok to broken_link.
    """
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    db_path = os.environ.get(DB_PATH_ENV)
    if not db_path:
        pytest.skip(f"{DB_PATH_ENV} not set")

    persona = PERSONAS["business"]
    suffix = str(int(time.time() * 1000) % 1_000_000_000)
    repo_name = f"test-business/pool4-broken-link-fp-{suffix}"

    project_dir = tmp_path / "fixture"
    project_dir.mkdir()
    bare_remote = tmp_path / "remote.git"

    initial_sha = _init_working_tree_with_remote(project_dir, bare_remote)

    # Add evidence file, commit + push. This is the sha we'll orphan.
    evidence_full_path = project_dir / EVIDENCE_REL_PATH
    evidence_full_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_full_path.write_text(
        "# Audit Trail\n\n(Pool 4 force-push test artifact)\n",
        encoding="utf-8",
    )
    _git(["add", EVIDENCE_REL_PATH], cwd=project_dir)
    _git(
        ["commit", "-q", "-m", "add audit-trail evidence (about to be orphaned)"],
        cwd=project_dir,
    )
    _git(["push", "-q", "origin", "main"], cwd=project_dir)
    doomed_sha = _git(
        ["rev-parse", "HEAD"], cwd=project_dir,
    ).stdout.strip()
    assert doomed_sha != initial_sha, "sanity: evidence commit must differ from init"

    (project_dir / ".compliancelintrc").write_text(
        json.dumps({
            "purpose": "Pool 4 broken_link force-push fixture",
            "repo_name": repo_name,
            "saas_url": SAAS_URL,
            "saas_api_key": persona.api_key,
            "scope": {
                "operator_role": ["provider"],
                "risk_classification": "high-risk",
            },
            "attester_name": "Pool 4 Force-Push Test",
            "attester_email": "pool4-force-push@test.invalid",
        }, indent=2),
        encoding="utf-8",
    )

    repo_id_for_cleanup: str | None = None
    evidence_id: str | None = None
    # IMPORTANT: do NOT pass cwd=project_dir — see sister cell's note.
    # Default REPO_ROOT cwd ensures the editable scanner is loaded
    # (with the 2026-05-06 is_committed_orphaned plumbing); a stale
    # pip-installed scanner would not detect the orphan and the cell
    # would silently false-pass.
    client = McpStdioClient.spawn()
    try:
        # ── Step 1: cl_scan + cl_sync 1 to create dashboard rows. ──
        project_context_json = _build_synthetic_context(client, project_dir)
        scan_resp = parse_first_json(client.call_tool("cl_scan", {
            "project_path": str(project_dir),
            "project_context": project_context_json,
            "articles": "9",
            "ai_provider": "Pool4 force-push Synthetic",
        }))
        if "error" in scan_resp:
            pytest.skip(f"cl_scan rejected synthetic context: {scan_resp.get('error')}")

        sync1_resp = parse_first_json(
            client.call_tool("cl_sync", {"project_path": str(project_dir)}),
        )
        assert "error" not in sync1_resp, f"cl_sync 1 errored: {sync1_resp}"

        with open_readonly() as conn:
            repo_row = fetch_repo_by_name(conn, repo_name)
            assert repo_row is not None, f"no repos row for {repo_name!r}"
            repo_id_for_cleanup = repo_row["id"]
            scan_row = conn.execute(
                "SELECT id FROM scans WHERE repo_id = ? "
                "ORDER BY scanned_at DESC LIMIT 1",
                (repo_id_for_cleanup,),
            ).fetchone()
            assert scan_row is not None
            dashboard_scan_id = scan_row["id"]

        # ── Step 2: seed an evidence row pointing at the file with
        #    committed_at_sha = doomed_sha and health_status='ok'.
        evidence_id = _seed_committed_evidence_row(
            db_path=db_path,
            scan_id=dashboard_scan_id,
            repo_path=EVIDENCE_REL_PATH,
            committed_at_sha=doomed_sha,
        )
        assert _read_health_status(db_path, evidence_id) == "ok", (
            "pre-seed sanity: row should start as 'ok'"
        )

        # ── Step 3: cl_sync 2 — sweep should leave row alone.
        # File is on disk AND doomed_sha is still on remote → ok.
        # This catches false positives in the new orphan check.
        sync2_resp = parse_first_json(
            client.call_tool("cl_sync", {"project_path": str(project_dir)}),
        )
        assert "error" not in sync2_resp, f"cl_sync 2 errored: {sync2_resp}"
        mid_status = _read_health_status(db_path, evidence_id)
        assert mid_status == "ok", (
            f"sweep should leave row 'ok' when file present + sha on remote; "
            f"got {mid_status!r}. Either the new orphan check has a false "
            f"positive OR doomed_sha was not actually pushed."
        )

        # ── Step 4: force-push. Reset HEAD to initial, replace the
        #    evidence commit with a different one, push --force. The
        #    bare remote's main branch tip is no longer doomed_sha.
        _git(["reset", "--hard", initial_sha], cwd=project_dir)
        # `git reset --hard` removed the controls/ subtree along with
        # the evidence file (both were added in the doomed commit).
        # Recreate the directory tree + file so that
        # check_file_exists_secure still passes (file present) but
        # the commit history at doomed_sha is unreachable from any
        # remote-tracking ref.
        evidence_full_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_full_path.write_text(
            "# Audit Trail\n\n(replaced after force-push)\n",
            encoding="utf-8",
        )
        _git(["add", EVIDENCE_REL_PATH], cwd=project_dir)
        _git(
            ["commit", "-q", "-m", "rewrite history — replace evidence commit"],
            cwd=project_dir,
        )
        _git(["push", "--force", "-q", "origin", "main"], cwd=project_dir)
        # Defensive: refresh refs/remotes view; --force push already
        # updated origin/main but `fetch --prune` ensures local
        # remote-tracking refs are coherent.
        _git(["fetch", "origin", "--prune"], cwd=project_dir)

        new_head_sha = _git(
            ["rev-parse", "HEAD"], cwd=project_dir,
        ).stdout.strip()
        assert new_head_sha != doomed_sha, (
            "sanity: after force-push the working HEAD must be a "
            "different commit than the orphaned doomed_sha"
        )

        # File still on disk — file-missing branch must NOT fire.
        assert evidence_full_path.is_file(), (
            "evidence file must still be on disk for the force-push "
            "variant — the cell tests sha-orphan detection, not "
            "file-missing detection"
        )

        # ── Step 5: cl_sync 3 — sweep runs; orphan check fires.
        sync3_resp = parse_first_json(
            client.call_tool("cl_sync", {"project_path": str(project_dir)}),
        )
        assert "error" not in sync3_resp, f"cl_sync 3 errored: {sync3_resp}"
        # The sweep summary should show at least 1 broken row this pass.
        broken_link_summary = sync3_resp.get("broken_link_check") or {}
        if broken_link_summary:
            assert broken_link_summary.get("broken", 0) >= 1, (
                f"sweep summary should report broken >= 1 after force-push; "
                f"got {broken_link_summary}. The new orphan-commit branch "
                f"in scanner/core/broken_link.py:build_reports may not be "
                f"firing — check is_committed_orphaned plumbing."
            )
    finally:
        client.close()

    # ── Layer 3 verify: dashboard DB flipped health_status. ──
    final_status = _read_health_status(db_path, evidence_id)
    assert final_status == "broken_link", (
        f"After force-push + cl_sync, evidence_items.health_status should "
        f"be 'broken_link' (orphaned committed_at_sha={doomed_sha[:12]}); "
        f"got {final_status!r}. Either the orphan check did not fire OR "
        f"the POST /evidence-health round-trip didn't update the DB."
    )

    # ── Cleanup: purge cascade. ──
    if repo_id_for_cleanup is not None:
        try:
            purge_repo(
                SAAS_URL, persona.api_key, repo_id_for_cleanup,
                confirm_name=repo_name,
            )
        except CleanupError as e:
            pytest.fail(
                f"force-push cleanup purge failed: {e}; orphan repo "
                f"id={repo_id_for_cleanup}"
            )
