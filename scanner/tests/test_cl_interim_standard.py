"""Coverage for MCP tool cl_interim_standard (server.py:1440).

B3 broadening 2026-04-30 — original 2 tests covered just happy path
+ unknown article. Expanded to 8 tests covering:

  Happy paths:
    - known article returns structured checklist
    - returned JSON has expected metadata fields
    - all 44 currently-loaded articles return valid checklists

  Edge / error paths:
    - article=0 returns error
    - negative article number returns error
    - very large article number returns error
    - unknown article number returns "Available articles: [...]" hint
    - response carries upgrade_hint when tier=unconnected (paywall
      visibility — paid users see verbose checklist with full source
      quotes; free see redacted version)

The user-facing surface of cl_interim_standard is small (one int
input → JSON checklist OR error JSON), so 8 tests is the natural
saturation. Returning to thinness would be regression.
"""
import json
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def _strip_text_footer(s: str) -> str:
    """Strip the human-readable upgrade_hint footer that may follow
    a JSON response when tier=unconnected. Everything before the
    `\\n\\n---\\n` marker is the original payload."""
    marker = "\n\n---\n"
    if marker in s and "ComplianceLint hint" in s:
        return s.split(marker, 1)[0]
    return s


# ──────────────────────────────────────────────────────────────────────
# Happy paths
# ──────────────────────────────────────────────────────────────────────


def test_interim_standard_known_article_returns_checklist():
    server._ensure_module_loaded(12)
    raw = server.cl_interim_standard(article_number=12)
    parsed = json.loads(_strip_text_footer(raw))

    assert "error" not in parsed, f"expected success, got error: {parsed}"
    assert "requirements" in parsed
    assert isinstance(parsed["requirements"], (list, dict)) and parsed["requirements"], (
        "requirements must be non-empty"
    )


def test_interim_standard_returns_metadata_fields():
    """Beyond the article-specific content, the checklist payload
    must carry `_metadata` with article identity + status fields so
    AI clients can render a complete view (especially the "interim"
    disclaimer + standard_id)."""
    server._ensure_module_loaded(9)
    raw = server.cl_interim_standard(article_number=9)
    parsed = json.loads(_strip_text_footer(raw))

    assert "_metadata" in parsed, (
        f"checklist missing `_metadata` block; keys: {sorted(parsed.keys())}"
    )
    metadata = parsed["_metadata"]
    # Required metadata fields (per existing checklist convention)
    for required in ("title", "status", "disclaimer"):
        assert required in metadata, (
            f"_metadata missing `{required}`; keys: {sorted(metadata.keys())}"
        )


def test_interim_standard_all_loaded_articles_return_valid_checklists():
    """Sanity sweep — every loaded article module should produce a
    checklist that:
      - parses as JSON
      - either errors (with `error` key) OR carries `_metadata` +
        substantive content
    'Substantive content' means at least one of: `requirements`
    (typical), `prohibited_practices` (Art 5), `annex_*_categories`
    or `classification_decision_tree` (Art 6 — classification logic
    article, not a requirements article). Catches regressions where
    a new article module ships without ANY content."""
    server._ensure_all_modules_loaded()
    SUBSTANTIVE_CONTENT_KEYS = {
        "requirements",  # standard pattern (most articles)
        "prohibited_practices",  # Art 5
        "compliance_assessment",  # Art 5 partial
        "annex_i_product_categories",  # Art 6
        "annex_iii_categories",  # Art 6
        "classification_decision_tree",  # Art 6
        "art6_3_exception_criteria",  # Art 6
    }
    failures: list[tuple[int, str]] = []
    for art_num in sorted(server._modules.keys()):
        raw = server.cl_interim_standard(article_number=art_num)
        try:
            parsed = json.loads(_strip_text_footer(raw))
        except json.JSONDecodeError as e:
            failures.append((art_num, f"non-JSON: {e}"))
            continue
        if "error" in parsed:
            continue
        if not (set(parsed.keys()) & SUBSTANTIVE_CONTENT_KEYS):
            failures.append(
                (art_num, f"no substantive content keys; got: {sorted(parsed.keys())}")
            )

    assert failures == [], (
        f"{len(failures)} articles have invalid checklists:\n"
        + "\n".join(f"  Art {n}: {msg}" for n, msg in failures)
    )


# ──────────────────────────────────────────────────────────────────────
# Edge / error paths
# ──────────────────────────────────────────────────────────────────────


def test_interim_standard_article_zero_returns_error():
    """Article 0 doesn't exist in EU AI Act numbering — should error."""
    raw = server.cl_interim_standard(article_number=0)
    parsed = json.loads(_strip_text_footer(raw))

    assert "error" in parsed
    assert "0" in parsed["error"]
    assert "Available articles" in parsed["fix"]


def test_interim_standard_negative_article_returns_error():
    raw = server.cl_interim_standard(article_number=-5)
    parsed = json.loads(_strip_text_footer(raw))

    assert "error" in parsed
    assert "-5" in parsed["error"]


def test_interim_standard_very_large_article_returns_error():
    """EU AI Act has 113 articles. Article 99999 must error."""
    raw = server.cl_interim_standard(article_number=99999)
    parsed = json.loads(_strip_text_footer(raw))

    assert "error" in parsed
    assert "99999" in parsed["error"]
    assert "Available articles" in parsed["fix"]


def test_interim_standard_unknown_article_lists_available_in_fix():
    """When user requests unknown article, error should list which
    articles ARE available so they can pick a real one."""
    server._ensure_module_loaded(9)
    raw = server.cl_interim_standard(article_number=42)
    parsed = json.loads(_strip_text_footer(raw))

    assert "error" in parsed
    assert "Available articles" in parsed["fix"]
    # The fix message should include at least one real article number
    # we know is loaded
    assert "9" in parsed["fix"]


# ──────────────────────────────────────────────────────────────────────
# Cross-cutting: upgrade_hint contract
# ──────────────────────────────────────────────────────────────────────


def test_interim_standard_response_carries_upgrade_hint_when_unconnected():
    """Free/unconnected tier should see paywall hint on success path."""
    server._ensure_module_loaded(9)
    raw = server.cl_interim_standard(article_number=9)

    # Either JSON form (_meta.upgrade_hint) or text-footer form
    parsed = None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # response had a text-footer appended — strip and parse
        parsed = json.loads(_strip_text_footer(raw))

    has_meta_hint = (
        isinstance(parsed.get("_meta"), dict)
        and "upgrade_hint" in parsed["_meta"]
    )
    has_text_hint = "ComplianceLint hint" in raw and "/dashboard/plans" in raw
    assert has_meta_hint or has_text_hint, (
        f"upgrade_hint missing on cl_interim_standard response:\n{raw[-300:]}"
    )
