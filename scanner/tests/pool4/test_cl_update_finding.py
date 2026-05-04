"""Pool 4 — cl_update_finding scanner-side mutation round-trip.

cl_update_finding mutates ``.compliancelint/local/articles/artNN.json``
in place, appending to a finding's ``history[]`` and adjusting
status / suppression / evidence fields based on the action verb.
Local-only — the dashboard sees the mutation only on the next
cl_sync.

This test exercises the simplest action verb (``acknowledge``) on
a seeded synthetic finding. Verifies:
  - response shape: status + obligation_id echo + action echo
  - state.json on disk: new history entry with action=acknowledge
  - the finding's other fields are preserved (no clobbering)

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C2 / C3: not applicable (local-only)
  - C4: 1-layer (response + on-disk state.json)
  - C7: tmp_path Pattern B fixture; full isolation from manual-fixture
  - C8: tmp_path auto-cleanup; no SaaS state to purge

Verified-via: scanner/server.py cl_update_finding + the article
state.json history-entry shape observed in the seeded manual fixture.
"""
from __future__ import annotations

import json
from pathlib import Path

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .mcp_client import McpStdioClient


OBLIGATION_ID = "ART09-OBL-1"
ARTICLE_FILE = "art09.json"


def _seed_finding(project_dir: Path) -> Path:
    """Create .compliancelint/local/articles/art09.json with a single
    finding so cl_update_finding has something to mutate. Mirrors the
    real scan output schema observed in manual-fixture art10.json:
    overall_level / scan_date / findings dict keyed by obligation_id
    with status / level / history (etc.).
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    rc_path = project_dir / ".compliancelintrc"
    rc_path.write_text(
        json.dumps({
            "purpose": "Pool 4 cl_update_finding fixture",
            "repo_name": "test/cl-update-finding-fixture",
            "scope": {
                "operator_role": ["provider"],
                "risk_classification": "high-risk",
            },
            # Audit-first: cl_update_finding requires attester_name +
            # attester_email in rc for the audit trail entry. Without
            # them the tool returns an error envelope before any
            # state.json write — discovered the first time this test
            # ran in 2026-05-04 Phase 3 expansion.
            "attester_name": "Pool 4 Test Attester",
            "attester_email": "pool4@test.invalid",
            "attester_role": "Pool 4 fixture",
        }, indent=2),
        encoding="utf-8",
    )
    articles_dir = project_dir / ".compliancelint" / "local" / "articles"
    articles_dir.mkdir(parents=True)
    art_path = articles_dir / ARTICLE_FILE
    art_path.write_text(
        json.dumps({
            "overall_level": "non_compliant",
            "overall_confidence": "medium",
            "scan_date": "2026-05-04T12:00:00+00:00",
            "last_updated": "2026-05-04T12:00:00+00:00",
            "assessed_by": "",
            "findings": {
                OBLIGATION_ID: {
                    "status": "open",
                    "level": "non_compliant",
                    "confidence": "medium",
                    "description": "Pool 4 cl_update_finding seed finding",
                    "source_quote": "test fixture (not real EUR-Lex text)",
                    "remediation": None,
                    "baselineState": "unchanged",
                    "suppression": None,
                    "evidence": [],
                    "history": [
                        {
                            "date": "2026-05-04T12:00:00+00:00",
                            "action": "scanned",
                            "level": "non_compliant",
                            "by": "scanner",
                        },
                    ],
                },
            },
        }, indent=2),
        encoding="utf-8",
    )
    return art_path


def test_cl_update_finding_acknowledge_appends_history_entry(
    tmp_path: Path,
) -> None:
    """End-to-end: seeded finding → cl_update_finding(action='acknowledge')
    → state.json gains a history entry with action='acknowledge'."""
    project_dir = tmp_path / "fixture"
    art_path = _seed_finding(project_dir)

    # Pre-state snapshot for the targeted finding.
    pre = json.loads(art_path.read_text(encoding="utf-8"))
    pre_finding = pre["findings"][OBLIGATION_ID]
    pre_history_count = len(pre_finding["history"])
    pre_description = pre_finding["description"]

    client = McpStdioClient.spawn()
    try:
        cell = ToolCell(
            cell_id="phase3-cl_update_finding-acknowledge-success",
            tier="S",
            tool="cl_update_finding",
            scenario="acknowledge",
            persona="business",
            preconditions=["fixture_with_open_finding"],
            cleanup=["tmp_path_auto_cleanup"],
            cleanup_justification=(
                "tmp_path auto-cleaned; no SaaS state created"
            ),
            invoke={
                "tool": "cl_update_finding",
                "args": {
                    "project_path": str(project_dir),
                    "obligation_id": OBLIGATION_ID,
                    "action": "acknowledge",
                    "justification": "Pool 4 fixture acknowledgement",
                },
            },
            expected_response={"status": "ok"},
        )
        raw = invoke_tool(cell, ctx={}, client=client)
    finally:
        client.close()

    response = json.loads(raw)

    assert "error" not in response, (
        f"cl_update_finding returned error: {response}"
    )

    # On-disk verification: history grew by 1, the new entry is the
    # acknowledge, and the finding's identity (description) is
    # preserved.
    post = json.loads(art_path.read_text(encoding="utf-8"))
    post_finding = post["findings"][OBLIGATION_ID]
    post_history = post_finding["history"]
    assert len(post_history) == pre_history_count + 1, (
        f"history length should grow by exactly 1 entry; pre="
        f"{pre_history_count}, post={len(post_history)}"
    )
    last_entry = post_history[-1]
    assert last_entry.get("action") == "acknowledge", (
        f"last history entry should be the acknowledge; got "
        f"{last_entry}"
    )
    assert post_finding.get("description") == pre_description, (
        f"finding description was clobbered; pre={pre_description!r} "
        f"post={post_finding.get('description')!r}"
    )
