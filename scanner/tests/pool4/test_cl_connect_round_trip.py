"""Pool 4 Phase 2.C — cl_connect already_connected round-trip.

cl_connect has two response paths (per scanner/server.py:2255-2360):

  1. **already_connected** — when rc has a valid saas_api_key, the
     scanner pings GET /api/v1/auth/check; on 200+valid, returns
     ``status: "already_connected"`` with email + dashboard_url. No
     state mutation. This is the path the test exercises.

  2. **device flow** — when no valid api_key, opens browser +
     polls /api/v1/auth/connect/poll for 90s waiting for human OAuth
     completion. Impossible to automate without an OAuth-callback
     simulator; deferred to Step 5 tier-A pipeline cells per the
     internal route audit.

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C2: live :3000 prod server (auth/check requires it)
  - C3: real seeded test-business persona (we exercise its api_key)
  - C4: 1-layer verification — cl_connect already_connected does
    NOT mutate SaaS state (auth/check is GET-only). Asserter
    checks response shape only. (Multi-layer verification reserved
    for cl_sync / cl_delete / Step-5 tier-A cells.)
  - C7: Pattern A overlay
  - C8: rc restored by Pattern A context manager

Verified-via: scanner/server.py:2255 cl_connect already_connected
branch + the internal /api/v1/auth/check route handler.
"""
from __future__ import annotations

import json

import pytest

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .fixtures import PERSONAS, manual_fixture_dir, pattern_a
from .mcp_client import McpStdioClient


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_cl_connect_already_connected_business(
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end: rc has valid api_key → cl_connect returns
    already_connected with the right email + dashboard_url.

    Phase 2.C milestone for cl_connect happy path. The 'fresh
    connect' (device-flow) path stays manual-only until Step 5
    builds the OAuth-callback simulator.
    """
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    fixture_dir = manual_fixture_dir()
    if fixture_dir is None or not fixture_dir.is_dir():
        pytest.skip("POOL4_MANUAL_FIXTURE_DIR not set or path missing")

    persona = PERSONAS["business"]

    with pattern_a("business") as fx:
        client = McpStdioClient.spawn()
        try:
            cell = ToolCell(
                cell_id="phase2c-cl_connect-already_connected-business",
                tier="S",
                tool="cl_connect",
                scenario="already_connected",
                persona="business",
                preconditions=["seeded_user_business", "rc_has_valid_api_key"],
                cleanup=["restore_rc"],
                cleanup_justification=None,
                invoke={
                    "tool": "cl_connect",
                    "args": {"project_path": str(fx.project_path)},
                },
                expected_response={
                    "status": "already_connected",
                    "email": persona.email,
                },
            )
            raw = invoke_tool(cell, ctx={}, client=client)
        finally:
            client.close()

        response = json.loads(raw)

        assert "error" not in response, (
            f"cl_connect returned error envelope: {response}"
        )
        assert response.get("status") == "already_connected", (
            f"cl_connect did not return already_connected; got status="
            f"{response.get('status')!r}, full response keys="
            f"{list(response.keys())}"
        )
        assert response.get("email") == persona.email, (
            f"cl_connect email mismatch: expected {persona.email!r}, "
            f"got {response.get('email')!r}. The auth/check route may "
            f"be returning a stale or wrong user — check the api_key "
            f"→ user mapping in dev DB."
        )
        dashboard_url = response.get("dashboard_url", "")
        assert ":3000/dashboard" in dashboard_url, (
            f"dashboard_url should reference the local dev server's "
            f"/dashboard path; got {dashboard_url!r}"
        )
        message = response.get("message", "")
        assert "cl_sync" in message.lower() or "already" in message.lower(), (
            f"cl_connect message should hint at next steps; got "
            f"{message!r}"
        )
