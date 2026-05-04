"""Pool 4 Phase 2 expansion — cl_sync with GDPR Art 18 processing-restricted user.

Per the SaaS-side route audit, /api/v1/scans returns 423 with a GDPR
Art 18 message when the caller's user row has processing_restricted=1.
This is the user-facing toggle for "Restrict Processing" — once flipped,
new scans cannot be ingested while restriction is in force.

Test setup:
  - test-free-invited persona is the LEAST-used in the suite (no
    member relationship beyond a Pro-repo invite); chosen to minimise
    blast radius if cleanup fails for any reason
  - DB mutation: temporarily flip processing_restricted from 0 to 1
    via direct sqlite3 write, then attempt cl_sync, then flip back
  - try/finally guarantees the restore on any exception

Verifications:
  - cl_sync returns an error envelope (no scan_id)
  - error / details mention "restrict" or "GDPR" or "423"
  - DB defense: no new repo created
  - Cleanup proven: persona's processing_restricted is back to 0
    before this test exits

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C2: live :3000 prod server
  - C3: real seeded test-free-invited persona
  - C7: Pattern A overlay; rc restored
  - C8: rc restored AND processing_restricted toggle restored

Recovery if this cell ever leaves a persona stuck at 1 (shouldn't
happen with try/finally, but documented for paranoid recovery):

    sqlite3 "$POOL4_DB_PATH" \
      "UPDATE users SET processing_restricted=0 WHERE email LIKE 'test-%'"

Verified-via: scanner/server.py cl_sync HTTP-error branch + the SaaS
POST /api/v1/scans handler's GDPR Art 18 gate (423 path).
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .fixtures import PERSONAS, manual_fixture_dir, pattern_a
from .mcp_client import McpStdioClient
from .saas_introspection import (
    DB_PATH_ENV,
    fetch_repo_by_name,
    open_readonly,
)


# Least-impact persona for this test — minimises blast radius if
# cleanup fails. Same reasoning as the cell docstring explains.
TARGET_PERSONA_EMAIL = "test-free-invited@compliancelint.dev"


@contextmanager
def _temporarily_restrict_processing(email: str) -> Iterator[None]:
    """Flip users.processing_restricted to 1 for `email` and guarantee
    the restore on context exit. Uses a writable sqlite3 connection
    (``open_readonly`` is intentionally read-only to defend the rest of
    the suite from accidental writes).
    """
    db_path = os.environ.get(DB_PATH_ENV)
    if not db_path:
        raise RuntimeError(
            f"{DB_PATH_ENV} not set; cannot perform DB write needed for "
            f"the GDPR Art 18 423 path"
        )
    if not Path(db_path).is_file():
        raise RuntimeError(f"DB file not found at {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # Pre-flight: verify current state is 0 (so we know what to
        # restore to and so the test isn't a no-op against an already-
        # restricted user).
        row = conn.execute(
            "SELECT processing_restricted FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if row is None:
            raise RuntimeError(
                f"persona {email!r} not seeded — re-run seed-demo.ts"
            )
        original_value = int(row["processing_restricted"])
        if original_value != 0:
            raise RuntimeError(
                f"persona {email!r} already has processing_restricted="
                f"{original_value} — refusing to clobber state. Run "
                f"the cleanup SQL from the docstring before re-running."
            )

        # Flip ON.
        conn.execute(
            "UPDATE users SET processing_restricted = 1 WHERE email = ?",
            (email,),
        )
        conn.commit()

        try:
            yield
        finally:
            # Always restore to original (0).
            conn.execute(
                "UPDATE users SET processing_restricted = ? WHERE email = ?",
                (original_value, email),
            )
            conn.commit()
    finally:
        conn.close()


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_cl_sync_with_processing_restricted_returns_423_envelope(
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end: persona has processing_restricted=1 → cl_sync returns
    423 error envelope; DB has no new repo; restriction restored on exit."""
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    fixture_dir = manual_fixture_dir()
    if fixture_dir is None or not fixture_dir.is_dir():
        pytest.skip("POOL4_MANUAL_FIXTURE_DIR not set or path missing")

    unique_suffix = str(int(time.time() * 1000) % 1_000_000_000)
    new_repo_name = f"test-free-invited/pool4-cl-sync-423-{unique_suffix}"

    target_api_key = "cl_test_free_invited_key_for_development"

    with _temporarily_restrict_processing(TARGET_PERSONA_EMAIL):
        with pattern_a(
            "free",  # nominal — overlay below replaces saas_api_key
            repo_name_override=new_repo_name,
            extra_rc_fields={"saas_api_key": target_api_key},
        ):
            client = McpStdioClient.spawn()
            try:
                cell = ToolCell(
                    cell_id="phase2-cl_sync-processing_restricted_423",
                    tier="S",
                    tool="cl_sync",
                    scenario="processing_restricted_423",
                    persona="free_invited",
                    preconditions=[
                        "seeded_user_test_free_invited",
                        "user_processing_restricted_flag_set",
                    ],
                    cleanup=["restore_rc", "restore_processing_restricted"],
                    cleanup_justification=(
                        "cleanup is the test's load-bearing guarantee — "
                        "the temporarily_restrict_processing context "
                        "manager restores the flag in its finally; rc "
                        "restored by pattern_a"
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
            f"cl_sync should have returned an error envelope when caller "
            f"is processing-restricted; got {response}"
        )
        err_text = (
            (response.get("error") or "")
            + " "
            + (response.get("details") or "")
        ).lower()
        assert (
            "restrict" in err_text
            or "423" in err_text
            or "gdpr" in err_text
            or "art. 18" in err_text
            or "art 18" in err_text
        ), (
            f"error envelope should mention restriction/GDPR/423/Art 18; "
            f"got: {err_text[:300]!r}"
        )

        # DB defense: no new repo for this persona.
        with open_readonly() as conn:
            new_repo_row = fetch_repo_by_name(conn, new_repo_name)
            assert new_repo_row is None, (
                f"DB has a repos row for {new_repo_name!r} despite the "
                f"423 rejection — GDPR Art 18 gate has been bypassed."
            )

    # Post-test: verify cleanup actually restored the flag. If this
    # assertion fails, the persona is stuck at 1 and the recovery SQL
    # in the docstring must be run before re-running this cell.
    with open_readonly() as conn:
        row = conn.execute(
            "SELECT processing_restricted FROM users WHERE email = ?",
            (TARGET_PERSONA_EMAIL,),
        ).fetchone()
        assert row is not None
        assert int(row["processing_restricted"]) == 0, (
            f"CLEANUP FAILED: {TARGET_PERSONA_EMAIL} still has "
            f"processing_restricted={row['processing_restricted']}. "
            f"Run the recovery SQL from the cell docstring NOW before "
            f"running other Pool 4 tests."
        )
