"""Art. 5(1)(ba) NCII + 5(1)(bb) CSAM — added by Reg (EU) 2026/1744 (Digital Omnibus).

Both points apply from 2026-12-02 (Art. 113, third paragraph, point (a), as
amended). Before that date the findings are informational NOT_APPLICABLE (they
must not move the Art. 5 overall level); from that date on they behave like
every other Art. 5 prohibition: detected → NON_COMPLIANT, not detected →
COMPLIANT, unknown → UNABLE_TO_DETERMINE.

Evidence: Consensus Lock 2026-10-02 (parallel independent extraction Claude + o3).
"""
import json
import os
from datetime import date

import pytest

from core.context import _build_answers_template
from core.protocol import BaseArticleModule, ComplianceLevel
from conftest import _ctx_with

OBL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "obligations", "art05-prohibited-practices.json"
)

_NEW = [
    ("has_ncii_generation", "ART05-PRO-1ba"),
    ("has_csam_generation", "ART05-PRO-1bb"),
]
_BASE_FIELDS = [
    "has_subliminal_manipulation", "has_exploitation_of_vulnerabilities",
    "has_social_scoring", "has_predictive_policing",
    "has_facial_recognition_scraping", "has_emotion_recognition_workplace",
    "has_biometric_categorization", "has_real_time_biometric_id",
]

BEFORE = date(2026, 12, 1)
ON = date(2026, 12, 2)
AFTER = date(2027, 6, 1)


def _obligations() -> dict:
    with open(OBL_PATH, encoding="utf-8") as f:
        return {o["id"]: o for o in json.load(f)["obligations"]}


def _scan(art05_module, tmp_path, monkeypatch, today: date, answers: dict):
    monkeypatch.setitem(type(art05_module).scan.__globals__, "_today", lambda: today)
    BaseArticleModule.set_context(_ctx_with("art5", answers))
    return art05_module.scan(str(tmp_path))


def _finding(result, obl_id):
    found = [f for f in result.findings if f.obligation_id == obl_id]
    assert len(found) == 1, f"expected exactly one finding for {obl_id}, got {len(found)}"
    return found[0]


def _clean_base() -> dict:
    return {field: False for field in _BASE_FIELDS}


# ── Obligation data (Step 5h-5 values) ───────────────────────────────────


class TestObligationData:
    def test_art5_has_ten_obligations(self):
        assert len(_obligations()) == 10

    @pytest.mark.parametrize("obl_id,source", [("ART05-PRO-1ba", "Art. 5(1)(ba)"), ("ART05-PRO-1bb", "Art. 5(1)(bb)")])
    def test_new_obligation_fields(self, obl_id, source):
        o = _obligations()[obl_id]
        assert o["source"] == source
        assert o["deontic_type"] == "prohibition"
        assert o["modality"] == "shall not"
        assert o["addressee"] == "any_person"
        assert o["applicable_from"] == "2026-12-02"
        assert o["automation_assessment"]["level"] == "partial"

    def test_atom_counts_match_consensus_lock(self):
        obls = _obligations()
        assert len(obls["ART05-PRO-1ba"]["decomposed_atoms"]) == 7
        assert len(obls["ART05-PRO-1bb"]["decomposed_atoms"]) == 6

    def test_manipulation_threshold_only_on_ncii(self):
        """Art. 5(1b) applies to point (ba) only."""
        obls = _obligations()
        ba_atoms = {a["atom"] for a in obls["ART05-PRO-1ba"]["decomposed_atoms"]}
        bb_atoms = {a["atom"] for a in obls["ART05-PRO-1bb"]["decomposed_atoms"]}
        assert "ncii_manipulation_threshold" in ba_atoms
        assert not any("manipulation_threshold" in a for a in bb_atoms)

    def test_safeguards_atom_requires_both_prevention_and_correction(self):
        """Consensus-lock D-3: lacking EITHER safeguard satisfies the foreseeable-outcome route."""
        for obl_id, atom_id in [("ART05-PRO-1ba", "ncii_market_trigger_inadequate_safeguards"),
                                ("ART05-PRO-1bb", "csam_market_trigger_inadequate_safeguards")]:
            atom = next(a for a in _obligations()[obl_id]["decomposed_atoms"] if a["atom"] == atom_id)
            assert "BOTH" in atom["requirement"]
            assert "lacking either one means the prohibition applies" in atom["requirement"]

    def test_amendment_recorded_in_metadata(self):
        with open(OBL_PATH, encoding="utf-8") as f:
            meta = json.load(f)["_metadata"]
        amendment = next(a for a in meta["amendments"] if a["amending_celex"] == "32026R1744")
        assert amendment["obligations_added"] == ["ART05-PRO-1ba", "ART05-PRO-1bb"]
        assert amendment["applicable_from"] == "2026-12-02"


# ── Answers template exposes the new fields ──────────────────────────────


@pytest.mark.parametrize("field,_obl_id", _NEW)
def test_new_fields_in_answers_template(field, _obl_id):
    assert field in _build_answers_template()["art5"]


# ── Before 2026-12-02: informational NOT_APPLICABLE ──────────────────────


class TestBeforeApplicableDate:
    @pytest.mark.parametrize("field,obl_id", _NEW)
    @pytest.mark.parametrize("answer", [True, False, None])
    def test_not_yet_applicable(self, field, obl_id, answer, art05_module, tmp_path, monkeypatch):
        answers = {**_clean_base(), field: answer}
        result = _scan(art05_module, tmp_path, monkeypatch, BEFORE, answers)
        f = _finding(result, obl_id)
        assert f.level == ComplianceLevel.NOT_APPLICABLE
        assert f.is_informational is True
        assert "applies from 2026-12-02" in f.description

    @pytest.mark.parametrize("field,obl_id", _NEW)
    def test_detection_before_date_states_future_violation(self, field, obl_id, art05_module, tmp_path, monkeypatch):
        result = _scan(art05_module, tmp_path, monkeypatch, BEFORE, {**_clean_base(), field: True})
        assert "would be NON_COMPLIANT" in _finding(result, obl_id).description

    @pytest.mark.parametrize("field,_obl_id", _NEW)
    def test_detection_before_date_does_not_change_overall(self, field, _obl_id, art05_module, tmp_path, monkeypatch):
        result = _scan(art05_module, tmp_path, monkeypatch, BEFORE, {**_clean_base(), field: True})
        assert result.overall_level == ComplianceLevel.COMPLIANT


# ── From 2026-12-02: normal prohibition semantics ────────────────────────


class TestFromApplicableDate:
    @pytest.mark.parametrize("today", [ON, AFTER])
    @pytest.mark.parametrize("field,obl_id", _NEW)
    def test_detected_is_non_compliant(self, field, obl_id, today, art05_module, tmp_path, monkeypatch):
        result = _scan(art05_module, tmp_path, monkeypatch, today, {**_clean_base(), field: True})
        f = _finding(result, obl_id)
        assert f.level == ComplianceLevel.NON_COMPLIANT
        assert not f.is_informational
        assert result.overall_level == ComplianceLevel.NON_COMPLIANT

    @pytest.mark.parametrize("field,obl_id", _NEW)
    def test_not_detected_is_compliant(self, field, obl_id, art05_module, tmp_path, monkeypatch):
        result = _scan(art05_module, tmp_path, monkeypatch, ON, {**_clean_base(), field: False})
        assert _finding(result, obl_id).level == ComplianceLevel.COMPLIANT

    @pytest.mark.parametrize("field,obl_id", _NEW)
    def test_unknown_is_unable_to_determine(self, field, obl_id, art05_module, tmp_path, monkeypatch):
        result = _scan(art05_module, tmp_path, monkeypatch, ON, _clean_base())
        f = _finding(result, obl_id)
        assert f.level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_unknown_new_fields_block_overall_compliant(self, art05_module, tmp_path, monkeypatch):
        """Handoff §0: after 2026-12-02 a clean base scan must NOT read as COMPLIANT
        while the NCII / CSAM questions are unanswered."""
        result = _scan(art05_module, tmp_path, monkeypatch, ON, _clean_base())
        assert result.overall_level != ComplianceLevel.COMPLIANT

    def test_all_ten_clean_is_compliant(self, art05_module, tmp_path, monkeypatch):
        answers = {**_clean_base(), "has_ncii_generation": False, "has_csam_generation": False}
        result = _scan(art05_module, tmp_path, monkeypatch, ON, answers)
        assert result.overall_level == ComplianceLevel.COMPLIANT
        pro = [f for f in result.findings if f.obligation_id.startswith("ART05-PRO-")]
        assert len(pro) == 10
        assert all(f.level == ComplianceLevel.COMPLIANT for f in pro)

    def test_findings_carry_source_quote(self, art05_module, tmp_path, monkeypatch):
        result = _scan(art05_module, tmp_path, monkeypatch, ON, {**_clean_base(), "has_ncii_generation": True})
        assert _finding(result, "ART05-PRO-1ba").source_quote == _obligations()["ART05-PRO-1ba"]["source_quote"]


def test_applicable_date_is_read_from_obligation_json(art05_module, tmp_path, monkeypatch):
    """The module must take the date from applicable_from, not a hard-coded constant."""
    mod_globals = type(art05_module).scan.__globals__
    real_load = type(art05_module)._load_obligations

    def shifted(self):
        data = real_load(self)
        for o in data["obligations"]:
            if o["id"] == "ART05-PRO-1ba":
                o["applicable_from"] = "2030-01-01"
        return data

    monkeypatch.setattr(type(art05_module), "_load_obligations", shifted)
    monkeypatch.setitem(mod_globals, "_today", lambda: AFTER)
    BaseArticleModule.set_context(_ctx_with("art5", {**_clean_base(), "has_ncii_generation": True}))
    result = art05_module.scan(str(tmp_path))
    f = _finding(result, "ART05-PRO-1ba")
    assert f.level == ComplianceLevel.NOT_APPLICABLE
    assert "applies from 2030-01-01" in f.description
