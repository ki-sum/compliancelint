"""Template-gap task (2026-10-04, post-Omnibus): every answer key an article module reads is in the
compliance_answers template the AI fills, with a description.

Found: 24 modules read 59 keys that were not in the template and not legacy aliases — the AI was never asked
for them, so the obligations they decide were always UNABLE_TO_DETERMINE (e.g. ART16-OBL-1h CE marking,
ART53-OBL-1c copyright policy). Numbers (log retention days, training compute) had no field type at all.
"""
import glob
import json
import os
import re

import pytest

from core.context import (
    _AUX_FIELDS, _BOOL_FIELDS, _FIELD_DESCRIPTIONS, _LIST_FIELDS, _NUMBER_FIELDS, _build_answers_template,
)
from core.validation_gate import coerce_answers, validate_answers

SCANNER = os.path.join(os.path.dirname(__file__), "..")
MODULES = os.path.join(SCANNER, "modules")

# The legacy aliases were removed 2026-10-04 (template-gap T1); none may be read any more.
ALIASES: dict = {}

NEW_KEYS = {
    "bool": {
        "art6": ["has_risk_classification_doc"], "art10": ["uses_model_training"],
        "art16": ["has_documentation_kept", "has_log_retention", "has_conformity_assessment", "has_eu_declaration",
                  "has_ce_marking", "has_registration", "has_corrective_actions_process", "has_conformity_evidence",
                  "has_accessibility_compliance"],
        "art22": ["has_mandate_authority_contact"],
        "art25": ["has_third_party_written_agreement", "has_open_source_exception"],
        "art26": ["has_log_retention", "has_affected_persons_notification"],
        "art51": ["has_systemic_risk_assessment", "has_commission_designation"],
        "art53": ["has_copyright_policy", "has_training_data_summary", "training_data_summary_public",
                  "is_open_source_gpai", "has_systemic_risk"],
        "art54": ["is_open_source_gpai", "has_systemic_risk"],
        "art55": ["has_incident_tracking", "has_cybersecurity_protection"],
    },
    "list": {
        "art53": ["copyright_policy_evidence", "training_data_evidence"], "art54": ["mandate_evidence"],
        "art55": ["incident_evidence", "cybersecurity_evidence"], "art86": ["explanation_evidence"],
    },
    "number": {"art12": ["retention_days"], "art19": ["retention_days"], "art26": ["retention_days"],
               "art51": ["training_compute_flops"]},
    "text": {
        "art4": ["literacy_description"], "art6": ["annex_i_product_type", "reasoning"],
        "art12": ["logging_description", "retention_evidence"], "art18": ["retention_policy_evidence"],
        "art19": ["retention_evidence"], "art26": ["retention_evidence"], "art51": ["reasoning"],
        "art52": ["notification_evidence"], "art91": ["readiness_evidence"], "art92": ["cooperation_evidence"],
        "art111": ["transition_evidence", "change_tracking_evidence", "gpai_timeline_evidence"],
    },
}
REGISTRY = {"bool": _BOOL_FIELDS, "list": _LIST_FIELDS, "number": _NUMBER_FIELDS, "text": _AUX_FIELDS}
DEFAULT = {"bool": None, "list": [], "number": None, "text": ""}


def _module_reads():
    for p in sorted(glob.glob(os.path.join(MODULES, "art*", "module.py"))):
        art = "art" + str(int(re.search(r"art0*(\d+)", os.path.basename(os.path.dirname(p))).group(1)))
        yield art, set(re.findall(r'answers\.get\("([a-z_0-9]+)"', open(p, encoding="utf-8").read()))


def test_the_inventory_has_52_keys():
    assert sum(len(v) for kind in NEW_KEYS.values() for v in kind.values()) == 52


@pytest.mark.parametrize("kind", sorted(NEW_KEYS))
def test_new_keys_are_registered_with_their_type_and_template_default(kind):
    tmpl = _build_answers_template()
    for art, keys in NEW_KEYS[kind].items():
        for k in keys:
            assert k in REGISTRY[kind].get(art, []), f"{art}.{k} not registered as {kind}"
            assert k in tmpl.get(art, {}), f"{art}.{k} not in the answers template"
            assert tmpl[art][k] == DEFAULT[kind], f"{art}.{k} template default {tmpl[art][k]!r}"


def test_every_new_key_has_a_description_from_the_data_file():
    from core.application_dates import chapter_iii_dates, long_date
    data = json.load(open(os.path.join(SCANNER, "data", "answer_field_descriptions.json"), encoding="utf-8"))
    dates = chapter_iii_dates()
    render = lambda t: t.replace("{chapter_iii_annex_iii}", long_date(dates["annex_iii"])).replace(  # noqa: E731
        "{chapter_iii_annex_i}", long_date(dates["annex_i"]))
    for kind in NEW_KEYS.values():
        for art, keys in kind.items():
            for k in keys:
                assert data[art][k].strip(), f"{art}.{k} empty in the data file"
                assert _FIELD_DESCRIPTIONS[art][k] == render(data[art][k]), f"{art}.{k} not merged into _FIELD_DESCRIPTIONS"


def test_drift_every_module_read_key_is_in_the_template():
    """T4: a module may only read keys the AI is asked for."""
    tmpl = _build_answers_template()
    missing = {}
    for art, reads in _module_reads():
        gap = sorted(reads - set(tmpl.get(art, {})) - ALIASES.get(art, set()))
        if gap:
            missing[art] = gap
    assert missing == {}


# ── number fields through the validation gate ────────────────────────────────

def _art12(**fields):
    return {"_scope": {"risk_classification": "high-risk"}, "art12": {"has_logging": True, **fields}}


@pytest.mark.parametrize("raw, expected", [(180, 180), (180.0, 180.0), ("180", 180), (" 365 ", 365),
                                           ("1e25", 1e25), (None, None),
                                           # forms an AI writes for compute / periods
                                           ("10^26", 1e26), ("3.5 x 10^26", 3.5e26), ("3.5×10^26", 3.5e26),
                                           ("1.5e25 FLOPs", 1.5e25), ("180 days", 180)])
def test_number_fields_are_coerced(raw, expected):
    out, _log = coerce_answers(_art12(retention_days=raw))
    assert out["art12"]["retention_days"] == expected


@pytest.mark.parametrize("raw", ["thirty days", True, ["180"]])
def test_a_non_number_is_a_validation_error_not_renamed_or_dropped(raw):
    out, _log = coerce_answers(_art12(retention_days=raw))
    assert out["art12"]["retention_days"] == raw  # not silently changed
    errors, _missing = validate_answers(out)
    assert any(e.field == "retention_days" for e in errors.get("art12", [])), errors


@pytest.mark.parametrize("raw, expected", [("180", 180), ("1e25", 1e25), (365, 365), ("thirty", None),
                                           (True, None), (None, None)])
def test_modules_read_numbers_never_strings(raw, expected):
    """ProjectContext.get_article_answers (what modules read) turns a numeric string into a number and any
    other non-number into None, so e.g. Art 12 `retention_days < 180` never compares a string."""
    from core.context import ProjectContext
    ctx = ProjectContext(primary_language="python", compliance_answers={"art12": {"retention_days": raw}})
    assert ctx.get_article_answers("art12")["retention_days"] == expected


# ── ART10-OBL-6: Art 10(6) applies only to systems developed without training techniques ─────────────

def _art10_obl6(uses_model_training, art10_module, tmp_path):
    from conftest import _ctx_with
    from core.protocol import BaseArticleModule
    BaseArticleModule.set_context(_ctx_with("art10", {"uses_model_training": uses_model_training}))
    found = [f for f in art10_module.scan(str(tmp_path)).findings if f.obligation_id == "ART10-OBL-6"]
    assert found, "ART10-OBL-6 not reported"
    return {f.level.value for f in found}


def test_art10_obl6_not_applicable_when_the_system_trains_models(art10_module, tmp_path):
    assert _art10_obl6(True, art10_module, tmp_path) == {"not_applicable"}


@pytest.mark.parametrize("value", [False, None])
def test_art10_obl6_stays_applicable_otherwise(value, art10_module, tmp_path):
    assert "not_applicable" not in _art10_obl6(value, art10_module, tmp_path)


def test_art10_obl6_record_declares_the_skip_field():
    rec = next(o for o in json.load(open(os.path.join(SCANNER, "obligations", "art10-data-governance.json"),
                                          encoding="utf-8"))["obligations"] if o["id"] == "ART10-OBL-6")
    assert rec["context_skip_field"] == "uses_model_training"
    assert rec["context_skip_value"] is True


def test_wizard_uses_training_data_sets_art10_uses_model_training():
    """The SaaS wizard's usesTrainingData is authoritative for art10.uses_model_training (ART10-OBL-6 skip)."""
    import sys
    sys.path.insert(0, SCANNER)
    from server import _apply_wizard_overrides_to_answers
    answers = {"art10": {"uses_model_training": None}}
    _apply_wizard_overrides_to_answers(answers, {"usesTrainingData": True})
    assert answers["art10"]["uses_model_training"] is True
    answers = {"art10": {"uses_model_training": True}}
    _apply_wizard_overrides_to_answers(answers, {"usesTrainingData": False})
    assert answers["art10"]["uses_model_training"] is False


def test_art113_dates_in_descriptions_come_from_application_dates():
    """Template check 9 (founder): a date another article sets (here the Art. 113 Chapter III dates that
    Art. 111(2) refers to) comes from data/application_dates.json, never typed into a text. The o3-verified
    Art. 111 descriptions keep placeholders in the data file; the served text has the current dates."""
    from core.application_dates import chapter_iii_dates, long_date
    raw = json.load(open(os.path.join(SCANNER, "data", "answer_field_descriptions.json"), encoding="utf-8"))
    dates = {k: long_date(v) for k, v in chapter_iii_dates().items()}
    for field in ("transition_evidence", "change_tracking_evidence"):
        assert "{chapter_iii_annex_iii}" in raw["art111"][field] and "{chapter_iii_annex_i}" in raw["art111"][field]
        for typed in dates.values():
            assert typed not in raw["art111"][field]
        served = _FIELD_DESCRIPTIONS["art111"][field]
        assert dates["annex_iii"] in served and dates["annex_i"] in served and "{" not in served


def test_a_former_alias_no_longer_answers_another_obligation(art15_module, tmp_path):
    """T1: art15 `has_cybersecurity` was read as `has_fallback_behavior` (a different Art. 15(4) duty), so an
    AI reporting cybersecurity measures made the fallback obligation look met. The key is now ignored."""
    from conftest import _ctx_with
    from core.protocol import BaseArticleModule
    BaseArticleModule.set_context(_ctx_with("art15", {"has_cybersecurity": True}))
    with_alias = {(f.obligation_id, f.level.value) for f in art15_module.scan(str(tmp_path)).findings}
    BaseArticleModule.set_context(_ctx_with("art15", {}))
    without = {(f.obligation_id, f.level.value) for f in art15_module.scan(str(tmp_path)).findings}
    assert with_alias == without
