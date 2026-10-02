"""Art. 5 — compliance_answers template must expose every field module.py reads.

Regression for gap G-19 (NCII migration 2026-10-02): since v1.0.0 the
cl_analyze_project template offered art5 = {is_realtime_processing,
prohibited_practices} while the module only reads the has_* booleans, so an
AI client that filled the template exactly got UNABLE_TO_DETERMINE for every
Art. 5 prohibition and Art. 5 could never reach COMPLIANT.
"""
from core.context import _build_answers_template
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _module_fields(art05_module) -> list[str]:
    # module.py is loaded via importlib without a sys.modules entry, so read
    # the module-level constant through the class's function globals.
    prohibition_fields = type(art05_module).scan.__globals__["_PROHIBITION_FIELDS"]
    return [field for field, _obl_id, _label in prohibition_fields]


def test_every_field_read_by_module_is_in_template(art05_module):
    template = _build_answers_template()["art5"]
    missing = [f for f in _module_fields(art05_module) if f not in template]
    assert missing == [], f"art5 template lacks fields module.py reads: {missing}"


def test_template_fields_default_to_null(art05_module):
    template = _build_answers_template()["art5"]
    for field in _module_fields(art05_module):
        assert template[field] is None, field


def test_template_shaped_answers_reach_compliant(art05_module, tmp_path):
    """Fill the template exactly as an AI client would: every has_* = False."""
    answers = dict(_build_answers_template()["art5"])
    for field in _module_fields(art05_module):
        answers[field] = False
    BaseArticleModule.set_context(_ctx_with("art5", answers))
    result = art05_module.scan(str(tmp_path))
    assert result.overall_level == ComplianceLevel.COMPLIANT
    base_ids = [f"ART05-PRO-1{c}" for c in "abcdefgh"]
    by_id = {f.obligation_id: f for f in result.findings}
    for obl_id in base_ids:
        assert by_id[obl_id].level == ComplianceLevel.COMPLIANT, obl_id
