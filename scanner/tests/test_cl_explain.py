"""Thin coverage for MCP tool cl_explain (server.py:541).

Covers:
  - happy path: known regulation + known article returns structured Explanation JSON
  - error path: unsupported regulation returns typed error with fix hint
  - error path: unknown article number returns error listing available articles
"""
import json
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


EXPLANATION_KEYS = {
    "article_number",
    "article_title",
    "one_sentence",
    "official_summary",
    "related_articles",
    "recital",
    "automation_summary",
    "compliance_checklist_summary",
    "enforcement_date",
    "waiting_for",
}


def test_explain_known_article_returns_valid_explanation():
    raw = server.cl_explain(regulation="eu-ai-act", article=12)
    parsed = json.loads(raw)

    assert "error" not in parsed, f"expected success, got error payload: {parsed}"
    missing = EXPLANATION_KEYS - parsed.keys()
    assert not missing, f"Explanation missing keys: {missing}"
    assert parsed["article_number"] == 12
    assert isinstance(parsed["article_title"], str) and parsed["article_title"].strip()
    assert isinstance(parsed["official_summary"], str) and parsed["official_summary"].strip()


def test_explain_unsupported_regulation_returns_error():
    raw = server.cl_explain(regulation="gdpr", article=12)
    parsed = json.loads(raw)

    assert "error" in parsed, f"expected error payload, got: {parsed}"
    assert "not yet supported" in parsed["error"].lower()
    assert "fix" in parsed
    assert "eu-ai-act" in parsed["fix"]


def test_explain_unknown_article_lists_available():
    raw = server.cl_explain(regulation="eu-ai-act", article=999)
    parsed = json.loads(raw)

    assert "error" in parsed, f"expected error for unknown article, got: {parsed}"
    assert "999" in parsed["error"]
    assert "fix" in parsed
    assert "Available articles" in parsed["fix"]
