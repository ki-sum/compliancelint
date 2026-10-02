"""AI clients must be told what each Art 5 answer field means.

Self-audit B2 (2026-10-02): cl_analyze_project gave the AI field NAMES only, and
scanning_strategy.articles was empty for all 44 articles (its builder read
automation_assessment.detection_method from the public obligation JSONs, which no longer carry
it since §AA — the field is merged in from the SaaS classification API). For
has_ncii_generation the bare name invites a capability reading ("can the system generate
images?") and would mark every image generator with safeguards NON_COMPLIANT from 2026-12-02.
"""
import pytest

from core import context as cx


def _art5_template() -> dict:
    return cx._build_answers_template()["art5"]


def test_template_has_only_fields_the_module_reads(art05_module):
    fields = type(art05_module).scan.__globals__["_PROHIBITION_FIELDS"]
    expected = {f for f, _o, _l in fields} | {f.replace("has_", "") + "_evidence" for f, _o, _l in fields}
    assert set(_art5_template()) == expected


def test_evidence_fields_default_to_empty_string(art05_module):
    t = _art5_template()
    assert all(v == "" for k, v in t.items() if k.endswith("_evidence"))
    assert all(v is None for k, v in t.items() if k.startswith("has_"))


def test_every_art5_template_field_is_described(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    meta = cx.analyze_project_metadata(str(tmp_path))
    desc = meta["compliance_answers_field_descriptions"]["art5"]
    assert set(desc) == set(_art5_template())
    assert all(isinstance(v, str) and len(v) > 20 for v in desc.values())


@pytest.mark.parametrize("field", ["has_ncii_generation", "has_csam_generation"])
def test_new_prohibitions_explain_the_art5_1a_test(field):
    d = cx._FIELD_DESCRIPTIONS["art5"][field]
    assert "Art. 5(1a)" in d
    assert "not enough" in d  # capability alone does not meet the test


def test_scanning_strategy_uses_merged_classification(monkeypatch):
    from core import obligation_lookup

    def fake_rows():
        yield {"id": "ART12-OBL-1", "automation_assessment": {
            "level": "full", "detection_method": "Look for logging setup", "what_to_scan": ["code"]}}

    monkeypatch.setattr(obligation_lookup, "iter_obligation_rows", fake_rows)
    s = cx._build_scanning_strategy()
    assert s["articles"]["art12"]["detection_hints"] == ["Look for logging setup"]
    assert "note" not in s


def test_scanning_strategy_says_why_it_is_empty(monkeypatch):
    from core import obligation_lookup

    def fake_rows():
        yield {"id": "ART12-OBL-1", "automation_assessment": {"level": "full"}}

    monkeypatch.setattr(obligation_lookup, "iter_obligation_rows", fake_rows)
    s = cx._build_scanning_strategy()
    assert s["articles"] == {}
    assert "compliance_answers_field_descriptions" in s["note"]
