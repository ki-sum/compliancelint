"""Pool 4 Phase 2 expansion — cl_sync schema_drift / scanner version too old.

Per Kisum decision 2026-05-05: schema_drift is NOT aspirational — it's
the load-bearing gate that prevents version mismatch between scanner
and dashboard from corrupting DB state silently after a breaking
schema change.

Implementation landed same day:
  - dashboard/src/lib/version-compat.ts — single source of truth
  - dashboard /api/v1/version — public manifest endpoint
  - dashboard /api/v1/scans — 426 Upgrade Required when
    body.scanner_version < MIN_SCANNER_VERSION
  - scanner/server.py — special 426 case in cl_sync's HTTP-error
    branch + COMPLIANCELINT_SCANNER_VERSION_OVERRIDE env var (test-only
    hook to simulate an old scanner without rebuilding the MCP package)

This cell exercises the gate end-to-end through real MCP transport:
  - Spawn MCP subprocess with COMPLIANCELINT_SCANNER_VERSION_OVERRIDE
    set to "0.5.0" (below the dashboard's MIN_SCANNER_VERSION="1.0.0")
  - Call cl_sync via real JSON-RPC over stdio
  - Dashboard's 426 fires; cl_sync wraps it with an upgrade-required
    error envelope
  - Verify the envelope mentions upgrade + the pip command
  - DB defense: no new repo created (the 426 short-circuits before any
    DB write)

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport (env var passed via spawn(env=...))
  - C2: live :3000 prod server
  - C3: real seeded test-business persona
  - C7: Pattern A overlay; rc restored
  - C8: nothing to clean up — 426 short-circuits at the gate

Verified-via: scanner/server.py cl_sync HTTP-426 branch + the SaaS
POST /api/v1/scans schema_drift gate (lib/version-compat.ts
checkScannerCompat → action='force_upgrade' when scanner_version <
MIN_SCANNER_VERSION).
"""
from __future__ import annotations

import json
import time

import pytest

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .fixtures import PERSONAS, manual_fixture_dir, pattern_a
from .mcp_client import McpStdioClient
from .saas_introspection import fetch_repo_by_name, open_readonly


SAAS_URL = "http://localhost:3000"

# A scanner version BELOW the dashboard's MIN_SCANNER_VERSION ("1.0.0").
# 0.5.0 represents a hypothetical pre-1.0 scanner that was on PyPI
# pre-launch; today no real customers should be on this version, but
# the gate must still hold to prevent corruption from any stragglers.
OLD_SCANNER_VERSION = "0.5.0"


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_cl_sync_with_old_scanner_version_returns_426_envelope(
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end: scanner reports an old version → dashboard returns
    426 → cl_sync surfaces an upgrade-required error envelope; DB has
    no new repo."""
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    fixture_dir = manual_fixture_dir()
    if fixture_dir is None or not fixture_dir.is_dir():
        pytest.skip("POOL4_MANUAL_FIXTURE_DIR not set or path missing")

    persona = PERSONAS["business"]
    unique_suffix = str(int(time.time() * 1000) % 1_000_000_000)
    new_repo_name = f"test-business/pool4-schema-drift-{unique_suffix}"

    with pattern_a("business", repo_name_override=new_repo_name):
        # Spawn MCP with the test-only version override env var. This
        # makes cl_sync's payload report scanner_version=OLD_SCANNER_VERSION
        # while the actual installed package is the current CL_VERSION.
        client = McpStdioClient.spawn(
            env={"COMPLIANCELINT_SCANNER_VERSION_OVERRIDE": OLD_SCANNER_VERSION},
        )
        try:
            cell = ToolCell(
                cell_id="phase2-cl_sync-schema_drift_426",
                tier="S",
                tool="cl_sync",
                scenario="schema_drift_force_upgrade",
                persona="business",
                preconditions=[
                    "seeded_user_business",
                    f"scanner_version_override={OLD_SCANNER_VERSION}",
                    "dashboard_min_scanner_version_above_override",
                ],
                cleanup=["restore_rc"],
                cleanup_justification=(
                    "no SaaS state created — 426 short-circuits at the "
                    "version gate before any DB write"
                ),
                invoke={
                    "tool": "cl_sync",
                    "args": {"project_path": str(fixture_dir)},
                },
                expected_response={"status": "error"},
            )
            raw = invoke_tool(cell, ctx={}, client=client)
        finally:
            client.close()

    response = json.loads(raw)

    assert "error" in response, (
        f"cl_sync should have returned an error envelope when scanner "
        f"version is below dashboard MIN; got {response}"
    )
    err_text = (
        (response.get("error") or "")
        + " "
        + (response.get("details") or "")
        + " "
        + (response.get("fix") or "")
    ).lower()
    # The 426 path's error message should mention the upgrade requirement
    # AND the upgrade command. AI clients use these signals to nudge the
    # user to actually run pip install -U.
    assert "upgrade" in err_text, (
        f"426 envelope should mention 'upgrade'; got: {err_text[:300]!r}"
    )
    assert (
        "pip install" in err_text
        or "compliancelint" in err_text
    ), (
        f"426 envelope should reference the upgrade command "
        f"(pip install -U compliancelint); got: {err_text[:300]!r}"
    )

    # DB defense: no new repo created. The 426 fires BEFORE the route's
    # repo upsert, so there must be zero rows for the new repo name.
    with open_readonly() as conn:
        new_repo_row = fetch_repo_by_name(conn, new_repo_name)
        assert new_repo_row is None, (
            f"DB has a repos row for {new_repo_name!r} despite the 426 "
            f"rejection — the schema_drift gate has been bypassed. This "
            f"is a CRITICAL regression: an old scanner could now corrupt "
            f"newer-schema DB state."
        )


def test_dashboard_version_endpoint_publishes_compat_thresholds(
    server_reachable: bool,
) -> None:
    """The /api/v1/version endpoint MUST publish the four compat fields
    so scanners can pre-flight before sending a doomed POST. Schema
    pinning here = a public-API contract that must not silently change.
    """
    if not server_reachable:
        pytest.skip("server :3000 not ready")

    import urllib.request

    with urllib.request.urlopen(
        f"{SAAS_URL}/api/v1/version", timeout=3,
    ) as resp:
        assert resp.status == 200
        payload = json.loads(resp.read())

    required_fields = {
        "dashboard_version",
        "min_scanner_version",
        "recommended_scanner_version",
        "upgrade_command",
    }
    missing = required_fields - set(payload.keys())
    assert not missing, (
        f"/api/v1/version payload missing required fields: {missing}. "
        f"Got keys: {sorted(payload.keys())}"
    )
    # SemVer-shape on each version field.
    import re
    semver_pat = re.compile(r"^\d+\.\d+\.\d+")
    for k in (
        "dashboard_version",
        "min_scanner_version",
        "recommended_scanner_version",
    ):
        assert semver_pat.match(payload[k]), (
            f"{k}={payload[k]!r} is not a valid semver — public API "
            f"contract requires MAJOR.MINOR.PATCH"
        )
    # Upgrade command should mention either pip or npx.
    assert (
        "pip install" in payload["upgrade_command"]
        or "npx compliancelint" in payload["upgrade_command"]
    ), (
        f"upgrade_command should reference pip or npx; "
        f"got: {payload['upgrade_command']!r}"
    )
