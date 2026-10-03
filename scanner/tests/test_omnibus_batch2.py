"""Omnibus batch 2 — Art 4, 25, 27, 43 migrated to the consolidated text 02024R1689-20260727.

Reg (EU) 2026/1744 amended Art 4 (AI literacy: "support the development", no guarantee of a
specific level), Art 25(2) (points (a)-(c) of the cooperation duty) and 25(4) ("AI model"),
Art 27(4) (obligation -> deployer permission) and Art 43(3) (QMS assessment, Annex VII points 3
and 5; new fourth subparagraph: Annex I + Annex III systems follow the Annex I procedure — a scope
modifier of 43(1)/(2), not a record of its own, founder 2026-10-03).

Evidence: private consensus lock "omnibus-batch2" 2026-10-03 (parallel independent extraction
Claude + o3).
"""
import json
import os
import re

import pytest

from core.protocol import BaseArticleModule, ComplianceLevel
from conftest import _ctx_with

HERE = os.path.dirname(__file__)
SCANNER = os.path.normpath(os.path.join(HERE, ".."))
OBL_DIR = os.path.join(SCANNER, "obligations")
DIFF_DIR = os.path.join(SCANNER, "..", "docs", "sources", "diffs", "eu-ai-act",
                        "2024-07-12__2026-07-27", "per-article")

MIGRATED = {
    4: "art04-ai-literacy.json",
    25: "art25-value-chain-responsibilities.json",
    27: "art27-fundamental-rights-impact.json",
    43: "art43-conformity-assessment.json",
}
AMENDED = {
    "ART04-OBL-1": 4,
    "ART25-OBL-2": 25, "ART25-EXC-2": 25, "ART25-OBL-4": 25,
    "ART27-PERM-4": 27,
    "ART43-OBL-3": 43,
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


def _atoms(article: int, oid: str) -> dict:
    return {a["atom"]: a for a in _obligations(article)[oid]["decomposed_atoms"]}


def _in(quote: str, text: str) -> bool:
    q, t = _norm(quote), _norm(text)
    if q in t or q.rstrip(".;:,") in t:
        return True
    head, sep, body = q.partition(": ")
    return bool(sep) and head + ":" in t and body.rstrip(".;:,") in t


# ── Obligation records ──

@pytest.mark.parametrize("article", sorted(MIGRATED))
def test_every_quote_occurs_in_consolidated_text(article):
    text = _diff(article)["to_text"]
    stale = [oid for oid, o in _obligations(article).items() if not _in(o["source_quote"], text)]
    assert not stale, f"Art {article}: quotes not in the consolidated text: {stale}"


@pytest.mark.parametrize("oid,article", sorted(AMENDED.items()))
def test_amended_quote_keeps_2024_wording_in_history(oid, article):
    hist = _obligations(article)[oid].get("_source_quote_history")
    assert hist, f"{oid}: no _source_quote_history"
    last = hist[-1]
    assert last["amending_celex"] == "32026R1744"
    assert _in(last["source_quote"], _diff(article)["from_text"]), f"{oid}: history quote not in the 2024 text"
    assert not _in(last["source_quote"], _diff(article)["to_text"]), f"{oid}: history quote is still current"


def test_art4_supports_literacy_without_guaranteeing_a_level():
    o = _obligations(4)["ART04-OBL-1"]
    assert o["source"] == "Art. 4(1)"
    assert (o["addressee"], o["deontic_type"], o["modality"]) == ("provider_and_deployer", "obligation", "shall")
    atoms = _atoms(4, "ART04-OBL-1")
    assert set(atoms) == {"measures_taken_to_support_ai_literacy", "staff_literacy_covered",
                          "context_considered", "affected_persons_considered", "no_guarantee_of_specific_level"}
    assert atoms["measures_taken_to_support_ai_literacy"]["_history"][-1]["atom"] == "measures_taken_for_ai_literacy"
    assert "support the development" in atoms["measures_taken_to_support_ai_literacy"]["requirement"]
    assert "sufficient level" not in atoms["measures_taken_to_support_ai_literacy"]["requirement"]
    # consensus D1: elements the amendment did not change keep their existing atoms
    for unchanged in ("context_considered", "affected_persons_considered"):
        assert "_history" not in atoms[unchanged], unchanged
    # Prompt D A01 (o3): "Literacy SHALL cover ..." read as an outcome duty after the amendment
    staff = atoms["staff_literacy_covered"]
    assert staff["requirement"].startswith("The measures SHALL support the development of AI literacy")
    assert staff["_history"][-1]["requirement"].startswith("Literacy SHALL cover")


def test_art25_2_cooperation_includes_points_a_to_c():
    atoms = _atoms(25, "ART25-OBL-2")
    assert set(atoms) == {"initial_provider_cooperates", "initial_provider_shares_information",
                          "technical_documentation_made_available",
                          "known_limitations_and_failure_modes_shared",
                          "targeted_technical_access_provided"}
    assert "_history" not in atoms["initial_provider_cooperates"]
    assert "_history" not in atoms["initial_provider_shares_information"]
    assert "Article 16" in atoms["technical_documentation_made_available"]["requirement"]
    assert "testing and validation" in atoms["targeted_technical_access_provided"]["requirement"]


def test_art25_exc2_derogates_paragraph_2_not_paragraph_4():
    o = _obligations(25)["ART25-EXC-2"]
    assert o["linked_obligation"] == ["ART25-OBL-2"]
    assert "obligation to cooperate with the new providers" in o["source_quote"]
    assert _obligations(25)["ART25-EXC-4"]["linked_obligation"] == ["ART25-OBL-4"]


def test_art25_4_covers_suppliers_of_ai_models():
    o = _obligations(25)["ART25-OBL-4"]
    assert "AI model" in o["source_quote"]
    assert o["addressee"] == "provider"
    assert "AI model" in o["addressee_note"]


def test_art27_4_is_a_deployer_permission():
    obls = _obligations(27)
    assert "ART27-OBL-4" not in obls
    o = obls["ART27-PERM-4"]
    assert (o["addressee"], o["deontic_type"], o["modality"]) == ("deployer", "permission", "may")
    assert o["_id_history"][-1]["id"] == "ART27-OBL-4"
    assert set(_atoms(27, "ART27-PERM-4")) == {"fria_may_reuse_dpia"}
    # never evaluated (permission); the DPIA condition lives in the atom — Logic Lock: no dangling scope fields
    assert "context_skip_field" not in o and "scope_limitation" not in o
    assert "already met through a data protection impact assessment" in _atoms(27, "ART27-PERM-4")["fria_may_reuse_dpia"]["requirement"]


def test_art43_3_assessment_covers_qms_and_annex_vii_points():
    atoms = _atoms(43, "ART43-OBL-3")
    assert set(atoms) == {"sectoral_assessment", "section_2_requirements_in_assessment",
                          "qms_assessment_included", "annex_vii_points_apply"}
    # Prompt D A04 (o3): "Annex I product systems" was overbroad — Section A legislation
    assert "Section A of Annex I" in atoms["sectoral_assessment"]["requirement"]
    assert atoms["sectoral_assessment"]["_history"][-1]["requirement"] == "SHALL follow relevant sectoral conformity assessment procedure"
    assert "Article 17" in atoms["qms_assessment_included"]["requirement"]


def test_art43_3_fourth_subparagraph_narrows_43_1_and_43_2():
    """Sectoral overlap rule = scope modifier (methodology rule, founder 2026-10-03): no new record;
    43(1)/(2) carry it in their scope, with the verbatim text of the fourth subparagraph."""
    obls = _obligations(43)
    assert set(obls) == {"ART43-OBL-1", "ART43-OBL-2", "ART43-OBL-3", "ART43-OBL-4"}
    text = _diff(43)["to_text"]
    for oid in ("ART43-OBL-1", "ART43-OBL-2"):
        o = obls[oid]
        assert "Section A of Annex I" in o["scope_limitation"] and "43(3), fourth subparagraph" in o["scope_limitation"]
        ref = next(r for r in o["cross_references"] if r["context"].startswith("Art. 43(3), fourth subparagraph"))
        quoted = re.search(r'"(.+)"', ref["context"]).group(1)
        assert quoted.startswith("Where a high-risk AI system is both covered")
        assert _in(quoted, text), oid
    # declarative twin of the module rule (Logic Lock; HG show_when sync)
    assert (obls["ART43-OBL-2"]["context_skip_field"], obls["ART43-OBL-2"]["context_skip_value"]) == ("is_annex_i_product", True)


def test_art50_7a_renamed_to_obligation_id():
    with open(os.path.join(OBL_DIR, "art50-transparency-obligations.json"), encoding="utf-8") as f:
        obls = {o["id"]: o for o in json.load(f)["obligations"]}
    assert "ART50-EMP-7a" not in obls
    o = obls["ART50-OBL-7a"]
    assert (o["deontic_type"], o["modality"]) == ("obligation", "shall")
    assert o["_id_history"][-1]["id"] == "ART50-EMP-7a"


def _served(x):
    """Drop `_`-prefixed keys at every level (internal audit data, never served)."""
    if isinstance(x, dict):
        return {k: _served(v) for k, v in x.items() if not k.startswith("_")}
    if isinstance(x, list):
        return [_served(v) for v in x]
    return x


@pytest.mark.parametrize("old_id", ["ART27-OBL-4", "ART50-EMP-7a"])
def test_renamed_ids_are_gone_from_the_scanner(old_id):
    """Old ids may survive only in internal audit keys (`_metadata`, `_id_history` and other
    `_`-prefixed keys, which no tool serves); everything served or read uses the new id."""
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
            if old_id not in text:
                continue
            if name.endswith(".json") and os.path.basename(root) == "obligations":
                if old_id not in json.dumps(_served(json.loads(text)), ensure_ascii=False):
                    continue
            hits.append(os.path.relpath(path, SCANNER))
    assert scanned > 100, f"walked only {scanned} files"
    assert not hits, f"{old_id} still referenced in {hits}"


# ── Module behaviour ──

def _find(result, oid):
    return [f for f in result.findings if f.obligation_id == oid]


def test_art27_module_emits_no_finding_for_the_permission(art27_module, tmp_path):
    BaseArticleModule.set_context(_ctx_with("art27", {
        "has_fria_documentation": True, "has_fria_versioning": True, "has_existing_dpia": True}))
    result = art27_module.scan(str(tmp_path))
    assert not _find(result, "ART27-PERM-4")
    assert not _find(result, "ART27-OBL-4")


def test_art43_annex_i_product_takes_the_annex_i_route(art43_module, tmp_path):
    """43(3) fourth subparagraph: a system covered by Annex I Section A legislation follows that
    legislation's procedure even if it also falls within Annex III — 43(1)/(2) do not apply."""
    BaseArticleModule.set_context(_ctx_with("art43", {
        "has_internal_control_assessment": False, "has_change_management_procedures": True,
        "is_annex_i_product": True}))
    result = art43_module.scan(str(tmp_path))
    for oid in ("ART43-OBL-1", "ART43-OBL-2"):
        f = _find(result, oid)
        assert len(f) == 1, oid
        assert f[0].level == ComplianceLevel.NOT_APPLICABLE, oid
        assert "43(3)" in f[0].description, oid
    assert _find(result, "ART43-OBL-3")[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


def test_art43_not_annex_i_keeps_annex_iii_routes(art43_module, tmp_path):
    BaseArticleModule.set_context(_ctx_with("art43", {
        "has_internal_control_assessment": False, "has_change_management_procedures": True,
        "is_annex_i_product": False}))
    result = art43_module.scan(str(tmp_path))
    assert _find(result, "ART43-OBL-2")[0].level == ComplianceLevel.NON_COMPLIANT
    assert _find(result, "ART43-OBL-3")[0].level == ComplianceLevel.NOT_APPLICABLE


def test_art43_annex_i_unknown_keeps_internal_control_finding(art43_module, tmp_path):
    BaseArticleModule.set_context(_ctx_with("art43", {
        "has_internal_control_assessment": False, "has_change_management_procedures": True}))
    result = art43_module.scan(str(tmp_path))
    assert _find(result, "ART43-OBL-2")[0].level == ComplianceLevel.NON_COMPLIANT
    assert _find(result, "ART43-OBL-1")[0].level == ComplianceLevel.UNABLE_TO_DETERMINE
