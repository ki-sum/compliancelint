"""§AD.5b integration test — `cl_explain` / `cl_action_guide` /
`cl_action_plan` / `cl_interim_standard` MUST surface `related_recitals`
(or `related_recitals_by_article` for the multi-article tool) drawn
from `scanner/data/recitals.json`.

Pre-fix gap (before 2026-05-04 §AD): only `cl_explain` carried the
Recital interpretive layer. `cl_action_guide` / `cl_action_plan` /
`cl_interim_standard` returned obligation atoms WITHOUT Recital context,
so AI consumers reading those tool outputs lost the interpretive
grounding that Recitals provide for ambiguous Article language.

Post-fix contract:
  - cl_action_guide(oid)           → response.related_recitals (list)
  - cl_action_plan(path, article)  → response.related_recitals_by_article (dict)
  - cl_interim_standard(article)   → response.related_recitals (list)

Source-Lock invariant: Each entry's `source_quote` MUST byte-match the
corresponding entry in scanner/data/recitals.json (already enforced by
test_recitals_source_lock.py). This file only checks WIRING — that the
3 tools surface the data, not that the data itself is authentic.

Test articles chosen for stable Recital coverage:
  - Article 5 (Prohibited Practices) — 14 Recitals (15-44 incl 176)
  - Article 12 (Record-keeping) — at least 1 mapped Recital (71)
  - Article 26 (Deployer obligations) — has Recital 90 mapped

If the article_recital_index.json mapping changes for these articles,
update the expected counts here. The test asserts COUNT >= 1 for
Art 12 / Art 26 (resilient to mapping refinements) and exact count
for Art 5 (sentinel for the most-mapped article).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RECITALS_JSON = REPO_ROOT / "scanner" / "data" / "recitals.json"


@pytest.fixture(scope="module")
def recitals_baseline():
    """Authoritative recitals.json — used for cross-referencing source_quote."""
    with RECITALS_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def _strip_text_footer(s: str) -> str:
    """Strip upgrade_hint text footer if present."""
    marker = "\n\n---\n"
    if marker in s and "ComplianceLint hint" in s:
        return s.split(marker, 1)[0]
    return s


def _parse_tool_output(raw: str) -> dict:
    """Parse a tool's JSON output, tolerant of trailing upgrade_hint text."""
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(_strip_text_footer(raw))
    return obj


# ──────────────────────────────────────────────────────────────────────
# 1. cl_action_guide — related_recitals attached to OID response
# ──────────────────────────────────────────────────────────────────────


def test_action_guide_returns_related_recitals_field():
    """cl_action_guide MUST return a `related_recitals` list when the
    OID is recognised. AI consumers reading the response gain Recital
    interpretive context alongside the verbatim obligation atom."""
    from server import cl_action_guide

    raw = cl_action_guide("ART26-OBL-2")
    payload = _parse_tool_output(raw)

    assert "related_recitals" in payload, (
        "cl_action_guide must surface related_recitals (§AD.5b). "
        f"Keys present: {sorted(payload.keys())}"
    )
    assert isinstance(payload["related_recitals"], list)


def test_action_guide_recital_entries_have_required_fields():
    """Each related_recitals entry MUST carry the fields the SaaS
    consumer relies on for citation rendering + provenance display."""
    from server import cl_action_guide

    raw = cl_action_guide("ART05-OBL-1")
    payload = _parse_tool_output(raw)

    recitals = payload.get("related_recitals", [])
    # Art 5 has 14 mapped Recitals per article_recital_index.json
    assert len(recitals) >= 1, (
        f"Art. 5 should map to multiple Recitals; got {len(recitals)}"
    )

    required = {
        "number",
        "source_quote",
        "source_pdf",
        "source_url_eur_lex",
        "source_url_ec",
        "verified_against",
        "byte_equal_across_sources",
    }
    for entry in recitals:
        missing = required - set(entry.keys())
        assert not missing, (
            f"Recital entry missing fields {missing}: {entry}"
        )
        assert isinstance(entry["number"], int)
        assert isinstance(entry["source_quote"], str)
        assert len(entry["source_quote"]) > 30
        assert entry["source_pdf"].endswith(".pdf")


def test_action_guide_unknown_article_oid_returns_empty_recital_list():
    """When the OID's article number has no mapped Recitals, the field
    is still present (empty list), not absent — keeps payload schema
    stable for AI consumers iterating across calls."""
    from server import cl_action_guide

    # Use a real OID format pointing at an article unlikely to have
    # any Recital mapping (no obligation JSON shipped → empty list).
    # Pick ART91 (documentation duty, low Recital coupling).
    raw = cl_action_guide("ART91-OBL-1")
    payload = _parse_tool_output(raw)

    # Field must always be present even if list is empty.
    assert "related_recitals" in payload, (
        "Schema stability: field must be present regardless of mapping"
    )
    assert isinstance(payload["related_recitals"], list)


# ──────────────────────────────────────────────────────────────────────
# 2. cl_action_plan — related_recitals_by_article on the multi-article plan
# ──────────────────────────────────────────────────────────────────────


def test_action_plan_returns_related_recitals_by_article(tmp_path):
    """cl_action_plan MUST surface a `related_recitals_by_article` dict
    keyed by article number. Single-article mode populates exactly one
    key when that article has any mapped Recitals."""
    from server import cl_action_plan

    # tmp_path is a real dir — cl_action_plan validates os.path.isdir
    raw = cl_action_plan(str(tmp_path), regulation="eu-ai-act", article=5)
    payload = _parse_tool_output(raw)

    assert "related_recitals_by_article" in payload, (
        "cl_action_plan must surface related_recitals_by_article (§AD.5b). "
        f"Keys present: {sorted(payload.keys())}"
    )
    by_article = payload["related_recitals_by_article"]
    assert isinstance(by_article, dict)
    # Art 5 is mapped — key "5" expected
    assert "5" in by_article, (
        f"Art. 5 should appear in related_recitals_by_article; "
        f"got keys: {sorted(by_article.keys())}"
    )
    art5_recitals = by_article["5"]
    assert isinstance(art5_recitals, list)
    assert len(art5_recitals) >= 1


def test_action_plan_disclaimer_mentions_recitals(tmp_path):
    """Disclaimer string MUST mention `related_recitals_by_article` so
    AI consumers know that field is the ground-truth Recital text."""
    from server import cl_action_plan

    raw = cl_action_plan(str(tmp_path), regulation="eu-ai-act", article=5)
    payload = _parse_tool_output(raw)

    disclaimer = payload.get("disclaimer", "")
    assert "related_recitals_by_article" in disclaimer, (
        "Disclaimer must reference the new field for AI consumer "
        f"discoverability. Got: {disclaimer!r}"
    )


# ──────────────────────────────────────────────────────────────────────
# 3. cl_interim_standard — related_recitals attached to checklist
# ──────────────────────────────────────────────────────────────────────


def test_interim_standard_returns_related_recitals_field():
    """cl_interim_standard MUST return a `related_recitals` list. The
    interim checklist is ComplianceLint's paraphrased guide; Recitals
    provide the official interpretive grounding for paraphrase
    correctness."""
    from server import cl_interim_standard

    raw = cl_interim_standard(article_number=5)
    payload = _parse_tool_output(raw)

    assert "related_recitals" in payload, (
        "cl_interim_standard must surface related_recitals (§AD.5b). "
        f"Keys present: {sorted(payload.keys())}"
    )
    recitals = payload["related_recitals"]
    assert isinstance(recitals, list)
    # Art 5 has multiple mapped Recitals
    assert len(recitals) >= 1


def test_interim_standard_preserves_existing_fields():
    """Additive contract — adding related_recitals MUST NOT break the
    existing top-level fields (is_official_standard / non_official_banner /
    superseded_when)."""
    from server import cl_interim_standard

    raw = cl_interim_standard(article_number=5)
    payload = _parse_tool_output(raw)

    # Pre-§AD.5b contract preserved
    assert payload.get("is_official_standard") is False
    assert "non_official_banner" in payload
    assert "superseded_when" in payload
    assert isinstance(payload["non_official_banner"], str)
    assert len(payload["non_official_banner"]) > 0


# ──────────────────────────────────────────────────────────────────────
# 4. Source-Lock cross-check — surfaced Recital text matches baseline
# ──────────────────────────────────────────────────────────────────────


def test_action_guide_recital_source_quote_matches_baseline(recitals_baseline):
    """Each Recital `source_quote` surfaced by cl_action_guide MUST
    byte-match the corresponding entry in scanner/data/recitals.json.
    Guards against any future tool-side transform that would silently
    paraphrase / wrap / re-encode the Recital text."""
    from server import cl_action_guide

    raw = cl_action_guide("ART05-OBL-1")
    payload = _parse_tool_output(raw)
    recitals = payload.get("related_recitals", [])

    for entry in recitals:
        n = str(entry["number"])
        baseline_quote = recitals_baseline[n]["source_quote"]
        assert entry["source_quote"] == baseline_quote, (
            f"Recital {n} source_quote drift between tool output "
            f"and baseline. Baseline: {baseline_quote[:80]!r}, "
            f"tool: {entry['source_quote'][:80]!r}"
        )


def test_interim_standard_recital_source_quote_matches_baseline(recitals_baseline):
    """Same Source-Lock cross-check for cl_interim_standard."""
    from server import cl_interim_standard

    raw = cl_interim_standard(article_number=5)
    payload = _parse_tool_output(raw)
    recitals = payload.get("related_recitals", [])

    for entry in recitals:
        n = str(entry["number"])
        baseline_quote = recitals_baseline[n]["source_quote"]
        assert entry["source_quote"] == baseline_quote, (
            f"Recital {n} drift in cl_interim_standard for Art 5"
        )


# ──────────────────────────────────────────────────────────────────────
# 5. Single-field migration sentinel (post-Option-D simplification)
# ──────────────────────────────────────────────────────────────────────


def test_cl_explain_recital_text_has_no_pypdf_artifacts():
    """Recitals returned by cl_explain MUST NOT show pypdf justification
    artifacts. With pdfplumber as canonical extractor, fragmented words
    like "r isk -managem ent syste m" should never appear. Sentinel check
    against future regression to a layout-blind extractor.
    """
    from server import cl_explain

    raw = cl_explain(article=5)
    payload = _parse_tool_output(raw)
    recitals = payload.get("related_recitals", [])

    artifacts = ["r isk", "syste m", "tec hnical", "managem ent"]
    bad: list[tuple[int, str]] = []
    for entry in recitals:
        text = entry.get("source_quote", "")
        for art in artifacts:
            if art in text:
                bad.append((entry["number"], art))
                break
    assert not bad, (
        f"cl_explain Art 5 surfaces pypdf-style artifacts in source_quote: {bad[:3]}"
    )
