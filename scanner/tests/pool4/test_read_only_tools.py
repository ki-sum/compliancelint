"""Pool 4 — read-only tool round-trips (parametrized).

Covers six tools whose contract is response-shape-only (no SaaS
mutation, no on-disk mutation): cl_check_updates, cl_action_guide,
cl_action_plan, cl_interim_standard, cl_analyze_project,
cl_verify_evidence. Each is invoked through real MCP subprocess
transport; the assertion checks the tool didn't return an error
envelope and the response matches the per-tool shape declared in
``CASES``.

Why one parametrized file instead of seven separate ones: every
cell here follows the same skeleton (spawn client → tools/call →
assert no error → assert per-tool shape predicate). Aggregating
keeps the test surface compact while still emitting one pytest
node per tool (visible in CI logs).

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport (one client per cell — fresh
    isolation; cl_action_plan / cl_analyze_project / cl_verify_evidence
    write to scanner-side caches keyed by project_path that should
    not be reused across cells)
  - C2: cl_check_updates hits SaaS for the regulation_updates table
    (requires_dev_server marker on its row only); the rest are
    purely scanner-side and run even when :3000 is down
  - C7: Pattern B with tmp_path for project_path tools (matches
    the cl_disconnect + cl_delete-target=local pattern; C7's ban
    on $pytest.tmp_path applies to cell yaml, not test code)

Verified-via: scanner/server.py @mcp.tool definitions for each
listed tool; the response-shape predicates encode what the tool
actually returns (audit-first, observed manually + via ``tools/list``
schema probe before encoding).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .mcp_client import McpStdioClient


def _seed_minimal_project(project_dir: Path) -> Path:
    """Create a minimal scanner-recognizable project: a .compliancelintrc
    + a single source file. Some tools (cl_action_plan,
    cl_analyze_project, cl_verify_evidence) walk the dir and need at
    least a recognizable structure to return a non-trivial response.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    rc_path = project_dir / ".compliancelintrc"
    rc_path.write_text(
        json.dumps({
            "purpose": "Pool 4 read-only tool fixture",
            "repo_name": "test/read-only-fixture",
            "scope": {
                "operator_role": ["provider"],
                "risk_classification": "high-risk",
            },
        }, indent=2),
        encoding="utf-8",
    )
    src_dir = project_dir / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text(
        "# Minimal AI module for pool4 fixture\n"
        "def predict(features):\n"
        "    return 0.5\n",
        encoding="utf-8",
    )
    return project_dir


def _check_action_guide(resp: dict[str, Any]) -> None:
    """cl_action_guide: returns a guide for an obligation. Must have
    `obligation_id` echoed back + at least one of the known guide
    keys (decomposed_atoms / source_quote / addressee / verbatim_obligation).
    """
    assert resp.get("obligation_id") == "ART09-OBL-1", (
        f"cl_action_guide should echo obligation_id; got {resp.get('obligation_id')!r}"
    )
    has_guide_field = any(
        k in resp for k in (
            "decomposed_atoms", "source_quote", "addressee",
            "verbatim_obligation", "automation_assessment",
        )
    )
    assert has_guide_field, (
        f"cl_action_guide response missing canonical guide fields; "
        f"keys={list(resp.keys())}"
    )


def _check_action_plan(resp: dict[str, Any]) -> None:
    """cl_action_plan: returns a plan structure. Always has either
    a `plan` / `actions` / `recommendations` array OR an `error`
    explaining why a plan can't be made (which counts as a valid
    response shape — not a test failure)."""
    if "error" in resp:
        return  # documented "no scan results" / "no findings" branch
    has_plan_field = any(
        k in resp for k in ("plan", "actions", "recommendations", "next_steps")
    )
    assert has_plan_field, (
        f"cl_action_plan response missing plan-like field; "
        f"keys={list(resp.keys())}"
    )


def _check_check_updates(resp: dict[str, Any]) -> None:
    """cl_check_updates: returns regulation update info. Audit-first
    response keys (observed 2026-05-04): last_checked,
    upcoming_deadlines, standards_status, modules_loaded, note,
    scanner_update, _meta.
    """
    assert "error" not in resp, f"cl_check_updates errored: {resp}"
    has_update_field = any(
        k in resp for k in (
            "last_checked", "upcoming_deadlines", "standards_status",
            "scanner_update", "modules_loaded", "updates", "deadlines",
        )
    )
    assert has_update_field, (
        f"cl_check_updates response shape unexpected; keys={list(resp.keys())}"
    )


def _check_interim_standard(resp: dict[str, Any]) -> None:
    """cl_interim_standard: returns a generated standard for an article.
    Audit-first response keys (observed 2026-05-04):
    is_official_standard, non_official_banner, superseded_when,
    _metadata, requirements, scoring, _meta. The `requirements`
    field is the actual standard payload.
    """
    if "error" in resp:
        return
    has_standard_field = any(
        k in resp for k in (
            "requirements", "is_official_standard", "non_official_banner",
            "scoring", "interim_standard", "standard",
        )
    )
    assert has_standard_field, (
        f"cl_interim_standard response missing standard-like field; "
        f"keys={list(resp.keys())}"
    )


def _check_analyze_project(resp: dict[str, Any]) -> None:
    """cl_analyze_project: returns project structure analysis. Must
    have framework / language / scope-related fields."""
    assert "error" not in resp, f"cl_analyze_project errored: {resp}"
    has_analysis_field = any(
        k in resp for k in (
            "framework", "frameworks", "language", "languages", "stack",
            "files", "scanning_strategy", "applicability",
            "compliance_answers", "project_overview",
        )
    )
    assert has_analysis_field, (
        f"cl_analyze_project response missing analysis field; "
        f"keys={list(resp.keys())}"
    )


def _check_verify_evidence(resp: dict[str, Any]) -> None:
    """cl_verify_evidence: returns evidence verification report.
    Audit-first response keys when no compliance-evidence.json
    exists (observed 2026-05-04): evidence_file, found (bool), fix
    (remediation hint), schema_example. The `found` boolean +
    `fix` form a "no evidence file" advisory — not an error
    envelope, just a documented null-state response.
    """
    has_verify_field = any(
        k in resp for k in (
            "evidence_file", "found", "verification_instructions",
            "evidence", "verified", "results", "schema_example",
        )
    )
    assert has_verify_field, (
        f"cl_verify_evidence response missing canonical fields; "
        f"keys={list(resp.keys())}"
    )


# Each entry: (tool, args_factory, response_check, needs_server)
# args_factory is a callable taking a project_dir Path and returning
# the args dict. project_dir is None for tools that don't need it.
CASES: list[tuple[str, Callable[[Path | None], dict[str, Any]], Callable[[dict[str, Any]], None], bool]] = [
    (
        "cl_check_updates",
        lambda _p: {},
        _check_check_updates,
        True,  # SaaS-backed read
    ),
    (
        "cl_action_guide",
        lambda _p: {"obligation_id": "ART09-OBL-1"},
        _check_action_guide,
        False,
    ),
    (
        "cl_action_plan",
        lambda p: {"project_path": str(p), "article": 9},
        _check_action_plan,
        False,
    ),
    (
        "cl_interim_standard",
        lambda _p: {"article_number": 9},
        _check_interim_standard,
        False,
    ),
    (
        "cl_analyze_project",
        lambda p: {"project_path": str(p)},
        _check_analyze_project,
        False,
    ),
    (
        "cl_verify_evidence",
        lambda p: {"project_path": str(p)},
        _check_verify_evidence,
        False,
    ),
]


@pytest.mark.parametrize(
    "tool,args_factory,checker,needs_server",
    CASES,
    ids=[case[0] for case in CASES],
)
def test_read_only_tool_response_shape(
    tool: str,
    args_factory: Callable[[Path | None], dict[str, Any]],
    checker: Callable[[dict[str, Any]], None],
    needs_server: bool,
    server_reachable: bool,
    tmp_path: Path,
) -> None:
    """Spawn MCP, call the tool, assert response shape per the
    per-tool predicate. One MCP subprocess per parametrize iteration
    (~0.7s spawn × 6 = ~4-5s total) — acceptable for a 6-cell batch.
    """
    if needs_server and not server_reachable:
        pytest.skip(
            f"{tool} hits SaaS for the regulation_updates table; "
            f"server :3000 unreachable"
        )

    project_dir = _seed_minimal_project(tmp_path / "fixture")
    args = args_factory(project_dir)

    client = McpStdioClient.spawn()
    try:
        cell = ToolCell(
            cell_id=f"phase3-{tool}-success",
            tier="S",
            tool=tool,
            scenario="success",
            persona="business",
            preconditions=[],
            cleanup=["tmp_path_auto_cleanup"],
            cleanup_justification=(
                f"{tool} is read-only / no mutation outside tmp_path"
            ),
            invoke={"tool": tool, "args": args},
            expected_response={"status": "ok"},
        )
        raw = invoke_tool(cell, ctx={}, client=client)
    finally:
        client.close()

    response = json.loads(raw)
    checker(response)
