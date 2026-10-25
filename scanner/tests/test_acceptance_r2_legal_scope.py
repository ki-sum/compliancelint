"""Acceptance round 2 (2026-10-09) — legal-scope fixes in the scanner, founder: fix before release. Primary text
(Regulation (EU) 2024/1689 as amended by Regulation (EU) 2026/1744):

- Art. 80(1) concerns "an AI system classified by the provider as non-high-risk pursuant to Article 6(3)" — not
  applicable when the provider does not claim the Art. 6(3) derogation.
- Art. 6(4): "A provider who considers that an AI system referred to in Annex III is not high-risk" — same condition.
- Art. 6(1)(a) covers an AI system that is itself an Annex I product or intended to be used as a safety component of
  one, in Section A or Section B. The scanner's is_annex_i_product answer covers Section A only, so it cannot make
  ART06-CLS-1 not applicable (o3 Prompt G item C2, 2026-10-09: the earlier gate was rejected).
- Art. 43(1) concerns "high-risk AI systems listed in point 1 of Annex III" (o3 Prompt G item C3: the reason names
  the points, not Art. 43(2), which also depends on the Art. 43(3) product route).
- Art. 47(2) is the content of the declaration — it cannot be non-compliant before a declaration exists (47(1)).
- Art. 50(5): "The information referred to in paragraphs 1 to 4" — not applicable when none of 50(1)-(4) applies; the
  information is given "at the latest at the time of the first interaction or exposure"; Art. 50(4) first
  subparagraph = deep fakes, second = text on matters of public interest.
- Art. 9(9): "shall give consideration to whether … minors … and, as appropriate, other vulnerable groups" — a duty
  of every high-risk provider, not conditional on affects_children.
"""
import json
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.context import ProjectContext  # noqa: E402
from core.protocol import BaseArticleModule, ComplianceLevel  # noqa: E402

NA = ComplianceLevel.NOT_APPLICABLE


def _load_module(article_dir_name: str):
    import importlib.util
    module_dir = os.path.join(SCANNER_ROOT, "modules", article_dir_name)
    sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(
        article_dir_name.replace("-", "_"), os.path.join(module_dir, "module.py"),
        submodule_search_locations=[module_dir],
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    BaseArticleModule.clear_index_cache()
    return mod.create_module()


def _scan(article_dir: str, answers: dict, tmp_path, risk: str = "high-risk"):
    ctx = ProjectContext(
        primary_language="python", risk_classification=risk, risk_classification_confidence="high",
        compliance_answers={"_scope": {"is_ai_system": True, "risk_classification": risk}, **answers},
    )
    mod = _load_module(article_dir)
    BaseArticleModule.set_context(ctx)
    BaseArticleModule.set_config(None)
    try:
        return {f.obligation_id: f for f in mod.scan(str(tmp_path)).findings}
    finally:
        BaseArticleModule.set_context(None)


def test_art80_not_applicable_without_an_art6_3_claim(tmp_path):
    f = _scan("art80-non-high-risk-misclassification",
              {"art49": {"claims_art6_3_exception": False}, "art80": {"has_compliance_remediation_plan": False}}, tmp_path)
    for oid in ("ART80-OBL-4", "ART80-OBL-5", "ART80-OBL-7"):
        assert f[oid].level == NA, oid
        assert "Article 6(3)" in f[oid].description


def test_art80_kept_with_an_art6_3_claim(tmp_path):
    f = _scan("art80-non-high-risk-misclassification",
              {"art49": {"claims_art6_3_exception": True}, "art80": {"has_compliance_remediation_plan": False}}, tmp_path)
    assert f["ART80-OBL-4"].level != NA


def test_art6_4_not_applicable_without_an_art6_3_claim(tmp_path):
    f = _scan("art06-risk-classification",
              {"art49": {"claims_art6_3_exception": False}, "art6": {"annex_iii_categories": ["5(b)"], "has_risk_classification_doc": None}}, tmp_path)
    assert f["ART06-OBL-4"].level == NA
    assert f["ART06-OBL-4"].description == (
        "Not applicable: Article 6(4) applies to a provider who considers that an AI system referred to in Annex III "
        "is not high-risk; the answers state that the Article 6(3) derogation is not relied on.")


def test_art6_1_not_made_not_applicable_by_a_section_a_answer(tmp_path):
    # is_annex_i_product = the Section A question; a Section B product (machinery, motor vehicles …) or the
    # safety-component side is not ruled out by it, nor by the absence of an AI-detected product type.
    f = _scan("art06-risk-classification",
              {"art11": {"is_annex_i_product": False}, "art6": {"annex_iii_categories": ["5(b)"], "annex_i_product_type": None}}, tmp_path)
    assert f["ART06-CLS-1"].level != NA
    src = open(os.path.join(SCANNER_ROOT, "modules", "art06-risk-classification", "module.py"), encoding="utf-8").read()
    assert "not a safety component of, or itself, a" not in src


@pytest.mark.parametrize("categories,applicable", [(["5(b)"], False), (["4(a)", "5(b)"], False), (["1(a)"], True)])
def test_art43_1_only_for_annex_iii_point_1(categories, applicable, tmp_path):
    f = _scan("art43-conformity-assessment",
              {"art6": {"annex_iii_categories": categories}, "art43": {"is_annex_i_product": False}}, tmp_path)
    assert (f["ART43-OBL-1"].level != NA) is applicable
    if not applicable:
        assert f["ART43-OBL-1"].description == (
            "Not applicable: Article 43(1) concerns high-risk AI systems listed in point 1 of Annex III; the answers "
            f"place the system in Annex III point(s) {', '.join(categories)}, not point 1.")


def test_art43_1_point_reason_with_an_unknown_annex_i_answer(tmp_path):
    # The decisive fact is that no category is point 1; an unanswered Section A question does not block it.
    f = _scan("art43-conformity-assessment", {"art6": {"annex_iii_categories": ["5(b)"]}}, tmp_path)
    assert f["ART43-OBL-1"].level == NA
    assert f["ART43-OBL-1"].description.endswith("point(s) 5(b), not point 1.")


def test_art47_2_not_non_compliant_without_a_declaration(tmp_path):
    f = _scan("art47-declaration-of-conformity",
              {"art47": {"has_doc_declaration": False, "has_annex_v_content": False}}, tmp_path)
    assert f["ART47-OBL-1"].level == ComplianceLevel.NON_COMPLIANT
    assert f["ART47-OBL-2"].level == ComplianceLevel.UNABLE_TO_DETERMINE
    assert "47(1)" in f["ART47-OBL-2"].description


def test_art50_5_not_applicable_when_paragraphs_1_to_4_do_not_apply(tmp_path):
    f = _scan("art50-transparency-obligations", {"art50": {
        "is_chatbot_or_interactive_ai": False, "is_generating_synthetic_content": False,
        "is_emotion_recognition_system": False, "is_biometric_categorization_system": False,
        "is_deep_fake_system": False, "publishes_public_interest_text": False}}, tmp_path, risk="minimal-risk")
    assert f["ART50-OBL-4b"].level == NA
    assert f["ART50-OBL-5"].level == NA
    assert "paragraphs 1 to 4" in f["ART50-OBL-5"].description


def test_art50_5_stays_while_the_public_interest_text_case_is_open(tmp_path):
    # Art. 50(4) second subparagraph unanswered → 50(5) may still apply.
    f = _scan("art50-transparency-obligations", {"art50": {
        "is_chatbot_or_interactive_ai": False, "is_generating_synthetic_content": False,
        "is_emotion_recognition_system": False, "is_biometric_categorization_system": False,
        "is_deep_fake_system": False}}, tmp_path, risk="minimal-risk")
    assert f["ART50-OBL-5"].level != NA


def test_public_interest_text_field_is_described():
    from core.context import _FIELD_DESCRIPTIONS, _build_answers_template
    assert "publishes_public_interest_text" in _build_answers_template()["art50"]
    assert "second subparagraph" in _FIELD_DESCRIPTIONS["art50"]["publishes_public_interest_text"]


def test_public_interest_text_contradicts_open_source(tmp_path):
    f = _scan("art04-ai-literacy", {"_scope": {"is_open_source": True}, "art50": {"publishes_public_interest_text": True}}, tmp_path, risk="minimal-risk")
    assert all("[Art. 2(12)]" not in x.description for x in f.values())


def test_art50_texts(tmp_path):
    src = open(os.path.join(SCANNER_ROOT, "modules", "art50-transparency-obligations", "module.py"), encoding="utf-8").read()
    assert "prior to their first interaction" not in src
    assert "at the latest at the time of the first interaction" in src
    assert "Art. 50(4) does not apply." not in src
    assert "first subparagraph" in src
    assert "(C2PA recommended)" not in src


def test_art50_2_marking_text_is_technology_neutral(tmp_path):
    f = _scan("art50-transparency-obligations", {"art50": {
        "is_generating_synthetic_content": True, "has_content_watermarking": False}}, tmp_path, risk="limited-risk")
    # Wording of the legal review o3 Y (2026-10-25, QA #36).
    assert f["ART50-OBL-2"].description == (
        "System generates synthetic content, but no machine-readable marking mechanism enabling detection as "
        "artificially generated or manipulated was identified for its synthetic outputs. Article 50(2) requires such "
        "marking, subject to its applicable exceptions and technical-feasibility qualifications. Review the evidence "
        "and confirm whether marking is implemented elsewhere.")


def test_art9_9_has_no_children_condition():
    data = json.load(open(os.path.join(SCANNER_ROOT, "obligations", "art09-risk-management.json"), encoding="utf-8"))
    o = next(x for x in data["obligations"] if x["id"] == "ART09-OBL-9")
    assert not o.get("context_skip_field")


def test_art14_exc_5b_reason_names_the_point_1a_condition(tmp_path):
    # The exception to the Art. 14(5) separate-verification requirement only arises for Annex III point 1(a)
    # systems; its "not applicable" reason cited the law-enforcement condition next to is_biometric_system=False.
    f = _scan("art14-human-oversight", {"_scope": {"is_biometric_system": False}}, tmp_path)
    d = f["ART14-EXC-5b"].description
    assert f["ART14-EXC-5b"].level == NA
    assert "point 1(a) of Annex III" in d
    rec = json.load(open(os.path.join(SCANNER_ROOT, "obligations", "art14-human-oversight.json"), encoding="utf-8"))
    o = next(x for x in rec["obligations"] if x["id"] == "ART14-EXC-5b")
    assert "point 1(a) of Annex III" in o["scope_limitation"]
