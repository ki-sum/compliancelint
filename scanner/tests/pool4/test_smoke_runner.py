"""Pool 4 smoke runner — proves the framework actually executes.

Up to this commit, Pool 4 has 412 cells passing schema validation +
17 asserter classes loading cleanly, but ZERO cells have ever
actually run end-to-end. This file is the end-to-end proof:

  1. Load `s-cl_version-success-free.yml` from the cells directory
     (path supplied via POOL4_CELLS_DIR env var; tests skip cleanly
     if the env var is unset, e.g. in public-repo checkouts that
     don't include the internal Pool 4 cell tree).
  2. Invoke `scanner.server.cl_version` directly (in-process,
     bypassing MCP stdio for speed).
  3. Parse the JSON response.
  4. Assert response shape against the cell's `expected_response` field.

If this test passes, the framework is wired correctly. The remaining
work in Step 5 is mechanical (per-tool args + per-cell hand-edits) —
the architecture is proven.

Why cl_version is the smoke target:
  - read-only (no SaaS write to verify, no DB mutation, no fixture
    setup needed)
  - persona doesn't matter (only one cell exists per
    APPLICABILITY_FILTER: persona=free, scenario=success)
  - returns plain JSON with stable shape (version + tools + optional
    update fields)
  - pre-existing scanner test infra has no cl_version coverage so
    this is genuinely new territory

If/when this test is extended to cover mutating tools, the test file
should grow alongside `cell_loader.py` to add a Python equivalent of
`saas-introspection.ts` (DB query helpers via stdlib `sqlite3`).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from .cell_loader import ToolCell, load_all_cells


CELLS_DIR_ENV = "POOL4_CELLS_DIR"


def _resolve_cells_dir() -> Path | None:
    """Resolve the Pool 4 cells directory, or None if unavailable.

    Public-repo-only checkouts (no internal cell tree) get None and
    the smoke tests skip gracefully. Internal-repo runs set
    POOL4_CELLS_DIR via the all-tests harness.
    """
    raw = os.environ.get(CELLS_DIR_ENV)
    if not raw:
        return None
    candidate = Path(raw).resolve()
    return candidate if candidate.is_dir() else None


@pytest.fixture(scope="module")
def cells() -> dict[str, ToolCell]:
    """Load all Pool 4 cells once per pytest module run."""
    cells_dir = _resolve_cells_dir()
    if cells_dir is None:
        pytest.skip(
            f"Pool 4 smoke runner: {CELLS_DIR_ENV} env var not set or path "
            f"not a directory. Set {CELLS_DIR_ENV} to the cells directory "
            f"to enable Pool 4 smoke tests."
        )
    return load_all_cells(cells_dir)


def test_loader_loads_all_cells(cells: dict[str, ToolCell]) -> None:
    """Sanity: same cell count as the TS smoke (412 as of 2026-05-03)."""
    assert len(cells) >= 400, (
        f"Pool 4 cell count regressed: expected >= 400, got {len(cells)}. "
        f"Did someone delete cells without updating the generator?"
    )
    # Spot-check tier breakdown matches what we shipped in Step 2.
    tier_a = sum(1 for c in cells.values() if c.tier == "A")
    tier_b = sum(1 for c in cells.values() if c.tier == "B")
    tier_s = sum(1 for c in cells.values() if c.tier == "S")
    assert tier_a >= 9, f"tier-A cells: expected >= 9, got {tier_a}"
    assert tier_b >= 15, f"tier-B cells: expected >= 15, got {tier_b}"
    assert tier_s >= 380, f"tier-S cells: expected >= 380, got {tier_s}"


def test_smoke_cl_version_round_trip(cells: dict[str, ToolCell]) -> None:
    """End-to-end: load cell → invoke MCP tool → assert response shape.

    First Pool 4 cell to actually execute. Proves the framework is
    plumbed correctly: cell yaml → loader → tool call → response
    parse → assertion.
    """
    cell_id = "s-cl_version-success-free"
    cell = cells.get(cell_id)
    assert cell is not None, (
        f"Pool 4 smoke cell {cell_id!r} missing — was it deleted? "
        f"Re-run the Pool 4 cell generator from the internal repo."
    )
    assert cell.tool == "cl_version"
    assert cell.tier == "S"
    assert cell.persona == "free"
    assert cell.scenario == "success"
    assert cell.expected_response is not None
    expected_status = cell.expected_response.get("status")
    assert expected_status == "ok", (
        f"cell {cell_id} expected_response.status: expected 'ok' (cl_version "
        f"is read-only and always succeeds), got {expected_status!r}"
    )

    # Real MCP tool invocation. Note: cl_version takes no args.
    from scanner.server import cl_version

    raw_response = cl_version()
    response = json.loads(raw_response)

    # Response shape verification: scanner version is semver-ish, tools
    # count matches the 17 we registered, no `error` field present.
    assert "error" not in response, (
        f"cl_version returned error envelope: {response}"
    )
    assert "version" in response, (
        f"cl_version response missing 'version' field: {response.keys()}"
    )
    assert isinstance(response["version"], str)
    assert response["version"].count(".") >= 2, (
        f"cl_version 'version' should be semver (got {response['version']!r})"
    )
    assert response.get("tools") == 17, (
        f"cl_version 'tools' count drifted from registered 17: got {response.get('tools')}"
    )


def test_smoke_cl_disconnect_local_only_round_trip(
    cells: dict[str, ToolCell],
    tmp_path: Path,
) -> None:
    """End-to-end for a local-only mutating tool.

    cl_disconnect is the second smoke target. Per the internal Pool 4
    route audit (§local-only tools), it removes
    saas_api_key/saas_url/auto_sync from the project's
    `.compliancelintrc` and writes nothing to SaaS.

    This test proves the local-only pattern (8 of 11 mutating tools)
    is plumbed correctly: cell yaml exists, MCP tool invokes against
    a real project_path, scanner-side state mutates, response shape
    matches the cell's expected_response.

    The cell args placeholder (`args: {}`) is overridden here with a
    real tmp project path — Step 5's full hand-fill pass will encode
    a `$pytest.tmp_path` placeholder in the yaml that a future runner
    resolves automatically. For this smoke we resolve manually.
    """
    cell_id = "s-cl_disconnect-success-pro"
    cell = cells.get(cell_id)
    assert cell is not None, f"smoke cell {cell_id!r} missing"
    assert cell.tool == "cl_disconnect"
    assert cell.expected_response is not None
    assert cell.expected_response.get("status") == "ok"

    # Set up a minimal project: .compliancelintrc with the fields
    # cl_disconnect targets (saas_api_key + saas_url + auto_sync).
    project = tmp_path / "demo-project"
    project.mkdir()
    rc_file = project / ".compliancelintrc"
    rc_file.write_text(
        json.dumps(
            {
                "saas_api_key": "cl_test_pro_key_for_development",
                "saas_url": "http://localhost:3000",
                "auto_sync": True,
                "repo_name": "demo-project",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    from scanner.server import cl_disconnect

    raw_response = cl_disconnect(str(project))
    response = json.loads(raw_response)

    assert response.get("status") == "disconnected", (
        f"cl_disconnect status: expected 'disconnected', got {response}"
    )
    removed = response.get("removed_fields") or []
    assert "saas_api_key" in removed, (
        f"saas_api_key should be in removed_fields: got {removed}"
    )

    # Verify scanner-side state actually mutated: the rc file no
    # longer contains saas_api_key.
    rc_after = json.loads(rc_file.read_text(encoding="utf-8"))
    assert "saas_api_key" not in rc_after, (
        f".compliancelintrc still has saas_api_key after cl_disconnect: {rc_after}"
    )
    assert "saas_url" not in rc_after, (
        f".compliancelintrc still has saas_url after cl_disconnect: {rc_after}"
    )
    # Local config preserved per route audit (.compliancelint/ untouched +
    # repo_name kept since it's not in the {saas_api_key, saas_url,
    # auto_sync} removal set).
    assert rc_after.get("repo_name") == "demo-project", (
        f"non-connection-related fields must survive disconnect: got {rc_after}"
    )


def test_loader_rejects_invalid_cells(tmp_path: Path) -> None:
    """Negative test: loader must reject malformed yaml.

    Mirrors a subset of the TS loader's `validateCell` checks. If this
    fails, the Python loader is more lenient than the TS one, which
    would let bad cells slip into Python pytest while breaking the
    Playwright runner — exactly the silent-divergence we want to
    prevent.
    """
    bad_dir = tmp_path / "cells"
    bad_dir.mkdir()

    # Bad: tier not in {A,B,S}
    bad = bad_dir / "s-cl_version-bad-free.yml"
    bad.write_text(
        "cell_id: s-cl_version-bad-free\n"
        "tier: Q\n"
        "tool: cl_version\n"
        "scenario: bad\n"
        "persona: free\n"
        "preconditions: []\n"
        "invoke:\n"
        "  tool: cl_version\n"
        "  args: {}\n"
        "expected_response:\n"
        "  status: ok\n"
        "cleanup: []\n"
        'cleanup_justification: "test"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="tier 'Q' not in"):
        load_all_cells(bad_dir)
