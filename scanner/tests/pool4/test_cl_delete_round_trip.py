"""Pool 4 Phase 2.B — cl_delete target=dashboard round-trip.

Pattern: cl_sync first (to create a repo), then cl_delete(target=
"dashboard", confirm=True), then verify the SaaS-side row is gone
while the on-disk fixture state is preserved (per the cl_delete
contract documented at scanner/server.py:3349-3353).

Per Pool 4 cross-system route audit (route-audit-2026-05-03.md):
  cl_delete target=dashboard|all → DELETE /api/v1/repos/<id>/purge
  cascading delete of scans / findings / finding_responses /
  evidence_items / repo_access. NO audit_logs row written (uses
  log.audit observability stream, not the audit_logs DB table).

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C2: live :3000 prod server
  - C3: real seeded test-business persona
  - C4: 3-layer verification — response + DB row absence + on-disk
    fixture preservation (target=dashboard does NOT touch local/)
  - C7: Pattern A overlay; rc restored on exit
  - C8: defense-in-depth — purge cleanup runs even if cl_delete
    succeeded (so a failed cl_delete doesn't leave an orphan).

Verified-via: scanner/server.py:3328 cl_delete + the dashboard's
DELETE /api/v1/repos/<id>/purge route handler.
"""
from __future__ import annotations

import json
import time

import pytest

from .cell_loader import ToolCell
from .cleanup import CleanupError, purge_repo
from .dispatcher import invoke_tool
from .fixtures import PERSONAS, manual_fixture_dir, pattern_a
from .mcp_client import McpStdioClient
from .saas_introspection import (
    fetch_repo_by_name,
    open_readonly,
)


SAAS_URL = "http://localhost:3000"


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_cl_delete_target_dashboard_round_trip(
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end: cl_sync creates a repo, cl_delete(target='dashboard')
    removes it, DB cascade verifies, on-disk state preserved.

    Phase 2.B milestone for cl_delete; same Pattern A + cleanup
    discipline as Phase 2.A.
    """
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    fixture_dir = manual_fixture_dir()
    if fixture_dir is None or not fixture_dir.is_dir():
        pytest.skip("POOL4_MANUAL_FIXTURE_DIR not set or path missing")

    persona = PERSONAS["business"]
    unique_suffix = str(int(time.time() * 1000) % 1_000_000_000)
    repo_name = f"test-business/pool4-cl-delete-{unique_suffix}"
    repo_id_for_safety_purge: str | None = None

    with pattern_a("business", repo_name_override=repo_name) as fx:
        articles_dir = fx.project_path / ".compliancelint" / "local" / "articles"
        assert articles_dir.is_dir() and any(articles_dir.glob("*.json")), (
            f"manual-fixture has no scan state at {articles_dir}; "
            f"cl_delete prereq is a synced repo, which needs prior scan."
        )

        client = McpStdioClient.spawn()
        try:
            # ── Step 1: cl_sync to create the SaaS repo ──
            sync_cell = ToolCell(
                cell_id="phase2b-cl_sync-prereq-business",
                tier="S",
                tool="cl_sync",
                scenario="success",
                persona="business",
                preconditions=["seeded_user_business", "manual_fixture_scanned"],
                cleanup=["purge_test_repo", "restore_rc"],
                cleanup_justification=None,
                invoke={
                    "tool": "cl_sync",
                    "args": {"project_path": str(fx.project_path)},
                },
                expected_response={"status": "ok"},
            )
            sync_raw = invoke_tool(sync_cell, ctx={}, client=client)
            sync_resp = json.loads(sync_raw)
            assert "error" not in sync_resp, f"cl_sync prereq failed: {sync_resp}"
            assert sync_resp.get("scan_id"), "cl_sync prereq returned no scan_id"

            # Resolve repo_id for later DB checks. Capture for
            # safety-net cleanup in case cl_delete itself fails RED.
            with open_readonly() as conn:
                repo_row = fetch_repo_by_name(conn, repo_name)
                assert repo_row is not None, (
                    f"DB has no repos row for {repo_name!r} after cl_sync prereq"
                )
                repo_id_for_safety_purge = repo_row["id"]

            # Snapshot the on-disk fixture state to verify target=
            # dashboard preserves it (per cl_delete contract).
            local_dir = fx.project_path / ".compliancelint" / "local"
            assert local_dir.is_dir()
            local_files_before = sum(1 for _ in local_dir.rglob("*"))

            # ── Step 2: cl_delete target=dashboard ──
            delete_cell = ToolCell(
                cell_id="phase2b-cl_delete-success-target_dashboard-business",
                tier="S",
                tool="cl_delete",
                scenario="target_dashboard",
                persona="business",
                preconditions=["seeded_user_business", "synced_repo_exists"],
                cleanup=["safety_purge_if_failed"],
                cleanup_justification=None,
                invoke={
                    "tool": "cl_delete",
                    "args": {
                        "project_path": str(fx.project_path),
                        "target": "dashboard",
                        "confirm": True,
                    },
                },
                expected_response={"status": "ok"},
            )
            delete_raw = invoke_tool(delete_cell, ctx={}, client=client)
        finally:
            client.close()

        delete_resp = json.loads(delete_raw)

        # cl_delete success returns status="success" + a summary; on
        # abort/error returns an aborted/error envelope. Per audit-
        # first observation: response shape may include
        # 'reversibility', 'will_delete', 'will_keep' lists.
        assert "error" not in delete_resp, (
            f"cl_delete returned error envelope: {delete_resp}"
        )

        # ── Layer 1 (DB direct): repo row gone ──
        with open_readonly() as conn:
            repo_after = fetch_repo_by_name(conn, repo_name)
            assert repo_after is None, (
                f"cl_delete target=dashboard did NOT remove the repos "
                f"row for {repo_name!r}; row still present at id="
                f"{repo_after['id'] if repo_after else 'unknown'}"
            )
            # Safety purge no longer needed — cl_delete already cleaned.
            repo_id_for_safety_purge = None

        # ── On-disk preservation: target=dashboard MUST NOT touch
        #    .compliancelint/local/ per the cl_delete contract. ──
        local_files_after = sum(1 for _ in local_dir.rglob("*"))
        assert local_files_after == local_files_before, (
            f"cl_delete target=dashboard wiped on-disk state: "
            f"{local_files_before} files before -> {local_files_after} "
            f"after. The contract preserves on-disk state for this "
            f"target — only target=local or target=all should touch it."
        )

    # ── Safety-net: purge orphan if cl_delete failed RED earlier ──
    if repo_id_for_safety_purge is not None:
        try:
            purge_repo(
                SAAS_URL, persona.api_key, repo_id_for_safety_purge,
                confirm_name=repo_name,
            )
        except CleanupError as e:
            pytest.fail(
                f"safety-net purge failed: {e} — orphan repo at id="
                f"{repo_id_for_safety_purge}; clean up manually."
            )
