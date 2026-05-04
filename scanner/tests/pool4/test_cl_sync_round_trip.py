"""Pool 4 Phase 2 milestone — cl_sync end-to-end with 3-layer verification.

This is the first cross-system Pool 4 cell. It exercises the
production cl_sync flow exactly as a real Claude Code session would:

  1. Pattern A fixture overlay: write saas_api_key + saas_url + a
     unique repo_name into the manual-fixture rc (test-business
     persona for unlimited repo allowance).
  2. Spawn `python -m scanner.server` as a MCP subprocess and send
     tools/call cl_sync over JSON-RPC stdio.
  3. Parse the response: assert scan_id present, dashboard_url
     points at the local dev server, no error envelope.
  4. Layer 1 verification (DB direct): query the dashboard sqlite,
     confirm the new scans row is present + has positive
     total_obligations + matching counts.
  5. Layer 2 verification (Dashboard API): GET
     /api/v1/repos/<repoId>/scans/<scanId> with the test-business
     api key; assert the API counts equal the DB counts (no
     normalize-layer bypass).
  6. Cleanup: DELETE /api/v1/repos/<repoId>/purge with confirmName
     matching the unique repo_name; assert the row is gone.
  7. Pattern A context manager restores the original rc bytes.

Per Pool 4 hard constraints:
  - C1 (no in-process import): MCP subprocess transport throughout.
  - C2 (real prod server): requires_dev_server marker → skip if :3000
    is unreachable; otherwise hit the live server on the same port a
    user would.
  - C3 (real seeded users): requires_seeded_users marker → skip if
    test-business is missing from the dev DB.
  - C4 (3-layer verification): explicit DB + API checks.
  - C7 (real fixture): Pattern A overlay against a real seeded fixture
    (manual-fixture has prior scan state from the snapshot pipeline).
  - C8 (cleanup): pattern_a context manager + explicit purge_repo call.

Verified-via: scanner/server.py:2415 cl_sync flow + the internal
dashboard's POST /api/v1/scans route handler.
"""
from __future__ import annotations

import json
import time

import pytest

from .cleanup import CleanupError, fetch_scan_via_api, purge_repo
from .dispatcher import invoke_tool
from .fixtures import PERSONAS, manual_fixture_dir, pattern_a
from .mcp_client import McpStdioClient
from .saas_introspection import (
    count_findings_for_scan,
    count_scans_for_repo,
    fetch_latest_scan_for_repo,
    fetch_repo_by_name,
    open_readonly,
)


SAAS_URL = "http://localhost:3000"


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_cl_sync_round_trip_business_persona(
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end cl_sync against the live dev server with 3-layer
    verification + cleanup.

    Phase 2.A milestone proof. Once green, the same pattern extends
    mechanically to the remaining 35 cl_sync cells (other personas,
    other scenarios) and to cl_connect / cl_delete.
    """
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    fixture_dir = manual_fixture_dir()
    if fixture_dir is None or not fixture_dir.is_dir():
        pytest.skip("POOL4_MANUAL_FIXTURE_DIR not set or path missing")

    persona = PERSONAS["business"]
    # Unique per-run repo name — two parallel sessions don't collide
    # AND a prior run's leftover repo doesn't conflict on re-run if
    # cleanup failed.
    unique_suffix = str(int(time.time() * 1000) % 1_000_000_000)
    repo_name = f"test-business/pool4-cl-sync-{unique_suffix}"

    repo_id_for_cleanup: str | None = None

    with pattern_a("business", repo_name_override=repo_name) as fx:
        # Sanity: project state already seeded with prior scan data
        # (manual-fixture snapshot pipeline left .compliancelint/local/
        # articles/*.json on disk — the audit-first proof that cl_sync
        # has something to upload). Asserting > 0 article files prevents
        # a silent "uploaded zero rows" pass.
        articles_dir = fx.project_path / ".compliancelint" / "local" / "articles"
        article_count = (
            len(list(articles_dir.glob("*.json"))) if articles_dir.is_dir() else 0
        )
        assert article_count > 0, (
            f"manual-fixture has no scan state at {articles_dir}; "
            f"run cl_scan_all on the fixture once before pool4 cross-system "
            f"cells can verify a non-empty sync."
        )

        client = McpStdioClient.spawn()
        try:
            from .cell_loader import ToolCell

            synthetic_cell = ToolCell(
                cell_id="phase2-cl_sync-success-business",
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

            raw = invoke_tool(synthetic_cell, ctx={}, client=client)
        finally:
            client.close()

        response = json.loads(raw)

        assert "error" not in response, (
            f"cl_sync returned error envelope: {response}"
        )
        scan_id = response.get("scan_id")
        assert scan_id, f"cl_sync response missing scan_id: keys={list(response.keys())}"
        dashboard_url = response.get("dashboard_url", "")
        # The dashboard reports its public URL using whichever interface
        # answered the request (per feedback_prod_server_bind_all_interfaces:
        # the server binds 0.0.0.0 and may use a LAN IP rather than
        # localhost). Just check the :3000 + /dashboard/repos/<id>/scans/<id>
        # shape — the host portion varies.
        assert ":3000/dashboard/repos/" in dashboard_url and "/scans/" in dashboard_url, (
            f"dashboard_url should be the dev server's repos/<id>/scans/<id> "
            f"path; got {dashboard_url!r}"
        )

        # ── Layer 1: DB direct ──
        with open_readonly() as conn:
            repo_row = fetch_repo_by_name(conn, repo_name)
            assert repo_row is not None, (
                f"DB has no repos row for name={repo_name!r} after cl_sync"
            )
            repo_id = repo_row["id"]
            repo_id_for_cleanup = repo_id

            scans_count = count_scans_for_repo(conn, repo_id)
            assert scans_count == 1, (
                f"expected exactly 1 scan row for new repo (this is a fresh "
                f"upload); got {scans_count}"
            )

            latest_scan = fetch_latest_scan_for_repo(conn, repo_id)
            assert latest_scan is not None
            assert latest_scan["id"] == scan_id, (
                f"latest scan id mismatch — DB={latest_scan['id']!r} vs "
                f"response={scan_id!r}"
            )

            findings_total = count_findings_for_scan(conn, scan_id)
            assert findings_total > 0, (
                f"findings table has 0 rows for scan_id={scan_id} — sync "
                f"uploaded an empty scan? state.json had {article_count} "
                f"article files"
            )

        # ── Layer 2: Dashboard API ──
        # API returns totalFindings (= COUNT(*) of findings rows for this
        # scan) NOT totalObligations (which is a scans column reflecting
        # the obligation count from state.json). The Layer-1 vs Layer-2
        # check is "does the API see the same row count as the DB" — a
        # mismatch indicates a route filter or normalize bypass.
        api_view = fetch_scan_via_api(
            SAAS_URL, persona.api_key, repo_id, scan_id,
        )
        api_total = api_view.get("totalFindings", 0)
        assert api_total == findings_total, (
            f"3-layer divergence: API totalFindings={api_total} vs DB "
            f"COUNT(findings)={findings_total}. Indicates a route filter "
            f"or normalize-layer bypass — check route handler vs DB."
        )

        # Per-status sanity: DB row count by status should equal API's
        # compliantCount + nonCompliantCount + notApplicableCount +
        # undeterminedCount (the canonical 4-bucket split).
        api_buckets = (
            api_view.get("compliantCount", 0)
            + api_view.get("nonCompliantCount", 0)
            + api_view.get("notApplicableCount", 0)
            + api_view.get("undeterminedCount", 0)
        )
        assert api_buckets == api_total, (
            f"API status-bucket sum ({api_buckets}) != totalFindings "
            f"({api_total}) — UI status filter would render incorrect KPIs"
        )

    # ── Cleanup: purge repo ──
    # Outside the `with` block so the rc is restored regardless of
    # purge outcome (state on disk doesn't depend on the SaaS row
    # surviving).
    if repo_id_for_cleanup is not None:
        try:
            purge_repo(
                SAAS_URL, persona.api_key, repo_id_for_cleanup,
                confirm_name=repo_name,
            )
        except CleanupError as e:
            pytest.fail(
                f"cleanup purge_repo failed: {e}. The test PASS condition "
                f"is met but the dev DB now has an orphan repo row at "
                f"id={repo_id_for_cleanup}; clean up manually or ignore."
            )

        # Defense-in-depth: confirm the repo really is gone.
        with open_readonly() as conn:
            after = fetch_repo_by_name(conn, repo_name)
            assert after is None, (
                f"purge_repo reported success but DB still has a repos row "
                f"for {repo_name!r} — cascade may have skipped this row"
            )
