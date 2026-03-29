"""Art. 13 Transparency tests -- obligation mapping."""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


class TestArt13Transparency:

    def test_explainability_true_gives_partial(self, art13_module, tmp_path):
        """has_explainability=True -> ART13-OBL-1 PARTIAL."""
        ctx = _ctx_with("art13", {
            "has_explainability": True,
            "explainability_evidence": ["SHAP in model_explain.py"],
            "has_transparency_info": True,
            "transparency_paths": ["docs/model_card.md"],
        })
        BaseArticleModule.set_context(ctx)
        result = art13_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART13-OBL-1"]
        assert obl1[0].level == ComplianceLevel.PARTIAL

    def test_explainability_false_gives_non_compliant(self, art13_module, tmp_path):
        """has_explainability=False -> ART13-OBL-1 NON_COMPLIANT."""
        ctx = _ctx_with("art13", {
            "has_explainability": False,
            "has_transparency_info": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art13_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART13-OBL-1"]
        assert obl1[0].level == ComplianceLevel.NON_COMPLIANT

    def test_explainability_null_gives_utd(self, art13_module, tmp_path):
        """has_explainability=None -> ART13-OBL-1 UTD."""
        ctx = _ctx_with("art13", {
            "has_explainability": None,
            "has_transparency_info": None,
        })
        BaseArticleModule.set_context(ctx)
        result = art13_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART13-OBL-1"]
        assert obl1[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_transparency_info_true_gives_partial(self, art13_module, tmp_path):
        """has_transparency_info=True -> ART13-OBL-2 PARTIAL."""
        ctx = _ctx_with("art13", {
            "has_explainability": True,
            "has_transparency_info": True,
            "transparency_paths": ["docs/user_guide.md"],
        })
        BaseArticleModule.set_context(ctx)
        result = art13_module.scan(str(tmp_path))
        obl2 = [f for f in result.findings if f.obligation_id == "ART13-OBL-2"]
        assert obl2[0].level == ComplianceLevel.PARTIAL

    def test_transparency_info_false_gives_non_compliant(self, art13_module, tmp_path):
        """has_transparency_info=False -> ART13-OBL-2 NON_COMPLIANT."""
        ctx = _ctx_with("art13", {
            "has_explainability": True,
            "has_transparency_info": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art13_module.scan(str(tmp_path))
        obl2 = [f for f in result.findings if f.obligation_id == "ART13-OBL-2"]
        assert obl2[0].level == ComplianceLevel.NON_COMPLIANT

    def test_obl3_always_utd(self, art13_module, tmp_path):
        """ART13-OBL-3 (content checklist) always UTD."""
        ctx = _ctx_with("art13", {
            "has_explainability": True,
            "has_transparency_info": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art13_module.scan(str(tmp_path))
        obl3 = [f for f in result.findings if f.obligation_id == "ART13-OBL-3"]
        assert obl3[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_obligation_coverage_total_4(self, art13_module, tmp_path):
        """Total obligations must be 4 (3 original + ART13-OBL-1b added in cross-verification)."""
        result = art13_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations") == 4

    def test_all_4_obligation_ids_in_json(self, art13_module):
        """JSON must have exactly 4 obligations (3 original + ART13-OBL-1b added in cross-verification)."""
        data = art13_module._load_obligations()
        assert len(data.get("obligations", [])) == 4
