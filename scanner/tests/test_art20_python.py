"""Art. 20 Corrective actions and duty of information tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_corrective_action_procedure   → ART20-OBL-1
  has_supply_chain_notification     → ART20-OBL-1b
  has_risk_investigation_procedure  → ART20-OBL-2
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art20", {
        "has_corrective_action_procedure": True,
        "has_supply_chain_notification": True,
        "has_risk_investigation_procedure": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art20", {
        "has_corrective_action_procedure": False,
        "has_supply_chain_notification": False,
        "has_risk_investigation_procedure": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art20", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART20-OBL-1: Corrective action procedure ──

class TestArt20Obl1:

    def test_has_corrective_action_true_gives_partial(self, art20_module, tmp_path):
        """has_corrective_action_procedure=True → ART20-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art20_module.scan(str(tmp_path))
        obl = _find(result, "ART20-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_corrective_action_false_gives_non_compliant(self, art20_module, tmp_path):
        """has_corrective_action_procedure=False → ART20-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art20_module.scan(str(tmp_path))
        obl = _find(result, "ART20-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_corrective_action_none_gives_utd(self, art20_module, tmp_path):
        """has_corrective_action_procedure=None → ART20-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art20_module.scan(str(tmp_path))
        obl = _find(result, "ART20-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART20-OBL-1b: Supply chain notification ──

class TestArt20Obl1b:

    def test_has_notification_true_gives_partial(self, art20_module, tmp_path):
        """has_supply_chain_notification=True → ART20-OBL-1b PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art20_module.scan(str(tmp_path))
        obl = _find(result, "ART20-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_notification_false_gives_non_compliant(self, art20_module, tmp_path):
        """has_supply_chain_notification=False → ART20-OBL-1b NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art20_module.scan(str(tmp_path))
        obl = _find(result, "ART20-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_notification_none_gives_utd(self, art20_module, tmp_path):
        """has_supply_chain_notification=None → ART20-OBL-1b UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art20_module.scan(str(tmp_path))
        obl = _find(result, "ART20-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART20-OBL-2: Risk investigation and authority notification ──

class TestArt20Obl2:

    def test_has_investigation_true_gives_partial(self, art20_module, tmp_path):
        """has_risk_investigation_procedure=True → ART20-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art20_module.scan(str(tmp_path))
        obl = _find(result, "ART20-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_investigation_false_gives_non_compliant(self, art20_module, tmp_path):
        """has_risk_investigation_procedure=False → ART20-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art20_module.scan(str(tmp_path))
        obl = _find(result, "ART20-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_investigation_none_gives_utd(self, art20_module, tmp_path):
        """has_risk_investigation_procedure=None → ART20-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art20_module.scan(str(tmp_path))
        obl = _find(result, "ART20-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt20Structural:

    def test_all_3_obligation_ids_in_json(self, art20_module):
        """Obligation JSON must have exactly 3 obligations."""
        data = art20_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 3

    def test_obligation_coverage_present(self, art20_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art20_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_automatable_obligations_utd(self, art20_module, tmp_path):
        """When AI provides no answers, automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art20_module.scan(str(tmp_path))
        automatable_ids = ["ART20-OBL-1", "ART20-OBL-1b", "ART20-OBL-2"]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art20_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 20(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art20_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art20_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art20_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art20_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art20_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_obligation_findings_present(self, art20_module, tmp_path):
        """All 3 obligations must appear in findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art20_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART20-OBL-1", "ART20-OBL-1b", "ART20-OBL-2"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"
