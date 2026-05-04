"""§AD.* Recital→Article mapping regression test (2026-05-04 batch).

After fetch_recitals.py extracts the 180 Recitals, the
`related_articles[]` field on each entry lists which AI Act articles the
Recital references. The initial extraction populated this via Article-N
regex over the Recital text — many real topic mappings were missed
because the Recital uses different vocabulary than the article title
(e.g., Recital 96 IS the FRIA Recital but doesn't say "Article 27"
literally).

The 2026-05-04 batch added 48 (Recital, Article) pairs validated by a
sub-agent topic review (see audit/recital-mapping-validated-2026-05-04.md
for the per-pair legal justification). This test asserts those 48 pairs
remain present so a future regeneration of recitals.json or a regex
rebuild doesn't silently strip them.

If `propose_recital_mappings.py` + `apply_recital_mappings_2026_05_04.py`
are re-run, the result is idempotent — these mappings will still hold.
If a future revision INTENTIONALLY removes a mapping, update this test
in the same commit and document the reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RECITALS_JSON = REPO_ROOT / "scanner" / "data" / "recitals.json"
INDEX_JSON = REPO_ROOT / "scanner" / "data" / "article_recital_index.json"


# (Article, Recital) pairs from the 2026-05-04 sub-agent validation.
# Mirrors APPROVED_MAPPINGS in apply_recital_mappings_2026_05_04.py.
EXPECTED_MAPPINGS: list[tuple[int, int]] = [
    (9, 64), (9, 65),
    (10, 67), (10, 68), (10, 69),
    (11, 71),
    (13, 66), (13, 72),
    (15, 66), (15, 74), (15, 76), (15, 77),
    (17, 81), (17, 146),
    (19, 71),
    (20, 155),
    (22, 82),
    (23, 83), (23, 84),
    (27, 96),
    (41, 121),
    (43, 123), (43, 124), (43, 125), (43, 126),
    (47, 77),
    (49, 131),
    (53, 97), (53, 101), (53, 104), (53, 105),
    (53, 106), (53, 107), (53, 108), (53, 109),
    (54, 82),
    (60, 141),
    (61, 141),
    (71, 131),
    (72, 81), (72, 155),
    (73, 155),
    (80, 53),
    (86, 10),
    (91, 163), (91, 164),
    (92, 164),
    (111, 178),
]


@pytest.fixture(scope="module")
def recitals():
    with RECITALS_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def index():
    with INDEX_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_expected_mappings_present_in_recitals_json(recitals):
    """Every (Article, Recital) pair from the 2026-05-04 batch MUST be
    listed in `recitals[Recital]['related_articles']`. Symmetric to the
    article_recital_index.json check below."""
    missing: list[tuple[int, int]] = []
    for article, recital in EXPECTED_MAPPINGS:
        entry = recitals.get(str(recital))
        assert entry is not None, f"Recital {recital} missing from recitals.json"
        related = entry.get("related_articles", [])
        if article not in related:
            missing.append((article, recital))
    assert not missing, (
        f"Recital→Article mappings missing in recitals.json: {missing[:10]}"
        + (f" (and {len(missing) - 10} more)" if len(missing) > 10 else "")
    )


def test_expected_mappings_present_in_article_index(index):
    """Mirror check on article_recital_index.json — both directions
    (article_to_recitals and recital_to_articles) must reflect the same
    pairs. Drift between the two files indicates apply step ran
    incorrectly."""
    art_to_rec = index.get("article_to_recitals", {})
    rec_to_art = index.get("recital_to_articles", {})

    missing_in_art_to_rec: list[tuple[int, int]] = []
    missing_in_rec_to_art: list[tuple[int, int]] = []
    for article, recital in EXPECTED_MAPPINGS:
        recitals_for_art = art_to_rec.get(str(article), [])
        if recital not in recitals_for_art:
            missing_in_art_to_rec.append((article, recital))
        articles_for_rec = rec_to_art.get(str(recital), [])
        if article not in articles_for_rec:
            missing_in_rec_to_art.append((article, recital))

    assert not missing_in_art_to_rec, (
        f"Mappings missing in article_to_recitals: {missing_in_art_to_rec[:10]}"
    )
    assert not missing_in_rec_to_art, (
        f"Mappings missing in recital_to_articles: {missing_in_rec_to_art[:10]}"
    )


def test_minimum_article_coverage(index):
    """At least 40 articles must have ≥1 mapped Recital. The 2026-05-04
    batch brought coverage from 18 → 45+ articles. This is a floor —
    bump it up after future mapping additions land."""
    art_to_rec = index.get("article_to_recitals", {})
    n_articles_mapped = len([k for k, v in art_to_rec.items() if v])
    assert n_articles_mapped >= 40, (
        f"Article coverage regression: only {n_articles_mapped} articles "
        f"have ≥1 mapped Recital (floor: 40). Re-run "
        f"apply_recital_mappings_2026_05_04.py or investigate drift."
    )


def test_2026_05_04_batch_dual_mapping_consistency(recitals, index):
    """For the 48 pairs added by apply_recital_mappings_2026_05_04.py, the
    pair MUST appear consistently in both files. This is narrower than a
    full dual-mapping check because:
      - recitals.json `related_articles[]` was originally populated by
        Article-N regex extraction over Recital text (some entries
        legitimately reference other regulations' articles, e.g. GDPR);
      - article_recital_index.json was built separately from EC
        co-citation + obligation JSON cross-refs (curated subset).
    The two files have DIFFERENT data origins and aren't expected to
    agree on pre-existing entries. Only the §AD.* batch needs both-side
    consistency by virtue of how we applied it.
    """
    rec_to_art_index = index.get("recital_to_articles", {})
    art_to_rec_index = index.get("article_to_recitals", {})

    drift: list[str] = []
    for article, recital in EXPECTED_MAPPINGS:
        rec_key = str(recital)
        art_key = str(article)
        related_in_recital = recitals.get(rec_key, {}).get("related_articles", [])
        related_in_index_recital = rec_to_art_index.get(rec_key, [])
        recitals_in_index_article = art_to_rec_index.get(art_key, [])

        if article not in related_in_recital:
            drift.append(f"recitals.json[{rec_key}].related_articles missing Art {article}")
        if article not in related_in_index_recital:
            drift.append(f"index.recital_to_articles[{rec_key}] missing Art {article}")
        if recital not in recitals_in_index_article:
            drift.append(f"index.article_to_recitals[{art_key}] missing Recital {recital}")

    assert not drift, (
        f"§AD.* 2026-05-04 batch drift between recitals.json and "
        f"article_recital_index.json: {drift[:5]}"
    )
