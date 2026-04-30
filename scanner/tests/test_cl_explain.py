"""Coverage for MCP tool cl_explain (server.py:767).

B3 broadening 2026-04-30 — original 3 tests covered happy + 2 error
paths. Expanded to 9 tests covering full surface:

  Happy paths:
    - known article (existing) returns Explanation with all 10 keys
    - article 4 (smallest, single OBL) explains cleanly
    - explanation has rich content (non-empty strings, not stub)

  Edge cases:
    - article=0 → unknown article error
    - negative article → unknown article error
    - unsupported regulation → error with eu-ai-act suggestion
    - unknown article on supported regulation → "Available articles"
      list

  Cross-cutting:
    - response carries upgrade_hint when tier=unconnected
    - response is parseable as JSON (no trailing footer for cl_explain
      since responses are always JSON object form)
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


# ──────────────────────────────────────────────────────────────────────
# Happy paths
# ──────────────────────────────────────────────────────────────────────


def test_explain_known_article_returns_valid_explanation():
    raw = server.cl_explain(regulation="eu-ai-act", article=12)
    parsed = json.loads(raw)

    assert "error" not in parsed, f"expected success, got error payload: {parsed}"
    missing = EXPLANATION_KEYS - parsed.keys()
    assert not missing, f"Explanation missing keys: {missing}"
    assert parsed["article_number"] == 12
    assert isinstance(parsed["article_title"], str) and parsed["article_title"].strip()
    assert isinstance(parsed["official_summary"], str) and parsed["official_summary"].strip()


def test_explain_smallest_article_4_explains_cleanly():
    """Art 4 (AI Literacy) is the smallest single-obligation article.
    Sanity that cl_explain works on the simplest case."""
    raw = server.cl_explain(regulation="eu-ai-act", article=4)
    parsed = json.loads(raw)

    assert "error" not in parsed
    assert parsed["article_number"] == 4
    assert "literacy" in parsed["article_title"].lower()


def test_explain_content_is_substantive_not_stub():
    """Each explanation field must be non-trivially populated. Catches
    regressions where a stub Explanation ships with empty strings."""
    raw = server.cl_explain(regulation="eu-ai-act", article=9)
    parsed = json.loads(raw)

    assert len(parsed["official_summary"]) > 50, "official_summary too short — stub?"
    assert len(parsed["one_sentence"]) > 20, "one_sentence too short — stub?"
    # related_articles is a dict {article_label: description} per
    # Explanation schema — keys are referenced articles, values
    # describe the relationship.
    assert isinstance(parsed["related_articles"], dict)
    assert parsed["related_articles"], "related_articles dict is empty"
    # Compliance checklist summary: either a non-empty string OR a
    # non-empty dict
    cc = parsed["compliance_checklist_summary"]
    assert (isinstance(cc, str) and cc.strip()) or (isinstance(cc, dict) and cc)


# ──────────────────────────────────────────────────────────────────────
# Edge / error paths
# ──────────────────────────────────────────────────────────────────────


def test_explain_article_zero_returns_error():
    raw = server.cl_explain(regulation="eu-ai-act", article=0)
    parsed = json.loads(raw)

    assert "error" in parsed
    assert "0" in parsed["error"]
    assert "Available articles" in parsed["fix"]


def test_explain_negative_article_returns_error():
    raw = server.cl_explain(regulation="eu-ai-act", article=-7)
    parsed = json.loads(raw)

    assert "error" in parsed
    assert "-7" in parsed["error"]


def test_explain_unsupported_regulation_returns_error():
    raw = server.cl_explain(regulation="gdpr", article=12)
    parsed = json.loads(raw)

    assert "error" in parsed
    assert "not yet supported" in parsed["error"].lower()
    assert "fix" in parsed
    assert "eu-ai-act" in parsed["fix"]


def test_explain_unknown_article_lists_available():
    raw = server.cl_explain(regulation="eu-ai-act", article=999)
    parsed = json.loads(raw)

    assert "error" in parsed
    assert "999" in parsed["error"]
    assert "fix" in parsed
    assert "Available articles" in parsed["fix"]


# ──────────────────────────────────────────────────────────────────────
# Cross-cutting
# ──────────────────────────────────────────────────────────────────────


def test_explain_response_carries_upgrade_hint_when_unconnected():
    """Free/unconnected tier should see paywall hint on success path.
    cl_explain always returns JSON object form so the hint embeds at
    `_meta.upgrade_hint`."""
    raw = server.cl_explain(regulation="eu-ai-act", article=12)
    parsed = json.loads(raw)

    meta = parsed.get("_meta")
    assert isinstance(meta, dict) and "upgrade_hint" in meta, (
        f"upgrade_hint missing on cl_explain response. Keys: {list(parsed.keys())}"
    )
    hint = meta["upgrade_hint"]
    assert hint["url"].endswith("/dashboard/plans")


def test_explain_response_is_pure_json_no_text_footer():
    """cl_explain returns ONLY JSON — never a text-footer trail. AI
    clients can json.loads(response) directly without stripping."""
    raw = server.cl_explain(regulation="eu-ai-act", article=12)
    # Should parse without error AND no marker after
    parsed = json.loads(raw)  # Would raise if trailing junk
    assert isinstance(parsed, dict)
    # No "ComplianceLint hint" plain-text marker (would mean text
    # footer was appended)
    assert "ComplianceLint hint" not in raw, (
        "cl_explain response has text-footer; should embed _meta.upgrade_hint instead"
    )
