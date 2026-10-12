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
    assert "provider within Art. 3(3) of a general-purpose AI model within Art. 3(63)" in SCOPE["is_gpai_provider"]
    ar = SCOPE["is_authorised_representative"]
    assert "received and accepted a written mandate within Art. 3(5)" in ar
    assert "established in a third country" in ar and "Art. 22" in ar and "Art. 54" in ar


def test_every_described_scope_field_is_in_the_template():
    template_scope = _build_answers_template()["_scope"]
    for key in SCOPE:
        assert key in template_scope, key


def test_annex_iii_categories_has_a_value_format():
    d = _FIELD_DESCRIPTIONS["art6"]["annex_iii_categories"]
    assert '"5(b)"' in d
    assert '"2"' in d  # Annex III point 2 has no letter
    assert "[]" in d


def test_rule_2_names_the_boolean_fields_only():
    src = _server_source()
    assert "Values must be: true, false, or null — NEVER strings" not in src
    assert re.search(r"Boolean fields: true, false or null", src)
    assert re.search(r"Text fields take strings", src)


def test_null_vs_false_guidance_for_duties_that_do_not_concern_the_organisation():
    # Second legal review (2026-10-09, D6): a duty addressed to another operator is not applicable, not uncertain —
    # never false; scope fields carry the role where one exists; the rule says honestly how the rest is reported.
    src = re.sub(r"\s+", " ", _server_source().replace("║", " "))
    # Third review (2026-10-09, F1): the null shown as "unable to determine" is a tool limitation, not a legal finding.
    # 2026-10-12: "provider" is an answer in the role-first Profiling Wizard — the last sentence no longer says that
    # provider duties are never excluded on the basis of the provider role; it says what the dashboard excludes.
    # Legal review of 2026-10-12 (item M8) — verbatim: Article 25(2) can bind the initial provider, so it is named
    # separately from the provider duties that the Profiling Wizard excludes.
    final = (
        "5. A duty addressed solely to another operator does not apply to this organisation in that capacity. Never "
        "answer false solely because the operator role does not apply (false means the required measure is "
        "missing). If a _scope field covers the role (is_importer, is_distributor, is_gpai_provider, "
        "is_authorised_representative), set it to false. Deployer and ordinary provider duties have no offline role "
        "field: answer null when the duty is inapplicable solely because of the operator role. The offline scanner "
        "displays null as \"unable to determine\", which is a tool limitation, not a legal finding. On a paid "
        "dashboard plan, duties excluded by the Profiling Wizard are reported as not applicable: deployer duties "
        "where the answers do not establish deployer status; and ordinary provider duties where the answers "
        "establish neither provider status under Article 3(3) nor deemed-provider status under Article 25(1) or (3). "
        "Article 25(2) must be assessed separately because it can bind the initial provider after an Article 25(1) "
        "circumstance occurs, even though that initial provider is no longer considered the provider of the specific "
        "system."
    )
    assert final in src
    assert "including under Article 25." not in src


def test_risk_classification_example_uses_the_canonical_values():
    src = _server_source()
    assert '"risk_classification": "prohibited" | "high-risk" | "limited-risk" | "minimal-risk"' in src
