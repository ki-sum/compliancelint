"""Pool 4 — cl_report_bug local-only round-trip.

cl_report_bug builds a bundle file at
``$HOME/compliancelint-bugreport-{ts}.md`` per scanner/server.py.
The bundle aggregates recent scanner.log entries + MCP transport
metadata + redacted environment for the user to attach to a GitHub
bug report. No SaaS upload. No state mutation outside HOME.

This test isolates HOME via env override on the MCP subprocess
(``McpStdioClient.spawn(env=...)``) so the bundle lands in tmp_path
instead of the user's actual home dir. Verifies:
  - response shape: bundle_path / size_bytes / next_steps
  - bundle_path resolves under our overridden HOME
  - bundle file exists on disk and is non-empty

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C2 / C3: not applicable
  - C4: 1-layer (response + filesystem)
  - C7: tmp_path is the env-overridden HOME for full isolation
  - C8: tmp_path auto-cleaned at session end

Verified-via: scanner/server.py @mcp.tool cl_report_bug + the
build_bundle helper in core/bug_report.
"""
from __future__ import annotations

import json
from pathlib import Path

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .mcp_client import McpStdioClient


def test_cl_report_bug_writes_bundle_under_home(tmp_path: Path) -> None:
    """End-to-end: cl_report_bug → bundle file lands under
    overridden HOME; response carries the path + size."""
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()

    # Override both HOME (POSIX-style) and USERPROFILE (Windows). The
    # scanner uses Path.home() which checks USERPROFILE first on
    # Windows; setting both keeps the test cross-platform.
    client = McpStdioClient.spawn(env={
        "HOME": str(fake_home),
        "USERPROFILE": str(fake_home),
    })
    try:
        cell = ToolCell(
            cell_id="phase3-cl_report_bug-success",
            tier="S",
            tool="cl_report_bug",
            scenario="success",
            persona="business",
            preconditions=["home_overridden_to_tmp"],
            cleanup=["tmp_path_auto_cleanup"],
            cleanup_justification=(
                "tmp_path auto-removed at session end; bundle lives "
                "under overridden HOME so the user's real home dir "
                "stays untouched."
            ),
            invoke={"tool": "cl_report_bug", "args": {}},
            expected_response={"status": "ok"},
        )
        raw = invoke_tool(cell, ctx={}, client=client)
    finally:
        client.close()

    response = json.loads(raw)

    assert "error" not in response, (
        f"cl_report_bug returned error envelope: {response}"
    )
    bundle_path_str = response.get("bundle_path")
    assert bundle_path_str, (
        f"cl_report_bug response missing bundle_path; got {response}"
    )
    bundle_path = Path(bundle_path_str)
    assert bundle_path.is_file(), (
        f"bundle_path doesn't point to an existing file: {bundle_path}"
    )

    # Bundle must land UNDER our overridden HOME (proof the env
    # override worked end-to-end). On Windows the actual user HOME
    # would be C:\Users\<who>; if it landed there, the override
    # silently failed and we'd be writing to the user's real dir.
    fake_home_resolved = fake_home.resolve()
    bundle_resolved = bundle_path.resolve()
    assert str(bundle_resolved).startswith(str(fake_home_resolved)), (
        f"bundle landed outside overridden HOME — env override "
        f"silently failed. bundle={bundle_resolved} fake_home="
        f"{fake_home_resolved}"
    )

    # Non-empty: build_bundle should produce at least the header +
    # scanner.log tail + env section (~ a few KB minimum on a real
    # bundle, but use a permissive floor so a stripped-down build
    # still passes).
    size = response.get("size_bytes", 0)
    assert size > 0, (
        f"bundle reported size_bytes={size}; build_bundle should always "
        f"produce non-empty content"
    )

    next_steps = response.get("next_steps", "")
    assert isinstance(next_steps, str) and next_steps, (
        f"cl_report_bug response missing next_steps text"
    )
    assert "github" in next_steps.lower() or "support" in next_steps.lower(), (
        f"next_steps should hint at where to send the bundle "
        f"(GitHub issue or email); got {next_steps[:200]!r}"
    )
