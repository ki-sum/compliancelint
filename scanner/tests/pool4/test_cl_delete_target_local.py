"""Pool 4 Phase 2 — cl_delete target=local round-trip.

cl_delete target=local is the scanner-side-only branch (per
scanner/server.py:3343-3348):

  - Removes: ``.compliancelint/local/`` (scan cache) + the
    project's ``~/.compliancelint/logs/{hash}/`` directory.
  - Preserves: ``.compliancelint/evidence/`` (git-committed audit
    trail) + ``.compliancelintrc`` (dashboard binding).
  - No SaaS mutation. Use case: force a clean rescan or clear
    cache corruption.

Per Pool 4 cross-system route audit, target=local is filed under
"local-only tools" — the asserter verifies scanner-side state
(filesystem) only, not SaaS DB. C4's 3-layer rule is N/A here.

Why this test uses pytest's ``tmp_path`` instead of Pattern A:
  - Hard constraint C7 forbids ``$pytest.tmp_path`` in CELL YAML
    (the hook rule R5 enforces it). Python TEST code may use
    tmp_path freely; the C7 rule is about cells declaring fixtures.
  - target=local is destructive on the project's
    .compliancelint/local/ directory. Running it against the
    manual-fixture would wipe the seeded scan data that
    Phase 2.A/B/C tests depend on (cl_sync round-trip).
  - tmp_path gives full isolation: each test invocation gets a
    fresh project_path, so the wipe affects only this test.

Verified-via: scanner/server.py:3328 cl_delete + the target=local
branch starting at scanner/server.py:3343.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .mcp_client import McpStdioClient


def _seed_minimal_scan_state(project_dir: Path) -> int:
    """Create a minimum-viable .compliancelint/local/articles/art09.json
    so cl_delete target=local has something to wipe.

    Returns the count of files placed under .compliancelint/ (used to
    sanity-check the wipe afterwards). Mirrors the real scanner output
    structure: per-article json with ``findings`` keyed by obligation
    id, plus a single seed finding so the file isn't trivially empty.
    """
    local_dir = project_dir / ".compliancelint" / "local" / "articles"
    local_dir.mkdir(parents=True, exist_ok=True)
    art09 = local_dir / "art09.json"
    art09.write_text(
        json.dumps({
            "overall_level": "non_compliant",
            "overall_confidence": "low",
            "scan_date": "2026-05-04T12:00:00+00:00",
            "last_updated": "2026-05-04T12:00:00+00:00",
            "assessed_by": "",
            "findings": {
                "ART09-OBL-1": {
                    "status": "open",
                    "level": "non_compliant",
                    "confidence": "medium",
                    "description": "Pool 4 cl_delete target=local fixture finding",
                    "source_quote": "test fixture",
                    "remediation": None,
                    "baselineState": "unchanged",
                    "suppression": None,
                    "evidence": [],
                    "history": [],
                },
            },
        }, indent=2),
        encoding="utf-8",
    )
    files = list((project_dir / ".compliancelint").rglob("*"))
    return sum(1 for f in files if f.is_file())


def test_cl_delete_target_local_wipes_cache_preserves_rc(
    tmp_path: Path,
) -> None:
    """End-to-end: tmp project with seeded local cache → cl_delete
    target=local wipes the cache, leaves rc + evidence dir alone.

    No server / no SaaS / no persona. cl_delete target=local is
    purely scanner-side, so this test stays GREEN even when the
    dashboard is down (no requires_dev_server marker).
    """
    project_dir = tmp_path / "pool4-local-fixture"
    project_dir.mkdir()

    # Minimal rc — cl_delete may load it but doesn't need an api key
    # for target=local.
    rc_path = project_dir / ".compliancelintrc"
    rc_path.write_text(
        json.dumps({
            "purpose": "Pool 4 cl_delete target=local fixture",
            "repo_name": "test/local-only-fixture",
            "scope": {
                "operator_role": ["provider"],
                "risk_classification": "high-risk",
            },
        }, indent=2),
        encoding="utf-8",
    )
    rc_bytes_before = rc_path.read_bytes()

    # Seed scan state so target=local has something to wipe.
    initial_file_count = _seed_minimal_scan_state(project_dir)
    assert initial_file_count > 0, "fixture seeding failed (no files written)"

    # Also seed an evidence dir — cl_delete target=local preserves it.
    evidence_dir = project_dir / ".compliancelint" / "evidence"
    evidence_dir.mkdir(parents=True)
    evidence_marker = evidence_dir / "audit-trail-marker.json"
    evidence_marker.write_text('{"committed_at": "2026-05-04"}', encoding="utf-8")

    client = McpStdioClient.spawn()
    try:
        cell = ToolCell(
            cell_id="phase2-cl_delete-success-target_local",
            tier="S",
            tool="cl_delete",
            scenario="target_local",
            persona="business",  # persona moot — local doesn't hit SaaS
            preconditions=["fixture_with_local_state"],
            cleanup=["tmp_path_auto_cleanup"],
            cleanup_justification=(
                "tmp_path is pytest-managed; auto-removed at session end. "
                "No SaaS state was created."
            ),
            invoke={
                "tool": "cl_delete",
                "args": {
                    "project_path": str(project_dir),
                    "target": "local",
                    "confirm": True,
                },
            },
            expected_response={"status": "ok"},
        )
        raw = invoke_tool(cell, ctx={}, client=client)
    finally:
        client.close()

    response = json.loads(raw)

    assert "error" not in response, (
        f"cl_delete target=local returned error: {response}"
    )

    # ── Filesystem assertions ──
    # The wipe MUST remove .compliancelint/local/ entirely.
    local_dir = project_dir / ".compliancelint" / "local"
    assert not local_dir.exists(), (
        f"cl_delete target=local did NOT wipe .compliancelint/local/; "
        f"it still exists with files: "
        f"{[p.name for p in local_dir.rglob('*') if p.is_file()][:5]}"
    )

    # Evidence dir + rc MUST be preserved per the cl_delete contract.
    assert evidence_dir.exists() and evidence_marker.exists(), (
        f"cl_delete target=local wiped .compliancelint/evidence/ — that "
        f"violates the contract. Audit-trail data was lost."
    )
    assert rc_path.exists(), (
        ".compliancelintrc was deleted; target=local must preserve it"
    )
    rc_bytes_after = rc_path.read_bytes()
    assert rc_bytes_after == rc_bytes_before, (
        ".compliancelintrc bytes drifted post-cl_delete; the rc must be "
        "untouched (target=local is scanner-side only)"
    )
