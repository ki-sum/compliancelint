"""Pool 4 smoke runner — proves the real-flow framework executes.

Phase 1 milestone test. Up to commit eb83ff4 the smoke ran via
in-process Python (``from scanner.server import cl_version``); per
Pool 4 hard constraint C1 that pattern is now banned. This file is
the post-pivot version: real MCP subprocess transport, JSON-RPC over
stdio, end-to-end through the same code path a Claude Code session
hits.

What's covered in Phase 1:
  - ``test_loader_loads_all_cells`` — sanity that the cells dir is
    populated (unchanged from pre-pivot)
  - ``test_smoke_cl_version_round_trip`` — first cell to actually
    execute end-to-end through MCP subprocess. Proves spawn,
    handshake, tools/call, response unwrap, JSON parse, assertion.
  - ``test_smoke_cl_explain_covered_article_via_dispatcher`` — same,
    via the cell-driven dispatcher path with non-trivial args
    (regulation/article literals)
  - ``test_loader_rejects_invalid_cells`` — negative test (unchanged)

What's NOT covered yet:
  - The parametrized matrix smoke over all HAND-EDITED cells. Phase
    2-4 of the plan re-introduces it once per-tool fixture builders
    + cross-system asserters land.
  - cl_disconnect: needs Pattern A fixture overlay (rc seed + restore
    around the call). Phase 3 implements that via the
    ``fixtures.pattern_b`` builder + a per-cell fixture.

If THIS file passes, the framework is plumbed correctly: cell yaml →
loader → dispatcher → real MCP subprocess → tool handler → JSON
response → assertion. Phase 2-5 work is mechanical (per-tool args,
per-cell hand-edits, asserters). The architecture is proven.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from .cell_loader import ToolCell, load_all_cells
from .dispatcher import invoke_tool
from .mcp_client import McpStdioClient


CELLS_DIR_ENV = "POOL4_CELLS_DIR"


def _resolve_cells_dir() -> Path | None:
    """Resolve the Pool 4 cells directory, or None if unavailable.

    Public-repo-only checkouts (no internal cell tree) get None and
    the smoke tests skip gracefully. Internal-repo runs set
    ``POOL4_CELLS_DIR`` via the all-tests harness.
    """
    raw = os.environ.get(CELLS_DIR_ENV)
    if not raw:
        return None
    candidate = Path(raw).resolve()
    return candidate if candidate.is_dir() else None


@pytest.fixture(scope="module")
def cells() -> dict[str, ToolCell]:
    """Load all Pool 4 cells once per module run."""
    cells_dir = _resolve_cells_dir()
    if cells_dir is None:
        pytest.skip(
            f"Pool 4 smoke runner: {CELLS_DIR_ENV} env var not set or path "
            f"not a directory. Set {CELLS_DIR_ENV} to the cells directory "
            f"to enable Pool 4 smoke tests."
        )
    return load_all_cells(cells_dir)


def test_loader_loads_all_cells(cells: dict[str, ToolCell]) -> None:
    """Sanity floor — catches 'someone deleted the cells dir' but
    tolerates ongoing APPLICABILITY_FILTER refinements that legitimately
    shrink the cell tree.

    The real coverage signal is per-cell PASS via the matrix smoke
    once Phase 2-5 add per-tool builders. Don't lower the floor here
    when filter refinements happen — let it be the canary.
    """
    assert len(cells) >= 200, (
        f"Pool 4 cell count regressed below sanity floor: got {len(cells)}. "
        f"Did the cells directory get deleted?"
    )
    tier_a = sum(1 for c in cells.values() if c.tier == "A")
    tier_b = sum(1 for c in cells.values() if c.tier == "B")
    tier_s = sum(1 for c in cells.values() if c.tier == "S")
    assert tier_a >= 5, f"tier-A cells: expected >= 5, got {tier_a}"
    assert tier_b >= 10, f"tier-B cells: expected >= 10, got {tier_b}"
    assert tier_s >= 150, f"tier-S cells: expected >= 150, got {tier_s}"


def test_smoke_cl_version_round_trip(
    cells: dict[str, ToolCell],
    mcp_client_session: McpStdioClient,
) -> None:
    """End-to-end: load cell → invoke MCP tool over real subprocess
    → assert response shape.

    The first Pool 4 cell to run through real MCP transport. cl_version
    has no args, no SaaS dependency, no fixture project — the simplest
    possible cell — so a green here means the framework's spawn /
    handshake / call / response unwrap path all work.

    Why ``mcp_client_session`` (session-scoped) for cl_version: pure-
    read tool, no state leakage possible across cells. Reusing one
    subprocess across all session-scoped reads saves the ~0.5-1s
    Windows startup × N reads.
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

    raw_response = invoke_tool(cell, ctx={}, client=mcp_client_session)
    response = json.loads(raw_response)

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
        f"cl_version 'tools' count drifted from registered 17: "
        f"got {response.get('tools')}"
    )


def test_smoke_cl_explain_covered_article_via_dispatcher(
    cells: dict[str, ToolCell],
    mcp_client_session: McpStdioClient,
) -> None:
    """End-to-end for a read-only tool with a rich payload, exercising
    the dispatcher's non-trivial-args path (regulation+article literals).

    Per scanner/server.py:786-836 cl_explain returns the obligation
    explanation plus Q1 anti-hallucination fields:
      - ``verbatim_obligations[]`` — character-for-character EU AI Act text
      - ``eur_lex_official_url`` — canonical PDF link
      - ``disclaimer`` — explicit "prose fields are paraphrased" warning

    If those fields disappear in a future scanner refactor, this test
    fails RED — exactly the regression detection Pool 4 was built to
    catch via real MCP transport.
    """
    cell_id = "s-cl_explain-covered_article-free"
    cell = cells.get(cell_id)
    assert cell is not None, f"smoke cell {cell_id!r} missing"
    assert cell.tool == "cl_explain"
    assert cell.invoke is not None
    assert cell.invoke["args"]["article"] == 9, (
        f"cell args.article should be 9 (canonical risk-mgmt article); "
        f"got {cell.invoke['args']}"
    )

    raw_response = invoke_tool(cell, ctx={}, client=mcp_client_session)
    response = json.loads(raw_response)

    assert "verbatim_obligations" in response, (
        f"cl_explain response missing 'verbatim_obligations' (Q1 anti-"
        f"hallucination enrichment): keys={list(response.keys())}"
    )
    assert isinstance(response["verbatim_obligations"], list)
    assert len(response["verbatim_obligations"]) > 0, (
        f"Article 9 verbatim_obligations should be non-empty (19 obligations "
        f"per scanner/obligations/art09.json); got 0"
    )
    assert "eur_lex_official_url" in response, (
        f"cl_explain response missing 'eur_lex_official_url': "
        f"{list(response.keys())}"
    )
    assert "eur-lex.europa.eu" in response["eur_lex_official_url"], (
        f"eur_lex_official_url should point to EUR-Lex domain: "
        f"{response['eur_lex_official_url']!r}"
    )
    assert "disclaimer" in response, (
        f"cl_explain response missing 'disclaimer' (Q1 anti-hallucination)"
    )
    assert "verbatim" in response["disclaimer"].lower(), (
        f"disclaimer should mention verbatim/paraphrase distinction: "
        f"{response['disclaimer'][:120]!r}"
    )


def test_loader_rejects_invalid_cells(tmp_path: Path) -> None:
    """Negative test: loader must reject malformed yaml.

    Mirrors a subset of the TS loader's ``validateCell`` checks. If
    this fails, the Python loader is more lenient than the TS one,
    which would let bad cells slip into Python pytest while breaking
    the Playwright runner — exactly the silent-divergence we want to
    prevent.
    """
    bad_dir = tmp_path / "cells"
    bad_dir.mkdir()

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
