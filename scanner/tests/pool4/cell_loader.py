"""Pool 4 cell loader (Python).

Mirror of the Pool 4 TypeScript loader (lives in the internal repo)
for the Python pytest runner. Loads `*.yml` cell files from a caller-
supplied directory and validates the same invariants the TypeScript
loader enforces:

  - cell_id matches filename (without .yml/.yaml extension)
  - tier in {A, B, S}
  - tool in 17-tool McpToolName union
  - persona in {free, starter, pro, business}
  - cleanup non-empty OR cleanup_justification set
  - skip_reason non-empty if present
  - tier-A: chain[] >= 2 steps, no invoke
  - tier-S/B: invoke + expected_response, no chain

A cell that fails validation here AND passes in the TS loader (or
vice versa) is a bug — both loaders must agree on the contract. The
yaml file format is the language-neutral source of truth; loaders
just interpret it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


VALID_TIERS = ("A", "B", "S")

VALID_TOOLS = (
    "cl_analyze_project",
    "cl_scan",
    "cl_scan_all",
    "cl_explain",
    "cl_action_guide",
    "cl_action_plan",
    "cl_check_updates",
    "cl_interim_standard",
    "cl_update_finding",
    "cl_update_finding_batch",
    "cl_verify_evidence",
    "cl_connect",
    "cl_sync",
    "cl_disconnect",
    "cl_delete",
    "cl_version",
    "cl_report_bug",
)

VALID_PERSONAS = ("free", "starter", "pro", "business")


@dataclass
class ToolCell:
    """Loaded representation of a Pool 4 yaml cell."""

    cell_id: str
    tier: str
    tool: str
    scenario: str
    persona: str
    preconditions: list[str]
    cleanup: list[str]
    cleanup_justification: str | None = None
    invoke: dict[str, Any] | None = None
    expected_response: dict[str, Any] | None = None
    saas_state_after: dict[str, Any] | None = None
    chain: list[dict[str, Any]] | None = None
    skip_reason: str | None = None
    references: list[str] = field(default_factory=list)


def load_all_cells(cells_dir: Path) -> dict[str, ToolCell]:
    """Load every `*.yml` cell under `cells_dir`. Returns a dict keyed
    by cell_id. Raises on duplicate cell_id or any validation failure.

    Skips placeholder files (`.keep`, `_*.yml`).
    """
    if not cells_dir.is_dir():
        raise FileNotFoundError(f"load_all_cells: not a directory: {cells_dir}")

    registry: dict[str, ToolCell] = {}
    for path in sorted(cells_dir.iterdir()):
        if path.suffix not in (".yml", ".yaml"):
            continue
        if path.name.startswith("_") or path.name == ".keep":
            continue
        with open(path, encoding="utf-8") as fp:
            raw = yaml.safe_load(fp)
        cell = _validate_cell(raw, path.name)
        if cell.cell_id in registry:
            raise ValueError(
                f"load_all_cells: duplicate cell_id {cell.cell_id!r} in {path.name}"
            )
        registry[cell.cell_id] = cell
    return registry


def _validate_cell(raw: Any, filename: str) -> ToolCell:
    """Throws on any malformed cell. Mirrors the TS validator."""
    if not isinstance(raw, dict):
        raise ValueError(
            f"validate_cell({filename}): root must be a mapping, got {type(raw).__name__}"
        )

    expected_id = filename.removesuffix(".yml").removesuffix(".yaml")
    if raw.get("cell_id") != expected_id:
        raise ValueError(
            f"validate_cell({filename}): cell_id {raw.get('cell_id')!r} does not "
            f"match filename-derived id {expected_id!r}"
        )

    tier = raw.get("tier")
    if tier not in VALID_TIERS:
        raise ValueError(
            f"validate_cell({filename}): tier {tier!r} not in {VALID_TIERS}"
        )

    tool = raw.get("tool")
    if tool not in VALID_TOOLS:
        raise ValueError(
            f"validate_cell({filename}): tool {tool!r} not in McpToolName union"
        )

    persona = raw.get("persona")
    if persona not in VALID_PERSONAS:
        raise ValueError(
            f"validate_cell({filename}): persona {persona!r} not in {VALID_PERSONAS}"
        )

    scenario = raw.get("scenario")
    if not isinstance(scenario, str) or not scenario:
        raise ValueError(
            f"validate_cell({filename}): scenario must be a non-empty string"
        )

    preconditions = raw.get("preconditions")
    if not isinstance(preconditions, list):
        raise ValueError(
            f"validate_cell({filename}): preconditions must be a list (use [] if none)"
        )

    cleanup = raw.get("cleanup")
    if not isinstance(cleanup, list):
        raise ValueError(
            f"validate_cell({filename}): cleanup must be a list"
        )
    cleanup_justification = raw.get("cleanup_justification")
    if not cleanup and not cleanup_justification:
        raise ValueError(
            f"validate_cell({filename}): cleanup is empty — must set "
            f"cleanup_justification explaining why no side effects to undo"
        )

    skip_reason = raw.get("skip_reason")
    if skip_reason is not None:
        if not isinstance(skip_reason, str) or not skip_reason:
            raise ValueError(
                f"validate_cell({filename}): skip_reason must be non-empty if set"
            )

    invoke = raw.get("invoke")
    expected_response = raw.get("expected_response")
    chain = raw.get("chain")

    if skip_reason is None:
        if tier == "A":
            if not isinstance(chain, list) or len(chain) < 2:
                raise ValueError(
                    f"validate_cell({filename}): tier-A cells require chain[] with >= 2 steps"
                )
            if invoke is not None:
                raise ValueError(
                    f"validate_cell({filename}): tier-A cells must use chain[], not invoke"
                )
        else:
            if not isinstance(invoke, dict):
                raise ValueError(
                    f"validate_cell({filename}): tier-{tier} cells require invoke{{tool, args}}"
                )
            if not isinstance(expected_response, dict):
                raise ValueError(
                    f"validate_cell({filename}): tier-{tier} cells require expected_response"
                )
            if chain is not None:
                raise ValueError(
                    f"validate_cell({filename}): tier-{tier} cells must use invoke, not chain[]"
                )

    return ToolCell(
        cell_id=raw["cell_id"],
        tier=tier,
        tool=tool,
        scenario=scenario,
        persona=persona,
        preconditions=preconditions,
        cleanup=cleanup,
        cleanup_justification=cleanup_justification,
        invoke=invoke,
        expected_response=expected_response,
        saas_state_after=raw.get("saas_state_after"),
        chain=chain,
        skip_reason=skip_reason,
        references=raw.get("references") or [],
    )
