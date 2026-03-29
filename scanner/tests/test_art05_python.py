"""Art. 5 Prohibited Practices tests — per-prohibition coverage."""
import pytest
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


# All 8 prohibition fields with their obligation IDs
_PROHIBITIONS = [
    ("has_subliminal_manipulation", "ART05-PRO-1a"),
    ("has_exploitation_of_vulnerabilities", "ART05-PRO-1b"),
    ("has_social_scoring", "ART05-PRO-1c"),
    ("has_predictive_policing", "ART05-PRO-1d"),
    ("has_facial_recognition_scraping", "ART05-PRO-1e"),
    ("has_emotion_recognition_workplace", "ART05-PRO-1f"),
    ("has_biometric_categorization", "ART05-PRO-1g"),
    ("has_real_time_biometric_id", "ART05-PRO-1h"),
]


class TestArt5ProhibitedPractices:

    def test_all_false_all_compliant(self, art05_module, tmp_path):
        """When all has_* fields are False, all 8 findings should be COMPLIANT."""
        ctx = _ctx_with("art5", {field: False for field, _ in _PROHIBITIONS})
        BaseArticleModule.set_context(ctx)
        result = art05_module.scan(str(tmp_path))
        compliant = [f for f in result.findings if f.level == ComplianceLevel.COMPLIANT]
        assert len(compliant) == 8

    def test_all_none_all_utd(self, art05_module, tmp_path):
        """When no has_* fields provided, all 8 should be UNABLE_TO_DETERMINE."""
        ctx = _ctx_with("art5", {})
        BaseArticleModule.set_context(ctx)
        result = art05_module.scan(str(tmp_path))
        pro_findings = [f for f in result.findings if f.obligation_id.startswith("ART05-PRO")]
        utd = [f for f in pro_findings if f.level == ComplianceLevel.UNABLE_TO_DETERMINE]
        assert len(utd) == 8

    @pytest.mark.parametrize("field,obl_id", _PROHIBITIONS)
    def test_detected_true_is_non_compliant(self, field, obl_id, art05_module, tmp_path):
        """When a prohibition is detected (True), finding should be NON_COMPLIANT."""
        ctx = _ctx_with("art5", {field: True})
        BaseArticleModule.set_context(ctx)
        result = art05_module.scan(str(tmp_path))
        obl = [f for f in result.findings if f.obligation_id == obl_id]
        assert len(obl) > 0, f"Expected finding for {obl_id}"
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT, (
            f"{obl_id} should be NON_COMPLIANT when {field}=True"
        )

    @pytest.mark.parametrize("field,obl_id", _PROHIBITIONS)
    def test_detected_false_is_compliant(self, field, obl_id, art05_module, tmp_path):
        """When a prohibition is not detected (False), finding should be COMPLIANT."""
        ctx = _ctx_with("art5", {field: False})
        BaseArticleModule.set_context(ctx)
        result = art05_module.scan(str(tmp_path))
        obl = [f for f in result.findings if f.obligation_id == obl_id]
        assert len(obl) > 0, f"Expected finding for {obl_id}"
        assert obl[0].level == ComplianceLevel.COMPLIANT, (
            f"{obl_id} should be COMPLIANT when {field}=False"
        )

    @pytest.mark.parametrize("field,obl_id", _PROHIBITIONS)
    def test_not_provided_is_unable_to_determine(self, field, obl_id, art05_module, tmp_path):
        """When has_* field is not provided (None), finding should be UNABLE_TO_DETERMINE."""
        ctx = _ctx_with("art5", {})
        BaseArticleModule.set_context(ctx)
        result = art05_module.scan(str(tmp_path))
        obl = [f for f in result.findings if f.obligation_id == obl_id]
        assert len(obl) > 0, f"Expected finding for {obl_id}"
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
            f"{obl_id} should be UNABLE_TO_DETERMINE when {field} not provided"
        )

    def test_single_detection_does_not_affect_others(self, art05_module, tmp_path):
        """Detecting one prohibition should not affect other prohibitions."""
        ctx = _ctx_with("art5", {"has_social_scoring": True})
        BaseArticleModule.set_context(ctx)
        result = art05_module.scan(str(tmp_path))
        social = [f for f in result.findings if f.obligation_id == "ART05-PRO-1c"]
        assert social[0].level == ComplianceLevel.NON_COMPLIANT
        # Other prohibitions should be UTD (not provided), not NON_COMPLIANT
        others = [f for f in result.findings
                  if f.obligation_id.startswith("ART05-PRO") and f.obligation_id != "ART05-PRO-1c"]
        for f in others:
            assert f.level != ComplianceLevel.NON_COMPLIANT, (
                f"{f.obligation_id} should not be NON_COMPLIANT when only social_scoring is detected"
            )

    def test_obligation_coverage_present(self, art05_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art05_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_description_no_legal_citation_prefix(self, art05_module, tmp_path):
        """Descriptions should NOT contain legal citation prefix."""
        ctx = _ctx_with("art5", {field: False for field, _ in _PROHIBITIONS})
        BaseArticleModule.set_context(ctx)
        result = art05_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:50]}"
            )
