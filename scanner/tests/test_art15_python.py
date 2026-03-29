"""Art. 15 Accuracy, Robustness and Cybersecurity tests."""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


class TestArt15AccuracyRobustness:

    def test_accuracy_true_gives_partial(self, art15_module, tmp_path):
        ctx = _ctx_with("art15", {
            "has_accuracy_testing": True, "accuracy_evidence": ["eval.py"],
            "has_robustness_testing": True, "has_fallback_behavior": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art15_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART15-OBL-1"]
        assert obl1[0].level == ComplianceLevel.PARTIAL

    def test_accuracy_false_gives_non_compliant(self, art15_module, tmp_path):
        ctx = _ctx_with("art15", {
            "has_accuracy_testing": False, "has_robustness_testing": False,
            "has_fallback_behavior": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art15_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART15-OBL-1"]
        assert obl1[0].level == ComplianceLevel.NON_COMPLIANT

    def test_accuracy_null_gives_utd(self, art15_module, tmp_path):
        ctx = _ctx_with("art15", {
            "has_accuracy_testing": None, "has_robustness_testing": None,
            "has_fallback_behavior": None,
        })
        BaseArticleModule.set_context(ctx)
        result = art15_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART15-OBL-1"]
        assert obl1[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_robustness_true_gives_partial(self, art15_module, tmp_path):
        ctx = _ctx_with("art15", {
            "has_accuracy_testing": True, "has_robustness_testing": True,
            "robustness_evidence": ["error_handler.py"], "has_fallback_behavior": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art15_module.scan(str(tmp_path))
        obl4 = [f for f in result.findings if f.obligation_id == "ART15-OBL-4"]
        assert obl4[0].level == ComplianceLevel.PARTIAL

    def test_fallback_false_gives_non_compliant(self, art15_module, tmp_path):
        ctx = _ctx_with("art15", {
            "has_accuracy_testing": True, "has_robustness_testing": True,
            "has_fallback_behavior": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art15_module.scan(str(tmp_path))
        obl5 = [f for f in result.findings if f.obligation_id == "ART15-OBL-5"]
        assert obl5[0].level == ComplianceLevel.NON_COMPLIANT

    def test_obligation_coverage_total_8(self, art15_module, tmp_path):
        """Total must be 8 (7 original + ART15-PERM-4c added in cross-verification)."""
        result = art15_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations") == 8

    def test_all_8_obligations_in_json(self, art15_module):
        """JSON must have exactly 8 obligations (7 original + ART15-PERM-4c added in cross-verification)."""
        data = art15_module._load_obligations()
        assert len(data.get("obligations", [])) == 8
