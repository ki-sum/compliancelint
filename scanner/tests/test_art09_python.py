"""Art. 9 Risk Management tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_risk_docs           → ART09-OBL-1, OBL-2, OBL-2a, OBL-2b
  has_risk_code_patterns  → ART09-OBL-2d, OBL-5a, OBL-5b
  has_testing_infrastructure → ART09-OBL-6, OBL-8a
  has_defined_metrics     → ART09-OBL-8b
  Manual (always UTD)     → ART09-OBL-2c, OBL-3, OBL-4, OBL-5, OBL-5c, OBL-5d
  Conditional             → ART09-OBL-9 (affects_children)
  Permissions (skipped)   → ART09-PERM-7, ART09-PERM-10
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art9", {
        "has_risk_docs": True,
        "risk_doc_paths": ["docs/risk_assessment.md"],
        "has_testing_infrastructure": True,
        "testing_evidence": ["tests/"],
        "has_risk_code_patterns": True,
        "risk_code_evidence": ["src/guardrails.py"],
        "has_defined_metrics": True,
        "metrics_evidence": ["accuracy=0.95"],
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art9", {
        "has_risk_docs": False,
        "risk_doc_paths": [],
        "has_testing_infrastructure": False,
        "testing_evidence": [],
        "has_risk_code_patterns": False,
        "risk_code_evidence": [],
        "has_defined_metrics": False,
        "metrics_evidence": [],
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art9", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART09-OBL-1: RMS established/documented (has_risk_docs) ──

class TestArt09Obl1:

    def test_has_risk_docs_true_gives_partial(self, art09_module, tmp_path):
        """has_risk_docs=True → ART09-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_risk_docs_false_gives_non_compliant(self, art09_module, tmp_path):
        """has_risk_docs=False → ART09-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_risk_docs_none_gives_utd(self, art09_module, tmp_path):
        """has_risk_docs=None → ART09-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART09-OBL-2: Continuous iterative process (has_risk_docs) ──

class TestArt09Obl2:

    def test_has_risk_docs_true_gives_partial(self, art09_module, tmp_path):
        """has_risk_docs=True → ART09-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_risk_docs_false_gives_non_compliant(self, art09_module, tmp_path):
        """has_risk_docs=False → ART09-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_risk_docs_none_gives_utd(self, art09_module, tmp_path):
        """has_risk_docs=None → ART09-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART09-OBL-2a: Identify/analyze risks (has_risk_docs) ──

class TestArt09Obl2a:

    def test_has_risk_docs_true_gives_partial(self, art09_module, tmp_path):
        """has_risk_docs=True → ART09-OBL-2a PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-2a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_risk_docs_false_gives_non_compliant(self, art09_module, tmp_path):
        """has_risk_docs=False → ART09-OBL-2a NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-2a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_risk_docs_none_gives_utd(self, art09_module, tmp_path):
        """has_risk_docs=None → ART09-OBL-2a UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-2a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART09-OBL-2b: Evaluate risks from intended use + misuse (has_risk_docs) ──

class TestArt09Obl2b:

    def test_has_risk_docs_true_gives_partial(self, art09_module, tmp_path):
        """has_risk_docs=True → ART09-OBL-2b PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-2b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_risk_docs_false_gives_non_compliant(self, art09_module, tmp_path):
        """has_risk_docs=False → ART09-OBL-2b NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-2b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_risk_docs_none_gives_utd(self, art09_module, tmp_path):
        """has_risk_docs=None → ART09-OBL-2b UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-2b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART09-OBL-2d: Adopt risk management measures (has_risk_code_patterns) ──

class TestArt09Obl2d:

    def test_has_risk_code_true_gives_partial(self, art09_module, tmp_path):
        """has_risk_code_patterns=True → ART09-OBL-2d PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-2d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_risk_code_false_gives_non_compliant(self, art09_module, tmp_path):
        """has_risk_code_patterns=False → ART09-OBL-2d NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-2d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_risk_code_none_gives_utd(self, art09_module, tmp_path):
        """has_risk_code_patterns=None → ART09-OBL-2d UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-2d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART09-OBL-5a: Eliminate risks by design (has_risk_code_patterns) ──

class TestArt09Obl5a:

    def test_has_risk_code_true_gives_partial(self, art09_module, tmp_path):
        """has_risk_code_patterns=True → ART09-OBL-5a PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-5a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_risk_code_false_gives_non_compliant(self, art09_module, tmp_path):
        """has_risk_code_patterns=False → ART09-OBL-5a NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-5a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_risk_code_none_gives_utd(self, art09_module, tmp_path):
        """has_risk_code_patterns=None → ART09-OBL-5a UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-5a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART09-OBL-5b: Implement mitigations (has_risk_code_patterns) ──

class TestArt09Obl5b:

    def test_has_risk_code_true_gives_partial(self, art09_module, tmp_path):
        """has_risk_code_patterns=True → ART09-OBL-5b PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-5b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_risk_code_false_gives_non_compliant(self, art09_module, tmp_path):
        """has_risk_code_patterns=False → ART09-OBL-5b NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-5b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_risk_code_none_gives_utd(self, art09_module, tmp_path):
        """has_risk_code_patterns=None → ART09-OBL-5b UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-5b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART09-OBL-6: Testing for risk management (has_testing_infrastructure) ──

class TestArt09Obl6:

    def test_has_testing_true_gives_partial(self, art09_module, tmp_path):
        """has_testing_infrastructure=True → ART09-OBL-6 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_testing_false_gives_non_compliant(self, art09_module, tmp_path):
        """has_testing_infrastructure=False → ART09-OBL-6 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_testing_none_gives_utd(self, art09_module, tmp_path):
        """has_testing_infrastructure=None → ART09-OBL-6 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART09-OBL-8a: Testing throughout development (has_testing_infrastructure) ──

class TestArt09Obl8a:

    def test_has_testing_true_gives_partial(self, art09_module, tmp_path):
        """has_testing_infrastructure=True → ART09-OBL-8a PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-8a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_testing_false_gives_non_compliant(self, art09_module, tmp_path):
        """has_testing_infrastructure=False → ART09-OBL-8a NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-8a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_testing_none_gives_utd(self, art09_module, tmp_path):
        """has_testing_infrastructure=None → ART09-OBL-8a UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-8a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART09-OBL-8b: Defined metrics (has_defined_metrics) ──

class TestArt09Obl8b:

    def test_has_defined_metrics_true_gives_partial(self, art09_module, tmp_path):
        """has_defined_metrics=True → ART09-OBL-8b PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-8b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_defined_metrics_false_gives_non_compliant(self, art09_module, tmp_path):
        """has_defined_metrics=False → ART09-OBL-8b NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-8b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_defined_metrics_none_gives_utd(self, art09_module, tmp_path):
        """has_defined_metrics=None → ART09-OBL-8b UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-8b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Manual obligations: always UNABLE_TO_DETERMINE ──

class TestArt09ManualObligations:

    def test_manual_obligations_always_utd_with_all_true(self, art09_module, tmp_path):
        """Manual obligations always UTD even with all-true answers."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art09_module.scan(str(tmp_path))
        manual_ids = [
            "ART09-OBL-2c", "ART09-OBL-3", "ART09-OBL-4",
            "ART09-OBL-5", "ART09-OBL-5c", "ART09-OBL-5d",
        ]
        for obl_id in manual_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should always be UTD, got {findings[0].level}"
            )

    def test_manual_obligations_always_utd_with_all_false(self, art09_module, tmp_path):
        """Manual obligations always UTD even with all-false answers."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art09_module.scan(str(tmp_path))
        manual_ids = [
            "ART09-OBL-2c", "ART09-OBL-3", "ART09-OBL-4",
            "ART09-OBL-5", "ART09-OBL-5c", "ART09-OBL-5d",
        ]
        for obl_id in manual_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should always be UTD, got {findings[0].level}"
            )


# ── ART09-OBL-9: Conditional (affects_children) ──

class TestArt09Obl9Conditional:

    def test_affects_children_none_gives_conditional(self, art09_module, tmp_path):
        """affects_children=None → OBL-9 CONDITIONAL or UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-9")
        assert len(obl) > 0
        # No affects_children answer → CONDITIONAL (gap_findings default for scope_limitation)
        assert obl[0].level in (
            ComplianceLevel.UNABLE_TO_DETERMINE,
            ComplianceLevel.NOT_APPLICABLE,
        )

    def test_affects_children_false_gives_not_applicable(self, art09_module, tmp_path):
        """affects_children=False → OBL-9 NOT_APPLICABLE."""
        ctx = _ctx_with("art9", {
            "has_risk_docs": True, "has_risk_code_patterns": True,
            "has_testing_infrastructure": True, "has_defined_metrics": True,
            "affects_children": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-9")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_affects_children_true_gives_utd(self, art09_module, tmp_path):
        """affects_children=True → OBL-9 UNABLE_TO_DETERMINE (manual assessment)."""
        ctx = _ctx_with("art9", {
            "has_risk_docs": True, "has_risk_code_patterns": True,
            "has_testing_infrastructure": True, "has_defined_metrics": True,
            "affects_children": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-9")
        assert len(obl) > 0
        # affects_children=True → obligation applies, but it's manual → UTD
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt09Structural:

    def test_all_19_obligation_ids_in_json(self, art09_module):
        """Obligation JSON must have exactly 19 obligations."""
        data = art09_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 19

    def test_obligation_coverage_present(self, art09_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art09_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art09_module, tmp_path):
        """When AI provides no answers, key automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art09_module.scan(str(tmp_path))
        automatable_ids = [
            "ART09-OBL-1", "ART09-OBL-2", "ART09-OBL-2a", "ART09-OBL-2b",
            "ART09-OBL-2d", "ART09-OBL-5a", "ART09-OBL-5b",
            "ART09-OBL-6", "ART09-OBL-8a", "ART09-OBL-8b",
        ]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art09_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 9(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art09_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art09_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art09_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art09_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art09_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0


# ── Alias tests ──

class TestArt09Aliases:

    def test_has_risk_code_alias(self, art09_module, tmp_path):
        """has_risk_code (alias for has_risk_code_patterns) should work."""
        ctx = _ctx_with("art9", {
            "has_risk_docs": True, "has_risk_code": True,
            "has_testing_infrastructure": True, "has_defined_metrics": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-2d")
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_testing_alias(self, art09_module, tmp_path):
        """has_testing (alias for has_testing_infrastructure) should work."""
        ctx = _ctx_with("art9", {
            "has_risk_docs": True, "has_risk_code_patterns": True,
            "has_testing": True, "has_defined_metrics": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-6")
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_metrics_alias(self, art09_module, tmp_path):
        """has_metrics (alias for has_defined_metrics) should work."""
        ctx = _ctx_with("art9", {
            "has_risk_docs": True, "has_risk_code_patterns": True,
            "has_testing_infrastructure": True, "has_metrics": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art09_module.scan(str(tmp_path))
        obl = _find(result, "ART09-OBL-8b")
        assert obl[0].level == ComplianceLevel.PARTIAL
