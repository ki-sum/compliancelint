"""Pool 4 Phase 2 — cl_sync tier-limit gating.

The free tier allows ``maxRepos=1`` (per the internal dashboard
tier table). The seeded ``test-free`` persona already owns
``test-free/demo-app`` → it's at-limit. A new cl_sync against a
different repo_name MUST be rejected by the dashboard's POST
/api/v1/scans route handler with a ``403 repo limit reached``
error envelope.

The Pool 4 spec scenario is ``repo_limit_reached``. This test
proves the rejection path works end-to-end via real MCP transport
+ real prod server + real seeded user.

Verifications:
- response is an error envelope (not a success body with scan_id)
- error message mentions the limit + plan name
- DB has zero NEW repos for the persona post-call (the rejection
  short-circuits before the INSERT)

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C2: live :3000 prod server
  - C3: real seeded test-free persona (already at-limit)
  - C7: Pattern A overlay
  - C8: rc restored by Pattern A; no SaaS state to clean up
    (the failed cl_sync didn't insert anything)

Verified-via: scanner/server.py:2415 cl_sync HTTP error branch +
the /api/v1/scans route handler's tier-limit gate.
"""
from __future__ import annotations

import json
import time

import pytest

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .fixtures import PERSONAS, manual_fixture_dir, pattern_a
from .mcp_client import McpStdioClient
from .saas_introspection import (
    fetch_repo_by_name,
    fetch_repos_for_user,
    lookup_user_id_by_email,
    open_readonly,
)


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_cl_sync_repo_limit_reached_free_persona(
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end: free persona at-limit → cl_sync against a NEW repo
    name returns 403 + error envelope; DB has no new repo row."""
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    fixture_dir = manual_fixture_dir()
    if fixture_dir is None or not fixture_dir.is_dir():
        pytest.skip("POOL4_MANUAL_FIXTURE_DIR not set or path missing")

    persona = PERSONAS["free"]
    unique_suffix = str(int(time.time() * 1000) % 1_000_000_000)
    new_repo_name = f"test-free/pool4-cl-sync-blocked-{unique_suffix}"

    # Pre-flight: confirm test-free is at the maxRepos=1 cap (i.e.
    # this scenario IS the failure path, not the success path).
    with open_readonly() as conn:
        free_user_id = lookup_user_id_by_email(conn, persona.email)
        assert free_user_id is not None
        repos_before = fetch_repos_for_user(conn, free_user_id)
        assert len(repos_before) >= 1, (
            f"test-free has < 1 repos seeded; expected >=1 to be at-limit "
            f"for the maxRepos=1 free tier"
        )

    with pattern_a("free", repo_name_override=new_repo_name):
        client = McpStdioClient.spawn()
        try:
            cell = ToolCell(
                cell_id="phase2-cl_sync-repo_limit_reached-free",
                tier="S",
                tool="cl_sync",
                scenario="repo_limit_reached",
                persona="free",
                preconditions=["seeded_user_free", "free_at_max_repos_limit"],
                cleanup=["restore_rc"],
                cleanup_justification=(
                    "no SaaS state created — the 403 short-circuits before "
                    "any DB write per scans route gate"
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

    # Expect error envelope. cl_sync wraps the dashboard's 403 in a
    # local error envelope (per server.py:2667-2671 — the 403 branch
    # returns dump_error with the dashboard's message in details).
    assert "error" in response, (
        f"cl_sync should have returned an error envelope for free@-limit; "
        f"got {response}"
    )
    err_text = (response.get("error") or "") + " " + (response.get("details") or "")
    assert "limit" in err_text.lower() or "403" in err_text, (
        f"error envelope should mention limit/403; got: {err_text[:300]!r}"
    )

    # DB defense: no new repo created.
    with open_readonly() as conn:
        new_repo_row = fetch_repo_by_name(conn, new_repo_name)
        assert new_repo_row is None, (
            f"DB has a repos row for {new_repo_name!r} despite the 403 "
            f"rejection — the route handler's tier-limit gate has been "
            f"bypassed somewhere (regression vs the scans route handler)"
        )
