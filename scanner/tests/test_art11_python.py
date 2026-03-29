"""Art. 11 Technical Documentation tests — obligation mapping."""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


class TestArt11TechnicalDocumentation:

    def test_docs_present_gives_partial(self, art11_module, tmp_path):
        """has_technical_docs=True → ART11-OBL-1 PARTIAL."""
        ctx = _ctx_with("art11", {
            "has_technical_docs": True,
            "doc_paths": ["docs/architecture.md", "README.md"],
            "documented_aspects": ["architecture", "training", "testing"],
        })
        BaseArticleModule.set_context(ctx)
        result = art11_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART11-OBL-1"]
        assert obl1[0].level == ComplianceLevel.PARTIAL

    def test_no_docs_gives_non_compliant(self, art11_module, tmp_path):
        """has_technical_docs=False → ART11-OBL-1 NON_COMPLIANT."""
        ctx = _ctx_with("art11", {
            "has_technical_docs": False,
            "doc_paths": [],
            "documented_aspects": [],
        })
        BaseArticleModule.set_context(ctx)
        result = art11_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART11-OBL-1"]
        assert obl1[0].level == ComplianceLevel.NON_COMPLIANT

    def test_docs_null_gives_utd(self, art11_module, tmp_path):
        """has_technical_docs=None → ART11-OBL-1 UNABLE_TO_DETERMINE."""
        ctx = _ctx_with("art11", {"has_technical_docs": None})
        BaseArticleModule.set_context(ctx)
        result = art11_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART11-OBL-1"]
        assert obl1[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_annex_iv_always_utd(self, art11_module, tmp_path):
        """ART11-OBL-1c (Annex IV coverage) always UTD."""
        ctx = _ctx_with("art11", {
            "has_technical_docs": True,
            "doc_paths": ["README.md"],
        })
        BaseArticleModule.set_context(ctx)
        result = art11_module.scan(str(tmp_path))
        obl1c = [f for f in result.findings if f.obligation_id == "ART11-OBL-1c"]
        assert obl1c[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_obligation_coverage_present(self, art11_module, tmp_path):
        """ScanResult must include obligation_coverage with total=9 (5 original + 4 SME provisions added in cross-verification)."""
        result = art11_module.scan(str(tmp_path))
        cov = result.details.get("obligation_coverage", {})
        assert cov.get("total_obligations", 0) == 9

    def test_all_9_obligation_ids_in_json(self, art11_module):
        """Obligation JSON must have exactly 9 obligations (5 original + 4 SME provisions added in cross-verification)."""
        data = art11_module._load_obligations()
        assert len(data.get("obligations", [])) == 9
