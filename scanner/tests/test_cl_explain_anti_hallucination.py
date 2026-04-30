"""Q1 self-audit follow-up — cl_explain returns hand-written paraphrase
for every field. No verbatim source_quote, no link to canonical EUR-Lex
PDF, no explicit disclaimer that the summary is paraphrased.

Pre-fix risk: an AI agent (Claude / ChatGPT) reading the output cannot
distinguish "this is OUR summary" from "this is the law text", and may
further paraphrase as if it were verbatim — paraphrase amplification
across multiple AI hops, drifting away from the regulation.

Post-fix contract:
  - `verbatim_obligations` field surfaces every obligation atom from
    the article's JSON file with its EUR-Lex source_quote (zero AI
    inference, identical mechanism to cl_action_guide post-Q3)
  - `eur_lex_official_url` field gives the AI a direct pointer to the
    canonical PDF for ground-truth lookup
  - `disclaimer` field explicitly tells the consumer the prose summary
    fields are paraphrased and the verbatim text is in
    verbatim_obligations
  - existing fields (one_sentence, official_summary, recital, etc.)
    are PRESERVED — this is additive, not destructive
"""
import json
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _explain(article: int) -> dict:
    """Call cl_explain via the MCP tool wrapper, return parsed JSON."""
    from server import cl_explain

    raw = cl_explain(article=article)
    # cl_explain may append upgrade_hint as trailing text after the JSON;
    # strip everything from the first '\n\n' after the closing brace.
    # Easiest: parse the first balanced JSON object.
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(raw)
    return obj


# ──────────────────────────────────────────────────────────────────────
# 1. verbatim_obligations field — anti-hallucination by reference
# ──────────────────────────────────────────────────────────────────────


def test_explain_returns_verbatim_obligations_field():
    """cl_explain MUST return a `verbatim_obligations` list — every
    obligation atom from the article's JSON, with verbatim source_quote.
    AI consumers can read this to know the EUR-Lex ground truth."""
    payload = _explain(12)
    assert "verbatim_obligations" in payload, (
        "cl_explain must surface verbatim_obligations from the article "
        "JSON to prevent paraphrase amplification"
    )
    obligations = payload["verbatim_obligations"]
    assert isinstance(obligations, list)
    assert len(obligations) > 0, "Article 12 has known obligations"


def test_explain_verbatim_obligations_contain_source_quote():
    """Each verbatim_obligations entry MUST have id, source, and
    source_quote (verbatim from EUR-Lex)."""
    payload = _explain(12)
    obligations = payload["verbatim_obligations"]

    for ob in obligations:
        assert "id" in ob, f"Obligation missing 'id': {ob}"
        assert "source" in ob, f"Obligation missing 'source': {ob}"
        assert "source_quote" in ob, f"Obligation missing 'source_quote': {ob}"
        assert ob["source_quote"], (
            f"Obligation {ob.get('id')} has empty source_quote"
        )
        # Source quote must be substantive, not a placeholder
        assert len(ob["source_quote"]) > 20, (
            f"Obligation {ob.get('id')} source_quote suspiciously short: "
            f"{ob['source_quote']!r}"
        )


def test_explain_verbatim_obligations_match_committed_json():
    """The verbatim_obligations text MUST match the obligation JSON
    on disk byte-for-byte — guard against any AI inference / drift."""
    payload = _explain(12)

    # Load canonical art12 obligations
    json_path = os.path.join(
        SCANNER_ROOT, "obligations", "art12-record-keeping.json"
    )
    with open(json_path, encoding="utf-8") as f:
        canonical = json.load(f)
    canonical_by_id = {
        ob["id"]: ob["source_quote"] for ob in canonical["obligations"]
    }

    for ob in payload["verbatim_obligations"]:
        oid = ob["id"]
        # Some obligations in art12 are cross-references (e.g. ART19-OBL-1b);
        # they're loaded into art12 but the canonical lives in art19.
        # For the article-12 explain endpoint we expect the cross-ref
        # entries to be in art12's JSON.
        if oid in canonical_by_id:
            assert ob["source_quote"] == canonical_by_id[oid], (
                f"Drift detected for {oid}: cl_explain returned\n"
                f"  {ob['source_quote']!r}\n"
                f"but art12-record-keeping.json has\n"
                f"  {canonical_by_id[oid]!r}"
            )


# ──────────────────────────────────────────────────────────────────────
# 2. eur_lex_official_url — direct pointer to canonical PDF
# ──────────────────────────────────────────────────────────────────────


def test_explain_returns_eur_lex_official_url():
    """cl_explain MUST return a URL pointing at the canonical EUR-Lex
    text for the article. Lets AI consumers fetch ground truth without
    trusting our summary."""
    payload = _explain(12)
    assert "eur_lex_official_url" in payload, (
        "cl_explain must include a link to the canonical EUR-Lex source"
    )
    url = payload["eur_lex_official_url"]
    assert url.startswith("https://eur-lex.europa.eu/"), (
        f"eur_lex_official_url must point at eur-lex.europa.eu, got: {url!r}"
    )
    # It should reference the article number specifically when possible
    # (e.g. anchor #art_12 or article-12 in path)
    assert "12" in url, (
        f"eur_lex_official_url should reference article 12 specifically, "
        f"got: {url!r}"
    )


# ──────────────────────────────────────────────────────────────────────
# 3. disclaimer — explicit anti-hallucination signal
# ──────────────────────────────────────────────────────────────────────


def test_explain_returns_disclaimer_distinguishing_paraphrase():
    """cl_explain MUST return a `disclaimer` field telling the consumer
    that prose summary fields are paraphrased, and verbatim law text
    is in verbatim_obligations. Without this, an AI agent may quote
    `official_summary` as if it were the regulation's actual text."""
    payload = _explain(12)
    assert "disclaimer" in payload, "cl_explain must return a disclaimer"
    disclaimer = payload["disclaimer"].lower()
    # Must mention paraphrase / summary not being verbatim
    assert "paraphras" in disclaimer or "summary" in disclaimer, (
        f"Disclaimer should clarify summary != verbatim. Got: {disclaimer!r}"
    )
    # Must point at where to find verbatim text
    assert "verbatim_obligations" in payload["disclaimer"], (
        f"Disclaimer should point AI consumers at verbatim_obligations. "
        f"Got: {payload['disclaimer']!r}"
    )


# ──────────────────────────────────────────────────────────────────────
# 4. backwards compat — existing fields are PRESERVED
# ──────────────────────────────────────────────────────────────────────


def test_explain_preserves_existing_one_sentence_field():
    payload = _explain(12)
    assert "one_sentence" in payload
    assert payload["one_sentence"]


def test_explain_preserves_existing_official_summary_field():
    payload = _explain(12)
    assert "official_summary" in payload
    assert payload["official_summary"]


def test_explain_preserves_existing_automation_summary_field():
    payload = _explain(12)
    assert "automation_summary" in payload


# ──────────────────────────────────────────────────────────────────────
# 5. coverage across multiple articles (not just art12)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("article_number", [9, 12, 14, 26])
def test_explain_returns_verbatim_obligations_for_multiple_articles(
    article_number,
):
    """Verify the new fields work across a sample of articles, not
    just art12."""
    payload = _explain(article_number)
    assert "verbatim_obligations" in payload
    assert "eur_lex_official_url" in payload
    assert "disclaimer" in payload
    assert isinstance(payload["verbatim_obligations"], list)
    assert len(payload["verbatim_obligations"]) > 0


# ──────────────────────────────────────────────────────────────────────
# 6. graceful behaviour on unknown article
# ──────────────────────────────────────────────────────────────────────


def test_explain_unknown_article_returns_error_not_fabricated_payload():
    """For an article that isn't loaded, cl_explain must NOT fabricate
    fields — it must return the existing error response shape."""
    from server import cl_explain

    raw = cl_explain(article=999)  # impossibly high
    # Old behaviour (pre-fix) returned an error JSON; preserve.
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(raw)
    assert "error" in obj
    # Must NOT have fabricated verbatim_obligations
    assert "verbatim_obligations" not in obj or obj.get(
        "verbatim_obligations"
    ) in (None, [])
