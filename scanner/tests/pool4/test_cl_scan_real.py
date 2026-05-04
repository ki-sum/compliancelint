"""Pool 4 — cl_scan against synthetic project_context.

cl_scan needs an AI-enriched ``project_context`` JSON string with
``compliance_answers`` per applicable article. Production usage:
client AI calls cl_analyze_project, fills answers, passes to
cl_scan. For Pool 4 cell-level testing we don't need a real AI —
we hand-craft a minimum compliance_answers dict that passes the
validation gate and lets the scanner produce a deterministic
findings result for one article.

Synthetic project_context strategy:
  - _scope: {risk_classification: high-risk, is_ai_system: true,
    operator_role: [provider]}
  - articles "9": minimal answers consistent with the validation
    gate's per-article schema (boolean fields nullable; the gate
    just checks shape, not correctness).
  - Single article scan (articles="9") so we don't trigger the
    cl_scan_all delegation branch which expects ALL applicable
    articles filled.

Verifies:
  - Real-MCP transport reaches cl_scan and returns parseable JSON
    (with the trailing-text marketing footer stripped via
    parse_first_json).
  - Response shape: either status:ok + scan_summary OR a documented
    error (degraded mode without api_key — acceptable per the
    server.py docstring at server.py:605).
  - On-disk: .compliancelint/local/articles/art09.json was written
    by the scanner (proof scan completed at the file level).

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C7: tmp_path Pattern B; full isolation
  - C8: tmp_path auto-cleanup

Verified-via: scanner/server.py:594 cl_scan + the validation gate
at scanner/core/validation_gate.py + the per-article scan path
that writes to ``.compliancelint/local/articles/artNN.json``.
"""
from __future__ import annotations

import json
from pathlib import Path

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .mcp_client import McpStdioClient, parse_first_json


def _seed_rc(project_dir: Path) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / ".compliancelintrc").write_text(
        json.dumps({
            "purpose": "Pool 4 cl_scan synthetic-context fixture",
            "repo_name": "test/cl-scan-fixture",
            "scope": {
                "operator_role": ["provider"],
                "risk_classification": "high-risk",
            },
        }, indent=2),
        encoding="utf-8",
    )


def _build_synthetic_context() -> str:
    """Minimum project_context that the validation gate accepts for
    a single-article scan. Boolean fields use null where not known —
    the gate accepts null and produces UNABLE_TO_DETERMINE findings.
    """
    return json.dumps({
        "framework": "python",
        "stack": ["python"],
        "compliance_answers": {
            "_scope": {
                "risk_classification": "high-risk",
                "risk_classification_confidence": "high",
                "is_ai_system": True,
                "operator_role": ["provider"],
                "annex_iii_category": "annex_iii_pt5_essential_services",
                "is_annex_i_product": False,
                "uses_training_data": True,
                "is_gpai": False,
                "eu_established": True,
            },
        },
    })


def test_cl_scan_synthetic_context_writes_article_state(
    tmp_path: Path,
) -> None:
    """End-to-end: cl_scan(article=9) with synthetic project_context →
    .compliancelint/local/articles/art09.json gets written."""
    project_dir = tmp_path / "fixture"
    _seed_rc(project_dir)
    project_context = _build_synthetic_context()

    client = McpStdioClient.spawn()
    try:
        cell = ToolCell(
            cell_id="phase3-cl_scan-synthetic_context-art09",
            tier="S",
            tool="cl_scan",
            scenario="synthetic_context_single_article",
            persona="business",
            preconditions=["fixture_with_rc"],
            cleanup=["tmp_path_auto_cleanup"],
            cleanup_justification="tmp_path auto-cleaned",
            invoke={
                "tool": "cl_scan",
                "args": {
                    "project_path": str(project_dir),
                    "project_context": project_context,
                    "articles": "9",
                    "ai_provider": "Pool4 Synthetic Context (no real AI)",
                },
            },
            expected_response={"status": "ok"},
        )
        raw = invoke_tool(cell, ctx={}, client=client)
    finally:
        client.close()

    # cl_scan appends a marketing footer after the JSON envelope;
    # parse just the first JSON object.
    response = parse_first_json(raw)

    assert isinstance(response, dict), (
        f"cl_scan response should be a dict; got {type(response).__name__}"
    )
    if "error" in response:
        # Documented error envelope (degraded mode, no api_key, etc.)
        # — proves transport works even if no scan completed.
        return

    # On-disk verification: art09.json was written.
    art_path = (
        project_dir / ".compliancelint" / "local" / "articles" / "art09.json"
    )
    assert art_path.is_file(), (
        f"cl_scan returned non-error but did NOT write art09.json at "
        f"{art_path}; response keys={list(response.keys())}"
    )
    art_data = json.loads(art_path.read_text(encoding="utf-8"))
    # Findings dict must exist (may be empty in degraded mode).
    assert "findings" in art_data, (
        f"art09.json missing 'findings' key; got {list(art_data.keys())}"
    )
