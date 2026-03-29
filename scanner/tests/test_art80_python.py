"""Art. 80 Non-high-risk misclassification procedure tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_compliance_remediation_plan       → ART80-OBL-4
  has_corrective_action_for_all_systems → ART80-OBL-5
  has_classification_rationale          → ART80-OBL-7
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art80", {
        "has_compliance_remediation_plan": True,
        "has_corrective_action_for_all_systems": True,
        "has_classification_rationale": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art80", {
        "has_compliance_remediation_plan": False,
        "has_corrective_action_for_all_systems": False,
        "has_classification_rationale": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art80", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART80-OBL-4: Compliance remediation plan ──

class TestArt80Obl4:

    def test_has_remediation_plan_true_gives_partial(self, art80_module, tmp_path):
        """has_compliance_remediation_plan=True → ART80-OBL-4 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art80_module.scan(str(tmp_path))
        obl = _find(result, "ART80-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_remediation_plan_false_gives_non_compliant(self, art80_module, tmp_path):
        """has_compliance_remediation_plan=False → ART80-OBL-4 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art80_module.scan(str(tmp_path))
        obl = _find(result, "ART80-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_remediation_plan_none_gives_utd(self, art80_module, tmp_path):
        """has_compliance_remediation_plan=None → ART80-OBL-4 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art80_module.scan(str(tmp_path))
        obl = _find(result, "ART80-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART80-OBL-5: Corrective action for all affected systems ──

class TestArt80Obl5:

    def test_has_corrective_action_true_gives_partial(self, art80_module, tmp_path):
        """has_corrective_action_for_all_systems=True → ART80-OBL-5 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art80_module.scan(str(tmp_path))
        obl = _find(result, "ART80-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_corrective_action_false_gives_non_compliant(self, art80_module, tmp_path):
        """has_corrective_action_for_all_systems=False → ART80-OBL-5 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art80_module.scan(str(tmp_path))
        obl = _find(result, "ART80-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_corrective_action_none_gives_utd(self, art80_module, tmp_path):
        """has_corrective_action_for_all_systems=None → ART80-OBL-5 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art80_module.scan(str(tmp_path))
        obl = _find(result, "ART80-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART80-OBL-7: Classification rationale (anti-circumvention) ──

class TestArt80Obl7:

    def test_has_classification_rationale_true_gives_partial(self, art80_module, tmp_path):
        """has_classification_rationale=True → ART80-OBL-7 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art80_module.scan(str(tmp_path))
        obl = _find(result, "ART80-OBL-7")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_classification_rationale_false_gives_non_compliant(self, art80_module, tmp_path):
        """has_classification_rationale=False → ART80-OBL-7 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art80_module.scan(str(tmp_path))
        obl = _find(result, "ART80-OBL-7")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_classification_rationale_none_gives_utd(self, art80_module, tmp_path):
        """has_classification_rationale=None → ART80-OBL-7 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art80_module.scan(str(tmp_path))
        obl = _find(result, "ART80-OBL-7")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt80Structural:

    def test_all_3_obligation_ids_in_json(self, art80_module):
        """Obligation JSON must have exactly 3 obligations."""
        data = art80_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 3

    def test_obligation_coverage_present(self, art80_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art80_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_automatable_obligations_utd(self, art80_module, tmp_path):
        """When AI provides no answers, automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art80_module.scan(str(tmp_path))
        automatable_ids = ["ART80-OBL-4", "ART80-OBL-5", "ART80-OBL-7"]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art80_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 80(4)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art80_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art80_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art80_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art80_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art80_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_obligation_findings_present(self, art80_module, tmp_path):
        """All 3 obligations must appear in findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art80_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART80-OBL-4", "ART80-OBL-5", "ART80-OBL-7"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"
