"""The other 17 interim standards say what the Regulation requires, with its conditions, exceptions and addressees.

Found 2026-10-27 in an independent legal review of every interim standard not covered by the cross-check of Articles
10, 11, 13, 14, 15, 51, 52, 53 and 55 (same classes of error: methods written as duties, dropped conditions and
exceptions, wrong paragraphs and addressees, refs to unrelated obligations, quotes not in the adopted text).
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _standard(name):
    return json.loads((ROOT / "modules" / name / "interim-standard.json").read_text(encoding="utf-8"))


def _req(name, rid):
    return next(r for r in _standard(name)["requirements"] if r["id"] == rid)


def _all_text(name):
    return json.dumps(_standard(name), ensure_ascii=False)


def test_ai_literacy_is_owed_by_providers_and_deployers_and_takes_the_listed_factors_into_account():
    r01 = _req("art04-ai-literacy", "IS-ART04-R01")["requirement"]
    assert r01.startswith("The provider or deployer of an AI system MUST take measures to support the development")
    r03 = _req("art04-ai-literacy", "IS-ART04-R03")["requirement"]
    assert r03.startswith("The AI literacy measures MUST take into account the technical knowledge, experience, "
                          "education and training")
    assert "Recital 91" not in _all_text("art04-ai-literacy")


def test_article_5_keeps_its_conditions():
    text = _all_text("art05-prohibited-practices")
    # point (e) prohibits untargeted scraping outright; there is no "lawful basis" exception
    assert "without targeted, lawful basis" not in text
    assert "Untargeted collection of facial images from CCTV footage" in text
    # point (f): the medical exception has no consent condition
    assert "mental health monitoring with consent" not in text
    assert "sex life" in text and "philosophical" in text
    assert "AI Office guidelines (when available)" not in text
    assert "no decision that produces an adverse legal effect on a person may be taken based solely on the output " \
           "of the system (Art. 5(3))" in text


def test_article_6_states_the_profiling_rule_and_the_article_6_4_duties():
    text = _all_text("art06-risk-classification")
    assert "profiling" in text
    assert "Article 49(2)" in text or "Art. 49(2)" in text
    # proposal-era items are named as not in the adopted Annex III, not listed as high-risk subcategories
    assert "Not in the adopted Annex III: crime analytics on large data sets" in text
    assert "The Regulation requires no notification to a national authority." in text


@pytest.mark.parametrize("rid, ref", [
    ("IS-ART09-R02", ["ART09-OBL-2a", "ART09-OBL-2b"]),
    ("IS-ART09-R03", "ART09-OBL-2c"),
    ("IS-ART09-R06", "ART09-OBL-9"),
    ("IS-ART09-R07", "ART09-OBL-5c"),
])
def test_risk_management_requirements_refer_to_the_paragraph_they_implement(rid, ref):
    assert _req("art09-risk-management", rid)["obligation_ref"] == ref


def test_article_9_9_is_not_limited_to_systems_intended_for_children():
    r06 = _req("art09-risk-management", "IS-ART09-R06")
    assert "likely to have an adverse impact on persons under the age of 18" in r06["requirement"]


def test_article_12_has_no_paragraph_4_and_does_not_require_tamper_protection():
    text = _all_text("art12-record-keeping")
    assert "Art. 12(4)" not in text and "Article 12(4)" not in text
    assert _req("art12-record-keeping", "IS-ART12-R05")["requirement"].startswith("Logs SHOULD be protected")
    assert _req("art12-record-keeping", "IS-ART12-R03")["obligation_ref"] == [
        "ART12-OBL-2a", "ART12-OBL-3a", "ART12-OBL-3b", "ART12-OBL-3c", "ART12-OBL-3d"]


def test_retention_keeps_the_conditions_of_article_19_1_and_26_6():
    for name, rid in (("art12-record-keeping", "IS-ART12-R04"), ("art26-deployer-obligations", "IS-ART26-R04")):
        requirement = _req(name, rid)["requirement"]
        assert "to the extent such logs are under its control" in requirement
        assert "of at least six months" in requirement
        assert "in particular in Union law on the protection of personal data" in requirement


def test_qms_is_proportionate_and_its_data_management_is_pre_market():
    assert _req("art17-quality-management", "IS-ART17-R01")["obligation_ref"] == [
        "ART17-OBL-1", "ART17-OBL-2", "ART17-PERM-3"]
    assert "before and for the purpose of the placing on the market" in \
        _req("art17-quality-management", "IS-ART17-R03")["requirement"]


def test_deployer_duties_are_the_measures_of_article_26_not_documentation():
    assert _req("art26-deployer-obligations", "IS-ART26-R01")["requirement"].startswith(
        "The deployer MUST take appropriate technical and organisational measures")


def test_fria_names_who_is_bound_and_excludes_annex_iii_point_2():
    r01 = _req("art27-fundamental-rights-impact", "IS-ART27-R01")["requirement"]
    assert "other than one intended to be used in the area listed in Annex III, point 2" in r01
    assert "MAY rely on previously conducted" in _req("art27-fundamental-rights-impact", "IS-ART27-R02")["requirement"]


def test_declaration_of_conformity_has_the_three_forms_of_article_47_1():
    assert "written machine readable, physical or electronically signed EU declaration of conformity" in \
        _req("art47-declaration-of-conformity", "IS-ART47-R01")["requirement"]


def test_post_market_monitoring_and_incident_reporting_keep_their_permissions():
    assert _req("art72-post-market-monitoring", "IS-ART72-R03")["obligation_ref"] == ["ART72-OBL-3", "ART72-PER-1"]
    assert "ART73-PER-1" in _req("art73-serious-incident-reporting", "IS-ART73-R02")["obligation_ref"]


def test_right_to_explanation_does_not_prescribe_a_mechanism():
    assert _req("art86-right-to-explanation", "IS-ART86-R02")["requirement"].startswith("The deployer SHOULD")


def test_gpai_authorised_representative_keeps_the_open_source_exception_and_the_10_year_copy():
    assert "Article 54(6)" in _req("art54-gpai-authorised-representatives", "IS-ART54-R01")["requirement"] or \
        "Art. 54(6)" in _req("art54-gpai-authorised-representatives", "IS-ART54-R01")["requirement"]
    assert "for a period of 10 years" in _req("art54-gpai-authorised-representatives", "IS-ART54-R03")["requirement"]


@pytest.mark.parametrize("name, rid, ref, start", [
    ("art49-registration", "IS-ART49-R02", "ART49-OBL-2", "Before placing on the market or putting into service an AI "
     "system for which the provider has concluded that it is not high-risk according to Article 6(3)"),
    ("art49-registration", "IS-ART49-R03", "ART49-OBL-3", "Before putting into service or using a high-risk AI system "
     "listed in Annex III, with the exception of high-risk AI systems listed in point 2 of Annex III, deployers that "
     "are public authorities"),
    ("art54-gpai-authorised-representatives", "IS-ART54-R04", "ART54-OBL-5", "The authorised representative MUST "
     "terminate the mandate"),
])
def test_duties_that_had_no_requirement_now_have_one(name, rid, ref, start):
    req = _req(name, rid)
    assert req["obligation_ref"] == ref
    assert req["requirement"].startswith(start)


def test_registration_of_annex_iii_systems_excludes_point_2():
    assert "with the exception of high-risk AI systems referred to in point 2 of Annex III" in \
        _req("art49-registration", "IS-ART49-R01")["requirement"]


def test_art50_obl_5_quotes_the_accessibility_sentence():
    obligations = json.loads((ROOT / "obligations" / "art50-transparency-obligations.json")
                             .read_text(encoding="utf-8"))["obligations"]
    quote = next(o for o in obligations if o["id"] == "ART50-OBL-5")["source_quote"]
    assert quote.endswith("The information shall conform to the applicable accessibility requirements.")


def test_financial_institutions_are_deemed_to_monitor_only_under_the_conditions_of_article_26_5():
    r03 = _req("art26-deployer-obligations", "IS-ART26-R03")["requirement"]
    assert "financial institutions subject to requirements regarding their internal governance, arrangements or " \
           "processes under Union financial services law" in r03
    assert "This obligation does not cover sensitive operational data of deployers of AI systems which are law " \
           "enforcement authorities." in r03


def test_every_combination_of_the_two_core_deployer_requirements_has_a_score():
    scoring = _standard("art26-deployer-obligations")["scoring"]
    assert scoring["partial"] == "R01 or R02 met, but not all of R01 to R05"
    assert scoring["non_compliant"] == "Neither R01 nor R02 met"


def test_article_5_cites_the_adopted_commission_guidelines_and_the_statutory_medical_exception():
    text = _all_text("art05-prohibited-practices")
    assert "C(2025) 5052 final of 29 July 2025" in text
    assert "except where the use of the AI system is intended to be put in place or into the market for medical or " \
           "safety reasons" in text


def test_article_25_1_b_keeps_all_operators_and_the_high_risk_condition():
    requirement = _req("art43-conformity-assessment", "IS-ART43-R02")["requirement"]
    assert "any distributor, importer, deployer or other third-party that makes a substantial modification" in requirement
    assert "in such a way that it remains a high-risk AI system pursuant to Article 6" in requirement
