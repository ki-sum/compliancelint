"""Art. 18 Documentation keeping tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers -> Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_documentation_retention_policy -> ART18-OBL-1
  ART18-OBL-3                       -> context_skip_field: is_financial_institution (gap_findings)
"""
import pytest
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _load_module, _ctx_with


@pytest.fixture
def art18_module():
    return _load_module("art18-documentation-keeping")


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art18", {
        "has_documentation_retention_policy": True,
        "retention_policy_evidence": "docs/retention-policy.md specifies 10-year retention",
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art18", {
        "has_documentation_retention_policy": False,
        "retention_policy_evidence": "",
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art18", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART18-OBL-1: Documentation retention policy (has_documentation_retention_policy) ──

class TestArt18Obl1:

    def test_true_gives_partial(self, art18_module, tmp_path):
        """has_documentation_retention_policy=True -> ART18-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art18_module.scan(str(tmp_path))
        obl = _find(result, "ART18-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art18_module, tmp_path):
        """has_documentation_retention_policy=False -> ART18-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art18_module.scan(str(tmp_path))
        obl = _find(result, "ART18-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art18_module, tmp_path):
        """has_documentation_retention_policy=None -> ART18-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art18_module.scan(str(tmp_path))
        obl = _find(result, "ART18-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_true_includes_evidence(self, art18_module, tmp_path):
        """When True with evidence, the description should include it."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art18_module.scan(str(tmp_path))
        obl = _find(result, "ART18-OBL-1")
        assert len(obl) > 0
        assert "retention" in obl[0].description.lower()


# ── ART18-OBL-3: Financial institution (context_skip_field) ──

class TestArt18Obl3:

    def test_financial_institution_false_gives_not_applicable(self, art18_module, tmp_path):
        """is_financial_institution=False -> ART18-OBL-3 NOT_APPLICABLE via gap_findings."""
        from core.context import ProjectContext
        ctx = ProjectContext(
            primary_language="python",
            risk_classification="likely high-risk",
            compliance_answers={
                "art18": {"has_documentation_retention_policy": True},
                "_scope": {"is_financial_institution": False},
            },
        )
        BaseArticleModule.set_context(ctx)
        result = art18_module.scan(str(tmp_path))
        obl3 = _find(result, "ART18-OBL-3")
        assert len(obl3) > 0
        assert obl3[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_financial_institution_not_set_gives_gap(self, art18_module, tmp_path):
        """is_financial_institution not set -> ART18-OBL-3 appears as gap finding."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art18_module.scan(str(tmp_path))
        obl3 = _find(result, "ART18-OBL-3")
        # Should exist as a gap finding (either UTD or CONDITIONAL)
        assert len(obl3) > 0


# ── Structural tests ──

class TestArt18Structural:

    def test_obligation_json_has_2_obligations(self, art18_module):
        """Obligation JSON must have exactly 2 obligations."""
        data = art18_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 2

    def test_obligation_coverage_present(self, art18_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art18_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_obl1_utd(self, art18_module, tmp_path):
        """When AI provides no answers, ART18-OBL-1 -> UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art18_module.scan(str(tmp_path))
        obl = _find(result, "ART18-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_description_has_no_legal_citation_prefix(self, art18_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art18_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art18_module, tmp_path):
        """All-true answers -> no NON_COMPLIANT findings for covered obligations."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art18_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
            and f.obligation_id == "ART18-OBL-1"
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art18_module, tmp_path):
        """All-false answers -> at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art18_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0


# ── High-risk gate test ──

class TestArt18HighRiskGate:

    def test_not_high_risk_returns_not_applicable(self, art18_module, tmp_path):
        """Not-high-risk classification -> NOT_APPLICABLE."""
        from core.context import ProjectContext
        ctx = ProjectContext(
            primary_language="python",
            risk_classification="not high-risk",
            risk_classification_confidence="high",
            compliance_answers={"art18": {}},
        )
        BaseArticleModule.set_context(ctx)
        result = art18_module.scan(str(tmp_path))
        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE
