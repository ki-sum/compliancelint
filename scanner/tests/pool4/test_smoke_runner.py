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
from .dispatcher import invoke_tool


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
    # Floor numbers below: regression detectors. Set ~5% below current
    # truth so APPLICABILITY_FILTER refinements that legitimately drop
    # cells (e.g. filtering scenarios that aren't actually testable —
    # cl_check_updates non-success scenarios were removed 2026-05-03)
    # don't fail this assert spuriously. If the floor breaks, either
    # cells got accidentally deleted OR the filter dropped a category
    # — re-run smoke and decide before lowering.
    assert len(cells) >= 360, (
        f"Pool 4 cell count regressed: expected >= 360, got {len(cells)}. "
        f"Did someone delete cells without updating the generator?"
    )
    tier_a = sum(1 for c in cells.values() if c.tier == "A")
    tier_b = sum(1 for c in cells.values() if c.tier == "B")
    tier_s = sum(1 for c in cells.values() if c.tier == "S")
    assert tier_a >= 9, f"tier-A cells: expected >= 9, got {tier_a}"
    assert tier_b >= 15, f"tier-B cells: expected >= 15, got {tier_b}"
    assert tier_s >= 350, f"tier-S cells: expected >= 350, got {tier_s}"


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
    """End-to-end for a local-only mutating tool, via the cell dispatcher.

    cl_disconnect is the second smoke target. Per the internal Pool 4
    route audit (§local-only tools), it removes
    saas_api_key/saas_url/auto_sync from the project's
    `.compliancelintrc` and writes nothing to SaaS.

    This test proves the local-only pattern (8 of 11 mutating tools)
    AND the cell-driven dispatcher pattern (cell yaml drives the
    invoke; runner resolves $pytest.tmp_path placeholder at runtime).
    """
    cell_id = "s-cl_disconnect-success-pro"
    cell = cells.get(cell_id)
    assert cell is not None, f"smoke cell {cell_id!r} missing"
    assert cell.tool == "cl_disconnect"
    assert cell.expected_response is not None
    assert cell.expected_response.get("status") == "ok"

    # Set up a minimal project at $pytest.tmp_path/demo-project — the
    # cell's args.project_path placeholder resolves to ctx["tmp_path"].
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

    # Dispatcher resolves $pytest.tmp_path placeholder + invokes the
    # named MCP tool from scanner.server.
    raw_response = invoke_tool(cell, ctx={"tmp_path": project})
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


def test_smoke_cl_explain_covered_article_via_dispatcher(
    cells: dict[str, ToolCell],
) -> None:
    """End-to-end for a read-only tool that returns rich payload.

    cl_explain (article=9) is the third smoke target. Per
    scanner/server.py:786-836, it returns the obligation explanation
    plus Q1 anti-hallucination enrichment fields:
      - verbatim_obligations[] — character-for-character EU AI Act text
      - eur_lex_official_url — canonical PDF link
      - disclaimer — explicit "prose fields are paraphrased" warning

    This test exercises the dispatcher with a non-tmp_path placeholder
    set (regulation + article are literal values, no resolution needed)
    and verifies the response carries the Q1 enrichment fields. If
    those fields go missing in a future scanner refactor, this test
    fails RED — exactly the regression detection Pool 4 was built for.
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

    raw_response = invoke_tool(cell, ctx={})
    response = json.loads(raw_response)

    # Verify Q1 anti-hallucination enrichment present.
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
        f"cl_explain response missing 'eur_lex_official_url': {list(response.keys())}"
    )
    assert "eur-lex.europa.eu" in response["eur_lex_official_url"], (
        f"eur_lex_official_url should point to EUR-Lex domain: {response['eur_lex_official_url']!r}"
    )
    assert "disclaimer" in response, (
        f"cl_explain response missing 'disclaimer' (Q1 anti-hallucination)"
    )
    assert "verbatim" in response["disclaimer"].lower(), (
        f"disclaimer should mention verbatim/paraphrase distinction: "
        f"{response['disclaimer'][:120]!r}"
    )


def _find_hand_edited_cells(cells_dir: Path) -> list[str]:
    """Return cell_ids whose yaml file contains the # HAND-EDITED marker.

    yaml.safe_load strips comments, so the marker can't be discovered
    via the parsed cell. We grep the raw text instead. Read only the
    first 800 bytes (header zone) — the marker is by convention on
    line 2-3.
    """
    if not cells_dir.is_dir():
        return []
    found: list[str] = []
    for path in sorted(cells_dir.glob("*.yml")):
        try:
            with open(path, encoding="utf-8") as fp:
                head = fp.read(800)
        except OSError:
            continue
        if "HAND-EDITED" in head:
            found.append(path.stem)
    return found


def _cell_needs_fixture_ctx(cell: ToolCell) -> bool:
    """Return True if any cell.invoke.args value uses a $-placeholder
    that requires runtime ctx setup (tmp_path, persona email, etc.).
    Cells with only literal-value args can run via the parametrized
    matrix smoke; cells with placeholders need dedicated tests that
    seed the right fixture state.
    """
    if not cell.invoke or "args" not in cell.invoke:
        return False
    for value in (cell.invoke["args"] or {}).values():
        if isinstance(value, str) and value.startswith("$"):
            return True
    return False


# Collected at import time. Stays empty when env var is unset (public-
# repo CI without the cell tree); pytest's parametrize then expands to
# zero cases and the test is silently absent — same as how dedicated
# tests skip when the cells fixture skips.
_CELLS_DIR_FOR_PARAMETRIZE = _resolve_cells_dir()
if _CELLS_DIR_FOR_PARAMETRIZE is not None:
    _HAND_EDITED_IDS = _find_hand_edited_cells(_CELLS_DIR_FOR_PARAMETRIZE)
else:
    _HAND_EDITED_IDS = []


@pytest.mark.parametrize("cell_id", _HAND_EDITED_IDS, ids=lambda cid: cid)
def test_matrix_smoke_simple_args_cells(
    cells: dict[str, ToolCell],
    cell_id: str,
) -> None:
    """Parametrized matrix smoke — auto-discovers every HAND-EDITED
    cell with simple (no-placeholder) args and dispatches it.

    Cells that need fixture-driven ctx (e.g. $pytest.tmp_path) are
    skipped here and covered by dedicated tests above.

    Why parametrize over discovered cells (not a static list): when
    Step 5 hand-fills more cells, this test's coverage extends
    automatically without test_smoke_runner.py edits. New cell yaml
    + # HAND-EDITED marker → next pytest run picks it up.

    The assertion is intentionally minimal (status field matches
    expected_response.status). Per-tool deep assertions (e.g. Q1
    anti-hallucination payload check) live in dedicated tests
    above. The matrix smoke is a "did the dispatcher reach the
    tool and get a response of the right outcome class" sanity
    floor — it catches cell-args-out-of-sync-with-scanner-signature
    drift.
    """
    cell = cells.get(cell_id)
    assert cell is not None, f"hand-edited cell {cell_id!r} missing from registry"

    if _cell_needs_fixture_ctx(cell):
        pytest.skip(
            f"cell {cell_id} uses $-placeholder args that need fixture "
            f"context; covered by a dedicated test above"
        )

    raw_response = invoke_tool(cell, ctx={})
    response = json.loads(raw_response)

    expected_status = (cell.expected_response or {}).get("status")
    if expected_status == "ok":
        assert "error" not in response, (
            f"cell {cell_id} expected status='ok' but response has error: "
            f"{response.get('error')!r}"
        )
    elif expected_status == "error":
        assert "error" in response, (
            f"cell {cell_id} expected status='error' but response has no "
            f"error field: keys={list(response.keys())}"
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
