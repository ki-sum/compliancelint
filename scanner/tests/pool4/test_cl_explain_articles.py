"""Pool 4 — cl_explain across multiple articles (parametrized).

cl_explain is read-only and parametrizes naturally over (regulation,
article). This file extends Phase 1's single-article smoke
(test_smoke_runner.py covers article=9) to a sweep of high-risk
articles, proving the per-article obligation JSONs are reachable
+ correctly shaped through real MCP transport.

Articles chosen: 9 (risk management), 10 (data governance), 13
(transparency), 15 (accuracy), 50 (transparency for general AI).
Mixes high-risk-only with cross-cutting articles so the test
catches regressions in either set.

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport (one client per cell)
  - C7: no fixture project needed; pure read-only call

Verified-via: scanner/server.py cl_explain + the per-article
obligation JSONs at scanner/obligations/artNN.json.
"""
from __future__ import annotations

import json

import pytest

from .cell_loader import ToolCell
from .dispatcher import invoke_tool
from .mcp_client import McpStdioClient


ARTICLES = [9, 10, 13, 15, 50]


@pytest.mark.parametrize("article", ARTICLES, ids=[f"art{a}" for a in ARTICLES])
def test_cl_explain_returns_obligations_for_article(article: int) -> None:
    """End-to-end: cl_explain(regulation=eu-ai-act, article=N) →
    response has verbatim_obligations + eur_lex_official_url +
    disclaimer for each parametrized article."""
    client = McpStdioClient.spawn()
    try:
        cell = ToolCell(
            cell_id=f"phase3-cl_explain-art{article}-success",
            tier="S",
            tool="cl_explain",
            scenario="covered_article",
            persona="business",
            preconditions=[],
            cleanup=[],
            cleanup_justification="cl_explain is read-only",
            invoke={
                "tool": "cl_explain",
                "args": {"regulation": "eu-ai-act", "article": article},
            },
            expected_response={"status": "ok"},
        )
        raw = invoke_tool(cell, ctx={}, client=client)
    finally:
        client.close()

    response = json.loads(raw)

    assert "error" not in response, (
        f"cl_explain art{article} errored: {response}"
    )
    assert response.get("verbatim_obligations"), (
        f"cl_explain art{article} missing verbatim_obligations"
    )
    assert isinstance(response["verbatim_obligations"], list)
    assert len(response["verbatim_obligations"]) > 0, (
        f"cl_explain art{article} verbatim_obligations is empty"
    )
    assert "eur-lex.europa.eu" in (response.get("eur_lex_official_url") or ""), (
        f"cl_explain art{article} missing canonical eur_lex link"
    )
