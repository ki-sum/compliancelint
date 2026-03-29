"""Art. 16 Obligations of providers of high-risk AI systems tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers -> Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_section_2_compliance       -> ART16-OBL-1a
  has_provider_identification    -> ART16-OBL-1b
  has_qms                        -> ART16-OBL-1c
  has_documentation_kept         -> ART16-OBL-1d
  has_log_retention              -> ART16-OBL-1e
  has_conformity_assessment      -> ART16-OBL-1f
  has_eu_declaration             -> ART16-OBL-1g
  has_ce_marking                 -> ART16-OBL-1h
  has_registration               -> ART16-OBL-1i
  has_corrective_actions_process -> ART16-OBL-1j
  has_conformity_evidence        -> ART16-OBL-1k
  has_accessibility_compliance   -> ART16-OBL-1l
"""
import pytest
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _load_module, _ctx_with


@pytest.fixture
def art16_module():
    return _load_module("art16-provider-obligations")


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art16", {
        "has_section_2_compliance": True,
        "has_provider_identification": True,
        "has_qms": True,
        "has_documentation_kept": True,
        "has_log_retention": True,
        "has_conformity_assessment": True,
        "has_eu_declaration": True,
        "has_ce_marking": True,
        "has_registration": True,
        "has_corrective_actions_process": True,
        "has_conformity_evidence": True,
        "has_accessibility_compliance": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art16", {
        "has_section_2_compliance": False,
        "has_provider_identification": False,
        "has_qms": False,
        "has_documentation_kept": False,
        "has_log_retention": False,
        "has_conformity_assessment": False,
        "has_eu_declaration": False,
        "has_ce_marking": False,
        "has_registration": False,
        "has_corrective_actions_process": False,
        "has_conformity_evidence": False,
        "has_accessibility_compliance": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art16", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART16-OBL-1a: Section 2 compliance (has_section_2_compliance) ──

class TestArt16Obl1a:

    def test_true_gives_partial(self, art16_module, tmp_path):
        """has_section_2_compliance=True -> ART16-OBL-1a PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art16_module, tmp_path):
        """has_section_2_compliance=False -> ART16-OBL-1a NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art16_module, tmp_path):
        """has_section_2_compliance=None -> ART16-OBL-1a UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART16-OBL-1b: Provider identification (has_provider_identification) ──

class TestArt16Obl1b:

    def test_true_gives_partial(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART16-OBL-1c: QMS (has_qms) ──

class TestArt16Obl1c:

    def test_true_gives_partial(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1c")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1c")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1c")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART16-OBL-1d: Documentation kept (has_documentation_kept) ──

class TestArt16Obl1d:

    def test_true_gives_partial(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART16-OBL-1e: Log retention (has_log_retention) ──

class TestArt16Obl1e:

    def test_true_gives_partial(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1e")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1e")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1e")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART16-OBL-1f: Conformity assessment (has_conformity_assessment) ──

class TestArt16Obl1f:

    def test_true_gives_partial(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1f")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1f")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1f")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART16-OBL-1g: EU declaration (has_eu_declaration) ──

class TestArt16Obl1g:

    def test_true_gives_partial(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1g")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1g")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1g")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART16-OBL-1h: CE marking (has_ce_marking) ──

class TestArt16Obl1h:

    def test_true_gives_partial(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1h")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1h")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1h")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART16-OBL-1i: Registration (has_registration) ──

class TestArt16Obl1i:

    def test_true_gives_partial(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1i")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1i")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1i")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART16-OBL-1j: Corrective actions (has_corrective_actions_process) ──

class TestArt16Obl1j:

    def test_true_gives_partial(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1j")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1j")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1j")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART16-OBL-1k: Conformity evidence (has_conformity_evidence) ──

class TestArt16Obl1k:

    def test_true_gives_partial(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1k")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1k")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1k")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART16-OBL-1l: Accessibility compliance (has_accessibility_compliance) ──

class TestArt16Obl1l:

    def test_true_gives_partial(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1l")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1l")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art16_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art16_module.scan(str(tmp_path))
        obl = _find(result, "ART16-OBL-1l")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt16Structural:

    def test_all_12_obligation_ids_in_json(self, art16_module):
        """Obligation JSON must have exactly 12 obligations."""
        data = art16_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 12

    def test_obligation_coverage_present(self, art16_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art16_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_obligations_utd(self, art16_module, tmp_path):
        """When AI provides no answers, all obligations -> UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art16_module.scan(str(tmp_path))
        automatable_ids = [
            "ART16-OBL-1a", "ART16-OBL-1b", "ART16-OBL-1c", "ART16-OBL-1d",
            "ART16-OBL-1e", "ART16-OBL-1f", "ART16-OBL-1g", "ART16-OBL-1h",
            "ART16-OBL-1i", "ART16-OBL-1j", "ART16-OBL-1k", "ART16-OBL-1l",
        ]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art16_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art16_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art16_module, tmp_path):
        """All-true answers -> no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art16_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art16_module, tmp_path):
        """All-false answers -> at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art16_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0


# ── High-risk gate test ──

class TestArt16HighRiskGate:

    def test_not_high_risk_returns_not_applicable(self, art16_module, tmp_path):
        """Not-high-risk classification -> NOT_APPLICABLE."""
        from core.context import ProjectContext
        ctx = ProjectContext(
            primary_language="python",
            risk_classification="not high-risk",
            risk_classification_confidence="high",
            compliance_answers={"art16": {}},
        )
        BaseArticleModule.set_context(ctx)
        result = art16_module.scan(str(tmp_path))
        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE
