"""Pool 4 Phase 2 expansion — cl_sync from the demo persona.

Per the SaaS-side route audit, /api/v1/scans returns 403 with the
message "Demo account is read-only." when the caller is the seeded
demo user (`demo@compliancelint.dev`). The handler invokes
``isDemoUser(user)`` immediately after auth and short-circuits before
any DB write.

Why guard this: the demo API key is intentionally widely shared (used
on landing-page screenshots + docs) so without the demo block any
visitor with the demo URL could ingest scans against the public
showcase. Same rationale as the demo block on the purge route.

This cell uses the demo persona's pre-seeded api_key and asserts the
403 envelope shape end-to-end.

Verifications:
  - response is an error envelope (no scan_id)
  - error / details mention "demo" or "read-only" or 403
  - DB defense: no new repos row created (the 403 short-circuits at
    the demo gate before any write)

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C2: live :3000 prod server
  - C3: real seeded demo persona
  - C7: Pattern A overlay; rc restored
  - C8: nothing to clean up — auth-gated short-circuit, no SaaS state

Verified-via: scanner/server.py cl_sync HTTP-error branch + the SaaS
POST /api/v1/scans demo-block gate.
"""
from __future__ import annotations

import json
import time

import pytest

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .fixtures import manual_fixture_dir, pattern_a
from .mcp_client import McpStdioClient
from .saas_introspection import fetch_repo_by_name, open_readonly


# Pre-seeded demo persona (seed-demo.ts line 590-597). The shared
# demo api_key is part of the public landing-page surface; this cell
# pins the read-only contract.
DEMO_API_KEY = "cl_demo_key_for_development_only"


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_cl_sync_from_demo_user_returns_403_envelope(
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end: rc carries the demo api_key → cl_sync returns 403
    error envelope; DB has no new repo."""
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    fixture_dir = manual_fixture_dir()
    if fixture_dir is None or not fixture_dir.is_dir():
        pytest.skip("POOL4_MANUAL_FIXTURE_DIR not set or path missing")

    unique_suffix = str(int(time.time() * 1000) % 1_000_000_000)
    new_repo_name = f"demo/pool4-cl-sync-403-{unique_suffix}"

    with pattern_a(
        "free",  # nominal — overlay below replaces saas_api_key
        repo_name_override=new_repo_name,
        extra_rc_fields={"saas_api_key": DEMO_API_KEY},
    ):
        client = McpStdioClient.spawn()
        try:
            cell = ToolCell(
                cell_id="phase2-cl_sync-demo_user_403",
                tier="S",
                tool="cl_sync",
                scenario="demo_user_read_only",
                persona="demo",
                preconditions=["seeded_user_demo"],
                cleanup=["restore_rc"],
                cleanup_justification=(
                    "no SaaS state created — 403 short-circuits at the "
                    "demo gate before any DB write"
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
        f"cl_sync from demo persona should have returned an error "
        f"envelope; got {response}"
    )
    err_text = (
        (response.get("error") or "")
        + " "
        + (response.get("details") or "")
    ).lower()
    assert (
        "demo" in err_text
        or "read-only" in err_text
        or "read only" in err_text
        or "403" in err_text
    ), (
        f"error envelope should mention demo/read-only/403; "
        f"got: {err_text[:300]!r}"
    )

    # DB defense: demo can't ingest. Any new repo row under this name
    # = the demo gate has been bypassed.
    with open_readonly() as conn:
        new_repo_row = fetch_repo_by_name(conn, new_repo_name)
        assert new_repo_row is None, (
            f"DB has a repos row for {new_repo_name!r} despite the "
            f"403 demo block — the read-only gate has been bypassed. "
            f"This is a CRITICAL regression: any landing-page visitor "
            f"can now ingest scans against the public demo."
        )
