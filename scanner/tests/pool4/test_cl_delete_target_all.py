"""Pool 4 — cl_delete target=all (irreversible, magic_phrase gated).

target=all wipes EVERYTHING on the project's local + git-committed
trail per scanner/server.py:3355-3360:

  - Removes: .compliancelint/local/ + .compliancelint/evidence/
    + .compliancelintrc + ~/.compliancelint/logs/{hash}/
  - Boolean confirm=True is NOT SUFFICIENT.
  - Requires confirm_phrase="I understand this is irreversible"
    (exact string).

This test exercises both gates: invokes target=all WITHOUT the magic
phrase first to prove the gate fires, then WITH the phrase to prove
the wipe completes. tmp_path isolates from manual-fixture (target=all
would clobber the seeded scan state otherwise).

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C7: tmp_path Pattern B (full isolation)
  - C8: tmp_path auto-cleanup; no SaaS state involved

Verified-via: scanner/server.py:3328 cl_delete + the MAGIC_PHRASE
constant + the target=all branch's safety gate at 3399.
"""
from __future__ import annotations

import json
from pathlib import Path

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .mcp_client import McpStdioClient


MAGIC_PHRASE = "I understand this is irreversible"


def _seed_full_project(project_dir: Path) -> tuple[Path, Path, Path]:
    """Create rc + local/articles/art09.json + evidence/marker so
    target=all has all 3 categories of files to wipe.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    rc_path = project_dir / ".compliancelintrc"
    rc_path.write_text(
        json.dumps({
            "purpose": "Pool 4 cl_delete target=all fixture",
            "repo_name": "test/cl-delete-all-fixture",
            "scope": {"operator_role": ["provider"], "risk_classification": "high-risk"},
        }, indent=2),
        encoding="utf-8",
    )
    articles_dir = project_dir / ".compliancelint" / "local" / "articles"
    articles_dir.mkdir(parents=True)
    art_path = articles_dir / "art09.json"
    art_path.write_text(
        json.dumps({
            "overall_level": "non_compliant",
            "scan_date": "2026-05-04T12:00:00+00:00",
            "findings": {},
        }, indent=2),
        encoding="utf-8",
    )
    evidence_dir = project_dir / ".compliancelint" / "evidence"
    evidence_dir.mkdir(parents=True)
    evidence_marker = evidence_dir / "audit-trail.json"
    evidence_marker.write_text('{"committed": "2026-05-04"}', encoding="utf-8")
    return rc_path, art_path, evidence_marker


def test_cl_delete_target_all_gate_blocks_without_magic_phrase(
    tmp_path: Path,
) -> None:
    """First half: confirm=True alone MUST NOT trigger the wipe;
    response is the abort/gate envelope; files remain on disk.
    """
    project_dir = tmp_path / "fixture-gated"
    rc_path, art_path, evidence_marker = _seed_full_project(project_dir)

    client = McpStdioClient.spawn()
    try:
        cell = ToolCell(
            cell_id="phase3-cl_delete-target_all-gate_no_phrase",
            tier="S",
            tool="cl_delete",
            scenario="target_all_no_magic_phrase",
            persona="business",
            preconditions=["fixture_with_local_evidence_rc"],
            cleanup=["tmp_path_auto_cleanup"],
            cleanup_justification="tmp_path auto-cleaned",
            invoke={
                "tool": "cl_delete",
                "args": {
                    "project_path": str(project_dir),
                    "target": "all",
                    "confirm": True,
                    # Note: NO confirm_phrase — gate must fire.
                },
            },
            expected_response={"status": "error"},
        )
        raw = invoke_tool(cell, ctx={}, client=client)
    finally:
        client.close()

    response = json.loads(raw)
    # The safety gate may surface either as an explicit error envelope
    # OR as an abort response with reversibility/will_delete fields
    # but no actual wipe. Accept both shapes; the load-bearing
    # assertion is "files still exist".
    assert rc_path.exists(), (
        f"safety gate FAILED: rc was deleted despite missing "
        f"confirm_phrase. response={response}"
    )
    assert art_path.exists(), (
        f"safety gate FAILED: local state.json was deleted despite "
        f"missing confirm_phrase. response={response}"
    )
    assert evidence_marker.exists(), (
        f"safety gate FAILED: evidence/ was deleted despite missing "
        f"confirm_phrase. response={response}"
    )


def test_cl_delete_target_all_with_magic_phrase_wipes_everything(
    tmp_path: Path,
) -> None:
    """Second half: confirm=True + correct confirm_phrase → wipe.
    rc, local/, evidence/ all gone post-call.
    """
    project_dir = tmp_path / "fixture-wiped"
    rc_path, art_path, evidence_marker = _seed_full_project(project_dir)

    client = McpStdioClient.spawn()
    try:
        cell = ToolCell(
            cell_id="phase3-cl_delete-target_all-success",
            tier="S",
            tool="cl_delete",
            scenario="target_all_with_magic_phrase",
            persona="business",
            preconditions=["fixture_with_local_evidence_rc"],
            cleanup=["tmp_path_auto_cleanup"],
            cleanup_justification="tmp_path auto-cleaned",
            invoke={
                "tool": "cl_delete",
                "args": {
                    "project_path": str(project_dir),
                    "target": "all",
                    "confirm": True,
                    "confirm_phrase": MAGIC_PHRASE,
                },
            },
            expected_response={"status": "ok"},
        )
        raw = invoke_tool(cell, ctx={}, client=client)
    finally:
        client.close()

    response = json.loads(raw)

    assert "error" not in response, (
        f"cl_delete target=all with magic phrase returned error: "
        f"{response}"
    )

    # Wipe assertions — all three categories should be gone.
    assert not rc_path.exists(), (
        f".compliancelintrc still present after target=all + magic; "
        f"the contract says it must be removed"
    )
    assert not art_path.exists(), (
        f".compliancelint/local/articles/art09.json still present "
        f"after target=all"
    )
    assert not evidence_marker.exists(), (
        f".compliancelint/evidence/ still present after target=all "
        f"— this is the IRREVERSIBLE wipe path; audit-trail data "
        f"should be gone"
    )
