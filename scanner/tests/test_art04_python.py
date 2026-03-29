"""Art. 4 AI Literacy tests — obligation mapping."""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


class TestArt04AILiteracy:

    def test_literacy_present_gives_partial(self, art04_module, tmp_path):
        """has_ai_literacy_measures=True → ART04-OBL-1 PARTIAL."""
        ctx = _ctx_with("art4", {
            "has_ai_literacy_measures": True,
            "literacy_description": "AI usage policy in docs/ai-policy.md",
            "literacy_evidence": ["docs/ai-policy.md"],
        })
        BaseArticleModule.set_context(ctx)
        result = art04_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART04-OBL-1"]
        assert len(obl1) == 1
        assert obl1[0].level == ComplianceLevel.PARTIAL

    def test_no_literacy_gives_non_compliant(self, art04_module, tmp_path):
        """has_ai_literacy_measures=False → ART04-OBL-1 NON_COMPLIANT."""
        ctx = _ctx_with("art4", {
            "has_ai_literacy_measures": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art04_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART04-OBL-1"]
        assert len(obl1) == 1
        assert obl1[0].level == ComplianceLevel.NON_COMPLIANT

    def test_literacy_null_gives_utd(self, art04_module, tmp_path):
        """has_ai_literacy_measures=None → ART04-OBL-1 UNABLE_TO_DETERMINE."""
        ctx = _ctx_with("art4", {"has_ai_literacy_measures": None})
        BaseArticleModule.set_context(ctx)
        result = art04_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART04-OBL-1"]
        assert len(obl1) == 1
        assert obl1[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_description_included_when_present(self, art04_module, tmp_path):
        """literacy_description should appear in finding description."""
        ctx = _ctx_with("art4", {
            "has_ai_literacy_measures": True,
            "literacy_description": "Staff AI training program documented",
        })
        BaseArticleModule.set_context(ctx)
        result = art04_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART04-OBL-1"]
        assert "Staff AI training program documented" in obl1[0].description

    def test_obligation_coverage_present(self, art04_module, tmp_path):
        """ScanResult must include obligation_coverage with total=1."""
        result = art04_module.scan(str(tmp_path))
        cov = result.details.get("obligation_coverage", {})
        assert cov.get("total_obligations", 0) == 1

    def test_all_1_obligation_ids_in_json(self, art04_module):
        """Obligation JSON must have exactly 1 obligation."""
        data = art04_module._load_obligations()
        assert len(data.get("obligations", [])) == 1

    def test_not_high_risk_still_scans(self, art04_module, tmp_path):
        """Art. 4 applies to ALL AI systems, not just high-risk."""
        from core.context import ProjectContext
        ctx = ProjectContext(
            primary_language="python",
            risk_classification="not high-risk",
            risk_classification_confidence="high",
            compliance_answers={
                "art4": {"has_ai_literacy_measures": True, "literacy_description": "AI policy"},
            },
        )
        BaseArticleModule.set_context(ctx)
        result = art04_module.scan(str(tmp_path))
        # Should NOT be not_applicable — Art. 4 applies to all AI systems
        assert result.overall_level != ComplianceLevel.NOT_APPLICABLE

    def test_explain_returns_article_4(self, art04_module):
        """explain() returns article_number=4."""
        explanation = art04_module.explain()
        assert explanation.article_number == 4
        assert explanation.article_title == "AI Literacy"

    def test_action_plan_when_no_measures(self, art04_module, tmp_path):
        """action_plan() should include HIGH priority when no measures found."""
        ctx = _ctx_with("art4", {"has_ai_literacy_measures": False})
        BaseArticleModule.set_context(ctx)
        result = art04_module.scan(str(tmp_path))
        plan = art04_module.action_plan(result)
        assert any(a.priority == "HIGH" for a in plan.actions)

    def test_empty_answers_gives_utd(self, art04_module, tmp_path):
        """Empty art4 answers → UTD (no answers = AI could not determine)."""
        ctx = _ctx_with("art4", {})
        BaseArticleModule.set_context(ctx)
        result = art04_module.scan(str(tmp_path))
        obl1 = [f for f in result.findings if f.obligation_id == "ART04-OBL-1"]
        assert obl1[0].level == ComplianceLevel.UNABLE_TO_DETERMINE
