"""Art. 6 Risk Classification tests — obligation mapping."""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


class TestArt6RiskClassification:

    # ── CLS-1: Annex I product ──

    def test_annex_i_product_detected(self, art06_module, tmp_path):
        """When AI detects Annex I product type, ART06-CLS-1 must be NON_COMPLIANT."""
        ctx = _ctx_with("art6", {
            "annex_iii_categories": [],
            "annex_i_product_type": "Medical device",
            "is_high_risk": None,
            "reasoning": "Project references medical device certification"
        })
        BaseArticleModule.set_context(ctx)
        result = art06_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART06-CLS-1"]
        assert any(f.level == ComplianceLevel.NON_COMPLIANT for f in obl1)

    # ── CLS-2: Annex III categories ──

    def test_annex_iii_detected_flags_high_risk(self, art06_module, tmp_path):
        """When AI detects Annex III categories, ART06-CLS-2 must be NON_COMPLIANT."""
        ctx = _ctx_with("art6", {
            "annex_iii_categories": ["Biometrics", "Employment"],
            "annex_i_product_type": None,
            "is_high_risk": True,
            "reasoning": "Project uses facial recognition for hiring decisions"
        })
        BaseArticleModule.set_context(ctx)
        result = art06_module.scan(str(tmp_path))
        obl2 = [f for f in result.findings if f.obligation_id == "ART06-CLS-2"]
        assert any(f.level == ComplianceLevel.NON_COMPLIANT for f in obl2)

    # ── No indicators ──

    def test_no_indicators_gives_unable_to_determine(self, art06_module, tmp_path):
        """When AI finds no high-risk indicators, CLS-1/CLS-2 are UNABLE_TO_DETERMINE."""
        ctx = _ctx_with("art6", {
            "annex_iii_categories": [],
            "annex_i_product_type": None,
            "is_high_risk": False,
            "reasoning": "No regulated use-cases detected"
        })
        BaseArticleModule.set_context(ctx)
        result = art06_module.scan(str(tmp_path))
        obl = [f for f in result.findings if f.obligation_id in ("ART06-CLS-1", "ART06-CLS-2")]
        assert all(f.level == ComplianceLevel.UNABLE_TO_DETERMINE for f in obl)

    # ── OBL-4: Provider documentation (uses _finding_from_answer) ──

    def test_obl4_has_doc_true_compliant(self, art06_module, tmp_path):
        """When has_risk_classification_doc=True, OBL-4 should be PARTIAL/COMPLIANT."""
        ctx = _ctx_with("art6", {"has_risk_classification_doc": True})
        BaseArticleModule.set_context(ctx)
        result = art06_module.scan(str(tmp_path))
        obl4 = [f for f in result.findings if f.obligation_id == "ART06-OBL-4"]
        assert len(obl4) > 0
        assert obl4[0].level in (ComplianceLevel.PARTIAL, ComplianceLevel.COMPLIANT)

    def test_obl4_has_doc_false_non_compliant(self, art06_module, tmp_path):
        """When has_risk_classification_doc=False, OBL-4 should be NON_COMPLIANT."""
        ctx = _ctx_with("art6", {"has_risk_classification_doc": False})
        BaseArticleModule.set_context(ctx)
        result = art06_module.scan(str(tmp_path))
        obl4 = [f for f in result.findings if f.obligation_id == "ART06-OBL-4"]
        assert len(obl4) > 0
        assert obl4[0].level == ComplianceLevel.NON_COMPLIANT

    def test_obl4_has_doc_none_utd(self, art06_module, tmp_path):
        """When has_risk_classification_doc not provided, OBL-4 should be UTD."""
        ctx = _ctx_with("art6", {})
        BaseArticleModule.set_context(ctx)
        result = art06_module.scan(str(tmp_path))
        obl4 = [f for f in result.findings if f.obligation_id == "ART06-OBL-4"]
        assert len(obl4) > 0
        assert obl4[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    # ── General ──

    def test_obligation_coverage_present(self, art06_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art06_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0
