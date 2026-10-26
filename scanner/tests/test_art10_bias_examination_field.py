"""Article 10(2)(f) and (g) are answered separately (series-3 dry run, 2026-10-26).

The scanner read one answer, `has_bias_mitigation`, for both the examination of possible biases (Art. 10(2)(f)) and
the measures to detect, prevent and mitigate them (Art. 10(2)(g)). A recruiting system with safeguards in its scoring
prompt but no examination got "bias examination: partial"; the assistant itself said this overstated it. Now 2f reads
`has_bias_examination` (evidence in `bias_examination_evidence`), 2g keeps `has_bias_mitigation` (`bias_evidence`),
each field has a description, and the to-do list has one action per duty.
"""
from core.context import _FIELD_DESCRIPTIONS, _build_answers_template
from core.protocol import BaseArticleModule, ComplianceLevel
from conftest import _ctx_with


def _scan(art10_module, tmp_path, **answers):
    base = {"has_data_governance_doc": None, "data_doc_paths": [], "has_bias_examination": None,
            "bias_examination_evidence": [], "has_bias_mitigation": None, "bias_evidence": [],
            "has_data_lineage": None, "processes_special_category_data": None}
    BaseArticleModule.set_context(_ctx_with("art10", {**base, **answers}))
    return art10_module.scan(str(tmp_path))


def _level(result, oid):
    return next(f for f in result.findings if f.obligation_id == oid).level


def test_the_template_asks_for_the_examination_separately():
    template = _build_answers_template()["art10"]
    assert template["has_bias_examination"] is None
    assert template["bias_examination_evidence"] == []
    assert template["has_bias_mitigation"] is None


def test_each_bias_field_has_a_description():
    descs = _FIELD_DESCRIPTIONS["art10"]
    for field in ("has_bias_examination", "bias_examination_evidence", "has_bias_mitigation", "bias_evidence"):
        assert descs.get(field), field
    assert "Art. 10(2)(f)" in descs["has_bias_examination"]
    assert "Art. 10(2)(g)" in descs["has_bias_mitigation"]
    # the legal check's two points: measures alone and an unrun test are not an examination; "exists" is not "appropriate"
    assert "a test or examination that is planned or written but has not been carried out, are not an examination" in (
        descs["has_bias_examination"])
    assert "this answer records that measures exist, not that they are appropriate" in descs["has_bias_mitigation"]


def test_safeguards_without_an_examination_leave_2f_non_compliant(art10_module, tmp_path):
    result = _scan(art10_module, tmp_path, has_bias_mitigation=True, bias_evidence=["src/ranking.py: excluded factors"],
                   has_bias_examination=False)
    assert _level(result, "ART10-OBL-2f") == ComplianceLevel.NON_COMPLIANT
    assert _level(result, "ART10-OBL-2g") != ComplianceLevel.NON_COMPLIANT


def test_2f_quotes_the_examination_evidence_not_the_measures(art10_module, tmp_path):
    result = _scan(art10_module, tmp_path, has_bias_mitigation=True, bias_evidence=["src/ranking.py: excluded factors"],
                   has_bias_examination=True, bias_examination_evidence=["fairness/reports/2027-03-01.md: no gap > 5"])
    f2f = next(f for f in result.findings if f.obligation_id == "ART10-OBL-2f")
    assert "fairness/reports/2027-03-01.md" in f2f.description
    assert "excluded factors" not in f2f.description


def test_the_to_do_list_has_one_action_per_duty(art10_module, tmp_path):
    plan = art10_module.action_plan(_scan(art10_module, tmp_path, has_bias_examination=False, has_bias_mitigation=True))
    articles = [a.article for a in plan.actions]
    assert "Art. 10(2)(f)" in articles
    assert "Art. 10(2)(g)" not in articles
    assert "Art. 10(2)(f)(g)" not in articles

    plan = art10_module.action_plan(_scan(art10_module, tmp_path, has_bias_examination=True, has_bias_mitigation=False))
    articles = [a.article for a in plan.actions]
    assert "Art. 10(2)(g)" in articles and "Art. 10(2)(f)" not in articles
