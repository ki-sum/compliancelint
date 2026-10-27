"""Interim-standard wording follows the Regulation: what it makes optional stays optional, conditions and exceptions
stay in, and articles, paragraphs and Annex points are the current ones.

Found 2026-10-27 in an independent cross-check of the interim standards: redundancy written as a MUST although
Art. 15(4) says "may"; Art. 15 cited with draft paragraph numbers (15(3) for resilience, 15(2) for the declared
accuracy metrics); Annex IV points that do not hold what is cited; "when appropriate" and "as appropriate" dropped;
the open-source exception of Art. 53(2) and the exception of Art. 14(5), second subparagraph, left out; implementation
methods (split ratios, model cards, change logs, input validation, dependency scanning, confidence routing,
classification records, a rebuttal file) written as legal duties.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REQ = {
    req["id"]: req
    for path in (ROOT / "modules").glob("*/interim-standard.json")
    for req in json.loads(path.read_text(encoding="utf-8")).get("requirements", [])
}


def _text(rid, field="requirement"):
    return REQ[rid][field]


@pytest.mark.parametrize("rid", [
    "IS-ART11-R03", "IS-ART11-R04", "IS-ART11-R06", "IS-ART14-R06", "IS-ART15-R03", "IS-ART15-R06", "IS-ART15-R07",
    "IS-ART15-R08", "IS-ART15-R09", "IS-ART51-R02", "IS-ART51-R03", "IS-ART52-R03",
])
def test_a_method_the_regulation_does_not_prescribe_is_not_a_must(rid):
    requirement = _text(rid)
    if rid in ("IS-ART11-R04", "IS-ART11-R06"):
        # the legal content is a MUST, the format (model card, change log) is named as one possible format
        assert "one possible format" in requirement
        assert "MUST maintain a model card" not in requirement and "MUST maintain a change log" not in requirement
    else:
        assert "MUST" not in requirement


def test_redundancy_is_a_may_as_in_article_15_4():
    for rid in ("IS-ART15-R04", "IS-ART15-R09"):
        sentences = [s for s in _text(rid).split(".") if "redundan" in s]
        assert sentences and all("MAY" in s and "MUST" not in s for s in sentences), (rid, sentences)
    assert "may be achieved through technical redundancy solutions" in _text("IS-ART15-R09", "rationale")


def test_article_15_paragraphs_are_the_adopted_ones():
    # resilience and redundancy: Art. 15(4); declared accuracy metrics: Art. 15(3); cybersecurity attacks: Art. 15(5)
    for rid in ("IS-ART15-R02", "IS-ART15-R03", "IS-ART15-R04", "IS-ART15-R09"):
        rationale = _text(rid, "rationale")
        assert "15(4)" in rationale and "15(3)" not in rationale, (rid, rationale)
    r01 = _text("IS-ART15-R01", "rationale")
    assert "Art. 15(3) requires that 'the levels of accuracy and the relevant accuracy metrics" in r01
    assert "Art. 15(2)" not in r01
    r08 = _text("IS-ART15-R08", "rationale")
    assert "Art. 15(5)" in r08 and "Art. 15(4)" not in r08
    assert "'appropriate to the relevant circumstances and the risks'" in _text("IS-ART15-R05", "rationale")


def test_adversarial_testing_names_the_attacks_of_article_15_5_and_says_which_are_examples():
    r08 = REQ["IS-ART15-R08"]
    assert "not named in the Regulation" in r08["rationale"]
    attacks = " | ".join(r08["attack_types_to_test"])
    for named in ("Data poisoning", "Model poisoning", "Adversarial examples or model evasion",
                  "Confidentiality attacks, e.g. model inversion", "Confidentiality attacks, e.g. membership inference"):
        assert named in attacks, named


def test_feedback_loops_are_article_15_4_not_article_10_6():
    r06 = REQ["IS-ART10-R06"]
    assert "(Article 15(4), third subparagraph)" in r06["requirement"]
    assert "Art. 10(6) explicitly requires" not in r06["rationale"]
    assert "'High-risk AI systems that continue to learn after being placed on the market" in r06["rationale"]


def test_data_split_ratios_are_not_mandated():
    r05 = REQ["IS-ART10-R05"]
    assert "no specific split ratios are mandated" in r05["requirement"]
    assert "either as a fixed or variable split" in r05["rationale"]
    assert not any("70/15/15" in item for item in r05["minimum_requirements"])


@pytest.mark.parametrize("rid, cited, wrong", [
    ("IS-ART11-R01", "Annex IV(1) requires 'a general description of the AI system'", "Annex IV(1)(a) requires a"),
    ("IS-ART11-R02", "'a detailed description of the elements of the AI system", "Annex IV(2)(a) requires"),
    ("IS-ART11-R03", "Annex IV(2)(b)", "Annex IV(2)(e)"),
    ("IS-ART11-R05", "Annex IV(2)(g)", "Annex IV(4)"),
    ("IS-ART11-R06", "Annex IV(6)", None),
    ("IS-ART11-R07", "Annex IV(1)(d)", "Annex IV(1)(a)"),
    ("IS-ART13-R05", "Art. 13(3)(b)(iii)", "13(3)(b)(iv)"),
    ("IS-ART13-R06", "Art. 13(3)(b)(vi)", "13(3)(b)(iii)"),
])
def test_annex_iv_and_article_13_points_are_the_ones_that_hold_the_text(rid, cited, wrong):
    rationale = _text(rid, "rationale")
    assert cited in rationale, rationale
    if wrong:
        assert wrong not in rationale and wrong not in REQ[rid]["title"], rationale


def test_testing_documentation_title_names_annex_iv_point_2g():
    assert REQ["IS-ART11-R05"]["title"] == "Testing Documentation (Annex IV, point 2(g))"


@pytest.mark.parametrize("rid, kept", [
    ("IS-ART13-R06", "when appropriate"),
    ("IS-ART55-R03", "as appropriate**, to national competent authorities"),
    ("IS-ART53-R01", "Except where Article 53(2) applies"),
    ("IS-ART53-R02", "Except where Article 53(2) applies"),
    ("IS-ART14-R07", "necessary competence, training and authority"),
    ("IS-ART14-R07", "law enforcement, migration, border control or asylum"),
    ("IS-ART52-R03", "MAY submit sufficiently substantiated arguments"),
])
def test_conditions_and_exceptions_of_the_regulation_are_kept(rid, kept):
    assert kept.replace("**", "") in _text(rid)


def test_article_14_4_c_is_quoted_as_adopted():
    assert "'to correctly interpret the high-risk AI system's output, taking into account, for example, the " \
           "interpretation tools and methods available'" in _text("IS-ART14-R06", "rationale")


def test_notification_content_is_the_second_sentence_of_article_52_1():
    assert "'That notification shall include the information necessary to demonstrate that the relevant " \
           "requirement has been met.'" in _text("IS-ART52-R02", "rationale")


def test_art52_obl_1_quotes_both_sentences_of_article_52_1():
    obligations = json.loads((ROOT / "obligations" / "art52-classification-notification.json")
                             .read_text(encoding="utf-8"))["obligations"]
    quote = next(o for o in obligations if o["id"] == "ART52-OBL-1")["source_quote"]
    assert quote == (
        "Where a general-purpose AI model meets the condition referred to in Article 51(1), point (a), the relevant "
        "provider shall notify the Commission without delay and in any event within two weeks after that requirement "
        "is met or it becomes known that it will be met. That notification shall include the information necessary "
        "to demonstrate that the relevant requirement has been met."
    )


def test_the_two_person_verification_is_built_in_by_the_provider():
    # Art. 14(5): "the measures referred to in paragraph 3 ... shall be such as to ensure that ... no action or decision
    # is taken by the deployer" — the provider identifies those measures (Art. 14(3)); ART14-OBL-5 is the provider's.
    requirement = _text("IS-ART14-R07")
    assert requirement.startswith("For high-risk AI systems referred to in Annex III, point 1(a), the provider MUST "
                                  "identify oversight measures under Article 14(3)")
    assert "deployer MUST NOT" not in requirement


def test_data_quality_criteria_include_article_4a_1():
    assert "Article 10(2) to (4) and Article 4a(1) (Article 10(1))" in _text("IS-ART10-R05")


def test_the_open_source_exception_keeps_all_its_conditions():
    rationale = _text("IS-ART53-R01", "rationale")
    assert "licence that allows for the access, usage, modification, and distribution of the model" in rationale
    assert "unless the model is a general-purpose AI model with systemic risk" in rationale
    assert "have a good understanding of its capabilities and limitations" in _text("IS-ART53-R02", "rationale")


def test_annex_iv_1_keeps_where_applicable_and_both_forms():
    assert "and, where applicable, how it interacts with, or can be used to interact with," in \
        _text("IS-ART11-R01", "rationale")
    assert REQ["IS-ART11-R07"]["title"] == "Forms of Placing on the Market or Putting into Service (Annex IV, point 1(d))"
