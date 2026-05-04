"""Pool 4 Phase 2.G — cl_sync fingerprint_set audit_log row.

Per the Pool 4 cross-system route audit, /api/v1/scans/route.ts
writes audit_logs ONLY for fingerprint events:
  - repo_fingerprint_set — first-time sha record
  - repo_fingerprint_change — mismatch detected
  - repo_fingerprint_auto_resolved — scanner returned to baseline

This test exercises the ``set`` path: a fresh repo + cl_sync that
sends a first_commit_sha → server inserts the audit row for the
acting user. Verifies the ``saas_introspection`` audit-log helpers
(count_audit_logs / fetch_latest_audit_log / AuditLogQuery) work
end-to-end against a real write — not just synthetic existing rows.

What's exercised that prior cells don't cover:
  - audit_logs DB write path triggered by a cl_sync invocation
  - require_user_id_by_email JOIN at scale (resolves persona email
    → user.id → audit_logs.user_id filter)
  - Created-at-window filtering (records before invoke ignored,
    only the row(s) from this test's invocation counted)

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C2: live :3000 prod server
  - C3: real seeded test-business persona
  - C4: 3-layer is N/A (audit row IS the layer-1 verification);
    response shape + audit_log row covers C4 for fingerprint cells
  - C7: Pattern A overlay; metadata.json snapshot/restore (manual,
    because pattern_a only handles rc bytes)
  - C8: purge_repo on success path; metadata.json restored from
    git in finally block; rc restored by pattern_a context manager

Verified-via: scanner/server.py:2592-2604 cl_sync payload
construction (first_commit_sha field) + the dashboard's POST
/api/v1/scans route handler's fingerprint branch + the route
audit doc enumeration of fingerprint_set/change/auto_resolved.
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
    AuditLogQuery,
    count_audit_logs,
    fetch_latest_audit_log,
    fetch_repo_by_name,
    now_iso,
    open_readonly,
)


SAAS_URL = "http://localhost:3000"


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_cl_sync_fingerprint_set_writes_audit_row(
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end: inject first_commit_sha into metadata.json, run
    cl_sync, expect a repo_fingerprint_set audit_logs row for the
    persona within the invoke window."""
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    fixture_dir = manual_fixture_dir()
    if fixture_dir is None or not fixture_dir.is_dir():
        pytest.skip("POOL4_MANUAL_FIXTURE_DIR not set or path missing")

    persona = PERSONAS["business"]
    unique_suffix = str(int(time.time() * 1000) % 1_000_000_000)
    repo_name = f"test-business/pool4-cl-sync-fp-{unique_suffix}"
    # Synthetic 40-char hex sha — never matches a real git commit.
    # Per-test unique so the audit_log filter doesn't collide with
    # parallel runs.
    fake_first_sha = f"deadbeef{unique_suffix:0>32}"

    metadata_path = fixture_dir / ".compliancelint" / "local" / "metadata.json"
    if not metadata_path.is_file():
        pytest.skip(
            "manual-fixture metadata.json missing; cl_sync needs it for "
            "the cached SHA path. Run cl_scan_all on the fixture once."
        )
    metadata_original_bytes = metadata_path.read_bytes()
    metadata_doc = json.loads(metadata_original_bytes.decode("utf-8"))
    metadata_doc["first_commit_sha"] = fake_first_sha
    metadata_doc["head_commit_sha"] = fake_first_sha

    repo_id_for_cleanup: str | None = None

    try:
        # Patch metadata.json with the synthetic SHA. cl_sync's load_commit_shas
        # reads this without subprocess git (per the bug_mcp_tool_hang rule).
        metadata_path.write_text(
            json.dumps(metadata_doc, indent=2),
            encoding="utf-8",
        )

        with pattern_a("business", repo_name_override=repo_name) as fx:
            invoke_start = now_iso()

            client = McpStdioClient.spawn()
            try:
                cell = ToolCell(
                    cell_id="phase2-cl_sync-fingerprint_set-business",
                    tier="S",
                    tool="cl_sync",
                    scenario="fingerprint_set",
                    persona="business",
                    preconditions=[
                        "seeded_user_business",
                        "manual_fixture_scanned",
                        "metadata_has_first_commit_sha",
                    ],
                    cleanup=[
                        "purge_test_repo",
                        "restore_metadata",
                        "restore_rc",
                    ],
                    cleanup_justification=None,
                    invoke={
                        "tool": "cl_sync",
                        "args": {"project_path": str(fx.project_path)},
                    },
                    expected_response={"status": "ok"},
                )
                raw = invoke_tool(cell, ctx={}, client=client)
            finally:
                client.close()

            response = json.loads(raw)
            assert "error" not in response, (
                f"cl_sync returned error: {response}"
            )
            scan_id = response.get("scan_id")
            assert scan_id, f"cl_sync missing scan_id; response={response}"

            with open_readonly() as conn:
                repo_row = fetch_repo_by_name(conn, repo_name)
                assert repo_row is not None, (
                    f"repos has no row for {repo_name!r} after cl_sync"
                )
                repo_id_for_cleanup = repo_row["id"]

                # Layer-1 check: audit_logs has a fingerprint_set row
                # for the test-business user, created during the invoke
                # window. Per the route audit, this is the ONLY audit
                # action a normal sync writes — and only when the
                # scanner sent a first_commit_sha.
                audit_query = AuditLogQuery(
                    actor_email=persona.email,
                    action="repo_fingerprint_set",
                    created_at_min=invoke_start,
                )
                fp_count = count_audit_logs(conn, audit_query)
                assert fp_count >= 1, (
                    f"expected >=1 repo_fingerprint_set audit_logs row "
                    f"for {persona.email} since {invoke_start}; got "
                    f"{fp_count}. The cl_sync sent first_commit_sha="
                    f"{fake_first_sha[:16]}... so the route handler "
                    f"should have logged a set event."
                )

                latest = fetch_latest_audit_log(conn, audit_query)
                assert latest is not None
                # The audit row's `resource` typically references the
                # repo (e.g. "repos/<id>" or "<repo_name>"); the
                # `detail` may include the sha. Loose check: at least
                # one of resource/detail mentions our repo or sha.
                resource = latest.get("resource") or ""
                detail = latest.get("detail") or ""
                blob = f"{resource} {detail}"
                assert (
                    repo_id_for_cleanup in blob
                    or repo_name in blob
                    or fake_first_sha[:12] in blob
                ), (
                    f"latest fingerprint_set audit row doesn't reference "
                    f"this test's repo or sha; resource={resource!r} "
                    f"detail={detail[:200]!r}"
                )
    finally:
        # ALWAYS restore metadata.json bytes — Pattern A does not.
        try:
            metadata_path.write_bytes(metadata_original_bytes)
        except OSError:
            pass

    # Cleanup outside try (rc + metadata both restored at this point).
    if repo_id_for_cleanup is not None:
        try:
            purge_repo(
                SAAS_URL, persona.api_key, repo_id_for_cleanup,
                confirm_name=repo_name,
            )
        except CleanupError as e:
            pytest.fail(
                f"cleanup purge failed: {e}. Orphan repo at "
                f"id={repo_id_for_cleanup} — purge manually."
            )
