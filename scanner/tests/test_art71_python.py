"""Art. 71 EU database for high-risk AI systems tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_provider_database_entry → ART71-OBL-2
  gap_findings (conditional)  → ART71-OBL-3 (context_skip_field: is_public_authority_deployer)
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.protocol import ComplianceLevel, BaseArticleModule
from core.context import ProjectContext
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art71", {
        "has_provider_database_entry": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art71", {
        "has_provider_database_entry": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art71", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART71-OBL-2: Provider data entry in EU database (has_provider_database_entry) ──

class TestArt71Obl2:

    def test_true_gives_partial(self, art71_module, tmp_path):
        """has_provider_database_entry=True → ART71-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art71_module.scan(str(tmp_path))
        obl = _find(result, "ART71-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art71_module, tmp_path):
        """has_provider_database_entry=False → ART71-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art71_module.scan(str(tmp_path))
        obl = _find(result, "ART71-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art71_module, tmp_path):
        """has_provider_database_entry=None → ART71-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art71_module.scan(str(tmp_path))
        obl = _find(result, "ART71-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART71-OBL-3: Public-authority deployer data entry (conditional, via gap_findings) ──

class TestArt71Obl3:

    def test_conditional_utd_when_field_absent(self, art71_module, tmp_path):
        """ART71-OBL-3 → UNABLE_TO_DETERMINE [CONDITIONAL] when is_public_authority_deployer not provided."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art71_module.scan(str(tmp_path))
        obl = _find(result, "ART71-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_not_applicable_when_skip_false(self, art71_module, tmp_path):
        """ART71-OBL-3 → NOT_APPLICABLE when is_public_authority_deployer=false."""
        ctx = _ctx_with("art71", {
            "has_provider_database_entry": True,
            "is_public_authority_deployer": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art71_module.scan(str(tmp_path))
        obl = _find(result, "ART71-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE


# ── Structural tests ──

class TestArt71Structural:

    def test_all_2_obligation_ids_in_json(self, art71_module):
        """Obligation JSON must have exactly 2 obligations."""
        data = art71_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 2

    def test_obligation_coverage_present(self, art71_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art71_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art71_module, tmp_path):
        """When AI provides no answers, all obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art71_module.scan(str(tmp_path))
        all_ids = ["ART71-OBL-2", "ART71-OBL-3"]
        for obl_id in all_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art71_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 71(2)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art71_module.scan(str(tmp_path))
        for f in result.findings:
            if f.is_informational:
                continue
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art71_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art71_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art71_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art71_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_2_obligations_appear_in_findings(self, art71_module, tmp_path):
        """All 2 obligations must appear in findings (explicit or gap)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art71_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART71-OBL-2", "ART71-OBL-3"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"

    def test_summary_present(self, art71_module, tmp_path):
        """ScanResult must have article_number, article_title, and overall_level."""
        result = art71_module.scan(str(tmp_path))
        assert result.article_number == 71
        assert result.article_title == "EU database for high-risk AI systems listed in Annex III"
        assert result.overall_level is not None


# ── B: Server integration tests (TestClScanArticle71) ──

@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project directory for server integration tests."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hello')")
    return str(tmp_path)


class TestClScanArticle71:
    """Test cl_scan_article_71 MCP tool function end-to-end."""

    def _import_scan(self):
        from server import _scan_single_article
        return _scan_single_article

    def test_basic_scan(self, project_dir):
        _scan_single_article = self._import_scan()
        ctx = ProjectContext.from_json(json.dumps({
            "art71": {
                "has_provider_database_entry": True,
            }
        }))
        result_json = _scan_single_article(71, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        _scan_single_article = self._import_scan()
        ctx = ProjectContext.from_json(json.dumps({
            "art71": {
                "has_provider_database_entry": True,
            }
        }))
        result_json = _scan_single_article(71, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        _scan_single_article = self._import_scan()
        ctx = ProjectContext.from_json(json.dumps({
            "art71": {
                "has_provider_database_entry": False,
            }
        }))
        result_json = _scan_single_article(71, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        _scan_single_article = self._import_scan()
        result_json = _scan_single_article(71, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        _scan_single_article = self._import_scan()
        ctx = ProjectContext.from_json(json.dumps({
            "art71": {"has_provider_database_entry": True}
        }))
        result_json = _scan_single_article(71, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result


# ── C: verify_completeness(71) passes ──
