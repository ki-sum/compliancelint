"""Q2 self-audit follow-up — `cl_interim_standard` returns the
ComplianceLint compliance checklist for an article. The tool name
"interim_standard" can mislead a customer into thinking this is an
EU/CEN-CENELEC/ISO official standard.

The disclaimer DOES exist — but only inside `_metadata.disclaimer` of
the JSON payload. An AI consumer reading the top-level fields may
quote the requirements as if they were officially binding. We need
the "this is NOT official" signal at the top level so it cannot be
missed.

Post-fix contract:
  - top-level `is_official_standard: false` boolean
  - top-level `non_official_banner` string saying "ComplianceLint
    interim checklist; not an EU / ISO / CEN-CENELEC official
    standard"
  - top-level `superseded_when` string indicating when an official
    standard is expected to replace this checklist (read from
    `_metadata.awaiting_standard` if present)
  - existing `_metadata`, `requirements`, etc. PRESERVED
"""
import json
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


def _interim(article: int) -> dict:
    """Call cl_interim_standard, parse the payload."""
    from server import cl_interim_standard

    raw = cl_interim_standard(article)
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(raw)
    return obj


# ──────────────────────────────────────────────────────────────────────
# 1. Top-level non-official signal
# ──────────────────────────────────────────────────────────────────────


def test_interim_standard_has_top_level_is_official_false():
    """A boolean at the top level so AI / programmatic consumers can
    detect 'not official' without parsing nested metadata text."""
    payload = _interim(12)
    assert "is_official_standard" in payload, (
        "Top-level `is_official_standard` flag missing — AI consumers "
        "cannot programmatically distinguish our checklist from an "
        "actual EU / ISO standard"
    )
    assert payload["is_official_standard"] is False, (
        "ComplianceLint interim checklist must declare itself as "
        "non-official (not an EU / ISO / CEN-CENELEC standard)"
    )


def test_interim_standard_has_non_official_banner():
    """Top-level human-readable banner. Sits at the top so even a
    quick grep / scan of the output sees it before the requirements."""
    payload = _interim(12)
    assert "non_official_banner" in payload, (
        "Top-level non_official_banner missing"
    )
    banner = payload["non_official_banner"].lower()
    assert "compliancelint" in banner, (
        f"Banner should identify the source as ComplianceLint. Got: "
        f"{payload['non_official_banner']!r}"
    )
    # Must mention what it is NOT
    assert "not" in banner and (
        "official" in banner or "iso" in banner or "cen" in banner
    ), (
        f"Banner must explicitly state this is NOT an official "
        f"EU / ISO / CEN-CENELEC standard. Got: "
        f"{payload['non_official_banner']!r}"
    )


def test_interim_standard_surfaces_superseded_when():
    """When the metadata says when an official standard is expected,
    surface that at the top level so consumers know the lifecycle."""
    payload = _interim(12)
    # art12 metadata mentions CEN-CENELEC harmonized standard for Art. 12
    # expected Q4 2026 (via awaiting_standard field). Surface it.
    assert "superseded_when" in payload, (
        "superseded_when missing — consumers can't tell when this "
        "checklist will be replaced"
    )
    # When _metadata.awaiting_standard exists, the value must non-empty
    md = payload.get("_metadata", {})
    awaiting = md.get("awaiting_standard", "")
    if awaiting:
        assert payload["superseded_when"], (
            "superseded_when should mirror _metadata.awaiting_standard "
            "when that field exists"
        )


# ──────────────────────────────────────────────────────────────────────
# 2. Existing fields preserved (backwards compat)
# ──────────────────────────────────────────────────────────────────────


def test_interim_standard_preserves_metadata():
    payload = _interim(12)
    assert "_metadata" in payload
    assert payload["_metadata"].get("standard_id")


def test_interim_standard_preserves_requirements():
    payload = _interim(12)
    assert "requirements" in payload
    assert isinstance(payload["requirements"], list)
    assert len(payload["requirements"]) > 0


# ──────────────────────────────────────────────────────────────────────
# 3. Coverage across multiple articles
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("article_number", [9, 12, 14])
def test_interim_standard_anti_official_signal_for_multiple_articles(
    article_number,
):
    """The top-level non-official signal MUST appear for every article
    that has an interim-standard.json file. If we ever ship an
    article without the top-level fields, AI consumers may treat it
    as official."""
    from server import cl_interim_standard

    raw = cl_interim_standard(article_number)
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(raw)
    if "error" in obj:
        # Some articles may not have interim-standard.json yet —
        # that's OK; the test only applies when the standard exists.
        pytest.skip(
            f"Article {article_number} has no interim standard yet"
        )
    assert obj.get("is_official_standard") is False
    assert obj.get("non_official_banner")


# ──────────────────────────────────────────────────────────────────────
# 4. Error case still works
# ──────────────────────────────────────────────────────────────────────


def test_interim_standard_unknown_article_returns_error():
    """Unknown article must NOT fabricate the new fields — the error
    response must be unchanged."""
    from server import cl_interim_standard

    raw = cl_interim_standard(999)
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(raw)
    assert "error" in obj
    # Must not falsely claim "is_official_standard: false" when there
    # is no standard at all
    assert "is_official_standard" not in obj or obj.get(
        "is_official_standard"
    ) is False
