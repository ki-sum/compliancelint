"""Pool 4 — cl_action_guide across multiple obligation_ids.

cl_action_guide returns the deontic-decomposed guidance for a
single obligation. Parametrized across one obligation_id per
seeded high-risk article so the test catches regressions in the
per-article obligation JSONs at scanner/obligations/.

Articles chosen: 9 / 10 / 13 / 14 / 15 / 17. Each obligation_id
follows the convention ARTNN-OBL-1 (first obligation in the
deontic decomposition). If a future refactor renumbers the
obligations, this list updates accordingly.

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C7: read-only; no fixture project needed

Verified-via: scanner/server.py cl_action_guide + the per-article
obligation JSONs at scanner/obligations/artNN.json.
"""
from __future__ import annotations

import json

import pytest

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .mcp_client import McpStdioClient


OBLIGATIONS = [
    "ART09-OBL-1",
    "ART10-OBL-1",
    "ART13-OBL-1",
    "ART14-OBL-1",
    "ART15-OBL-1",
    "ART17-OBL-1",
]


@pytest.mark.parametrize("oid", OBLIGATIONS, ids=lambda o: o.lower())
def test_cl_action_guide_returns_guide_for_obligation(oid: str) -> None:
    """End-to-end: cl_action_guide(oid) → response echoes oid +
    has at least one canonical guide field."""
    client = McpStdioClient.spawn()
    try:
        cell = ToolCell(
            cell_id=f"phase3-cl_action_guide-{oid.lower()}",
            tier="S",
            tool="cl_action_guide",
            scenario="covered_obligation",
            persona="business",
            preconditions=[],
            cleanup=[],
            cleanup_justification="cl_action_guide is read-only",
            invoke={
                "tool": "cl_action_guide",
                "args": {"obligation_id": oid},
            },
            expected_response={"status": "ok"},
        )
        raw = invoke_tool(cell, ctx={}, client=client)
    finally:
        client.close()

    response = json.loads(raw)

    assert "error" not in response, (
        f"cl_action_guide({oid}) errored: {response}"
    )
    assert response.get("obligation_id") == oid, (
        f"oid echo mismatch; expected {oid!r}, got {response.get('obligation_id')!r}"
    )
    has_guide = any(
        k in response for k in (
            "decomposed_atoms", "source_quote", "addressee",
            "verbatim_obligation", "automation_assessment",
        )
    )
    assert has_guide, (
        f"cl_action_guide({oid}) missing canonical guide fields; "
        f"keys={list(response.keys())}"
    )
