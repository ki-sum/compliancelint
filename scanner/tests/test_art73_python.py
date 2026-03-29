"""Art. 73 Reporting of Serious Incidents tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_incident_reporting_procedure  → ART73-OBL-1
  has_reporting_timelines           → ART73-OBL-2
  has_expedited_reporting_procedure → ART73-OBL-3, ART73-OBL-4
  has_investigation_procedure       → ART73-OBL-5
  Permission (manual)               → ART73-PER-1
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art73", {
        "has_incident_reporting_procedure": True,
        "has_reporting_timelines": True,
        "has_expedited_reporting_procedure": True,
        "has_investigation_procedure": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art73", {
        "has_incident_reporting_procedure": False,
        "has_reporting_timelines": False,
        "has_expedited_reporting_procedure": False,
        "has_investigation_procedure": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art73", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART73-OBL-1: Incident reporting procedure ──

class TestArt73Obl1:

    def test_has_reporting_procedure_true_gives_partial(self, art73_module, tmp_path):
        """has_incident_reporting_procedure=True → ART73-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_reporting_procedure_false_gives_non_compliant(self, art73_module, tmp_path):
        """has_incident_reporting_procedure=False → ART73-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_reporting_procedure_none_gives_utd(self, art73_module, tmp_path):
        """has_incident_reporting_procedure=None → ART73-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART73-OBL-2: Reporting timelines (15-day deadline) ──

class TestArt73Obl2:

    def test_has_timelines_true_gives_partial(self, art73_module, tmp_path):
        """has_reporting_timelines=True → ART73-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_timelines_false_gives_non_compliant(self, art73_module, tmp_path):
        """has_reporting_timelines=False → ART73-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_timelines_none_gives_utd(self, art73_module, tmp_path):
        """has_reporting_timelines=None → ART73-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART73-OBL-3: Widespread infringement (2-day deadline) ──

class TestArt73Obl3:

    def test_has_expedited_true_gives_partial(self, art73_module, tmp_path):
        """has_expedited_reporting_procedure=True → ART73-OBL-3 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_expedited_false_gives_non_compliant(self, art73_module, tmp_path):
        """has_expedited_reporting_procedure=False → ART73-OBL-3 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_expedited_none_gives_utd(self, art73_module, tmp_path):
        """has_expedited_reporting_procedure=None → ART73-OBL-3 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART73-OBL-4: Death (10-day deadline) ──

class TestArt73Obl4:

    def test_has_expedited_true_gives_partial(self, art73_module, tmp_path):
        """has_expedited_reporting_procedure=True → ART73-OBL-4 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_expedited_false_gives_non_compliant(self, art73_module, tmp_path):
        """has_expedited_reporting_procedure=False → ART73-OBL-4 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_expedited_none_gives_utd(self, art73_module, tmp_path):
        """has_expedited_reporting_procedure=None → ART73-OBL-4 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART73-OBL-5: Investigation and corrective action ──

class TestArt73Obl5:

    def test_has_investigation_true_gives_partial(self, art73_module, tmp_path):
        """has_investigation_procedure=True → ART73-OBL-5 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_investigation_false_gives_non_compliant(self, art73_module, tmp_path):
        """has_investigation_procedure=False → ART73-OBL-5 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_investigation_none_gives_utd(self, art73_module, tmp_path):
        """has_investigation_procedure=None → ART73-OBL-5 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art73_module.scan(str(tmp_path))
        obl = _find(result, "ART73-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt73Structural:

    def test_all_6_obligation_ids_in_json(self, art73_module):
        """Obligation JSON must have exactly 6 obligations."""
        data = art73_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 6

    def test_obligation_coverage_present(self, art73_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art73_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_automatable_obligations_utd(self, art73_module, tmp_path):
        """When AI provides no answers, automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art73_module.scan(str(tmp_path))
        automatable_ids = ["ART73-OBL-1", "ART73-OBL-2", "ART73-OBL-3", "ART73-OBL-4", "ART73-OBL-5"]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art73_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 73(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art73_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art73_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art73_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art73_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art73_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_obligation_findings_present(self, art73_module, tmp_path):
        """All 5 automatable obligations must appear in findings.

        ART73-PER-1 is a permission (MAY) without scope_limitation — the obligation
        engine silently skips it per rule 2 (no finding generated for permissions).
        """
        BaseArticleModule.set_context(_full_true_ctx())
        result = art73_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART73-OBL-1", "ART73-OBL-2", "ART73-OBL-3", "ART73-OBL-4", "ART73-OBL-5"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"

    def test_per1_permission_not_in_findings(self, art73_module, tmp_path):
        """ART73-PER-1 (permission without scope_limitation) → no finding generated."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art73_module.scan(str(tmp_path))
        per1 = [f for f in result.findings if f.obligation_id == "ART73-PER-1"]
        assert len(per1) == 0, "PER-1 is a permission — should not generate a finding"
