"""Bug C regression tests (v1.1.6, 2026-08-11) — cl_scan / cl_explain
response sizes must stay under safe MCP caps for any AI client.

Backstory: pre-1.1.6 cl_scan(articles=50) returned ~283 KB (192 KB of
verbatim Layer 2 atoms + findings + recitals). Claude Code capped MCP
responses at ~25k tokens (~100 KB) and errored with 'result exceeds
maximum allowed tokens', forcing the AI to save-to-file and re-read.

Fix: SUMMARY tier for Layer 2 atoms in article-mode responses; verbatim
atoms accessible via `cl_explain(obligation_id=..., limit=..., offset=...)`
paginated (default 10, max 20 atoms per page).

These tests are generic — they assert absolute byte budgets that work
for any MCP client. Do NOT tune to Claude Code's specific cap; the
tools serve Claude, GPT, Gemini, local models, etc.
"""
from __future__ import annotations

import json

import pytest

from core.layer2_loader import (
    get_atoms_for_obligation,
    get_materials_summary_for_article,
    reset_cache,
)


# Safe budget for MCP responses across all AI clients (Claude Code
# ~25k tokens ≈ 100 KB; leave headroom for finding JSON + recitals).
LAYER2_SUMMARY_BUDGET_BYTES = 5_000
# Per-page atom bundle budget — 20 atoms × ~1160 bytes ≈ 23 KB max.
DEEP_DIVE_PAGE_BUDGET_BYTES = 28_000


@pytest.fixture(autouse=True)
def _reset_layer2_cache():
    reset_cache()
    yield
    reset_cache()


def test_summary_tier_fits_in_budget_for_art50():
    """SUMMARY tier for Art 50 (largest Layer 2 doc, 304 atoms) must
    stay well under 5 KB. Full tier was 192 KB."""
    summary = get_materials_summary_for_article(50)
    size = len(json.dumps(summary))
    assert size < LAYER2_SUMMARY_BUDGET_BYTES, (
        f"Art 50 SUMMARY tier is {size:,} bytes, exceeds "
        f"{LAYER2_SUMMARY_BUDGET_BYTES:,} budget. Something re-inlined "
        f"verbatim atom text — check get_materials_summary_for_article()."
    )


def test_summary_tier_preserves_doc_metadata():
    """SUMMARY tier drops atom bodies but MUST keep every field an
    auditor needs: doc_id, SHA256, source_url, publication_date,
    binding_nature, atoms_total, obligation_coverage."""
    summary = get_materials_summary_for_article(50)
    assert summary, "prereq: Art 50 has Layer 2 material"
    doc = summary[0]
    required = {
        "doc_id",
        "doc_type",
        "title",
        "issuing_body",
        "publication_date",
        "source_url",
        "source_sha256",
        "binding_nature",
        "atoms_total",
        "obligation_coverage",
        "deep_dive_via",
    }
    missing = required - set(doc.keys())
    assert not missing, f"SUMMARY tier missing fields: {missing}"
    # SHA256 must be a real 64-char hex string, not empty
    assert len(doc["source_sha256"]) == 64, (
        f"SHA256 wrong length: {doc['source_sha256']!r}"
    )
    # obligation_coverage must be a non-empty {oid: count} dict
    coverage = doc["obligation_coverage"]
    assert isinstance(coverage, dict) and coverage, (
        "obligation_coverage must be non-empty dict"
    )
    # Counts must sum to atoms_total (data-integrity check)
    assert sum(coverage.values()) == doc["atoms_total"], (
        f"Coverage sum {sum(coverage.values())} != atoms_total {doc['atoms_total']}"
    )


def test_summary_tier_returns_empty_for_articles_without_layer2():
    """Art 12 (record-keeping) has no Layer 2 material yet — summary
    tier must return [] gracefully."""
    assert get_materials_summary_for_article(12) == []
    assert get_materials_summary_for_article(6) == []


def test_summary_tier_deep_dive_hint_references_cl_explain():
    """The SUMMARY tier MUST tell AI consumers exactly how to fetch
    verbatim atoms — otherwise the moat (verbatim + SHA256 anchor)
    is invisible. Hint copy must reference cl_explain + obligation_id
    + limit + offset."""
    summary = get_materials_summary_for_article(50)
    assert summary
    hint = summary[0]["deep_dive_via"]
    assert "cl_explain" in hint
    assert "obligation_id" in hint
    assert "limit" in hint
    assert "offset" in hint


def _simulate_deep_dive_payload(obligation_id: str, limit: int, offset: int) -> dict:
    """Mirror the payload cl_explain builds in obligation_deep_dive mode.
    Kept in test rather than importing cl_explain because the tool call
    path also wraps append_upgrade_hint and pulls in ProjectConfig etc.
    which requires more fixture setup than this size regression needs.
    """
    all_atoms = get_atoms_for_obligation(obligation_id)
    total = len(all_atoms)
    capped_limit = max(1, min(20, limit))
    capped_offset = max(0, offset)
    page = all_atoms[capped_offset : capped_offset + capped_limit]
    has_more = (capped_offset + capped_limit) < total
    return {
        "mode": "obligation_deep_dive",
        "obligation_id": obligation_id,
        "atoms": page,
        "total_atoms": total,
        "offset": capped_offset,
        "limit": capped_limit,
        "has_more": has_more,
        "next_offset": capped_offset + capped_limit if has_more else None,
        "disclaimer": "placeholder-for-size-check",
    }


@pytest.mark.parametrize(
    "obligation_id",
    ["ART50-OBL-1", "ART50-OBL-2", "ART50-OBL-4", "ART50-OBL-4b"],
)
def test_deep_dive_default_page_fits_in_budget(obligation_id: str):
    """Default page (limit=10) must fit inside 28 KB budget across
    all high-atom-count obligations. OBL-1 has 88 atoms — full bundle
    would be 102 KB; paginated at 10 must be ~12 KB."""
    payload = _simulate_deep_dive_payload(obligation_id, limit=10, offset=0)
    size = len(json.dumps(payload))
    assert size < DEEP_DIVE_PAGE_BUDGET_BYTES, (
        f"{obligation_id} @ limit=10 = {size:,} bytes, exceeds "
        f"{DEEP_DIVE_PAGE_BUDGET_BYTES:,} budget"
    )


def test_deep_dive_max_limit_fits_in_budget():
    """limit=20 (the hard cap) for the largest obligation must still
    fit under budget. This is the ceiling — larger limits would risk
    responses that Claude Code's ~25k-token cap rejects."""
    payload = _simulate_deep_dive_payload("ART50-OBL-1", limit=20, offset=0)
    size = len(json.dumps(payload))
    assert size < DEEP_DIVE_PAGE_BUDGET_BYTES, (
        f"OBL-1 @ limit=20 = {size:,} bytes, exceeds "
        f"{DEEP_DIVE_PAGE_BUDGET_BYTES:,} budget"
    )


def test_deep_dive_pagination_covers_all_atoms():
    """Walking offset from 0 in `limit` increments until has_more=False
    must yield exactly the same atoms as the un-paginated full list.
    Guards against off-by-one errors that would silently drop atoms."""
    limit = 10
    obligation = "ART50-OBL-1"
    full = get_atoms_for_obligation(obligation)
    walked: list[dict] = []
    offset = 0
    while True:
        page = _simulate_deep_dive_payload(obligation, limit=limit, offset=offset)
        walked.extend(page["atoms"])
        if not page["has_more"]:
            break
        assert page["next_offset"] == offset + limit
        offset = page["next_offset"]
    assert len(walked) == len(full), (
        f"Pagination walked {len(walked)} atoms; full list has {len(full)}. "
        f"Off-by-one in cl_explain paging?"
    )
    # Same order preserved
    assert [a["id"] for a in walked] == [a["id"] for a in full]


def test_deep_dive_last_page_has_no_more():
    """Final page (offset such that offset+limit >= total) must set
    has_more=False and next_offset=None. Prevents infinite AI loop."""
    full = get_atoms_for_obligation("ART50-OBL-1")
    total = len(full)
    # Land exactly at last non-empty page
    limit = 10
    offset = (total // limit) * limit
    if offset == total:  # exact multiple; step back one page
        offset -= limit
    page = _simulate_deep_dive_payload("ART50-OBL-1", limit=limit, offset=offset)
    assert page["has_more"] is False
    assert page["next_offset"] is None


def test_deep_dive_limit_clamped_to_20():
    """Callers passing limit > 20 must get 20 (not silently overflow).
    Guards the budget cap against caller error."""
    payload = _simulate_deep_dive_payload("ART50-OBL-1", limit=100, offset=0)
    assert payload["limit"] == 20
    assert len(payload["atoms"]) == 20


def test_deep_dive_limit_clamped_to_1_min():
    """Callers passing limit <= 0 must get 1 (defensive floor)."""
    payload = _simulate_deep_dive_payload("ART50-OBL-1", limit=0, offset=0)
    assert payload["limit"] == 1
    assert len(payload["atoms"]) == 1


def test_deep_dive_unknown_obligation_returns_zero_total():
    """Unknown obligation_id must return total_atoms=0, has_more=False.
    Downstream fix-line copy handled by cl_explain itself."""
    payload = _simulate_deep_dive_payload("ART99-NONEXISTENT", limit=10, offset=0)
    assert payload["total_atoms"] == 0
    assert payload["atoms"] == []
    assert payload["has_more"] is False


# ── Bug D regression guard (v1.1.6) ──
# cl_scan / cl_scan_all responses must be pure JSON (no trailing
# text). Pre-1.1.6 they returned JSON + "\n\n--- Results synced ---"
# + post-scan markdown, breaking downstream json.loads() with an
# "Extra data: line N column 1" error.


def test_cl_explain_response_is_pure_json():
    """cl_explain(article=N) response, after stripping any upgrade-hint
    footer, must be parseable in one shot via json.loads() — no
    trailing markdown text after the JSON body."""
    import json as _json

    from server import cl_explain

    raw = cl_explain(article=50)
    # append_upgrade_hint may add a plain-text footer for non-JSON
    # responses, but the article-mode response IS JSON so
    # append_upgrade_hint merges upgrade_hint into `_meta` and returns
    # pure JSON. Strict parse must succeed with no leftovers.
    parsed = _json.loads(raw)
    assert isinstance(parsed, dict)
    assert parsed.get("article_number") == 50


def test_cl_explain_obligation_response_is_pure_json():
    """cl_explain(obligation_id=...) response must also be pure JSON."""
    import json as _json

    from server import cl_explain

    raw = cl_explain(obligation_id="ART50-OBL-1", limit=10, offset=0)
    parsed = _json.loads(raw)
    assert isinstance(parsed, dict)
    assert parsed.get("mode") == "obligation_deep_dive"
    assert parsed.get("obligation_id") == "ART50-OBL-1"
