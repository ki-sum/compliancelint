"""Pool 4 Phase 2 expansion — cl_delete target=dashboard from a member persona.

Per the SaaS-side route audit, the DELETE /api/v1/repos/<id>/purge
handler returns 403 "Only the repo owner can permanently delete..."
when the caller is a member, not the owner. This guards the team-
permissions invariant: invited members can DISCONNECT their access
(revoke their repo_access row) but cannot DESTROY the shared repo
for everyone.

Setup (all from the seed-demo seed script):
  - test-business owns the repo "test-business/demo-app"
  - test-business-invited has a repo_access row to that repo with
    role="member"
  - The invited persona's API key is recognised by the auth gate, so
    the caller passes 401; the owner check returns 403

Pattern: rc with the OWNER's repo_name + the MEMBER's api_key. cl_delete
target=dashboard sends the purge request; dashboard returns 403; cl_sync
wraps it as an error envelope (per scanner/server.py cl_delete HTTP
error branch).

Verifications:
  - response is an error envelope (no success status)
  - error / details mention "owner" or 403
  - DB defense: the repo row STILL EXISTS post-call (member could not
    delete the owner's repo)

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C2: live :3000 prod server
  - C3: real seeded test-business persona (owner) +
        test-business-invited (member) + their pre-seeded repo_access row
  - C7: Pattern A overlay; rc restored on exit
  - C8: nothing to clean up — the 403 short-circuits before any DB write,
        and the owner's pre-seeded repo MUST survive (test asserts this)

Verified-via: scanner/server.py cl_delete + the SaaS-side
DELETE /api/v1/repos/<id>/purge handler's owner gate.
"""
from __future__ import annotations

import json

import pytest

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .fixtures import manual_fixture_dir, pattern_a
from .mcp_client import McpStdioClient
from .saas_introspection import fetch_repo_by_name, open_readonly


# Pre-seeded by seed-demo.ts:
#   - Owner persona = "business" (test-business@…)
#   - Owner's repo  = "test-business/demo-app"
#   - Invited member persona key = test-business-invited's
SEEDED_OWNER_REPO_NAME = "test-business/demo-app"
INVITED_MEMBER_API_KEY = "cl_test_business_invited_key_for_development"


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_cl_delete_target_dashboard_from_member_returns_403(
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end: member persona attempts cl_delete target=dashboard
    on the OWNER's pre-seeded repo → 403 envelope; repo row survives."""
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    fixture_dir = manual_fixture_dir()
    if fixture_dir is None or not fixture_dir.is_dir():
        pytest.skip("POOL4_MANUAL_FIXTURE_DIR not set or path missing")

    # Pre-flight: confirm the owner's seeded repo exists (sanity that
    # this scenario IS the failure path, not a 404 due to missing seed).
    with open_readonly() as conn:
        seeded_row_before = fetch_repo_by_name(conn, SEEDED_OWNER_REPO_NAME)
        assert seeded_row_before is not None, (
            f"Pre-flight: seed missing — no repos row for "
            f"{SEEDED_OWNER_REPO_NAME!r}. Re-run seed-demo.ts before "
            f"this cell can exercise the member→owner-repo 403 path."
        )

    # Pattern A with the OWNER's repo name + the MEMBER's API key.
    # extra_rc_fields wins over the persona's api_key (see
    # fixtures.pattern_a line 200-201).
    with pattern_a(
        "business",
        repo_name_override=SEEDED_OWNER_REPO_NAME,
        extra_rc_fields={"saas_api_key": INVITED_MEMBER_API_KEY},
    ):
        client = McpStdioClient.spawn()
        try:
            cell = ToolCell(
                cell_id="phase2-cl_delete-member_403-target_dashboard",
                tier="S",
                tool="cl_delete",
                scenario="member_403",
                persona="business_invited",
                preconditions=[
                    "seeded_user_business_invited",
                    "seeded_repo_test-business/demo-app",
                    "seeded_repo_access_member_role",
                ],
                cleanup=["restore_rc"],
                cleanup_justification=(
                    "no SaaS state created — the 403 short-circuits at "
                    "the owner gate before any write. Defense asserts "
                    "the owner's repo row is unchanged."
                ),
                invoke={
                    "tool": "cl_delete",
                    "args": {
                        "project_path": str(fixture_dir),
                        "target": "dashboard",
                        "confirm": True,
                    },
                },
                expected_response={"status": "error"},
            )
            raw = invoke_tool(cell, ctx={}, client=client)
        finally:
            client.close()

    response = json.loads(raw)

    # Response shape (post 2026-05-04 fix):
    #   {
    #     "status": "failed",
    #     "results": {"dashboard": "error: Only the repo owner can…"}
    #   }
    # Status is now derived from per-target results — a target=dashboard
    # call where the only sub-target fully failed with "error: …" gets
    # status="failed" (not "deleted" as before the fix). The cell pins
    # the corrected behavior so a silent regression surfaces here.
    assert "results" in response, (
        f"cl_delete should return a per-target results dict; got {response}"
    )
    assert response.get("status") == "failed", (
        f"cl_delete with target=dashboard fully failing 403 should "
        f"surface top-level status='failed' (post 2026-05-04 fix); "
        f"got status={response.get('status')!r}, response={response}"
    )
    dashboard_result = (response.get("results") or {}).get("dashboard", "")
    assert isinstance(dashboard_result, str), (
        f"results.dashboard expected to be a string; "
        f"got {type(dashboard_result).__name__}: {dashboard_result!r}"
    )
    err_text = dashboard_result.lower()
    assert err_text.startswith("error:") or "error" in err_text, (
        f"dashboard sub-result should be prefixed with 'error:' for "
        f"the 403 path; got: {dashboard_result!r}"
    )
    assert (
        "owner" in err_text
        or "403" in err_text
        or "permission" in err_text
    ), (
        f"dashboard sub-result should mention owner/403/permission "
        f"(member can't permanently delete); got: {dashboard_result!r}"
    )

    # ── DB defense: owner's repo row MUST still exist ──
    # The member's purge attempt must not have cascaded ANYTHING. We
    # check just the repos-row presence; the cascade path
    # (scans/findings/evidence/repo_access) wouldn't even be reached
    # because the 403 fires before the DELETE FROM transaction.
    with open_readonly() as conn:
        seeded_row_after = fetch_repo_by_name(conn, SEEDED_OWNER_REPO_NAME)
        assert seeded_row_after is not None, (
            f"DB has NO repos row for {SEEDED_OWNER_REPO_NAME!r} after "
            f"a member's cl_delete attempt — the owner gate has been "
            f"bypassed. This is a CRITICAL regression: any invited "
            f"member can now destroy the owner's repo."
        )
        assert seeded_row_after["id"] == seeded_row_before["id"], (
            f"repo id changed unexpectedly: "
            f"{seeded_row_before['id']} -> {seeded_row_after['id']}"
        )
