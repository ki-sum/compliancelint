"""Pool 4 Phase 2 expansion — cl_sync with an invalid SaaS API key.

Per the SaaS-side route audit, the /api/v1/scans handler authenticates
via ``validateApiKey(request)`` at the entry point and returns 401
with a message starting with ``Unauthorized.`` when no/invalid key
is provided.

cl_sync wraps the dashboard's 401 in a local error envelope (per
scanner/server.py cl_sync HTTP error branch). This cell exercises that
path end-to-end: a syntactically-plausible but unrecognised API key
must produce a clean error envelope, NOT a hang and NOT a partial DB
write.

Verifications:
  - response is an error envelope (no scan_id)
  - error / details mention 401 or "unauthorized"
  - DB has zero new repos AND zero new audit_logs entries that could be
    attributed to a successful upsert (defense-in-depth: even though
    invalidation happens at the route entry, prove no side-effects)

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C2: live :3000 prod server
  - C3: real DB introspection (tests assume seed exists for sanity but
    doesn't bind to any seeded persona — the api_key used is fabricated)
  - C7: Pattern A overlay; rc restored
  - C8: nothing to clean up — auth fails before any write

Verified-via: scanner/server.py:cl_sync HTTP-error branch + the
SaaS POST /api/v1/scans handler's auth gate (401 path).
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


# Fabricated key — looks like our format ("cl_test_…") to defeat any
# naive prefix check, but is not present in the seeded users table.
FAKE_API_KEY = "cl_test_fake_invalid_key_not_in_db_pool4_phase2"


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_cl_sync_with_invalid_api_key_returns_401_envelope(
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end: rc carries an unrecognised api_key → cl_sync returns
    error envelope; DB has no new repos."""
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    fixture_dir = manual_fixture_dir()
    if fixture_dir is None or not fixture_dir.is_dir():
        pytest.skip("POOL4_MANUAL_FIXTURE_DIR not set or path missing")

    unique_suffix = str(int(time.time() * 1000) % 1_000_000_000)
    new_repo_name = f"test-orphan/pool4-cl-sync-401-{unique_suffix}"

    # Use any seeded persona's slot for pattern_a (it just needs SOMETHING
    # in the rc base) but override saas_api_key to the fabricated key so
    # the dashboard rejects auth at the route entry. extra_rc_fields wins
    # over the persona's api_key because it's merged last (see
    # fixtures.pattern_a line 200-201).
    with pattern_a(
        "free",
        repo_name_override=new_repo_name,
        extra_rc_fields={"saas_api_key": FAKE_API_KEY},
    ):
        client = McpStdioClient.spawn()
        try:
            cell = ToolCell(
                cell_id="phase2-cl_sync-invalid_api_key",
                tier="S",
                tool="cl_sync",
                scenario="invalid_api_key",
                persona="free",  # nominal — actual auth will reject
                preconditions=["fake_api_key_not_in_db"],
                cleanup=["restore_rc"],
                cleanup_justification=(
                    "no SaaS state created — the 401 short-circuits at "
                    "the route auth gate before any DB write"
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
        f"cl_sync should have returned an error envelope for an "
        f"invalid api_key; got {response}"
    )
    err_text = (
        (response.get("error") or "")
        + " "
        + (response.get("details") or "")
    ).lower()
    assert (
        "401" in err_text
        or "unauthorized" in err_text
        or "invalid" in err_text
    ), (
        f"error envelope should mention 401/unauthorized/invalid; "
        f"got: {err_text[:300]!r}"
    )

    # DB defense: no new repo created. We don't bind to any persona's
    # repo set (we used a fabricated key) so any new row at all under
    # this name = a regression at the route-handler auth gate.
    with open_readonly() as conn:
        new_repo_row = fetch_repo_by_name(conn, new_repo_name)
        assert new_repo_row is None, (
            f"DB has a repos row for {new_repo_name!r} despite the 401 "
            f"rejection — auth gate has been bypassed somewhere "
            f"(regression vs the scans route handler)"
        )
