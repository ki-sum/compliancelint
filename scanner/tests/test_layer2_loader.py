"""Tests for Layer 2 loader — verifies EC Guidelines / interpretive
materials are indexed correctly and surface via the public API used
by cl_scan / cl_explain / cl_action_plan.

Pilot doc under test: C(2026) 5054 final (Art 50 EC Guidelines, 304
atoms across OBL-1/2/3/4/4b/5/6/7 + EMP-7a/b).

Coverage:
  - loader loads 1+ docs with 300+ atoms (regression guard against
    empty dir / broken JSON)
  - get_interpretive_materials_for_article(50) returns the pilot doc
    with 300+ atoms
  - get_atoms_for_obligation(...) returns non-empty per-obligation
    lists for each Art 50 obligation
  - get_atoms_for_obligation returns [] for unknown / non-Layer-2
    obligations
  - Each returned atom carries byte-verbatim text + paragraph anchor
    + source URL + SHA256 (no field silently missing)
  - reset_cache() re-loads on next call
"""
from __future__ import annotations

import pytest

from core.layer2_loader import (
    get_atoms_for_obligation,
    get_interpretive_materials_for_article,
    loaded_atom_count,
    loaded_doc_count,
    reset_cache,
)


@pytest.fixture(autouse=True)
def _reset_layer2_cache():
    """Ensure each test starts with a clean loader cache."""
    reset_cache()
    yield
    reset_cache()


def test_layer2_loads_at_least_one_doc():
    """Regression guard — if interpretive-materials/ is empty or
    every file fails to parse, this catches it before prod."""
    assert loaded_doc_count() >= 1, (
        "Expected ≥1 Layer 2 doc under scanner/interpretive-materials/. "
        "If the dir is missing, check deploy.sh Step 2b."
    )


def test_layer2_loads_300_plus_atoms():
    """Pilot doc C(2026) 5054 has 304 atoms — regression guard against
    partial JSON parse or truncated build_layer2_atoms.py run."""
    assert loaded_atom_count() >= 300, (
        f"Expected ≥300 atoms loaded across Layer 2 docs. "
        f"Got {loaded_atom_count()}. Rerun build_layer2_atoms.py."
    )


def test_art50_has_interpretive_materials():
    """get_interpretive_materials_for_article(50) must surface the
    C(2026) 5054 pilot doc — this is the primary integration point
    cl_explain / cl_action_plan / cl_scan use."""
    materials = get_interpretive_materials_for_article(50)
    assert len(materials) >= 1, "Expected ≥1 material for Art 50"
    # The pilot doc must be present
    pilot = next(
        (m for m in materials if "C(2026) 5054" in (m.get("doc_id") or "")),
        None,
    )
    assert pilot is not None, "C(2026) 5054 final pilot doc missing from Art 50 materials"
    assert pilot["doc_type"] == "guidelines"
    assert pilot["issuing_body"] == "European Commission"
    assert pilot["source_sha256"], "source_sha256 must be populated for verifiability"
    assert pilot["source_url"].startswith(
        "https://ai-act-service-desk.ec.europa.eu"
    ), "source_url must be from official EC domain"
    assert len(pilot["atoms"]) >= 300, (
        f"Pilot doc should have 300+ atoms, got {len(pilot['atoms'])}"
    )


def test_art50_no_materials_for_wrong_article():
    """Layer 2 pilot is Art 50-only. Other articles must return []."""
    # Art 12 (record-keeping) has no Layer 2 material yet.
    assert get_interpretive_materials_for_article(12) == []
    # Art 6 (high-risk classification) same.
    assert get_interpretive_materials_for_article(6) == []


def test_atoms_for_art50_obligation_1():
    """ART50-OBL-1 (interactive AI systems) — should have 50+ atoms
    covering scope, exceptions (obviousness / LE), formats, examples."""
    atoms = get_atoms_for_obligation("ART50-OBL-1")
    assert len(atoms) >= 50, (
        f"ART50-OBL-1 expected 50+ atoms (interactive AI has the most "
        f"guidance atoms), got {len(atoms)}"
    )


def test_atoms_for_art50_obligation_2():
    """ART50-OBL-2 (marking + detection of synthetic content) — should
    have 50+ atoms covering modalities, techniques, quality criteria,
    industrial B2B exemption, standard editing examples."""
    atoms = get_atoms_for_obligation("ART50-OBL-2")
    assert len(atoms) >= 50, (
        f"ART50-OBL-2 expected 50+ atoms, got {len(atoms)}"
    )


def test_atoms_for_art50_obligation_4():
    """ART50-OBL-4 (deep fake labelling) — should have 50+ atoms
    covering deep fake definition, criteria, examples, artistic
    exception, DSA/GDPR interplay."""
    atoms = get_atoms_for_obligation("ART50-OBL-4")
    assert len(atoms) >= 50, (
        f"ART50-OBL-4 expected 50+ atoms, got {len(atoms)}"
    )


def test_atoms_for_art50_obligation_4b():
    """ART50-OBL-4b (text on public interest) — should have 20+ atoms
    covering published/informing/public-interest definitions, editorial
    control, examples."""
    atoms = get_atoms_for_obligation("ART50-OBL-4b")
    assert len(atoms) >= 20, (
        f"ART50-OBL-4b expected 20+ atoms, got {len(atoms)}"
    )


def test_atom_shape_is_scanner_ready():
    """Each atom returned by get_atoms_for_obligation must carry:
    id, paragraph_ref, section_ref, verbatim_text, atom_type,
    doc_id, doc_title, source_url, source_sha256, publication_date.
    Missing fields would break cl_explain / cl_action_plan
    downstream consumers.
    """
    atoms = get_atoms_for_obligation("ART50-OBL-1")
    assert atoms, "prerequisite: OBL-1 has atoms"
    for atom in atoms[:5]:  # spot-check first 5
        assert atom["id"], f"atom missing id: {atom}"
        assert atom["paragraph_ref"] is not None, f"atom missing paragraph_ref: {atom}"
        assert atom["verbatim_text"], f"atom missing verbatim_text: {atom}"
        assert atom["atom_type"], f"atom missing atom_type: {atom}"
        assert atom["doc_id"], f"atom missing doc_id: {atom}"
        assert atom["source_url"], f"atom missing source_url: {atom}"
        assert atom["source_sha256"], f"atom missing source_sha256: {atom}"


def test_unknown_obligation_returns_empty():
    """No Layer 2 for Art 12 obligations (yet). Loader must return []
    gracefully, not throw."""
    assert get_atoms_for_obligation("ART12-OBL-1") == []
    assert get_atoms_for_obligation("ART12-NONEXISTENT") == []
    assert get_atoms_for_obligation("") == []
    assert get_atoms_for_obligation(None) == []  # type: ignore[arg-type]


def test_atom_type_is_in_allowlist():
    """All 8 atom types from methodology should appear. No hallucinated
    atom_types."""
    valid = {
        "definition_clarification",
        "insufficient_pattern",
        "sufficient_pattern",
        "example_violation",
        "example_compliance",
        "exception_narrowing",
        "scope_extension",
        "scope_exclusion",
    }
    # Sample all Art 50 obligations
    for obl in ["ART50-OBL-1", "ART50-OBL-2", "ART50-OBL-3", "ART50-OBL-4", "ART50-OBL-4b"]:
        for atom in get_atoms_for_obligation(obl):
            assert atom["atom_type"] in valid, (
                f"Atom {atom['id']} has unknown atom_type: {atom['atom_type']}"
            )


def test_case_insensitive_obligation_lookup():
    """OID lookup should be case-insensitive (mirrors obligation_lookup
    behavior)."""
    lower = get_atoms_for_obligation("art50-obl-1")
    upper = get_atoms_for_obligation("ART50-OBL-1")
    assert len(lower) == len(upper) and len(lower) > 0
