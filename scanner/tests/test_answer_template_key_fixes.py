"""Answer-template key fixes before release (acceptance run A, AI-user notes; founder 2026-10-08).

- _scope.is_biometric_system had no description; the field gates the Annex III point 1(a) duties (Art. 12(3),
  Art. 14(5)), and a literal reading pulled 1:1 biometric verification in.
- _scope.is_open_source / is_gpai_provider / is_authorised_representative drive the Art. 2(12) and Chapter V scope gates
  (test_scope_gate_art2_12_chapter_v.py); a Yes to is_open_source is an attestation that the Art. 2(12) exceptions do
  not apply.
- art6.annex_iii_categories had no value format.
- cl_analyze_project's rule #2 said every value must be true / false / null, contradicting the string, list and
  number fields of the template.
- No guidance on null vs false for a duty that does not concern the organisation.
"""
import os
import re
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.context import _FIELD_DESCRIPTIONS, _build_answers_template  # noqa: E402

SCOPE = _FIELD_DESCRIPTIONS["_scope"]


def _server_source() -> str:
    with open(os.path.join(SCANNER_ROOT, "server.py"), encoding="utf-8") as f:
        return f.read()


def test_is_biometric_system_is_described_as_annex_iii_point_1a():
    d = SCOPE["is_biometric_system"]
    assert "Annex III point 1(a)" in d
    assert "remote biometric identification" in d
    assert "verification" in d  # 1:1 verification is excluded
    assert "Art. 12(3)" in d and "Art. 14(5)" in d


def test_is_open_source_is_an_attestation():
    d = SCOPE["is_open_source"]
    for needle in ("free and open-source licence", "high-risk", "Art. 5", "Art. 50", "Art. 2(12)", "Art. 51-55"):
        assert needle in d, needle


def test_gpai_and_representative_scope_fields_are_described():
    assert "Art. 3(63)" in SCOPE["is_gpai_provider"]
    assert "Art. 3(5)" in SCOPE["is_authorised_representative"]
    assert "Art. 54" in SCOPE["is_authorised_representative"]


def test_every_described_scope_field_is_in_the_template():
    template_scope = _build_answers_template()["_scope"]
    for key in SCOPE:
        assert key in template_scope, key


def test_annex_iii_categories_has_a_value_format():
    d = _FIELD_DESCRIPTIONS["art6"]["annex_iii_categories"]
    assert '"5(b)"' in d
    assert "[]" in d


def test_rule_2_names_the_boolean_fields_only():
    src = _server_source()
    assert "Values must be: true, false, or null — NEVER strings" not in src
    assert re.search(r"Boolean fields: true, false or null", src)
    assert re.search(r"Text fields take strings", src)


def test_null_vs_false_guidance_for_duties_that_do_not_concern_the_organisation():
    src = _server_source()
    assert re.search(r"does not concern this organisation", src)
    assert re.search(r"answer null, not false", src)


def test_risk_classification_example_uses_the_canonical_values():
    src = _server_source()
    assert '"risk_classification": "prohibited" | "high-risk" | "limited-risk" | "minimal-risk"' in src
