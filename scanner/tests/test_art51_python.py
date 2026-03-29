"""Art. 51 Classification of GPAI Models with Systemic Risk tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_systemic_risk_assessment          → ART51-CLS-1 (classification rule, _finding_from_answer)
  training_compute_exceeds_threshold    → ART51-CLS-2 (classification rule, custom Finding)
  always UTD                            → ART51-EMP-3 (Commission empowerment)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art51", {
        "is_gpai_model": True,
        "has_high_impact_capabilities": True,
        "training_compute_exceeds_threshold": True,
        "training_compute_flops": "10^26",
        "has_commission_designation": False,
        "has_systemic_risk_assessment": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art51", {
        "is_gpai_model": False,
        "has_high_impact_capabilities": False,
        "training_compute_exceeds_threshold": False,
        "has_commission_designation": False,
        "has_systemic_risk_assessment": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art51", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART51-CLS-1: Systemic risk classification assessment ──

class TestArt51Cls1:

    def test_true_gives_partial(self, art51_module, tmp_path):
        """has_systemic_risk_assessment=True → ART51-CLS-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art51_module.scan(str(tmp_path))
        obl = _find(result, "ART51-CLS-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art51_module, tmp_path):
        """has_systemic_risk_assessment=False → ART51-CLS-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art51_module.scan(str(tmp_path))
        obl = _find(result, "ART51-CLS-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art51_module, tmp_path):
        """has_systemic_risk_assessment=None → ART51-CLS-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art51_module.scan(str(tmp_path))
        obl = _find(result, "ART51-CLS-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART51-CLS-2: Training compute threshold presumption ──

class TestArt51Cls2:

    def test_exceeds_threshold_non_compliant(self, art51_module, tmp_path):
        """training_compute_exceeds_threshold=True → ART51-CLS-2 NON_COMPLIANT (flag)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art51_module.scan(str(tmp_path))
        obl = _find(result, "ART51-CLS-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_below_threshold_utd(self, art51_module, tmp_path):
        """training_compute_exceeds_threshold=False → ART51-CLS-2 UTD (may still be systemic)."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art51_module.scan(str(tmp_path))
        obl = _find(result, "ART51-CLS-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_none_gives_utd(self, art51_module, tmp_path):
        """training_compute_exceeds_threshold=None → ART51-CLS-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art51_module.scan(str(tmp_path))
        obl = _find(result, "ART51-CLS-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_flops_in_description_when_true(self, art51_module, tmp_path):
        """When compute exceeds threshold, FLOPs value should appear in description."""
        ctx = _ctx_with("art51", {
            "training_compute_exceeds_threshold": True,
            "training_compute_flops": "3.5 x 10^26",
            "has_systemic_risk_assessment": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art51_module.scan(str(tmp_path))
        obl = _find(result, "ART51-CLS-2")
        assert len(obl) > 0
        assert "3.5 x 10^26" in obl[0].description


# ── ART51-EMP-3: Commission empowerment ──

class TestArt51Emp3:

    def test_always_utd(self, art51_module, tmp_path):
        """ART51-EMP-3 → always UNABLE_TO_DETERMINE (Commission empowerment)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art51_module.scan(str(tmp_path))
        obl = _find(result, "ART51-EMP-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_utd_even_with_no_answers(self, art51_module, tmp_path):
        """ART51-EMP-3 → UTD even with empty context."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art51_module.scan(str(tmp_path))
        obl = _find(result, "ART51-EMP-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt51Structural:

    def test_all_3_obligation_ids_in_json(self, art51_module):
        """Obligation JSON must have exactly 3 obligations."""
        data = art51_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 3

    def test_obligation_coverage_present(self, art51_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art51_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art51_module, tmp_path):
        """When AI provides no answers, all obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art51_module.scan(str(tmp_path))
        all_ids = ["ART51-CLS-1", "ART51-CLS-2", "ART51-EMP-3"]
        for obl_id in all_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art51_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 51(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art51_module.scan(str(tmp_path))
        for f in result.findings:
            if f.is_informational:
                continue
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_3_obligations_appear_in_findings(self, art51_module, tmp_path):
        """All 3 obligations must appear in findings (explicit or gap)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art51_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART51-CLS-1", "ART51-CLS-2", "ART51-EMP-3"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"

    def test_classification_result_in_details(self, art51_module, tmp_path):
        """Details must include classification_result."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art51_module.scan(str(tmp_path))
        assert "classification_result" in result.details
        assert "PRESUMED_SYSTEMIC_RISK" in result.details["classification_result"]
