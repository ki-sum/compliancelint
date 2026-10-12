"""Art. 48 CE marking tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  (manual, always UTD)                    → ART48-OBL-1  (Art. 48(1))
  has_digital_ce_marking                  → ART48-OBL-2  (Art. 48(2); condition: is_provided_digitally)
  has_ce_marking                          → ART48-OBL-3  (Art. 48(3))
  has_notified_body_number                → ART48-OBL-4a (Art. 48(4), first sentence;
                                                          condition: has_notified_body_assessment)
  (manual, always UTD when it applies)    → ART48-OBL-4b (Art. 48(4), second sentence; same condition)
  has_notified_body_number_in_promotion   → ART48-OBL-4c (Art. 48(4), third sentence; same condition)
  (manual, always UTD when it applies)    → ART48-OBL-5  (Art. 48(5); condition: is_subject_to_other_ce_marking_law)

A conditional record is assessed from its answer only when its condition is answered true: with the condition
false it is NOT_APPLICABLE, with the condition unanswered (key absent, or null as in the answers template) it
stays UNABLE_TO_DETERMINE whatever the answer says.
"""
import json

import pytest

from core.application_dates import applicable_from
from core.context import _BOOL_FIELDS, _FIELD_DESCRIPTIONS, _build_answers_template
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with

ALL_IDS = ["ART48-OBL-1", "ART48-OBL-2", "ART48-OBL-3", "ART48-OBL-4a", "ART48-OBL-4b", "ART48-OBL-4c",
           "ART48-OBL-5"]
MANUAL_IDS = ["ART48-OBL-1", "ART48-OBL-4b", "ART48-OBL-5"]
ANSWER_FIELDS = ["has_ce_marking", "has_digital_ce_marking", "has_notified_body_number",
                 "has_notified_body_number_in_promotion"]
CONDITION_FIELDS = ["is_provided_digitally", "has_notified_body_assessment", "is_subject_to_other_ce_marking_law"]

# (obligation, condition field, answer field, words the finding uses when the condition is open)
CONDITIONAL_ANSWERED = [
    ("ART48-OBL-2", "is_provided_digitally", "has_digital_ce_marking", "is provided digitally"),
    ("ART48-OBL-4a", "has_notified_body_assessment", "has_notified_body_number", "whether a notified body"),
    ("ART48-OBL-4c", "has_notified_body_assessment", "has_notified_body_number_in_promotion",
     "whether a notified body"),
]
# (obligation, condition field, words the finding uses when the condition is open)
CONDITIONAL_MANUAL = [
    ("ART48-OBL-4b", "has_notified_body_assessment", "whether a notified body"),
    ("ART48-OBL-5", "is_subject_to_other_ce_marking_law", "is subject to other Union law"),
]
# The condition is unanswered: the key is absent, or present with null (the shape of the answers template).
UNANSWERED = [pytest.param(False, id="key-absent"), pytest.param(True, id="key-null")]


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


# ── ART48-OBL-1: general principles of Article 30 of Regulation (EC) No 765/2008 (manual, always UTD) ──

class TestArt48Obl1:

    def test_always_utd(self, art48_module, tmp_path):
        """ART48-OBL-1 is UNABLE_TO_DETERMINE when every answer is True (manual obligation)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art48_module.scan(str(tmp_path))
        obl = _find(result, "ART48-OBL-1")
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_utd_even_when_all_false(self, art48_module, tmp_path):
        """ART48-OBL-1 stays UNABLE_TO_DETERMINE when every answer is False."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art48_module.scan(str(tmp_path))
        obl = _find(result, "ART48-OBL-1")
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_names_the_regulation_and_points_to_human_gates(self, art48_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art48_module.scan(str(tmp_path))
        obl = _find(result, "ART48-OBL-1")[0]
        assert "Article 30 of Regulation (EC) No 765/2008" in obl.description
        assert "compliancelint.dev" in obl.human_gate_hint


# ── ART48-OBL-3: affixed visibly, legibly and indelibly (has_ce_marking) ──

class TestArt48Obl3:

    def test_true_gives_partial(self, art48_module, tmp_path):
        """has_ce_marking=True → ART48-OBL-3 PARTIAL."""
        result = _scan(art48_module, tmp_path, {"has_ce_marking": True})
        obl = _find(result, "ART48-OBL-3")
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art48_module, tmp_path):
        """has_ce_marking=False → ART48-OBL-3 NON_COMPLIANT."""
        result = _scan(art48_module, tmp_path, {"has_ce_marking": False})
        obl = _find(result, "ART48-OBL-3")
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art48_module, tmp_path):
        """has_ce_marking=None → ART48-OBL-3 UNABLE_TO_DETERMINE."""
        result = _scan(art48_module, tmp_path, {})
        obl = _find(result, "ART48-OBL-3")
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART48-OBL-2 / 4a / 4c: conditional records a boolean answer decides ──

@pytest.mark.parametrize("obl_id,condition,answer,open_words", CONDITIONAL_ANSWERED)
class TestArt48ConditionalAnswered:

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

    def test_condition_true_answer_none_gives_utd(self, art48_module, tmp_path, obl_id, condition, answer,
                                                  open_words):
        result = _scan(art48_module, tmp_path, {condition: True})
        obl = _find(result, obl_id)
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE
        assert open_words not in obl[0].description

    def test_condition_false_gives_not_applicable(self, art48_module, tmp_path, obl_id, condition, answer,
                                                  open_words):
        """The condition does not apply → NOT_APPLICABLE, also when the answer is False."""
        result = _scan(art48_module, tmp_path, {condition: False, answer: False})
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


# ── ART48-OBL-4b / 5: conditional records that need human judgment ──

@pytest.mark.parametrize("obl_id,condition,open_words", CONDITIONAL_MANUAL)
class TestArt48ConditionalManual:

    def test_condition_false_gives_not_applicable(self, art48_module, tmp_path, obl_id, condition, open_words):
        result = _scan(art48_module, tmp_path, {condition: False})
        obl = _find(result, obl_id)
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_condition_true_gives_utd_for_human_review(self, art48_module, tmp_path, obl_id, condition,
                                                       open_words):
        result = _scan(art48_module, tmp_path, {condition: True})
        obl = _find(result, obl_id)
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE
        assert "requires human review" in obl[0].description
        assert "AI could not determine" not in obl[0].description
        assert "compliancelint.dev" in obl[0].human_gate_hint

    @pytest.mark.parametrize("as_null", UNANSWERED)
    def test_condition_unanswered_gives_utd_naming_the_open_condition(self, art48_module, tmp_path, obl_id,
                                                                      condition, open_words, as_null):
        result = _scan(art48_module, tmp_path, _with_open_condition(condition, as_null, {}))
        obl = _find(result, obl_id)
        assert len(obl) == 1
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE
        assert open_words in obl[0].description

    def test_never_non_compliant_from_answers(self, art48_module, tmp_path, obl_id, condition, open_words):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art48_module.scan(str(tmp_path))
        assert _find(result, obl_id)[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── The three paragraph 4 records share one condition ──

class TestArt48NotifiedBodyCondition:

    def test_no_notified_body_makes_all_of_paragraph_4_not_applicable(self, art48_module, tmp_path):
        result = _scan(art48_module, tmp_path, {
            "has_ce_marking": True, "has_notified_body_assessment": False,
            "has_notified_body_number": False, "has_notified_body_number_in_promotion": False,
        })
        for obl_id in ("ART48-OBL-4a", "ART48-OBL-4b", "ART48-OBL-4c"):
            assert _find(result, obl_id)[0].level == ComplianceLevel.NOT_APPLICABLE, obl_id
        assert not [f for f in result.findings if f.level == ComplianceLevel.NON_COMPLIANT]
        assert result.overall_level == ComplianceLevel.PARTIAL


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

    def test_description_has_no_legal_citation_prefix(self, art48_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 48(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art48_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art48_module, tmp_path):
        """All-true answers → the four answered records PARTIAL, the three manual ones UTD, overall PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art48_module.scan(str(tmp_path))
        levels = {f.obligation_id: f.level for f in result.findings}
        for obl_id in ALL_IDS:
            expected = ComplianceLevel.UNABLE_TO_DETERMINE if obl_id in MANUAL_IDS else ComplianceLevel.PARTIAL
            assert levels[obl_id] == expected, obl_id
        assert result.overall_level == ComplianceLevel.PARTIAL

    def test_all_false_has_non_compliant(self, art48_module, tmp_path):
        """All-false answers with every condition applying → the four answered records are NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art48_module.scan(str(tmp_path))
        non_compliant = sorted(f.obligation_id for f in result.findings if f.level == ComplianceLevel.NON_COMPLIANT)
        assert non_compliant == ["ART48-OBL-2", "ART48-OBL-3", "ART48-OBL-4a", "ART48-OBL-4c"]
        assert result.overall_level == ComplianceLevel.NON_COMPLIANT

    @pytest.mark.parametrize("ctx_factory", [_full_true_ctx, _full_false_ctx, _empty_ctx, _template_ctx],
                             ids=["all-true", "all-false", "keys-absent", "template-nulls"])
    def test_all_7_obligations_appear_once_in_findings(self, art48_module, tmp_path, ctx_factory):
        """All 7 obligations must appear in findings (explicit or gap), each exactly once."""
        BaseArticleModule.set_context(ctx_factory())
        result = art48_module.scan(str(tmp_path))
        found = sorted(f.obligation_id for f in result.findings if f.obligation_id.startswith("ART48-OBL-"))
        assert found == sorted(ALL_IDS)

    def test_every_condition_false_leaves_three_records_assessed(self, art48_module, tmp_path):
        """Nothing conditional applies: Art. 48(1) and (3) remain, the other five are NOT_APPLICABLE."""
        result = _scan(art48_module, tmp_path, {**{f: False for f in CONDITION_FIELDS}, "has_ce_marking": True})
        levels = {f.obligation_id: f.level for f in result.findings}
        assert levels["ART48-OBL-1"] == ComplianceLevel.UNABLE_TO_DETERMINE
        assert levels["ART48-OBL-3"] == ComplianceLevel.PARTIAL
        for obl_id in ("ART48-OBL-2", "ART48-OBL-4a", "ART48-OBL-4b", "ART48-OBL-4c", "ART48-OBL-5"):
            assert levels[obl_id] == ComplianceLevel.NOT_APPLICABLE, obl_id

    def test_findings_carry_the_verbatim_source_quote(self, art48_module, tmp_path):
        quotes = {o["id"]: o["source_quote"] for o in art48_module._load_obligations()["obligations"]}
        BaseArticleModule.set_context(_full_true_ctx())
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

class TestArt48AnswersTemplate:

    def test_template_has_exactly_the_art48_fields(self):
        assert _build_answers_template()["art48"] == {f: None for f in ANSWER_FIELDS + CONDITION_FIELDS}

    def test_fields_are_boolean(self):
        assert sorted(_BOOL_FIELDS["art48"]) == sorted(ANSWER_FIELDS + CONDITION_FIELDS)

    @pytest.mark.parametrize("field,paragraph", [
        ("has_ce_marking", "Art. 48(3)"), ("has_digital_ce_marking", "Art. 48(2)"),
        ("is_provided_digitally", "Art. 48(2)"), ("has_notified_body_assessment", "Art. 48(4)"),
        ("has_notified_body_number", "Art. 48(4)"), ("has_notified_body_number_in_promotion", "Art. 48(4)"),
        ("is_subject_to_other_ce_marking_law", "Art. 48(5)"),
    ])
    def test_every_field_has_a_description_citing_its_paragraph(self, field, paragraph):
        text = _FIELD_DESCRIPTIONS["art48"][field]
        assert text.startswith("true if ")
        assert paragraph in text
        assert "null if you cannot determine it from the project" in text

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


# ── explain() and action_plan() ──

class TestArt48ExplainAndActionPlan:

    def test_explain(self, art48_module):
        e = art48_module.explain()
        assert (e.article_number, e.article_title) == (48, "CE marking")
        assert e.enforcement_date == applicable_from(48)
        assert "Art. 43" in e.related_articles and "Art. 47" in e.related_articles

    def test_action_plan_all_false(self, art48_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        plan = art48_module.action_plan(art48_module.scan(str(tmp_path)))
        assert [a.article for a in plan.actions] == [
            "Art. 48(3)", "Art. 48(2)", "Art. 48(4)", "Art. 48(4)", "Art. 48(1)",
        ]
        assert plan.actions[0].priority == "CRITICAL"

    def test_action_plan_skips_conditional_actions_when_the_condition_is_not_met(self, art48_module, tmp_path):
        result = _scan(art48_module, tmp_path, {
            "has_ce_marking": True, "is_provided_digitally": False, "has_digital_ce_marking": False,
            "has_notified_body_assessment": False, "has_notified_body_number": False,
            "has_notified_body_number_in_promotion": False,
        })
        plan = art48_module.action_plan(result)
        assert [a.article for a in plan.actions] == ["Art. 48(1)"]

    def test_action_plan_skips_conditional_actions_when_the_condition_is_open(self, art48_module, tmp_path):
        result = _scan(art48_module, tmp_path, {
            "has_ce_marking": True, "has_digital_ce_marking": False, "has_notified_body_number": False,
            "has_notified_body_number_in_promotion": False,
        })
        plan = art48_module.action_plan(result)
        assert [a.article for a in plan.actions] == ["Art. 48(1)"]


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
