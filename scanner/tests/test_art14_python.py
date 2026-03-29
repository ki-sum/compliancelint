"""Art. 14 Human Oversight tests -- obligation mapping."""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


class TestArt14HumanOversight:

    def test_oversight_true_gives_partial(self, art14_module, tmp_path):
        """has_human_oversight=True -> ART14-OBL-1 PARTIAL."""
        ctx = _ctx_with("art14", {
            "has_human_oversight": True,
            "oversight_evidence": ["Review gate in pipeline.py"],
            "has_override_mechanism": True,
            "override_evidence": ["/api/stop endpoint"],
        })
        BaseArticleModule.set_context(ctx)
        result = art14_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART14-OBL-1"]
        assert obl1[0].level == ComplianceLevel.PARTIAL

    def test_oversight_false_gives_non_compliant(self, art14_module, tmp_path):
        """has_human_oversight=False -> ART14-OBL-1 NON_COMPLIANT."""
        ctx = _ctx_with("art14", {
            "has_human_oversight": False,
            "has_override_mechanism": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art14_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART14-OBL-1"]
        assert obl1[0].level == ComplianceLevel.NON_COMPLIANT

    def test_oversight_null_gives_utd(self, art14_module, tmp_path):
        """has_human_oversight=None -> ART14-OBL-1 UTD."""
        ctx = _ctx_with("art14", {
            "has_human_oversight": None,
            "has_override_mechanism": None,
        })
        BaseArticleModule.set_context(ctx)
        result = art14_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART14-OBL-1"]
        assert obl1[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_override_true_gives_partial(self, art14_module, tmp_path):
        """has_override_mechanism=True -> ART14-OBL-3 PARTIAL."""
        ctx = _ctx_with("art14", {
            "has_human_oversight": True,
            "has_override_mechanism": True,
            "override_evidence": ["stop button"],
        })
        BaseArticleModule.set_context(ctx)
        result = art14_module.scan(str(tmp_path))
        obl3 = [f for f in result.findings if f.obligation_id == "ART14-OBL-3"]
        assert obl3[0].level == ComplianceLevel.PARTIAL

    def test_override_false_gives_non_compliant(self, art14_module, tmp_path):
        """has_override_mechanism=False -> ART14-OBL-3 NON_COMPLIANT."""
        ctx = _ctx_with("art14", {
            "has_human_oversight": True,
            "has_override_mechanism": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art14_module.scan(str(tmp_path))
        obl3 = [f for f in result.findings if f.obligation_id == "ART14-OBL-3"]
        assert obl3[0].level == ComplianceLevel.NON_COMPLIANT

    def test_obl2_always_utd(self, art14_module, tmp_path):
        """ART14-OBL-2 (risk prevention aim) always UTD."""
        ctx = _ctx_with("art14", {
            "has_human_oversight": True,
            "has_override_mechanism": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art14_module.scan(str(tmp_path))
        obl2 = [f for f in result.findings if f.obligation_id == "ART14-OBL-2"]
        assert obl2[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_obligation_coverage_total_6(self, art14_module, tmp_path):
        """Total obligations must be 6 (5 original + ART14-EXC-5b added in cross-verification)."""
        result = art14_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations") == 6

    def test_all_6_obligation_ids_in_json(self, art14_module):
        """JSON must have exactly 6 obligations (5 original + ART14-EXC-5b added in cross-verification)."""
        data = art14_module._load_obligations()
        assert len(data.get("obligations", [])) == 6
