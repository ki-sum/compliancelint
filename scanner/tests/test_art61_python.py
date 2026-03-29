"""Art. 61 Informed consent to participate in testing in real world conditions tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_informed_consent_procedure   → ART61-OBL-1
  has_consent_documentation        → ART61-OBL-2

Scope gate: conducts_real_world_testing — all obligations skip when false.
"""
import json
import pytest
from core.protocol import ComplianceLevel, BaseArticleModule
from core.context import ProjectContext
from conftest import _ctx_with

# Import server helper for integration tests
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from server import _scan_single_article


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project directory."""
    (tmp_path / "app.py").write_text("print('hello')")
    return str(tmp_path)


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art61", {
        "conducts_real_world_testing": True,
        "has_informed_consent_procedure": True,
        "has_consent_documentation": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art61", {
        "conducts_real_world_testing": True,
        "has_informed_consent_procedure": False,
        "has_consent_documentation": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art61", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── A1: Basic scan (all true → no NON_COMPLIANT) ──

class TestArt61BasicScan:

    def test_all_true_no_non_compliant(self, art61_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art61_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )


# ── A2: Feature detected → PARTIAL finding ──

class TestArt61Obl1:

    def test_has_consent_procedure_true_gives_partial(self, art61_module, tmp_path):
        """has_informed_consent_procedure=True → ART61-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art61_module.scan(str(tmp_path))
        obl = _find(result, "ART61-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_consent_procedure_false_gives_non_compliant(self, art61_module, tmp_path):
        """has_informed_consent_procedure=False → ART61-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art61_module.scan(str(tmp_path))
        obl = _find(result, "ART61-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_consent_procedure_none_gives_utd(self, art61_module, tmp_path):
        """has_informed_consent_procedure=None → ART61-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art61_module.scan(str(tmp_path))
        obl = _find(result, "ART61-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


class TestArt61Obl2:

    def test_has_consent_documentation_true_gives_partial(self, art61_module, tmp_path):
        """has_consent_documentation=True → ART61-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art61_module.scan(str(tmp_path))
        obl = _find(result, "ART61-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_consent_documentation_false_gives_non_compliant(self, art61_module, tmp_path):
        """has_consent_documentation=False → ART61-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art61_module.scan(str(tmp_path))
        obl = _find(result, "ART61-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_consent_documentation_none_gives_utd(self, art61_module, tmp_path):
        """has_consent_documentation=None → ART61-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art61_module.scan(str(tmp_path))
        obl = _find(result, "ART61-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── A3: Feature absent → NON_COMPLIANT finding ──

class TestArt61FeatureAbsent:

    def test_all_false_has_non_compliant(self, art61_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art61_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0


# ── A4: No context → error/UTD ──

class TestArt61NoContext:

    def test_no_answers_all_automatable_obligations_utd(self, art61_module, tmp_path):
        """When AI provides no answers, automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art61_module.scan(str(tmp_path))
        automatable_ids = ["ART61-OBL-1", "ART61-OBL-2"]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )


# ── A5: Invalid directory → error ──

class TestArt61InvalidDirectory:

    def test_invalid_path_raises_or_handles(self, art61_module):
        """Invalid directory should be handled gracefully."""
        BaseArticleModule.set_context(_full_true_ctx())
        try:
            result = art61_module.scan("/nonexistent/path/does/not/exist")
            # If it returns without error, it should have some result
            assert result is not None
        except (FileNotFoundError, OSError):
            pass  # Acceptable to raise


# ── A6: Summary present ──

class TestArt61Summary:

    def test_obligation_coverage_present(self, art61_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art61_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0


# ── A7: All obligation IDs in findings ──

class TestArt61AllObligations:

    def test_all_obligation_findings_present(self, art61_module, tmp_path):
        """All 2 obligations must appear in findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art61_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART61-OBL-1", "ART61-OBL-2"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"

    def test_all_2_obligation_ids_in_json(self, art61_module):
        """Obligation JSON must have exactly 2 obligations."""
        data = art61_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 2


# ── Structural tests ──

class TestArt61Structural:

    def test_description_has_no_legal_citation_prefix(self, art61_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 61(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art61_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_scan_result_article_number(self, art61_module, tmp_path):
        """ScanResult must have correct article number."""
        result = art61_module.scan(str(tmp_path))
        assert result.article_number == 61

    def test_scan_result_article_title(self, art61_module, tmp_path):
        """ScanResult must have correct article title."""
        result = art61_module.scan(str(tmp_path))
        assert "Informed consent" in result.article_title


# ── B: Server integration tests (TestClScanArticle61) ──

class TestClScanArticle61:
    """Test cl_scan_article_61 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art61": {
                "conducts_real_world_testing": True,
                "has_informed_consent_procedure": True,
                "has_consent_documentation": True,
            }
        }))
        result_json = _scan_single_article(61, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art61": {
                "conducts_real_world_testing": True,
                "has_informed_consent_procedure": True,
                "has_consent_documentation": True,
            }
        }))
        result_json = _scan_single_article(61, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art61": {
                "conducts_real_world_testing": True,
                "has_informed_consent_procedure": False,
                "has_consent_documentation": False,
            }
        }))
        result_json = _scan_single_article(61, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(61, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art61": {"has_informed_consent_procedure": false}}')
        result_json = _scan_single_article(61, "/nonexistent/path", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art61": {
                "conducts_real_world_testing": True,
                "has_informed_consent_procedure": True,
                "has_consent_documentation": True,
            }
        }))
        result_json = _scan_single_article(61, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art61": {
                "conducts_real_world_testing": True,
                "has_informed_consent_procedure": False,
                "has_consent_documentation": False,
            }
        }))
        result_json = _scan_single_article(61, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART61-OBL-1", "ART61-OBL-2"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art61": {"has_informed_consent_procedure": True}
        }))
        result_json = _scan_single_article(61, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


# ── C: verify_completeness(61) passes ──
