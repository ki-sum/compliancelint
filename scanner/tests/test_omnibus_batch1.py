"""Omnibus batch 1 — Art 11, 17, 50, 72, 111 migrated to the consolidated text 02024R1689-20260727.

Reg (EU) 2026/1744 amended Art 11(1), 17(2), 50(7), 72(3) and 111(2) and added Art 111(4).
Every source_quote of these articles must occur in the consolidated text; every amended quote
keeps its 2024 wording in `_source_quote_history` (internal, stripped from served output).

Evidence: private consensus lock "omnibus-batch1" 2026-10-03 (parallel independent extraction
Claude + o3).
"""
import json
import os
import re

import pytest

HERE = os.path.dirname(__file__)
OBL_DIR = os.path.join(HERE, "..", "obligations")
DIFF_DIR = os.path.join(HERE, "..", "..", "docs", "sources", "diffs", "eu-ai-act",
                        "2024-07-12__2026-07-27", "per-article")

MIGRATED = {
    11: "art11-technical-documentation.json",
    17: "art17-quality-management.json",
    50: "art50-transparency-obligations.json",
    72: "art72-post-market-monitoring.json",
    111: "art111-transitional-provisions.json",
}
AMENDED = {
    "ART11-OBL-1b": 11, "ART11-PERM-1d": 11, "ART11-OBL-1e": 11, "ART11-OBL-1f": 11,
    "ART17-OBL-2": 17,
    "ART50-OBL-7": 50, "ART50-OBL-7a": 50, "ART50-EMP-7b": 50,
    "ART72-OBL-3": 72,
    "ART111-OBL-2": 111,
}
_FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.translate(_FOLD)).strip()


def _diff(article: int) -> dict:
    with open(os.path.join(DIFF_DIR, f"art{article}.diff.json"), encoding="utf-8") as f:
        return json.load(f)


def _obligations(article: int) -> dict:
    with open(os.path.join(OBL_DIR, MIGRATED[article]), encoding="utf-8") as f:
        return {o["id"]: o for o in json.load(f)["obligations"]}


def _in(quote: str, text: str) -> bool:
    q, t = _norm(quote), _norm(text)
    if q in t or q.rstrip(".;:,") in t:
        return True
    head, sep, body = q.partition(": ")
    return bool(sep) and head + ":" in t and body.rstrip(".;:,") in t


@pytest.mark.parametrize("article", sorted(MIGRATED))
def test_every_quote_occurs_in_consolidated_text(article):
    text = _diff(article)["to_text"]
    stale = [oid for oid, o in _obligations(article).items() if not _in(o["source_quote"], text)]
    assert not stale, f"Art {article}: quotes not in the consolidated text: {stale}"


@pytest.mark.parametrize("oid,article", sorted(AMENDED.items()))
def test_amended_quote_keeps_2024_wording_in_history(oid, article):
    o = _obligations(article)[oid]
    hist = o.get("_source_quote_history")
    assert hist, f"{oid}: no _source_quote_history"
    last = hist[-1]
    assert last["amending_celex"] == "32026R1744"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", last["superseded_on"])
    assert _in(last["source_quote"], _diff(article)["from_text"]), f"{oid}: history quote not in the 2024 text"
    assert not _in(last["source_quote"], _diff(article)["to_text"]), f"{oid}: history quote is still current"


def test_art111_4_added():
    o = _obligations(111)["ART111-OBL-4"]
    assert o["source"] == "Art. 111(4)"
    assert (o["addressee"], o["deontic_type"], o["modality"]) == ("provider", "obligation", "shall")
    assert "_source_quote_history" not in o
    assert {a["atom"] for a in o["decomposed_atoms"]} == {
        "legacy_generative_systems_comply_with_art50_2", "scope_placed_on_market_before_2026_08_02"}


def test_art50_7a_is_a_commission_duty_not_an_empowerment():
    o = _obligations(50)["ART50-OBL-7a"]  # ART50-EMP-7a until batch 2
    assert (o["addressee"], o["deontic_type"], o["modality"]) == ("commission", "obligation", "shall")
    served = json.dumps({k: v for k, v in o.items() if not k.startswith("_")}, ensure_ascii=False)
    served = re.sub(r'"_history": \[.*?\]', "", served)
    # Recital 41: such codes "do not grant a presumption of conformity" — the served text must say so
    # and must not claim the opposite (the 2024-era note did).
    assert "do not grant a presumption of conformity" in o["note"]
    assert "provides a presumption" not in served and "presumption of compliance" not in served


def test_art50_7_addressee_is_the_commission():
    assert _obligations(50)["ART50-OBL-7"]["addressee"] == "commission"


def test_art17_2_rigour_floor_is_its_own_atom():
    atoms = {a["atom"]: a["requirement"] for a in _obligations(17)["ART17-OBL-2"]["decomposed_atoms"]}
    assert set(atoms) == {"proportionate_implementation", "rigour_and_protection_floor"}
    assert "SMC" in atoms["proportionate_implementation"]


@pytest.mark.parametrize("oid,atom", [
    ("ART11-PERM-1d", "sme_or_smc_may_simplify_documentation"),
    ("ART11-OBL-1e", "commission_establishes_simplified_form"),
    ("ART11-OBL-1f", "sme_or_smc_must_use_official_form"),
])
def test_art11_sme_atoms_cover_smcs(oid, atom):
    atoms = {a["atom"]: a for a in _obligations(11)[oid]["decomposed_atoms"]}
    assert atom in atoms and "SMC" in atoms[atom]["requirement"]
    renamed = [h for a in atoms.values() for h in a.get("_history", [])]
    assert renamed and all(h["amending_celex"] == "32026R1744" for h in renamed)


def test_art111_2_no_longer_names_2_august_2026():
    o = _obligations(111)["ART111-OBL-2"]
    served = json.dumps({k: v for k, v in o.items() if not k.startswith("_")}, ensure_ascii=False)
    served = re.sub(r'"_history": \[.*?\]', "", served)
    assert "2 August 2026" not in served
    assert "date of application of Chapter III" in o["source_quote"]

