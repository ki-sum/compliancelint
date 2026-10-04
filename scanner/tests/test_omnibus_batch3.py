"""Omnibus batch 3 — Art 10, new Art 4a and Art 6 migrated to the consolidated text 02024R1689-20260727.

Reg (EU) 2026/1744 deleted Art 10(5) and moved its content to new Art 4a(1) (providers of high-risk AI
systems may process special categories of personal data for bias detection and correction); new Art 4a(2)
extends that legal basis to deployers of high-risk AI systems and to providers and deployers of other AI
systems and models, without creating a duty to detect bias. Art 10(1) and (6) now refer to "paragraphs 2, 3
and 4 of this Article and ... Article 4a(1)". New Art 6(1a)-(1c) narrow "safety component" and the
third-party-assessment condition of Art 6(1)(b) — scope modifiers folded into ART06-CLS-1 (founder 2026-10-04).

Evidence: private consensus lock "omnibus-batch3" 2026-10-04 (parallel independent extraction Claude + o3).
"""
import json
import os
import re

import pytest

HERE = os.path.dirname(__file__)
SCANNER = os.path.normpath(os.path.join(HERE, ".."))
OBL_DIR = os.path.join(SCANNER, "obligations")
DIFF_DIR = os.path.join(SCANNER, "..", "docs", "sources", "diffs", "eu-ai-act",
                        "2024-07-12__2026-07-27", "per-article")

MIGRATED = {
    "4a": "art04a-special-category-data-bias.json",
    "6": "art06-risk-classification.json",
    "10": "art10-data-governance.json",
}
_FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.translate(_FOLD)).strip()


def _diff(article: str) -> dict:
    with open(os.path.join(DIFF_DIR, f"art{article}.diff.json"), encoding="utf-8") as f:
        return json.load(f)


def _file(article: str) -> dict:
    with open(os.path.join(OBL_DIR, MIGRATED[article]), encoding="utf-8") as f:
        return json.load(f)


def _obligations(article: str) -> dict:
    return {o["id"]: o for o in _file(article)["obligations"]}


def _atoms(article: str, oid: str) -> dict:
    return {a["atom"]: a for a in _obligations(article)[oid]["decomposed_atoms"]}


def _in(quote: str, text: str) -> bool:
    q, t = _norm(quote), _norm(text)
    return q in t or q.rstrip(".;:,") in t


# ── Obligation records ──

@pytest.mark.parametrize("article", sorted(MIGRATED))
def test_every_quote_occurs_in_consolidated_text(article):
    text = _diff(article)["to_text"]
    stale = [oid for oid, o in _obligations(article).items() if not _in(o["source_quote"], text)]
    assert not stale, f"Art {article}: quotes not in the consolidated text: {stale}"


@pytest.mark.parametrize("oid", ["ART10-OBL-1", "ART10-OBL-6"])
def test_amended_art10_quote_keeps_2024_wording_in_history(oid):
    o = _obligations("10")[oid]
    last = o["_source_quote_history"][-1]
    assert last["amending_celex"] == "32026R1744"
    assert _in(last["source_quote"], _diff("10")["from_text"])
    assert not _in(last["source_quote"], _diff("10")["to_text"])
    assert "paragraphs 2, 3 and 4 of this Article and" in o["source_quote"] and "Article 4a(1)" in o["source_quote"]


def test_art10_quality_atom_follows_the_new_cross_reference():
    atoms = _atoms("10", "ART10-OBL-1")
    assert set(atoms) == {"uses_quality_datasets", "all_dataset_types_covered"}
    assert "Art. 4a(1)" in atoms["uses_quality_datasets"]["requirement"]
    assert "paragraphs 2-5" in atoms["uses_quality_datasets"]["_history"][-1]["requirement"]
    assert "_history" not in atoms["all_dataset_types_covered"]   # consensus D1: unchanged element


def test_art10_5_record_removed_and_kept_for_audit():
    data = _file("10")
    assert "ART10-PERM-5" not in {o["id"] for o in data["obligations"]}
    (gone,) = [g for g in data["_metadata"]["removed_obligations"] if g["record"]["id"] == "ART10-PERM-5"]
    assert gone["moved_to"] == ["ART04a-PERM-1"]
    assert gone["amending_celex"] == "32026R1744"
    assert _in(gone["record"]["source_quote"], _diff("10")["from_text"])
    entry = data["_metadata"]["amendments"][-1]
    assert entry["obligations_removed"] == ["ART10-PERM-5"]


def test_art4a_1_is_the_high_risk_provider_permission_with_all_six_conditions():
    o = _obligations("4a")["ART04a-PERM-1"]
    assert (o["source"], o["addressee"], o["deontic_type"], o["modality"]) == (
        "Art. 4a(1)", "provider", "permission", "may")
    assert o["context_skip_field"] == "processes_special_category_data" and o["context_skip_value"] is False
    atoms = _atoms("4a", "ART04a-PERM-1")
    assert set(atoms) == {"special_data_strictly_necessary", "appropriate_safeguards", "data_protection_law_applies",
                          "other_data_insufficient", "reuse_limits_and_privacy_measures",
                          "access_controls_and_confidentiality", "no_access_by_other_parties",
                          "deletion_after_correction", "processing_records_state_reasons"}
    # the two atoms carried over from former ART10-PERM-5 (consensus D4) were reworded by o3 Prompt D A03
    # (founder 2026-10-04): statutory scope and full safeguard language
    removed = {g["record"]["id"]: g["record"] for g in _file("10")["_metadata"]["removed_obligations"]}
    old = {a["atom"]: a for a in removed["ART10-PERM-5"]["decomposed_atoms"]}
    assert atoms["special_data_strictly_necessary"]["requirement"].startswith(
        "Providers of high-risk AI systems MAY exceptionally process special categories of personal data")
    assert "in accordance with Art. 10(2), points (f) and (g)" in atoms["special_data_strictly_necessary"]["requirement"]
    assert atoms["appropriate_safeguards"]["requirement"] == (
        "Such processing SHALL be subject to appropriate safeguards for the fundamental rights and freedoms of natural persons.")
    for kept in ("special_data_strictly_necessary", "appropriate_safeguards"):
        assert atoms[kept]["description"] == old[kept]["description"]
        assert atoms[kept]["requirement"] != old[kept]["requirement"]


def test_art4a_2_extends_the_legal_basis_without_a_duty_to_detect_bias():
    o = _obligations("4a")["ART04a-PERM-2"]
    assert (o["source"], o["addressee"], o["deontic_type"], o["modality"]) == (
        "Art. 4a(2)", "provider_and_deployer", "permission", "may")
    assert "deployers of high-risk AI systems" in o["source_quote"]
    atoms = _atoms("4a", "ART04a-PERM-2")
    assert set(atoms) == {"bias_processing_strictly_necessary", "paragraph_1_conditions_applied", "no_duty_to_detect_bias"}
    assert "does NOT create any obligation" in atoms["no_duty_to_detect_bias"]["requirement"]


def test_art4a_file_is_the_lettered_article():
    data = _file("4a")
    assert data["_metadata"]["article"] == "4a"
    assert [o["id"] for o in data["obligations"]] == ["ART04a-PERM-1", "ART04a-PERM-2"]
    assert data["summary"]["permission_count"] == 2 and data["summary"]["total_obligations"] == 2


def test_art6_1_requires_both_conditions_and_carries_paragraphs_1a_to_1c():
    o = _obligations("6")["ART06-CLS-1"]
    assert o["source"] == "Art. 6(1), (1a)-(1c)"
    for para in ("1a. For the purposes of this Regulation", "1b. Notwithstanding paragraph 1a", "1c. A product"):
        assert para in o["source_quote"], para
    assert o["_source_quote_history"][-1]["source_quote"].startswith("Irrespective of whether an AI system")
    atoms = [a["atom"] for a in o["decomposed_atoms"]]
    assert atoms == ["both_conditions_required", "safety_component_or_product", "requires_third_party_assessment",
                     "non_safety_aspects_not_safety_component", "endangering_failure_is_safety_component",
                     "non_safety_third_party_assessment_excluded"]
    by = {a["atom"]: a for a in o["decomposed_atoms"]}
    assert "both" in by["both_conditions_required"]["requirement"]
    # consensus D7: the old (a)/(b) atoms read as if one condition alone made the system high-risk
    for cond in ("safety_component_or_product", "requires_third_party_assessment"):
        assert by[cond]["requirement"].startswith("Only where"), cond
        assert by[cond]["_history"][-1]["requirement"].startswith("System SHALL be considered high-risk if"), cond
    assert (o["addressee"], o["deontic_type"]) == ("provider", "classification_rule")   # consensus D6


def _served(x):
    if isinstance(x, dict):
        return {k: _served(v) for k, v in x.items() if not k.startswith("_")}
    if isinstance(x, list):
        return [_served(v) for v in x]
    return x


def test_removed_id_is_gone_from_the_scanner():
    """ART10-PERM-5 may survive only in internal audit keys (`_metadata`, `_`-prefixed keys)."""
    hits = []
    scanned = 0
    for root, _dirs, files in os.walk(SCANNER):
        parts = os.path.relpath(root, SCANNER).split(os.sep)
        if "__pycache__" in parts or parts[0] == "tests":
            continue
        for name in files:
            if not name.endswith((".py", ".json", ".md")):
                continue
            path = os.path.join(root, name)
            text = open(path, encoding="utf-8").read()
            scanned += 1
            if "ART10-PERM-5" not in text:
                continue
            if name.endswith(".json") and os.path.basename(root) == "obligations":
                if "ART10-PERM-5" not in json.dumps(_served(json.loads(text)), ensure_ascii=False):
                    continue
            hits.append(os.path.relpath(path, SCANNER))
    assert scanned > 100, f"walked only {scanned} files"
    assert not hits, f"ART10-PERM-5 still referenced in {hits}"
