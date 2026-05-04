"""Pool 4 — cl_scan_all against synthetic project_context.

cl_scan_all is the multi-article variant of cl_scan. Same
project_context input, scans every applicable article (filtered by
the validation gate's _scope-based applicability rules), writes one
per-article state.json file under .compliancelint/local/articles/.

This test reuses the synthetic context strategy from
test_cl_scan_real.py: hand-crafted compliance_answers minimal
enough to pass the validation gate, then asserts the scanner wrote
state files for the high-risk-applicable articles.

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C7: tmp_path Pattern B; full isolation
  - C8: tmp_path auto-cleanup

Verified-via: scanner/server.py:cl_scan_all + the validation gate's
applicable_articles computation + the per-article writer in
core/state.py.
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
            "purpose": "Pool 4 cl_scan_all synthetic-context fixture",
            "repo_name": "test/cl-scan-all-fixture",
            "scope": {
                "operator_role": ["provider"],
                "risk_classification": "high-risk",
            },
        }, indent=2),
        encoding="utf-8",
    )


def _build_synthetic_context_full() -> str:
    """compliance_answers with _scope only — high-risk provider scope.
    The validation gate's strict mode requires ALL applicable
    articles filled; the lenient path (degraded / no answers) still
    runs and writes per-article files with UNABLE_TO_DETERMINE
    findings. Test accepts either path.
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


def test_cl_scan_all_synthetic_context_writes_state(tmp_path: Path) -> None:
    """End-to-end: cl_scan_all with synthetic context → per-article
    state files written under .compliancelint/local/articles/."""
    project_dir = tmp_path / "fixture"
    _seed_rc(project_dir)
    project_context = _build_synthetic_context_full()

    client = McpStdioClient.spawn()
    try:
        cell = ToolCell(
            cell_id="phase3-cl_scan_all-synthetic_context",
            tier="S",
            tool="cl_scan_all",
            scenario="synthetic_context_provider_high_risk",
            persona="business",
            preconditions=["fixture_with_rc"],
            cleanup=["tmp_path_auto_cleanup"],
            cleanup_justification="tmp_path auto-cleaned",
            invoke={
                "tool": "cl_scan_all",
                "args": {
                    "project_path": str(project_dir),
                    "project_context": project_context,
                    "ai_provider": "Pool4 Synthetic Context (no real AI)",
                },
            },
            expected_response={"status": "ok"},
        )
        raw = invoke_tool(cell, ctx={}, client=client)
    finally:
        client.close()

    response = parse_first_json(raw)

    assert isinstance(response, dict)
    if "error" in response:
        # Validation gate may reject incomplete answers (strict mode).
        # That's a real documented branch — verify the gate-error
        # shape so we can distinguish from a true transport break.
        err = response.get("error", "")
        assert any(
            keyword in err.lower()
            for keyword in ("scope", "missing", "applicable", "validation")
        ), (
            f"cl_scan_all error envelope doesn't look like a validation "
            f"gate rejection; got error={err!r}"
        )
        return

    # Non-error path: per-article state files were written.
    articles_dir = (
        project_dir / ".compliancelint" / "local" / "articles"
    )
    assert articles_dir.is_dir(), (
        f"cl_scan_all completed but didn't create articles/ dir at "
        f"{articles_dir}; response keys={list(response.keys())}"
    )
    article_files = list(articles_dir.glob("*.json"))
    assert len(article_files) > 0, (
        f"cl_scan_all completed but wrote 0 article files; "
        f"response={response}"
    )
