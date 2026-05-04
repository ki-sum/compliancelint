"""Pool 4 Phase 3 starter — cl_disconnect local-only round-trip.

cl_disconnect is the simplest of the 8 local-only mutating tools
per the Pool 4 cross-system route audit:

  > cl_disconnect — Removes saas_api_key etc. from .compliancelintrc
  > Local-only — change becomes visible to SaaS only on next cl_sync
  > (or never, since cl_disconnect explicitly forgets the binding).

What this test proves:
  - The Pool 4 framework supports local-only mutating tools end-
    to-end via Pattern B (tmp_path scenario fixture).
  - cl_disconnect's response shape (status: "disconnected" +
    removed_fields[]) and on-disk rc mutation match the audit's
    description.
  - Non-saas fields (repo_name, scope, etc.) are preserved — only
    the dashboard-binding fields are removed.

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C2 / C3: not applicable — cl_disconnect doesn't hit SaaS or
    require seeded users; no markers needed.
  - C4: 1-layer (response + on-disk rc) — local-only path
  - C7: Pattern B (tmp_path + seeded rc); no Pattern A overlay
    because we want full isolation from the manual-fixture rc
    (cl_disconnect would mutate it irreversibly during the test
    window, defeating Pattern A's restore-on-exit guarantee).
  - C8: tmp_path auto-cleans at session end; no SaaS state to purge.

Verified-via: scanner/server.py:cl_disconnect (the local-only
removed_fields branch of the rc rewrite path).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .mcp_client import McpStdioClient


import pytest

from .fixtures import PERSONAS


@pytest.mark.parametrize(
    "persona_key",
    ["free", "starter", "pro", "business"],
    ids=lambda k: f"persona-{k}",
)
def test_cl_disconnect_strips_dashboard_binding_preserves_other_fields(
    persona_key: str,
    tmp_path: Path,
) -> None:
    """End-to-end across personas: tmp project with seeded rc using
    the persona's api_key → cl_disconnect strips saas_api_key +
    saas_url + auto_sync, leaves repo_name + scope alone.

    Parametrized: cl_disconnect is tier-agnostic but exercising 4
    api_keys catches drift if any persona's seeded key shape becomes
    invalid (e.g., a future seed-demo refactor breaks one tier).
    """
    persona = PERSONAS[persona_key]
    project_dir = tmp_path / f"pool4-disconnect-{persona_key}"
    project_dir.mkdir()
    rc_path = project_dir / ".compliancelintrc"
    rc_path.write_text(
        json.dumps(
            {
                "purpose": f"Pool 4 cl_disconnect fixture ({persona_key})",
                "saas_api_key": persona.api_key,
                "saas_url": "http://localhost:3000",
                "auto_sync": True,
                "repo_name": f"test/disconnect-{persona_key}-fixture",
                "scope": {
                    "operator_role": ["provider"],
                    "risk_classification": "high-risk",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    client = McpStdioClient.spawn()
    try:
        cell = ToolCell(
            cell_id=f"phase3-cl_disconnect-success-{persona_key}",
            tier="S",
            tool="cl_disconnect",
            scenario="success",
            persona=persona_key,
            preconditions=["fixture_with_seeded_dashboard_binding"],
            cleanup=["tmp_path_auto_cleanup"],
            cleanup_justification=(
                "tmp_path is pytest-managed; auto-removed at session end. "
                "No SaaS state was created."
            ),
            invoke={
                "tool": "cl_disconnect",
                "args": {"project_path": str(project_dir)},
            },
            expected_response={"status": "ok"},
        )
        raw = invoke_tool(cell, ctx={}, client=client)
    finally:
        client.close()

    response = json.loads(raw)

    assert "error" not in response, (
        f"cl_disconnect returned error: {response}"
    )
    assert response.get("status") == "disconnected", (
        f"cl_disconnect status: expected 'disconnected', got "
        f"{response.get('status')!r} (full response: {response})"
    )
    removed = set(response.get("removed_fields") or [])
    expected_removed = {"saas_api_key", "saas_url", "auto_sync"}
    missing = expected_removed - removed
    assert not missing, (
        f"cl_disconnect removed_fields missing {missing}; got {removed}. "
        f"All three binding fields should be reported as removed when "
        f"the seeded rc had them."
    )

    # On-disk verification: dashboard-binding fields gone, others intact.
    rc_after = json.loads(rc_path.read_text(encoding="utf-8"))
    for field in ("saas_api_key", "saas_url", "auto_sync"):
        assert field not in rc_after, (
            f"rc still contains {field!r} after cl_disconnect; "
            f"rc_after={rc_after}"
        )
    assert rc_after.get("repo_name") == f"test/disconnect-{persona_key}-fixture", (
        f"non-binding field repo_name was clobbered; got "
        f"{rc_after.get('repo_name')!r}"
    )
    assert rc_after.get("scope", {}).get("risk_classification") == "high-risk", (
        f"non-binding nested field scope.risk_classification was lost; "
        f"got rc_after.scope={rc_after.get('scope')!r}"
    )
    assert rc_after.get("purpose") == f"Pool 4 cl_disconnect fixture ({persona_key})", (
        f"non-binding field purpose was lost; got "
        f"{rc_after.get('purpose')!r}"
    )
