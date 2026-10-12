"""Art. 48 CE marking tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping (result field → record; condition field(s)):
  follows_general_ce_marking_principles            → ART48-OBL-1  (Art. 48(1))
  has_digital_ce_marking                           → ART48-OBL-2  (Art. 48(2); is_provided_digitally)
  has_ce_marking                                   → ART48-OBL-3  (Art. 48(3))
  has_notified_body_number                         → ART48-OBL-4a (Art. 48(4), first sentence;
                                                                   has_notified_body_assessment)
  notified_body_number_affixed_by_permitted_actor  → ART48-OBL-4b (Art. 48(4), second sentence;
                                                                   has_notified_body_assessment)
  has_notified_body_number_in_promotion            → ART48-OBL-4c (Art. 48(4), third sentence;
                                                                   has_notified_body_assessment AND
                                                                   has_ce_marking_promotional_material)
  ce_marking_indicates_other_union_law_compliance  → ART48-OBL-5  (Art. 48(5); is_subject_to_other_ce_marking_law)

A result answer maps true → PARTIAL (a person still confirms it), false → NON_COMPLIANT, null → UNABLE_TO_DETERMINE.
A conditional record is assessed from its answer only when every condition is answered true: with a condition
false it is NOT_APPLICABLE, with a condition unanswered (key absent, or null as in the answers template) it stays
UNABLE_TO_DETERMINE whatever the answer says.

The result fields of ART48-OBL-1, -4b and -5 and the promotional-material condition were added by the legal review
of 2026-10-12 (item J16).
"""
import json

import pytest

from core.application_dates import applicable_from
from core.context import _BOOL_FIELDS, _FIELD_DESCRIPTIONS, _build_answers_template
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with

ALL_IDS = ["ART48-OBL-1", "ART48-OBL-2", "ART48-OBL-3", "ART48-OBL-4a", "ART48-OBL-4b", "ART48-OBL-4c",
           "ART48-OBL-5"]
# Automation level manual: the finding always carries the Human Gates hint.
MANUAL_IDS = ["ART48-OBL-1", "ART48-OBL-4b", "ART48-OBL-5"]
ANSWER_FIELDS = ["has_ce_marking", "has_digital_ce_marking", "has_notified_body_number",
                 "has_notified_body_number_in_promotion", "follows_general_ce_marking_principles",
                 "notified_body_number_affixed_by_permitted_actor",
                 "ce_marking_indicates_other_union_law_compliance"]
CONDITION_FIELDS = ["is_provided_digitally", "has_notified_body_assessment", "is_subject_to_other_ce_marking_law",
                    "has_ce_marking_promotional_material"]

# (obligation, result field) of the records without a condition
UNCONDITIONAL = [
    ("ART48-OBL-1", "follows_general_ce_marking_principles"),
    ("ART48-OBL-3", "has_ce_marking"),
]
# (obligation, condition field, result field, words the finding uses when the condition is open)
ONE_CONDITION = [
    ("ART48-OBL-2", "is_provided_digitally", "has_digital_ce_marking", "is provided digitally"),
    ("ART48-OBL-4a", "has_notified_body_assessment", "has_notified_body_number", "whether a notified body"),
    ("ART48-OBL-4b", "has_notified_body_assessment", "notified_body_number_affixed_by_permitted_actor",
     "whether a notified body"),
    ("ART48-OBL-5", "is_subject_to_other_ce_marking_law", "ce_marking_indicates_other_union_law_compliance",
     "is subject to other Union law"),
]
# The condition is unanswered: the key is absent, or present with null (the shape of the answers template).
UNANSWERED = [pytest.param(False, id="key-absent"), pytest.param(True, id="key-null")]

PERMITTED_PERFORMER = ("the notified body itself, or, under the notified body's instructions, the provider or the "
                       "provider's authorised representative")
NB = "has_notified_body_assessment"
PROMO = "has_ce_marking_promotional_material"
IN_PROMO = "has_notified_body_number_in_promotion"


def _full_true_ctx():
    """Every condition applies and every answer is True."""
    return _ctx_with("art48", {f: True for f in ANSWER_FIELDS + CONDITION_FIELDS})


def _full_false_ctx():
    """Every condition applies and every answer is False."""
    return _ctx_with("art48", {**{f: True for f in CONDITION_FIELDS}, **{f: False for f in ANSWER_FIELDS}})


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art48", {})


def _template_ctx():
    """The answers template as the AI receives it: every Art. 48 field present with null."""
    return _ctx_with("art48", dict(_build_answers_template()["art48"]))


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


def _scan(module, tmp_path, answers):
    BaseArticleModule.set_context(_ctx_with("art48", answers))
    return module.scan(str(tmp_path))


def _with_open_condition(condition, as_null, answers):
    return {**answers, condition: None} if as_null else answers


# ── ART48-OBL-1 / ART48-OBL-3: records without a condition ──

@pytest.mark.parametrize("obl_id,answer", UNCONDITIONAL)
class TestArt48Unconditional:

    def test_true_gives_partial(self, art48_module, tmp_path, obl_id, answer):
        """Answer True → PARTIAL (evidence found, a person confirms)."""
        result = _scan(art48_module, tmp_path, {answer: True})
        obl = _find(result, obl_id)
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art48_module, tmp_path, obl_id, answer):
        """Answer False → NON_COMPLIANT."""
        result = _scan(art48_module, tmp_path, {answer: False})
        obl = _find(result, obl_id)
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    @pytest.mark.parametrize("as_null", UNANSWERED)
    def test_none_gives_utd(self, art48_module, tmp_path, obl_id, answer, as_null):
        """Answer None → UNABLE_TO_DETERMINE."""
        result = _scan(art48_module, tmp_path, {answer: None} if as_null else {})
        obl = _find(result, obl_id)
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


class TestArt48Obl1:

    def test_names_the_regulation_in_every_state(self, art48_module, tmp_path):
        for value in (True, False, None):
            result = _scan(art48_module, tmp_path, {"follows_general_ce_marking_principles": value})
            assert "Article 30 of Regulation (EC) No 765/2008" in _find(result, "ART48-OBL-1")[0].description, value

    def test_is_not_decided_by_the_other_answers(self, art48_module, tmp_path):
        """Art. 48(1) has its own answer: the CE marking being affixed says nothing about the general principles."""
        result = _scan(art48_module, tmp_path, {"has_ce_marking": True})
        assert _find(result, "ART48-OBL-1")[0].level == ComplianceLevel.UNABLE_TO_DETERMINE
        result = _scan(art48_module, tmp_path, {"has_ce_marking": False})
        assert _find(result, "ART48-OBL-1")[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART48-OBL-2 / 4a / 4b / 5: one condition ──

@pytest.mark.parametrize("obl_id,condition,answer,open_words", ONE_CONDITION)
class TestArt48OneCondition:

    def test_condition_true_answer_true_gives_partial(self, art48_module, tmp_path, obl_id, condition, answer,
                                                      open_words):
        result = _scan(art48_module, tmp_path, {condition: True, answer: True})
        obl = _find(result, obl_id)
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_condition_true_answer_false_gives_non_compliant(self, art48_module, tmp_path, obl_id, condition,
                                                               answer, open_words):
        result = _scan(art48_module, tmp_path, {condition: True, answer: False})
        obl = _find(result, obl_id)
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    @pytest.mark.parametrize("as_null", UNANSWERED)
    def test_condition_true_answer_none_gives_utd(self, art48_module, tmp_path, obl_id, condition, answer,
                                                  open_words, as_null):
        result = _scan(art48_module, tmp_path, {condition: True, **({answer: None} if as_null else {})})
        obl = _find(result, obl_id)
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE
        assert open_words not in obl[0].description

    @pytest.mark.parametrize("answer_value", [True, False, None])
    def test_condition_false_gives_not_applicable(self, art48_module, tmp_path, obl_id, condition, answer,
                                                  open_words, answer_value):
        """The condition does not apply → NOT_APPLICABLE whatever the answer says: the condition wins."""
        result = _scan(art48_module, tmp_path, {condition: False, answer: answer_value})
        obl = _find(result, obl_id)
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    @pytest.mark.parametrize("as_null", UNANSWERED)
    def test_condition_unanswered_is_not_non_compliant(self, art48_module, tmp_path, obl_id, condition, answer,
                                                       open_words, as_null):
        """Without the condition the record cannot be judged: a False answer must not read NON_COMPLIANT
        (most Annex III systems follow internal control and have no notified body number at all)."""
        result = _scan(art48_module, tmp_path, _with_open_condition(condition, as_null, {answer: False}))
        obl = _find(result, obl_id)
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE
        assert open_words in obl[0].description

    @pytest.mark.parametrize("as_null", UNANSWERED)
    def test_condition_unanswered_answer_true_stays_utd(self, art48_module, tmp_path, obl_id, condition, answer,
                                                        open_words, as_null):
        result = _scan(art48_module, tmp_path, _with_open_condition(condition, as_null, {answer: True}))
        obl = _find(result, obl_id)
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE
        assert open_words in obl[0].description


# ── ART48-OBL-4b: who affixes the number ──

class TestArt48Obl4bPermittedPerformer:
    """Art. 48(4), second sentence: the provider is responsible (Art. 16(h)) but need not affix the number itself."""

    @pytest.mark.parametrize("value", [True, False, None])
    def test_finding_names_the_permitted_performers(self, art48_module, tmp_path, value):
        result = _scan(art48_module, tmp_path, {NB: True, "notified_body_number_affixed_by_permitted_actor": value})
        assert PERMITTED_PERFORMER in _find(result, "ART48-OBL-4b")[0].description

    def test_record_names_the_permitted_performers(self, art48_module):
        record = next(o for o in art48_module._load_obligations()["obligations"] if o["id"] == "ART48-OBL-4b")
        assert record["addressee"] == "provider"
        assert "provider via Article 16(h)" in record["addressee_note"]
        assert PERMITTED_PERFORMER in record["addressee_note"]
        assert any(PERMITTED_PERFORMER in atom["description"] for atom in record["decomposed_atoms"])

    def test_interim_standard_names_the_permitted_performers(self, art48_module):
        requirement = next(r for r in art48_module.compliance_checklist()["requirements"]
                           if r["obligation_ref"] == "ART48-OBL-4b")
        assert PERMITTED_PERFORMER in requirement["requirement"]


# ── ART48-OBL-4c: two conditions (a notified body is involved AND such promotional material exists) ──

class TestArt48Obl4cPromotionalMaterial:

    def _level(self, module, tmp_path, answers):
        obl = _find(_scan(module, tmp_path, answers), "ART48-OBL-4c")
        assert len(obl) == 1, f"{len(obl)} findings for {answers}"
        return obl[0]

    def test_both_conditions_true_answer_true_gives_partial(self, art48_module, tmp_path):
        f = self._level(art48_module, tmp_path, {NB: True, PROMO: True, IN_PROMO: True})
        assert f.level == ComplianceLevel.PARTIAL

    def test_both_conditions_true_answer_false_gives_non_compliant(self, art48_module, tmp_path):
        f = self._level(art48_module, tmp_path, {NB: True, PROMO: True, IN_PROMO: False})
        assert f.level == ComplianceLevel.NON_COMPLIANT

    @pytest.mark.parametrize("as_null", UNANSWERED)
    def test_both_conditions_true_answer_none_gives_utd(self, art48_module, tmp_path, as_null):
        f = self._level(art48_module, tmp_path, {NB: True, PROMO: True, **({IN_PROMO: None} if as_null else {})})
        assert f.level == ComplianceLevel.UNABLE_TO_DETERMINE
        assert "whether a notified body" not in f.description
        assert "whether the project contains promotional material" not in f.description

    @pytest.mark.parametrize("notified_body", [True, None])
    @pytest.mark.parametrize("answer_value", [True, False, None])
    def test_no_such_promotional_material_gives_not_applicable(self, art48_module, tmp_path, notified_body,
                                                               answer_value):
        """has_ce_marking_promotional_material false → NOT_APPLICABLE, whatever the answer and also while the
        notified-body condition is still open (one condition that is not met is enough)."""
        f = self._level(art48_module, tmp_path, {NB: notified_body, PROMO: False, IN_PROMO: answer_value})
        assert f.level == ComplianceLevel.NOT_APPLICABLE
        assert "promotional material" in f.description

    @pytest.mark.parametrize("promo", [True, False, None])
    @pytest.mark.parametrize("answer_value", [True, False, None])
    def test_no_notified_body_gives_not_applicable(self, art48_module, tmp_path, promo, answer_value):
        """has_notified_body_assessment false → NOT_APPLICABLE, whatever the other condition and the answer."""
        f = self._level(art48_module, tmp_path, {NB: False, PROMO: promo, IN_PROMO: answer_value})
        assert f.level == ComplianceLevel.NOT_APPLICABLE

    @pytest.mark.parametrize("as_null", UNANSWERED)
    @pytest.mark.parametrize("answer_value", [True, False])
    def test_promotional_material_unanswered_stays_utd(self, art48_module, tmp_path, as_null, answer_value):
        """Whether such promotional material exists is open: the answer does not decide the record."""
        answers = _with_open_condition(PROMO, as_null, {NB: True, IN_PROMO: answer_value})
        f = self._level(art48_module, tmp_path, answers)
        assert f.level == ComplianceLevel.UNABLE_TO_DETERMINE
        assert "whether the project contains promotional material" in f.description
        assert "whether a notified body" not in f.description

    @pytest.mark.parametrize("as_null", UNANSWERED)
    @pytest.mark.parametrize("answer_value", [True, False])
    def test_notified_body_unanswered_stays_utd(self, art48_module, tmp_path, as_null, answer_value):
        answers = _with_open_condition(NB, as_null, {PROMO: True, IN_PROMO: answer_value})
        f = self._level(art48_module, tmp_path, answers)
        assert f.level == ComplianceLevel.UNABLE_TO_DETERMINE
        assert "whether a notified body" in f.description
        assert "whether the project contains promotional material" not in f.description

    @pytest.mark.parametrize("answer_value", [True, False, None])
    def test_both_conditions_unanswered_stays_utd_and_names_both(self, art48_module, tmp_path, answer_value):
        f = self._level(art48_module, tmp_path, {NB: None, PROMO: None, IN_PROMO: answer_value})
        assert f.level == ComplianceLevel.UNABLE_TO_DETERMINE
        assert "whether a notified body" in f.description
        assert "whether the project contains promotional material" in f.description

    def test_record_scope_names_both_conditions(self, art48_module):
        record = next(o for o in art48_module._load_obligations()["obligations"] if o["id"] == "ART48-OBL-4c")
        assert record["context_skip_field"] == NB
        assert "notified body" in record["scope_limitation"]
        assert "promotional material" in record["scope_limitation"]


# ── The three paragraph 4 records share the notified-body condition ──

class TestArt48NotifiedBodyCondition:

    def test_no_notified_body_makes_all_of_paragraph_4_not_applicable(self, art48_module, tmp_path):
        result = _scan(art48_module, tmp_path, {
            "has_ce_marking": True, NB: False,
            "has_notified_body_number": False, "notified_body_number_affixed_by_permitted_actor": False,
            PROMO: True, IN_PROMO: False,
        })
        for obl_id in ("ART48-OBL-4a", "ART48-OBL-4b", "ART48-OBL-4c"):
            assert _find(result, obl_id)[0].level == ComplianceLevel.NOT_APPLICABLE, obl_id
        assert not [f for f in result.findings if f.level == ComplianceLevel.NON_COMPLIANT]
        assert result.overall_level == ComplianceLevel.PARTIAL


# ── Manual records keep the Human Gates hint ──

class TestArt48ManualRecords:

    @pytest.mark.parametrize("ctx_factory", [_full_true_ctx, _full_false_ctx, _empty_ctx, _template_ctx],
                             ids=["all-true", "all-false", "keys-absent", "template-nulls"])
    def test_manual_records_point_to_human_gates(self, art48_module, tmp_path, ctx_factory):
        """A person confirms a manual record in every state in which it may apply."""
        BaseArticleModule.set_context(ctx_factory())
        result = art48_module.scan(str(tmp_path))
        for obl_id in MANUAL_IDS:
            assert "compliancelint.dev" in (_find(result, obl_id)[0].human_gate_hint or ""), obl_id

    def test_answered_true_is_partial_not_compliant(self, art48_module, tmp_path):
        """An AI answer alone never makes a manual record COMPLIANT."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art48_module.scan(str(tmp_path))
        for obl_id in MANUAL_IDS:
            assert _find(result, obl_id)[0].level == ComplianceLevel.PARTIAL, obl_id


# ── Structural tests ──

class TestArt48Structural:

    def test_all_7_obligation_ids_in_json(self, art48_module):
        """Obligation JSON must have exactly the 7 Art. 48 records, in paragraph order."""
        data = art48_module._load_obligations()
        assert [o["id"] for o in data.get("obligations", [])] == ALL_IDS

    def test_every_record_is_a_provider_obligation(self, art48_module):
        for o in art48_module._load_obligations()["obligations"]:
            assert (o["deontic_type"], o["modality"], o["addressee"]) == ("obligation", "shall", "provider"), o["id"]

    def test_record_sources_match_their_paragraph(self, art48_module):
        sources = {o["id"]: o["source"] for o in art48_module._load_obligations()["obligations"]}
        assert sources == {
            "ART48-OBL-1": "Art. 48(1)", "ART48-OBL-2": "Art. 48(2)", "ART48-OBL-3": "Art. 48(3)",
            "ART48-OBL-4a": "Art. 48(4)", "ART48-OBL-4b": "Art. 48(4)", "ART48-OBL-4c": "Art. 48(4)",
            "ART48-OBL-5": "Art. 48(5)",
        }

    def test_conditional_records_carry_their_condition_field(self, art48_module):
        by_id = {o["id"]: o for o in art48_module._load_obligations()["obligations"]}
        expected = {
            "ART48-OBL-1": None, "ART48-OBL-3": None,
            "ART48-OBL-2": "is_provided_digitally",
            "ART48-OBL-4a": "has_notified_body_assessment", "ART48-OBL-4b": "has_notified_body_assessment",
            "ART48-OBL-4c": "has_notified_body_assessment",
            "ART48-OBL-5": "is_subject_to_other_ce_marking_law",
        }
        for obl_id, field in expected.items():
            assert by_id[obl_id].get("context_skip_field") == field, obl_id
            assert (by_id[obl_id].get("scope_limitation") is not None) == (field is not None), obl_id
            if field is not None:
                assert by_id[obl_id]["context_skip_value"] is False, obl_id

    def test_automation_levels(self, art48_module):
        data = art48_module._load_obligations()
        levels = {o["id"]: o["automation_assessment"]["level"] for o in data["obligations"]}
        assert levels == {
            "ART48-OBL-1": "manual", "ART48-OBL-2": "partial", "ART48-OBL-3": "partial",
            "ART48-OBL-4a": "partial", "ART48-OBL-4b": "manual", "ART48-OBL-4c": "partial",
            "ART48-OBL-5": "manual",
        }
        assert sorted(i for i, lv in levels.items() if lv == "manual") == MANUAL_IDS
        assert data["summary"]["automation_breakdown"] == {"full": 0, "partial": 4, "manual": 3}
        assert data["summary"]["total_obligations"] == 7
        assert data["summary"]["addressee_breakdown"] == {"provider": 7}

    def test_high_risk_prerequisite_in_metadata(self, art48_module):
        meta = art48_module._load_obligations()["_metadata"]
        assert meta["article"] == 48
        assert meta["title"] == "CE marking"
        assert [p["required_level"] for p in meta["prerequisites"]] == ["high-risk"]

    def test_obligation_coverage_present(self, art48_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art48_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations") == 7

    @pytest.mark.parametrize("ctx_factory", [_empty_ctx, _template_ctx], ids=["keys-absent", "template-nulls"])
    def test_no_answers_all_obligations_utd(self, art48_module, tmp_path, ctx_factory):
        """When AI provides no answers, all 7 obligations → UNABLE_TO_DETERMINE, and no finding claims that a
        conditional paragraph applies."""
        BaseArticleModule.set_context(ctx_factory())
        result = art48_module.scan(str(tmp_path))
        for obl_id in ALL_IDS:
            findings = _find(result, obl_id)
            assert len(findings) == 1, f"{obl_id}: {len(findings)} findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )
            assert "applies to your system" not in findings[0].description, obl_id
            assert "None" not in findings[0].description, obl_id
        assert result.overall_level == ComplianceLevel.UNABLE_TO_DETERMINE

    @pytest.mark.parametrize("ctx_factory", [_full_true_ctx, _full_false_ctx, _empty_ctx, _template_ctx],
                             ids=["all-true", "all-false", "keys-absent", "template-nulls"])
    def test_description_has_no_legal_citation_prefix(self, art48_module, tmp_path, ctx_factory):
        """Finding descriptions must not start with legal citation prefix like [Art. 48(1)]."""
        BaseArticleModule.set_context(ctx_factory())
        result = art48_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art48_module, tmp_path):
        """All-true answers with every condition applying → all seven records PARTIAL, overall PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art48_module.scan(str(tmp_path))
        levels = {f.obligation_id: f.level for f in result.findings}
        for obl_id in ALL_IDS:
            assert levels[obl_id] == ComplianceLevel.PARTIAL, obl_id
        assert result.overall_level == ComplianceLevel.PARTIAL

    def test_all_false_has_non_compliant(self, art48_module, tmp_path):
        """All-false answers with every condition applying → all seven records are NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art48_module.scan(str(tmp_path))
        non_compliant = sorted(f.obligation_id for f in result.findings if f.level == ComplianceLevel.NON_COMPLIANT)
        assert non_compliant == sorted(ALL_IDS)
        assert result.overall_level == ComplianceLevel.NON_COMPLIANT

    @pytest.mark.parametrize("ctx_factory", [_full_true_ctx, _full_false_ctx, _empty_ctx, _template_ctx],
                             ids=["all-true", "all-false", "keys-absent", "template-nulls"])
    def test_all_7_obligations_appear_once_in_findings(self, art48_module, tmp_path, ctx_factory):
        """All 7 obligations must appear in findings (explicit or gap), each exactly once."""
        BaseArticleModule.set_context(ctx_factory())
        result = art48_module.scan(str(tmp_path))
        found = sorted(f.obligation_id for f in result.findings if f.obligation_id.startswith("ART48-OBL-"))
        assert found == sorted(ALL_IDS)

    def test_every_condition_false_leaves_two_records_assessed(self, art48_module, tmp_path):
        """Nothing conditional applies: Art. 48(1) and (3) remain, the other five are NOT_APPLICABLE — also when
        their answers are False (the condition wins)."""
        result = _scan(art48_module, tmp_path, {**{f: False for f in CONDITION_FIELDS},
                                                **{f: False for f in ANSWER_FIELDS},
                                                "has_ce_marking": True,
                                                "follows_general_ce_marking_principles": True})
        levels = {f.obligation_id: f.level for f in result.findings if f.obligation_id.startswith("ART48-OBL-")}
        assert levels["ART48-OBL-1"] == ComplianceLevel.PARTIAL
        assert levels["ART48-OBL-3"] == ComplianceLevel.PARTIAL
        for obl_id in ("ART48-OBL-2", "ART48-OBL-4a", "ART48-OBL-4b", "ART48-OBL-4c", "ART48-OBL-5"):
            assert levels[obl_id] == ComplianceLevel.NOT_APPLICABLE, obl_id
        assert len(levels) == 7
        assert result.overall_level == ComplianceLevel.PARTIAL

    def test_findings_carry_the_verbatim_source_quote(self, art48_module, tmp_path):
        quotes = {o["id"]: o["source_quote"] for o in art48_module._load_obligations()["obligations"]}
        for ctx in (_full_true_ctx(), _ctx_with("art48", {NB: True, PROMO: False})):
            BaseArticleModule.set_context(ctx)
            result = art48_module.scan(str(tmp_path))
            for obl_id in ALL_IDS:
                assert _find(result, obl_id)[0].source_quote == quotes[obl_id], obl_id

    def test_not_high_risk_system_is_not_applicable(self, art48_module, tmp_path):
        """Art. 48 concerns high-risk AI systems only."""
        ctx = _ctx_with("art48", {"has_ce_marking": False})
        ctx.risk_classification = "minimal-risk"
        ctx.risk_classification_confidence = "high"
        BaseArticleModule.set_context(ctx)
        result = art48_module.scan(str(tmp_path))
        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE
        assert [f.obligation_id for f in result.findings] == ["ART48-NOT-APPLICABLE"]

    def test_validation_gate_lists_art48_as_high_risk_only(self):
        from core.validation_gate import _HIGH_RISK_ONLY
        assert 48 in _HIGH_RISK_ONLY
        assert _HIGH_RISK_ONLY == BaseArticleModule._HIGH_RISK_ONLY_ARTICLES


# ── Answers template ──

# Descriptions accepted unchanged by the review: (field, paragraph the text cites).
ACCEPTED_DESCRIPTIONS = [
    ("has_ce_marking", "Art. 48(3)"), ("has_digital_ce_marking", "Art. 48(2)"),
    ("is_provided_digitally", "Art. 48(2)"), ("has_notified_body_assessment", "Art. 48(4)"),
    ("has_notified_body_number", "Art. 48(4)"), ("is_subject_to_other_ce_marking_law", "Art. 48(5)"),
]
# Descriptions worded by the review: (field, a passage of the reviewed text, how it words the null case).
REVIEWED_DESCRIPTIONS = [
    ("has_ce_marking_promotional_material",
     "false if the project establishes that no such promotional material exists",
     "null if this cannot be determined"),
    ("has_notified_body_number_in_promotion",
     "false if at least one such item omits it",
     "null if compliance cannot be determined"),
    ("follows_general_ce_marking_principles",
     "the general principles in Article 30 of Regulation (EC) No 765/2008; false if the evidence establishes a breach",
     "null if this cannot be determined"),
    ("notified_body_number_affixed_by_permitted_actor",
     "false if the evidence establishes that it was affixed outside those permitted cases",
     "null if this cannot be determined"),
    ("ce_marking_indicates_other_union_law_compliance",
     "also fulfils the requirements of that other law; false if it does not",
     "null if this cannot be determined"),
]


class TestArt48AnswersTemplate:

    def test_template_has_exactly_the_art48_fields(self):
        assert _build_answers_template()["art48"] == {f: None for f in ANSWER_FIELDS + CONDITION_FIELDS}
        assert len(ANSWER_FIELDS + CONDITION_FIELDS) == 11

    def test_fields_are_boolean(self):
        assert sorted(_BOOL_FIELDS["art48"]) == sorted(ANSWER_FIELDS + CONDITION_FIELDS)

    def test_every_field_has_a_description(self):
        assert sorted(_FIELD_DESCRIPTIONS["art48"]) == sorted(ANSWER_FIELDS + CONDITION_FIELDS)
        described = [f for f, _ in ACCEPTED_DESCRIPTIONS] + [f for f, _, _ in REVIEWED_DESCRIPTIONS]
        assert sorted(described) == sorted(ANSWER_FIELDS + CONDITION_FIELDS)

    @pytest.mark.parametrize("field,paragraph", ACCEPTED_DESCRIPTIONS)
    def test_accepted_description_cites_its_paragraph(self, field, paragraph):
        text = _FIELD_DESCRIPTIONS["art48"][field]
        assert text.startswith("true if ")
        assert paragraph in text
        assert "null if you cannot determine it from the project" in text

    @pytest.mark.parametrize("field,passage,null_wording", REVIEWED_DESCRIPTIONS)
    def test_reviewed_description_keeps_the_reviewed_wording(self, field, passage, null_wording):
        text = _FIELD_DESCRIPTIONS["art48"][field]
        assert text.startswith("true if")
        assert passage in text
        assert text.endswith(null_wording)

    def test_no_promotional_material_is_not_a_reason_for_a_null_result(self):
        """The absence of such promotional material is answered by has_ce_marking_promotional_material (the record
        is then not applicable); it no longer makes the result field null."""
        assert "no such promotional material" not in _FIELD_DESCRIPTIONS["art48"][IN_PROMO]
        assert "no such promotional material" in _FIELD_DESCRIPTIONS["art48"][PROMO]

    def test_validation_gate_accepts_the_filled_template(self):
        """Booleans for every Art. 48 field pass the gate unchanged: no rename, no error."""
        from core.validation_gate import coerce_answers, validate_answers
        answers = {"_scope": {"risk_classification": "high-risk", "is_ai_system": True},
                   "art48": {f: True for f in ANSWER_FIELDS + CONDITION_FIELDS}}
        out, log = coerce_answers(json.loads(json.dumps(answers)))
        assert out["art48"] == answers["art48"]
        assert not [entry for entry in log if "art48" in str(entry)]
        errors, _missing = validate_answers(out)
        assert errors.get("art48", []) == []

    def test_data_file_states_the_review_and_has_nothing_pending(self):
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "data", "answer_field_descriptions.json")
        with open(path, encoding="utf-8") as f:
            meta = json.load(f)["_metadata"]
        assert "pending_verification" not in meta
        assert "2026-10-12" in meta["verification"]


# ── explain() and action_plan() ──

class TestArt48ExplainAndActionPlan:

    def test_explain(self, art48_module):
        e = art48_module.explain()
        assert (e.article_number, e.article_title) == (48, "CE marking")
        assert e.enforcement_date == applicable_from(48)
        assert "Art. 43" in e.related_articles and "Art. 47" in e.related_articles

    def test_action_plan_all_false(self, art48_module, tmp_path):
        """Every condition applies and every answer is False: one action per record."""
        BaseArticleModule.set_context(_full_false_ctx())
        plan = art48_module.action_plan(art48_module.scan(str(tmp_path)))
        assert [a.article for a in plan.actions] == [
            "Art. 48(3)", "Art. 48(2)", "Art. 48(4)", "Art. 48(4)", "Art. 48(4)", "Art. 48(5)", "Art. 48(1)",
        ]
        assert plan.actions[0].priority == "CRITICAL"
        assert plan.actions[-1].priority == "HIGH"

    def test_action_plan_skips_conditional_actions_when_the_condition_is_not_met(self, art48_module, tmp_path):
        result = _scan(art48_module, tmp_path, {
            "has_ce_marking": True, "is_provided_digitally": False, "has_digital_ce_marking": False,
            NB: False, "has_notified_body_number": False, "notified_body_number_affixed_by_permitted_actor": False,
            PROMO: True, IN_PROMO: False,
            "is_subject_to_other_ce_marking_law": False, "ce_marking_indicates_other_union_law_compliance": False,
        })
        plan = art48_module.action_plan(result)
        assert [a.article for a in plan.actions] == ["Art. 48(1)"]
        assert plan.actions[0].priority == "MEDIUM"

    def test_action_plan_skips_conditional_actions_when_the_condition_is_open(self, art48_module, tmp_path):
        result = _scan(art48_module, tmp_path, {
            "has_ce_marking": True, "has_digital_ce_marking": False, "has_notified_body_number": False,
            "notified_body_number_affixed_by_permitted_actor": False, IN_PROMO: False,
            "ce_marking_indicates_other_union_law_compliance": False,
        })
        plan = art48_module.action_plan(result)
        assert [a.article for a in plan.actions] == ["Art. 48(1)"]

    def test_action_plan_skips_the_promotional_action_without_such_material(self, art48_module, tmp_path):
        result = _scan(art48_module, tmp_path, {
            "has_ce_marking": True, NB: True, "has_notified_body_number": True,
            "notified_body_number_affixed_by_permitted_actor": True, PROMO: False, IN_PROMO: False,
        })
        plan = art48_module.action_plan(result)
        assert [a.article for a in plan.actions] == ["Art. 48(1)"]


# ── Sentences worded by the legal review of 2026-10-12 (items L4, L8-L12) — verbatim ──

L4_TRUE = ("Project evidence indicates that the CE marking may comply with the general principles set out in "
           "Article 30 of Regulation (EC) No 765/2008. Confirm this in Human Gates.")
L4_FALSE = ("Project evidence indicates that the CE marking does not follow the general principles set out in "
            "Article 30 of Regulation (EC) No 765/2008, to which Article 48(1) makes the CE marking subject.")
L4_NONE = ("Whether the CE marking follows the general principles set out in Article 30 of Regulation (EC) No "
           "765/2008 requires human review. AI could not determine it from the project.")
L4_NOTE = ("Review the CE marking of the high-risk AI system against the general principles set out in Article 30 "
           "of Regulation (EC) No 765/2008 and record the result.")
L8_NOTE = ("Record who affixed the identification number of the notified body. Article 16(h) requires the provider "
           "to affix the CE marking in accordance with Article 48; Article 48(4) allows the notified body's "
           "identification number to be affixed by the notified body itself or, under its instructions, by the "
           "provider or by the provider's authorised representative.")
L9_TRUE = ("Promotional material that mentions that the high-risk AI system fulfils the requirements for CE marking "
           "indicates the identification number of the notified body responsible for the conformity assessment "
           "procedures set out in Article 43. Verify that all such promotional material indicates that number.")
L10_NOTE = ("Identify the other Union law that also provides for the affixing of the CE marking and confirm whether "
            "the high-risk AI system fulfils the requirements of that other law.")
# action → details
L11_DETAILS = {
    "Add the notified body's identification number after the CE marking": (
        "Where applicable, Art. 48(4) requires the CE marking to be followed by the identification number of the "
        "notified body responsible for the conformity assessment procedures set out in Art. 43."),
    "Have the notified body's identification number affixed by a permitted performer": (
        "Where applicable, Art. 48(4) provides that the identification number is affixed by the notified body "
        "itself or, under the notified body's instructions, by the provider or by the provider's authorised "
        "representative."),
    "Indicate the notified body's identification number in promotional material": (
        "Where applicable, Art. 48(4) requires the identification number of the notified body to be indicated in "
        "any promotional material which mentions that the high-risk AI system fulfils the requirements for CE "
        "marking."),
}
L12_ONE_SENTENCE = (
    "The CE marking of a high-risk AI system is subject to the general principles set out in Article 30 of "
    "Regulation (EC) No 765/2008; for a system provided digitally, a digital CE marking shall be used only if it can "
    "easily be accessed via the interface from which the system is accessed or via an easily accessible "
    "machine-readable code or other electronic means; the marking shall be affixed visibly, legibly and indelibly "
    "or, where that is not possible or not warranted on account of the nature of the system, to the packaging or "
    "accompanying documentation; and, where applicable, it shall be followed by the identification number of the "
    "notified body responsible for the conformity assessment procedures set out in Article 43.")
L12_SUMMARY = (
    "Art. 48 makes the CE marking of high-risk AI systems subject to the general principles set out in Article 30 "
    "of Regulation (EC) No 765/2008. For systems provided digitally a digital CE marking is used, only if it can "
    "easily be accessed via the interface from which the system is accessed or via an easily accessible "
    "machine-readable code or other electronic means. The CE marking is affixed visibly, legibly and indelibly or, "
    "where that is not possible or not warranted on account of the nature of the system, to the packaging or to the "
    "accompanying documentation, as appropriate. Where applicable, it is followed by the identification number of "
    "the notified body responsible for the Art. 43 conformity assessment procedures; that number is affixed by the "
    "notified body itself or, under its instructions, by the provider or by the provider's authorised "
    "representative, and is also indicated in promotional material which mentions that the system fulfils the "
    "requirements for CE marking. Where the high-risk AI system is subject to other Union law which also provides "
    "for the affixing of the CE marking, the CE marking indicates that the system also fulfils the requirements of "
    "that other law.")


class TestArt48ReviewedSentences:

    @pytest.mark.parametrize("value,sentence", [(True, L4_TRUE), (False, L4_FALSE), (None, L4_NONE)],
                             ids=["yes", "no", "not-determined"])
    def test_l4_general_principles(self, art48_module, tmp_path, value, sentence):
        f = _find(_scan(art48_module, tmp_path, {"follows_general_ce_marking_principles": value}), "ART48-OBL-1")[0]
        assert f.description == sentence
        assert f.remediation == L4_NOTE

    @pytest.mark.parametrize("answers", [
        {NB: True, "notified_body_number_affixed_by_permitted_actor": True},
        {NB: True, "notified_body_number_affixed_by_permitted_actor": False},
        {NB: True},
        {},
    ], ids=["yes", "no", "not-determined", "condition-not-determined"])
    def test_l8_note_is_the_same_wherever_it_is_shown(self, art48_module, tmp_path, answers):
        assert _find(_scan(art48_module, tmp_path, answers), "ART48-OBL-4b")[0].remediation == L8_NOTE

    def test_l9_promotional_material_names_the_responsible_notified_body(self, art48_module, tmp_path):
        f = _find(_scan(art48_module, tmp_path, {NB: True, PROMO: True, IN_PROMO: True}), "ART48-OBL-4c")[0]
        assert f.description == L9_TRUE

    @pytest.mark.parametrize("answers", [
        {"is_subject_to_other_ce_marking_law": True, "ce_marking_indicates_other_union_law_compliance": True},
        {"is_subject_to_other_ce_marking_law": True, "ce_marking_indicates_other_union_law_compliance": False},
        {"is_subject_to_other_ce_marking_law": True},
        {},
    ], ids=["yes", "no", "not-determined", "condition-not-determined"])
    def test_l10_note_is_the_same_wherever_it_is_shown(self, art48_module, tmp_path, answers):
        assert _find(_scan(art48_module, tmp_path, answers), "ART48-OBL-5")[0].remediation == L10_NOTE

    def test_l11_paragraph_4_actions_keep_where_applicable(self, art48_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        plan = art48_module.action_plan(art48_module.scan(str(tmp_path)))
        details = {a.action: a.details for a in plan.actions if a.article == "Art. 48(4)"}
        assert details == L11_DETAILS

    def test_l12_explanation(self, art48_module):
        e = art48_module.explain()
        assert e.one_sentence == L12_ONE_SENTENCE
        assert e.official_summary == L12_SUMMARY


# ── Server: single-article scan and full scan ──

class TestArt48Server:

    def test_interim_standard_is_served(self):
        import server
        server._ensure_module_loaded(48)
        raw = server.cl_interim_standard(article_number=48)
        payload, _ = json.JSONDecoder().raw_decode(raw.lstrip())
        assert payload["is_official_standard"] is False
        assert payload["_metadata"]["standard_id"] == "CL-IS-ART48-v0.1"
        refs = sorted(r["obligation_ref"] for r in payload["requirements"])
        assert refs == sorted(ALL_IDS)

    def test_full_scan_includes_article_48(self, tmp_path):
        """cl_scan_all runs the articles of its phase list: an article missing from it is silently skipped."""
        import server
        answers = _build_answers_template()
        answers["_scope"].update({"is_ai_system": True, "risk_classification": "high-risk",
                                  "risk_classification_confidence": "high"})
        answers["art48"].update({"has_ce_marking": False})
        raw = server.cl_scan_all(str(tmp_path), project_context=json.dumps(
            {"framework": "python", "compliance_answers": answers}))
        report, _ = json.JSONDecoder().raw_decode(raw.lstrip())
        assert report["report_type"] == "compliance_scan_summary", report
        assert "Art. 48 (CE marking): non_compliant" in report["articles_scanned"]
        assert len(report["articles_scanned"]) == report["total_modules"]
