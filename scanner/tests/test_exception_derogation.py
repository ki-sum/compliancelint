"""Tests for D1 — Exception derogation logic.

When a user attests an EXCEPTION obligation (deontic_type=exception) by
providing evidence, the scanner should mark every linked main obligation
as not_applicable on next re-scan.

Covered EXCs (6):
- ART14-EXC-5b     → ART14-OBL-5
- ART25-EXC-2      → ART25-OBL-4
- ART25-EXC-4      → ART25-OBL-4
- ART53-EXC-2      → ART53-OBL-1a, ART53-OBL-1b
- ART54-EXC-6      → ART54-OBL-1, -2, -3, -4, -5
- ART86-EXC-1      → ART86-OBL-1

ART06-EXC-3 intentionally excluded from D1 v1 — its blast radius covers
all of Chapter III Section 2 (~80+ obligations); better handled via
repo-level risk classification flag in a future iteration.
"""
import json
import os
import pathlib

import pytest

from core.state import save_article_result, update_finding, load_state
from core.config import ProjectConfig  # noqa: F401  (fixture side-effect)


# ═══════════════════════════════════════════════════════════════════════
# Data expectations (linked_obligation must exist in scanner obligations)
# ═══════════════════════════════════════════════════════════════════════

OBLIGATIONS_DIR = pathlib.Path(__file__).parent.parent / "obligations"

EXPECTED_DEROGATIONS = {
    "ART14-EXC-5b": ["ART14-OBL-5"],
    "ART25-EXC-2": ["ART25-OBL-4"],
    "ART25-EXC-4": ["ART25-OBL-4"],
    "ART53-EXC-2": ["ART53-OBL-1a", "ART53-OBL-1b"],
    "ART54-EXC-6": ["ART54-OBL-1", "ART54-OBL-2", "ART54-OBL-3", "ART54-OBL-4", "ART54-OBL-5"],
    "ART86-EXC-1": ["ART86-OBL-1"],
}


def _load_all_obligations():
    """Return flat map: obligation_id -> obligation dict."""
    out = {}
    for fp in OBLIGATIONS_DIR.glob("art*.json"):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for o in data.get("obligations", []):
            oid = o.get("id")
            if oid:
                out[oid] = o
    return out


class TestExceptionDerogationData:
    """Data integrity — the linked_obligation field is the contract between
    the legal decomposition and the runtime derogation logic."""

    def test_all_six_excs_have_linked_obligation(self):
        all_obls = _load_all_obligations()
        for exc_id in EXPECTED_DEROGATIONS:
            obl = all_obls.get(exc_id)
            assert obl is not None, f"EXC {exc_id} not found in scanner obligations"
            assert obl.get("deontic_type") == "exception", \
                f"{exc_id} deontic_type should be 'exception'"
            assert "linked_obligation" in obl, \
                f"{exc_id} missing linked_obligation field"
            assert isinstance(obl["linked_obligation"], list), \
                f"{exc_id}.linked_obligation must be a list"
            assert len(obl["linked_obligation"]) > 0, \
                f"{exc_id}.linked_obligation must be non-empty"

    def test_linked_obligation_targets_match_expected(self):
        all_obls = _load_all_obligations()
        for exc_id, expected_targets in EXPECTED_DEROGATIONS.items():
            obl = all_obls.get(exc_id, {})
            actual = obl.get("linked_obligation", [])
            assert sorted(actual) == sorted(expected_targets), \
                f"{exc_id}.linked_obligation mismatch: got {actual}, want {expected_targets}"

    def test_linked_obligation_targets_exist(self):
        all_obls = _load_all_obligations()
        for exc_id, targets in EXPECTED_DEROGATIONS.items():
            for t in targets:
                assert t in all_obls, \
                    f"{exc_id} links to {t} which does not exist as an obligation"

    def test_linked_obligation_targets_are_obligations(self):
        """Derogations should only point at actual obligations, not at
        permissions or other exceptions."""
        all_obls = _load_all_obligations()
        for exc_id, targets in EXPECTED_DEROGATIONS.items():
            for t in targets:
                deon = all_obls[t].get("deontic_type")
                assert deon == "obligation", \
                    f"{exc_id} links to {t} with deontic_type={deon}, expected 'obligation'"

    def test_art06_exc3_has_no_linked_obligation(self):
        """ART06-EXC-3 intentionally excluded from D1 v1 — it would derogate
        ~80+ obligations in Chapter III Section 2 and is better handled via
        the repo-level risk classification flag."""
        all_obls = _load_all_obligations()
        obl = all_obls.get("ART06-EXC-3")
        assert obl is not None, "ART06-EXC-3 must exist"
        linked = obl.get("linked_obligation")
        assert not linked, (
            "ART06-EXC-3 must NOT have linked_obligation in D1 v1. "
            "Its derogation scope (all of Chapter III Section 2) is better "
            "handled via repo-level risk classification flag."
        )


# ═══════════════════════════════════════════════════════════════════════
# Derogation runtime — attested EXC marks linked main obligations NA
# ═══════════════════════════════════════════════════════════════════════

ATTESTER = {"name": "QA", "email": "qa@co.com", "role": "QA", "source": "config"}


def _seed_project(tmp_path):
    """Set up project with attester config."""
    config = {"attester": {"name": "QA", "email": "qa@co.com", "role": "QA"}}
    (tmp_path / ".compliancelintrc").write_text(json.dumps(config), encoding="utf-8")
    return tmp_path


def _save_scan(tmp_path, article_num, findings_list):
    """Helper to save a scan result with given findings."""
    scan = {
        "overall_level": "partial",
        "overall_confidence": "medium",
        "assessed_by": "test",
        "findings": findings_list,
    }
    save_article_result(str(tmp_path), article_num, scan)


@pytest.fixture
def project_art53(tmp_path):
    """Art. 53 seeded: EXC-2 + OBL-1a + OBL-1b, all initially non_compliant."""
    _seed_project(tmp_path)
    _save_scan(tmp_path, 53, [
        {"obligation_id": "ART53-EXC-2", "level": "non_compliant",
         "description": "open-source exception not claimed", "source_quote": "EXC text"},
        {"obligation_id": "ART53-OBL-1a", "level": "non_compliant",
         "description": "Annex XI docs missing", "source_quote": "OBL-1a text"},
        {"obligation_id": "ART53-OBL-1b", "level": "non_compliant",
         "description": "downstream info missing", "source_quote": "OBL-1b text"},
    ])
    return tmp_path


class TestArt53Derogation:
    def test_attested_exc2_derogates_both_main_obls(self, project_art53):
        """ART53-EXC-2 attested → OBL-1a and OBL-1b become not_applicable."""
        update_finding(str(project_art53), "ART53-EXC-2",
                       "provide_evidence", "text",
                       "Model released under Apache-2.0 with public weights",
                       attester=ATTESTER)
        # Re-scan — scanner still reports main obligations as non_compliant
        _save_scan(project_art53, 53, [
            {"obligation_id": "ART53-EXC-2", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART53-OBL-1a", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART53-OBL-1b", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
        ])
        state = load_state(str(project_art53))
        findings = state["articles"]["art53"]["findings"]
        assert findings["ART53-OBL-1a"]["level"] == "not_applicable"
        assert findings["ART53-OBL-1b"]["level"] == "not_applicable"

    def test_unattested_exc2_leaves_main_obls_alone(self, project_art53):
        """ART53-EXC-2 NOT attested → main obligations stay non_compliant."""
        # Do not call update_finding on EXC-2
        _save_scan(project_art53, 53, [
            {"obligation_id": "ART53-EXC-2", "level": "non_compliant",
             "description": "no attestation", "source_quote": "Q"},
            {"obligation_id": "ART53-OBL-1a", "level": "non_compliant",
             "description": "NC", "source_quote": "Q"},
            {"obligation_id": "ART53-OBL-1b", "level": "non_compliant",
             "description": "NC", "source_quote": "Q"},
        ])
        state = load_state(str(project_art53))
        findings = state["articles"]["art53"]["findings"]
        assert findings["ART53-OBL-1a"]["level"] == "non_compliant"
        assert findings["ART53-OBL-1b"]["level"] == "non_compliant"

    def test_derogated_finding_records_derogation_source(self, project_art53):
        """Metadata trail — derogated findings must record WHICH EXC
        caused the derogation, for auditability."""
        update_finding(str(project_art53), "ART53-EXC-2",
                       "provide_evidence", "text",
                       "Apache-2.0 FOSS", attester=ATTESTER)
        _save_scan(project_art53, 53, [
            {"obligation_id": "ART53-EXC-2", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART53-OBL-1a", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART53-OBL-1b", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
        ])
        state = load_state(str(project_art53))
        obl1a = state["articles"]["art53"]["findings"]["ART53-OBL-1a"]
        assert obl1a.get("derogated_by") == ["ART53-EXC-2"], \
            f"Expected derogated_by=['ART53-EXC-2'], got {obl1a.get('derogated_by')}"


@pytest.fixture
def project_art14(tmp_path):
    _seed_project(tmp_path)
    _save_scan(tmp_path, 14, [
        {"obligation_id": "ART14-EXC-5b", "level": "non_compliant",
         "description": "law-enforcement exception not claimed", "source_quote": "Q"},
        {"obligation_id": "ART14-OBL-5", "level": "non_compliant",
         "description": "dual-verification missing", "source_quote": "Q"},
    ])
    return tmp_path


class TestArt14Derogation:
    def test_attested_exc5b_derogates_obl5(self, project_art14):
        update_finding(str(project_art14), "ART14-EXC-5b",
                       "provide_evidence", "text",
                       "System not used for law enforcement per national law",
                       attester=ATTESTER)
        _save_scan(project_art14, 14, [
            {"obligation_id": "ART14-EXC-5b", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART14-OBL-5", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
        ])
        state = load_state(str(project_art14))
        assert state["articles"]["art14"]["findings"]["ART14-OBL-5"]["level"] == "not_applicable"

    def test_unattested_exc5b_leaves_obl5_alone(self, project_art14):
        _save_scan(project_art14, 14, [
            {"obligation_id": "ART14-EXC-5b", "level": "non_compliant",
             "description": "no attestation", "source_quote": "Q"},
            {"obligation_id": "ART14-OBL-5", "level": "non_compliant",
             "description": "NC", "source_quote": "Q"},
        ])
        state = load_state(str(project_art14))
        assert state["articles"]["art14"]["findings"]["ART14-OBL-5"]["level"] == "non_compliant"


@pytest.fixture
def project_art25(tmp_path):
    _seed_project(tmp_path)
    _save_scan(tmp_path, 25, [
        {"obligation_id": "ART25-EXC-2", "level": "non_compliant",
         "description": "initial-provider statement not provided", "source_quote": "Q"},
        {"obligation_id": "ART25-EXC-4", "level": "non_compliant",
         "description": "FOSS third-party exception not claimed", "source_quote": "Q"},
        {"obligation_id": "ART25-OBL-4", "level": "non_compliant",
         "description": "written agreement with third-party suppliers missing",
         "source_quote": "Q"},
    ])
    return tmp_path


class TestArt25Derogation:
    def test_attested_exc2_derogates_obl4(self, project_art25):
        update_finding(str(project_art25), "ART25-EXC-2",
                       "provide_evidence", "text",
                       "Initial provider statement recorded", attester=ATTESTER)
        _save_scan(project_art25, 25, [
            {"obligation_id": "ART25-EXC-2", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART25-EXC-4", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART25-OBL-4", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
        ])
        state = load_state(str(project_art25))
        assert state["articles"]["art25"]["findings"]["ART25-OBL-4"]["level"] == "not_applicable"

    def test_attested_exc4_also_derogates_obl4(self, project_art25):
        update_finding(str(project_art25), "ART25-EXC-4",
                       "provide_evidence", "text",
                       "Apache-2.0 licensed third-party component",
                       attester=ATTESTER)
        _save_scan(project_art25, 25, [
            {"obligation_id": "ART25-EXC-2", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART25-EXC-4", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART25-OBL-4", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
        ])
        state = load_state(str(project_art25))
        assert state["articles"]["art25"]["findings"]["ART25-OBL-4"]["level"] == "not_applicable"

    def test_both_exc2_and_exc4_attested_records_both_derogations(self, project_art25):
        """When two EXCs both derogate the same main obligation, both must
        appear in derogated_by — audit trail preserves every legal basis."""
        update_finding(str(project_art25), "ART25-EXC-2",
                       "provide_evidence", "text",
                       "Initial-provider statement", attester=ATTESTER)
        update_finding(str(project_art25), "ART25-EXC-4",
                       "provide_evidence", "text",
                       "FOSS component", attester=ATTESTER)
        _save_scan(project_art25, 25, [
            {"obligation_id": "ART25-EXC-2", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART25-EXC-4", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART25-OBL-4", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
        ])
        state = load_state(str(project_art25))
        obl4 = state["articles"]["art25"]["findings"]["ART25-OBL-4"]
        assert obl4["level"] == "not_applicable"
        assert sorted(obl4.get("derogated_by", [])) == ["ART25-EXC-2", "ART25-EXC-4"]


@pytest.fixture
def project_art54(tmp_path):
    _seed_project(tmp_path)
    _save_scan(tmp_path, 54, [
        {"obligation_id": "ART54-EXC-6", "level": "non_compliant",
         "description": "FOSS GPAI exception not claimed", "source_quote": "Q"},
        {"obligation_id": "ART54-OBL-1", "level": "non_compliant",
         "description": "AR not appointed", "source_quote": "Q"},
        {"obligation_id": "ART54-OBL-2", "level": "non_compliant",
         "description": "AR tasks missing", "source_quote": "Q"},
        {"obligation_id": "ART54-OBL-3", "level": "non_compliant",
         "description": "mandate task empowerment missing", "source_quote": "Q"},
        {"obligation_id": "ART54-OBL-4", "level": "non_compliant",
         "description": "mandate addressability missing", "source_quote": "Q"},
        {"obligation_id": "ART54-OBL-5", "level": "non_compliant",
         "description": "AR records missing", "source_quote": "Q"},
    ])
    return tmp_path


class TestArt54Derogation:
    def test_attested_exc6_derogates_all_five_main_obls(self, project_art54):
        update_finding(str(project_art54), "ART54-EXC-6",
                       "provide_evidence", "text",
                       "FOSS GPAI model with public weights, non-systemic risk",
                       attester=ATTESTER)
        _save_scan(project_art54, 54, [
            {"obligation_id": "ART54-EXC-6", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART54-OBL-1", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART54-OBL-2", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART54-OBL-3", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART54-OBL-4", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART54-OBL-5", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
        ])
        state = load_state(str(project_art54))
        findings = state["articles"]["art54"]["findings"]
        for oid in ["ART54-OBL-1", "ART54-OBL-2", "ART54-OBL-3",
                    "ART54-OBL-4", "ART54-OBL-5"]:
            assert findings[oid]["level"] == "not_applicable", \
                f"{oid} should be not_applicable after EXC-6 attestation"


@pytest.fixture
def project_art86(tmp_path):
    _seed_project(tmp_path)
    _save_scan(tmp_path, 86, [
        {"obligation_id": "ART86-EXC-1", "level": "non_compliant",
         "description": "national-law exception not claimed", "source_quote": "Q"},
        {"obligation_id": "ART86-OBL-1", "level": "non_compliant",
         "description": "explanation mechanism missing", "source_quote": "Q"},
    ])
    return tmp_path


class TestArt86Derogation:
    def test_attested_exc1_derogates_obl1(self, project_art86):
        update_finding(str(project_art86), "ART86-EXC-1",
                       "provide_evidence", "text",
                       "National criminal-procedure law explicitly restricts right to explanation",
                       attester=ATTESTER)
        _save_scan(project_art86, 86, [
            {"obligation_id": "ART86-EXC-1", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
            {"obligation_id": "ART86-OBL-1", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
        ])
        state = load_state(str(project_art86))
        assert state["articles"]["art86"]["findings"]["ART86-OBL-1"]["level"] == "not_applicable"


# ═══════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════

class TestExceptionDerogationEdgeCases:
    def test_exc_without_main_finding_does_not_crash(self, tmp_path):
        """If a user attests EXC but the linked main obligation has no
        finding yet (different article not yet scanned), no crash."""
        _seed_project(tmp_path)
        # Seed ART53 scan with ONLY the EXC finding — no OBL-1a/1b findings
        _save_scan(tmp_path, 53, [
            {"obligation_id": "ART53-EXC-2", "level": "non_compliant",
             "description": "orphan EXC", "source_quote": "Q"},
        ])
        update_finding(str(tmp_path), "ART53-EXC-2",
                       "provide_evidence", "text", "FOSS", attester=ATTESTER)
        _save_scan(tmp_path, 53, [
            {"obligation_id": "ART53-EXC-2", "level": "non_compliant",
             "description": "still NC", "source_quote": "Q"},
        ])
        state = load_state(str(tmp_path))
        # Must not crash; EXC finding remains
        assert "ART53-EXC-2" in state["articles"]["art53"]["findings"]

    def test_derogation_persists_across_multiple_rescans(self, project_art53):
        """Derogation must be stable: EXC attested once, main obligations
        stay not_applicable across any number of re-scans."""
        update_finding(str(project_art53), "ART53-EXC-2",
                       "provide_evidence", "text", "Apache-2.0",
                       attester=ATTESTER)
        for i in range(3):
            _save_scan(project_art53, 53, [
                {"obligation_id": "ART53-EXC-2", "level": "non_compliant",
                 "description": f"rescan {i}", "source_quote": "Q"},
                {"obligation_id": "ART53-OBL-1a", "level": "non_compliant",
                 "description": f"rescan {i}", "source_quote": "Q"},
                {"obligation_id": "ART53-OBL-1b", "level": "non_compliant",
                 "description": f"rescan {i}", "source_quote": "Q"},
            ])
            state = load_state(str(project_art53))
            findings = state["articles"]["art53"]["findings"]
            assert findings["ART53-OBL-1a"]["level"] == "not_applicable", \
                f"Rescan {i} broke derogation for OBL-1a"
            assert findings["ART53-OBL-1b"]["level"] == "not_applicable", \
                f"Rescan {i} broke derogation for OBL-1b"
