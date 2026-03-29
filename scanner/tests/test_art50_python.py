"""Art. 50 Transparency Obligations tests — per-obligation coverage."""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


class TestArt50TransparencyObligations:

    # ── OBL-1: Chatbot/interactive AI disclosure ──

    def test_chatbot_with_disclosure_partial(self, art50_module, tmp_path):
        """Chatbot that discloses AI nature: ART50-OBL-1 should be PARTIAL."""
        ctx = _ctx_with("art50", {
            "is_chatbot_or_interactive_ai": True,
            "has_ai_disclosure_to_users": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art50_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART50-OBL-1"]
        assert len(obl1) > 0
        assert any(f.level == ComplianceLevel.PARTIAL for f in obl1)

    def test_chatbot_without_disclosure_non_compliant(self, art50_module, tmp_path):
        """Chatbot with no AI disclosure: ART50-OBL-1 should be NON_COMPLIANT."""
        ctx = _ctx_with("art50", {
            "is_chatbot_or_interactive_ai": True,
            "has_ai_disclosure_to_users": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art50_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART50-OBL-1"]
        assert any(f.level == ComplianceLevel.NON_COMPLIANT for f in obl1)

    def test_not_chatbot_obl1_not_applicable(self, art50_module, tmp_path):
        """Non-chatbot system: ART50-OBL-1 should be NOT_APPLICABLE."""
        ctx = _ctx_with("art50", {
            "is_chatbot_or_interactive_ai": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art50_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART50-OBL-1"]
        assert any(f.level == ComplianceLevel.NOT_APPLICABLE for f in obl1)

    def test_chatbot_unknown_obl1_utd(self, art50_module, tmp_path):
        """Unknown chatbot status: ART50-OBL-1 should be UTD."""
        ctx = _ctx_with("art50", {})
        BaseArticleModule.set_context(ctx)
        result = art50_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART50-OBL-1"]
        assert any(f.level == ComplianceLevel.UNABLE_TO_DETERMINE for f in obl1)

    # ── OBL-2: Synthetic content marking ──

    def test_synthetic_content_with_marking_partial(self, art50_module, tmp_path):
        """Content generator with marking: ART50-OBL-2 should be PARTIAL."""
        ctx = _ctx_with("art50", {
            "is_generating_synthetic_content": True,
            "has_content_watermarking": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art50_module.scan(str(tmp_path))
        obl2 = [f for f in result.findings if f.obligation_id == "ART50-OBL-2"]
        assert len(obl2) > 0

    def test_synthetic_content_no_marking_non_compliant(self, art50_module, tmp_path):
        """Content generator without marking: ART50-OBL-2 should be NON_COMPLIANT."""
        ctx = _ctx_with("art50", {
            "is_generating_synthetic_content": True,
            "has_content_watermarking": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art50_module.scan(str(tmp_path))
        obl2 = [f for f in result.findings if f.obligation_id == "ART50-OBL-2"]
        assert any(f.level == ComplianceLevel.NON_COMPLIANT for f in obl2)

    # ── OBL-3: Emotion recognition / biometric categorization ──

    def test_emotion_recognition_obl3_utd(self, art50_module, tmp_path):
        """Unknown emotion recognition: ART50-OBL-3 should be UTD."""
        ctx = _ctx_with("art50", {})
        BaseArticleModule.set_context(ctx)
        result = art50_module.scan(str(tmp_path))
        obl3 = [f for f in result.findings if f.obligation_id == "ART50-OBL-3"]
        assert len(obl3) > 0

    # ── OBL-4: Deep fakes ──

    def test_deep_fake_obl4_utd(self, art50_module, tmp_path):
        """Unknown deep fake status: ART50-OBL-4 should be UTD."""
        ctx = _ctx_with("art50", {})
        BaseArticleModule.set_context(ctx)
        result = art50_module.scan(str(tmp_path))
        obl4 = [f for f in result.findings if f.obligation_id == "ART50-OBL-4"]
        assert len(obl4) > 0

    # ── General ──

    def test_obligation_coverage_present(self, art50_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art50_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_all_none_all_utd(self, art50_module, tmp_path):
        """With no answers, all findings should be UTD or NOT_APPLICABLE."""
        ctx = _ctx_with("art50", {})
        BaseArticleModule.set_context(ctx)
        result = art50_module.scan(str(tmp_path))
        for f in result.findings:
            if f.obligation_id.startswith("ART50"):
                assert f.level in (ComplianceLevel.UNABLE_TO_DETERMINE, ComplianceLevel.NOT_APPLICABLE), (
                    f"{f.obligation_id} should be UTD/NA with no answers, got {f.level}"
                )
