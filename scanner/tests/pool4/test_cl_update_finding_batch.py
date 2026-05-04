"""Pool 4 — cl_update_finding_batch atomic-batch round-trip.

cl_update_finding_batch wraps N cl_update_finding calls in a single
MCP invocation. Use case per scanner/server.py: bulk acknowledge
across many findings in one tool call (the "I reviewed all
ART09-* findings" workflow). Local-only — same scanner-side
state.json mutation as cl_update_finding, just batched.

This test seeds two findings, batches two acknowledges, and
verifies BOTH history entries land in state.json.

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C7: tmp_path Pattern B fixture
  - C8: tmp_path auto-cleanup

Verified-via: scanner/server.py @mcp.tool cl_update_finding_batch
+ the article state.json schema observed in the manual-fixture.
"""
from __future__ import annotations

import json
from pathlib import Path

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .mcp_client import McpStdioClient


OBLIGATION_IDS = ["ART09-OBL-1", "ART09-OBL-2"]
ARTICLE_FILE = "art09.json"


def _seed_two_findings(project_dir: Path) -> Path:
    project_dir.mkdir(parents=True, exist_ok=True)
    rc_path = project_dir / ".compliancelintrc"
    rc_path.write_text(
        json.dumps({
            "purpose": "Pool 4 cl_update_finding_batch fixture",
            "repo_name": "test/cl-update-finding-batch-fixture",
            "scope": {
                "operator_role": ["provider"],
                "risk_classification": "high-risk",
            },
            "attester_name": "Pool 4 Test Attester",
            "attester_email": "pool4@test.invalid",
        }, indent=2),
        encoding="utf-8",
    )
    articles_dir = project_dir / ".compliancelint" / "local" / "articles"
    articles_dir.mkdir(parents=True)
    art_path = articles_dir / ARTICLE_FILE
    findings = {}
    for i, oid in enumerate(OBLIGATION_IDS, start=1):
        findings[oid] = {
            "status": "open",
            "level": "non_compliant",
            "confidence": "medium",
            "description": f"Pool 4 batch fixture finding {i}",
            "source_quote": "test fixture (not real EUR-Lex text)",
            "remediation": None,
            "baselineState": "unchanged",
            "suppression": None,
            "evidence": [],
            "history": [{
                "date": "2026-05-04T12:00:00+00:00",
                "action": "scanned",
                "level": "non_compliant",
                "by": "scanner",
            }],
        }
    art_path.write_text(
        json.dumps({
            "overall_level": "non_compliant",
            "overall_confidence": "medium",
            "scan_date": "2026-05-04T12:00:00+00:00",
            "last_updated": "2026-05-04T12:00:00+00:00",
            "assessed_by": "",
            "findings": findings,
        }, indent=2),
        encoding="utf-8",
    )
    return art_path


def test_cl_update_finding_batch_appends_history_for_each_update(
    tmp_path: Path,
) -> None:
    """End-to-end: seeded with 2 findings → batch of 2 acknowledges →
    each finding gains a history entry."""
    project_dir = tmp_path / "fixture"
    art_path = _seed_two_findings(project_dir)

    pre = json.loads(art_path.read_text(encoding="utf-8"))
    pre_history_counts = {
        oid: len(pre["findings"][oid]["history"])
        for oid in OBLIGATION_IDS
    }

    client = McpStdioClient.spawn()
    try:
        cell = ToolCell(
            cell_id="phase3-cl_update_finding_batch-acknowledge_two",
            tier="S",
            tool="cl_update_finding_batch",
            scenario="bulk_acknowledge",
            persona="business",
            preconditions=["fixture_with_two_open_findings"],
            cleanup=["tmp_path_auto_cleanup"],
            cleanup_justification="tmp_path auto-cleaned",
            invoke={
                "tool": "cl_update_finding_batch",
                "args": {
                    "project_path": str(project_dir),
                    # Audit-first: cl_update_finding_batch declares
                    # `updates: str`, expecting a JSON-stringified list
                    # (not a parsed array). Discovered the first time
                    # this test ran — passing a list errors with an
                    # empty response (failed type coercion before any
                    # JSON output).
                    "updates": json.dumps([
                        {
                            "obligation_id": oid,
                            "action": "acknowledge",
                            "justification": (
                                f"batch ack for {oid} (Pool 4 fixture)"
                            ),
                        }
                        for oid in OBLIGATION_IDS
                    ]),
                },
            },
            expected_response={"status": "ok"},
        )
        raw = invoke_tool(cell, ctx={}, client=client)
    finally:
        client.close()

    response = json.loads(raw)
    assert "error" not in response, (
        f"cl_update_finding_batch returned error: {response}"
    )

    post = json.loads(art_path.read_text(encoding="utf-8"))
    for oid in OBLIGATION_IDS:
        post_finding = post["findings"][oid]
        post_history = post_finding["history"]
        assert len(post_history) == pre_history_counts[oid] + 1, (
            f"history for {oid} should grow by 1; pre="
            f"{pre_history_counts[oid]}, post={len(post_history)}"
        )
        last = post_history[-1]
        assert last.get("action") == "acknowledge", (
            f"last history entry for {oid} should be acknowledge; got {last}"
        )
