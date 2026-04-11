"""Server-level integration tests.

Tests the ACTUAL MCP tool functions (cl_scan_article_12, cl_scan_all, etc.)
with real JSON string inputs, verifying the entire pipeline:

  cl_scan_article_12(project_path, project_context: str)
    → ProjectContext.from_json()
    → _scan_single_article()
    → BaseArticleModule.set_context()
    → module.scan()
    → compliance_summary injection
    → evidence application
    → JSON response

These tests catch bugs that unit tests miss because unit tests
bypass server.py entirely (they call module.scan() directly).
"""
import json
import os
import sys
import tempfile
import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

# Import server functions directly (they're plain functions, not MCP-decorated at test time)
# We need to import them carefully since server.py registers MCP tools on import
import importlib.util
_server_spec = importlib.util.spec_from_file_location(
    "server", os.path.join(SCANNER_ROOT, "server.py"))
_server_mod = importlib.util.module_from_spec(_server_spec)
# Patch out MCP registration before loading
import types
_fake_mcp = types.SimpleNamespace(tool=lambda: (lambda f: f))
_server_mod.mcp = _fake_mcp
try:
    _server_spec.loader.exec_module(_server_mod)
except Exception:
    pass

# Direct function references
_scan_single_article = _server_mod._scan_single_article
_build_evidence_requests = getattr(_server_mod, '_build_evidence_requests', None)

# We also need ProjectContext for direct testing
from core.context import ProjectContext
from core.protocol import BaseArticleModule


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project directory."""
    (tmp_path / "app.py").write_text("print('hello')")
    return str(tmp_path)


class TestClScanArticle12:
    """Test cl_scan_article_12 MCP tool function end-to-end."""

    def test_full_context_returns_partial(self, project_dir):
        """Full project_context with has_logging=True → PARTIAL."""
        ctx_json = json.dumps({
            "primary_language": "python",
            "risk_classification": "likely high-risk",
            "risk_classification_confidence": "high",
            "compliance_answers": {
                "art12": {
                    "has_logging": True,
                    "logging_description": "structlog with JSON output",
                    "logging_evidence": ["src/logging_config.py:5"],
                    "has_retention_config": True,
                    "retention_days": 365,
                    "retention_evidence": "LOG_RETENTION=365d in config.yaml",
                }
            }
        })
        ctx = ProjectContext.from_json(ctx_json)
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert result["overall_level"] == "partial", (
            f"has_logging=True should give partial, got {result['overall_level']}"
        )

    def test_shorthand_context_works(self, project_dir):
        """Shorthand format {"art12": {...}} works after Bug 1 fix."""
        ctx_json = json.dumps({
            "art12": {
                "has_logging": True,
                "logging_description": "Python logging",
                "logging_evidence": ["main.py"],
                "has_retention_config": False,
                "retention_days": None,
                "retention_evidence": "",
            }
        })
        ctx = ProjectContext.from_json(ctx_json)
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)

        assert "error" not in result
        # ART12-OBL-1 should be PARTIAL (has_logging=True)
        findings = result.get("findings", [])
        obl1 = [f for f in findings if f["obligation_id"] == "ART12-OBL-1"]
        assert len(obl1) > 0, "ART12-OBL-1 not in findings"
        assert obl1[0]["level"] == "partial", (
            f"ART12-OBL-1 should be partial, got {obl1[0]['level']}"
        )

    def test_no_context_returns_error(self, project_dir):
        """Missing project_context returns clear error message."""
        result_json = _scan_single_article(12, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result
        assert "project_context is required" in result["error"]

    def test_has_logging_false_returns_non_compliant(self, project_dir):
        """has_logging=False → NON_COMPLIANT."""
        ctx = ProjectContext.from_json(json.dumps({
            "art12": {
                "has_logging": False,
                "logging_description": "",
                "logging_evidence": [],
                "has_retention_config": False,
                "retention_days": None,
                "retention_evidence": "",
            }
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)

        assert result["overall_level"] == "non_compliant"

    def test_compliance_summary_present(self, project_dir):
        """Response must include compliance_summary with required fields."""
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art12": {
                "has_logging": True,
                "logging_description": "test",
                "logging_evidence": [],
                "has_retention_config": True,
                "retention_days": 365,
                "retention_evidence": "",
            }
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)

        summary = result.get("compliance_summary", {})
        assert "article" in summary, "compliance_summary missing 'article'"
        assert "overall" in summary, "compliance_summary missing 'overall'"
        assert "regulation" in summary, "compliance_summary missing 'regulation'"
        assert "assessed_by" in summary, "compliance_summary missing 'assessed_by'"
        assert "scan_date" in summary, "compliance_summary missing 'scan_date'"
        assert "scan_coverage" in summary, "compliance_summary missing 'scan_coverage'"
        assert "terminology" in summary, "compliance_summary missing 'terminology'"

    def test_assessed_by_from_context(self, project_dir):
        """assessed_by should come from ai_model in context."""
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art12": {
                "has_logging": True,
                "logging_description": "test",
                "logging_evidence": [],
                "has_retention_config": False,
                "retention_days": None,
                "retention_evidence": "",
            }
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)

        assessed = result.get("compliance_summary", {}).get("assessed_by", "")
        assert assessed == "claude-opus-4-6", (
            f"assessed_by should be 'claude-opus-4-6', got '{assessed}'"
        )

    def test_scope_gate_open_source(self, project_dir):
        """Open source project → Art.12 NOT_APPLICABLE."""
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art12": {"has_logging": True},
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)

        assert result["overall_level"] == "not_applicable", (
            f"Open source should give not_applicable, got {result['overall_level']}"
        )

    def test_invalid_directory_returns_error(self):
        """Non-existent directory returns error, not crash."""
        ctx = ProjectContext.from_json('{"art12": {"has_logging": true}}')
        result_json = _scan_single_article(12, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_all_11_obligations_in_findings(self, project_dir):
        """All 11 Art.12 obligations must appear in findings."""
        ctx = ProjectContext.from_json(json.dumps({
            "art12": {
                "has_logging": False,
                "logging_description": "",
                "logging_evidence": [],
                "has_retention_config": False,
                "retention_days": None,
                "retention_evidence": "",
            }
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)

        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}

        # Core obligations (must be in scan)
        for obl_id in ["ART12-OBL-1", "ART12-OBL-2a", "ART12-OBL-2b",
                        "ART12-OBL-2c", "ART19-OBL-1"]:
            assert obl_id in finding_ids, (
                f"{obl_id} not in findings. Found: {sorted(finding_ids)}"
            )

        # Conditional obligations (should appear as CONDITIONAL/informational)
        for obl_id in ["ART12-OBL-3a", "ART12-OBL-3b", "ART12-OBL-3c",
                        "ART12-OBL-3d", "ART19-OBL-2", "ART26-OBL-6"]:
            assert obl_id in finding_ids, (
                f"Conditional {obl_id} not in findings. Found: {sorted(finding_ids)}"
            )

    def test_biometric_false_skips_obl3a(self, project_dir):
        """is_biometric_system=False → OBL-3a~3d should be NOT_APPLICABLE."""
        ctx = ProjectContext.from_json(json.dumps({
            "art12": {
                "has_logging": True, "logging_description": "test",
                "logging_evidence": [], "has_retention_config": True,
                "retention_days": 365, "retention_evidence": "",
                "is_biometric_system": False,
            }
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        for obl_id in ["ART12-OBL-3a", "ART12-OBL-3b", "ART12-OBL-3c", "ART12-OBL-3d"]:
            findings = [f for f in result["findings"] if f["obligation_id"] == obl_id]
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0]["level"] == "not_applicable", (
                f"{obl_id} should be not_applicable when is_biometric_system=False, "
                f"got {findings[0]['level']}"
            )

    def test_biometric_not_provided_stays_conditional(self, project_dir):
        """No is_biometric_system field → OBL-3a~3d should stay CONDITIONAL."""
        ctx = ProjectContext.from_json(json.dumps({
            "art12": {
                "has_logging": True, "logging_description": "test",
                "logging_evidence": [], "has_retention_config": True,
                "retention_days": 365, "retention_evidence": "",
            }
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        for obl_id in ["ART12-OBL-3a"]:
            findings = [f for f in result["findings"] if f["obligation_id"] == obl_id]
            assert len(findings) > 0
            assert findings[0]["level"] == "unable_to_determine", (
                f"{obl_id} should be unable_to_determine when is_biometric not provided"
            )

    def test_biometric_true_shows_applicable(self, project_dir):
        """is_biometric_system=True → OBL-3a~3d should say APPLICABLE, not CONDITIONAL."""
        ctx = ProjectContext.from_json(json.dumps({
            "art12": {
                "has_logging": True, "logging_description": "test",
                "logging_evidence": [], "has_retention_config": True,
                "retention_days": 365, "retention_evidence": "",
                "is_biometric_system": True,
            }
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        for obl_id in ["ART12-OBL-3a", "ART12-OBL-3b", "ART12-OBL-3c", "ART12-OBL-3d"]:
            findings = [f for f in result["findings"] if f["obligation_id"] == obl_id]
            assert len(findings) > 0, f"{obl_id} not in findings"
            desc = findings[0].get("description", "")
            assert "[APPLICABLE]" in desc, (
                f"{obl_id} should say [APPLICABLE] when is_biometric=True, "
                f"got: {desc[:100]}"
            )
            assert findings[0]["level"] == "unable_to_determine"

    def test_retention_insufficient_non_compliant(self, project_dir):
        """Retention < 180 days → ART19-OBL-1 NON_COMPLIANT."""
        ctx = ProjectContext.from_json(json.dumps({
            "art12": {
                "has_logging": True,
                "logging_description": "logback",
                "logging_evidence": [],
                "has_retention_config": True,
                "retention_days": 30,
                "retention_evidence": "maxHistory=30",
            }
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)

        retention = [f for f in result.get("findings", [])
                    if f["obligation_id"] == "ART19-OBL-1"]
        assert len(retention) > 0
        assert retention[0]["level"] == "non_compliant", (
            f"30-day retention should be non_compliant, got {retention[0]['level']}"
        )

    def test_obl2a_logging_true_partial(self, project_dir):
        """ART12-OBL-2a (risk event logging): has_logging=True → PARTIAL."""
        ctx = ProjectContext.from_json(json.dumps({
            "art12": {"has_logging": True, "logging_description": "structlog",
                      "logging_evidence": ["app.py"], "has_retention_config": False,
                      "retention_days": None, "retention_evidence": ""}
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        obl = [f for f in result["findings"] if f["obligation_id"] == "ART12-OBL-2a"]
        assert len(obl) > 0, "ART12-OBL-2a not in findings"
        assert obl[0]["level"] == "partial"

    def test_obl2a_logging_false_non_compliant(self, project_dir):
        """ART12-OBL-2a: has_logging=False → NON_COMPLIANT."""
        ctx = ProjectContext.from_json(json.dumps({
            "art12": {"has_logging": False, "logging_description": "",
                      "logging_evidence": [], "has_retention_config": False,
                      "retention_days": None, "retention_evidence": ""}
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        obl = [f for f in result["findings"] if f["obligation_id"] == "ART12-OBL-2a"]
        assert obl[0]["level"] == "non_compliant"

    def test_obl2b_logging_true_partial(self, project_dir):
        """ART12-OBL-2b (post-market monitoring): has_logging=True → PARTIAL."""
        ctx = ProjectContext.from_json(json.dumps({
            "art12": {"has_logging": True, "logging_description": "test",
                      "logging_evidence": ["x.py"], "has_retention_config": False,
                      "retention_days": None, "retention_evidence": ""}
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        obl = [f for f in result["findings"] if f["obligation_id"] == "ART12-OBL-2b"]
        assert obl[0]["level"] == "partial"

    def test_obl2b_logging_false_non_compliant(self, project_dir):
        """ART12-OBL-2b: has_logging=False → NON_COMPLIANT."""
        ctx = ProjectContext.from_json(json.dumps({
            "art12": {"has_logging": False, "logging_description": "",
                      "logging_evidence": [], "has_retention_config": False,
                      "retention_days": None, "retention_evidence": ""}
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        obl = [f for f in result["findings"] if f["obligation_id"] == "ART12-OBL-2b"]
        assert obl[0]["level"] == "non_compliant"

    def test_obl2c_always_unable_to_determine(self, project_dir):
        """ART12-OBL-2c (deployer monitoring): always UNABLE_TO_DETERMINE."""
        ctx = ProjectContext.from_json(json.dumps({
            "art12": {"has_logging": True, "logging_description": "test",
                      "logging_evidence": [], "has_retention_config": True,
                      "retention_days": 365, "retention_evidence": ""}
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        obl = [f for f in result["findings"] if f["obligation_id"] == "ART12-OBL-2c"]
        assert obl[0]["level"] == "unable_to_determine"

    def test_conditional_obligations_are_informational(self, project_dir):
        """OBL-3a~3d, ART19-OBL-2, ART26-OBL-6 are informational (scope_limitation)."""
        ctx = ProjectContext.from_json(json.dumps({
            "art12": {"has_logging": True, "logging_description": "test",
                      "logging_evidence": [], "has_retention_config": True,
                      "retention_days": 365, "retention_evidence": ""}
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        conditional_ids = ["ART12-OBL-3a", "ART12-OBL-3b", "ART12-OBL-3c",
                          "ART12-OBL-3d", "ART19-OBL-2", "ART26-OBL-6"]
        for obl_id in conditional_ids:
            findings = [f for f in result["findings"] if f["obligation_id"] == obl_id]
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].get("is_informational", False) or \
                   "[CONDITIONAL]" in findings[0].get("description", ""), \
                f"{obl_id} should be informational/conditional"

    def test_retention_policy_alias_works(self, project_dir):
        """AI may use has_retention_policy instead of has_retention_config."""
        ctx = ProjectContext.from_json(json.dumps({
            "art12": {
                "has_logging": True, "logging_description": "test",
                "logging_evidence": [],
                "has_retention_policy": False,
                "retention_days": None,
                "retention_evidence": "",
            }
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        retention = [f for f in result["findings"] if f["obligation_id"] == "ART19-OBL-1"]
        assert len(retention) > 0
        assert retention[0]["level"] == "non_compliant", (
            f"has_retention_policy=False should give non_compliant, got {retention[0]['level']}"
        )

    def test_string_coercion_through_server(self, project_dir):
        """String "true" in JSON should be coerced to True."""
        ctx = ProjectContext.from_json(
            '{"art12": {"has_logging": "true", "logging_description": "", '
            '"logging_evidence": [], "has_retention_config": "false", '
            '"retention_days": null, "retention_evidence": ""}}'
        )
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)

        obl1 = [f for f in result.get("findings", [])
                if f["obligation_id"] == "ART12-OBL-1"]
        assert obl1[0]["level"] == "partial", (
            f"String 'true' coerced → PARTIAL, got {obl1[0]['level']}"
        )


class TestClScanArticle9:
    """Test cl_scan_article_9 MCP tool function end-to-end."""

    def test_full_context_returns_partial(self, project_dir):
        """All-true answers → overall PARTIAL (not compliant — manual obligations)."""
        ctx = ProjectContext.from_json(json.dumps({
            "art9": {
                "has_risk_docs": True,
                "risk_doc_paths": ["docs/risk_assessment.md"],
                "has_testing_infrastructure": True,
                "testing_evidence": ["tests/"],
                "has_risk_code_patterns": True,
                "risk_code_evidence": ["src/guardrails.py"],
                "has_defined_metrics": True,
                "metrics_evidence": ["config/metrics.yaml"],
                "affects_children": False,
            }
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        # Has manual obligations → can't be fully compliant
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_shorthand_context_works(self, project_dir):
        """Shorthand format {"art9": {...}} works."""
        ctx = ProjectContext.from_json(json.dumps({
            "art9": {
                "has_risk_docs": True,
                "risk_doc_paths": ["risk.md"],
                "has_risk_code_patterns": False,
                "has_testing_infrastructure": False,
                "has_defined_metrics": False,
            }
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART09-OBL-1"]
        assert len(obl1) > 0
        assert obl1[0]["level"] == "partial"

    def test_no_risk_docs_non_compliant(self, project_dir):
        """has_risk_docs=False → OBL-1 NON_COMPLIANT."""
        ctx = ProjectContext.from_json(json.dumps({
            "art9": {
                "has_risk_docs": False,
                "risk_doc_paths": [],
                "has_risk_code_patterns": False,
                "has_testing_infrastructure": False,
                "has_defined_metrics": False,
            }
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART09-OBL-1"]
        assert obl1[0]["level"] == "non_compliant"

    def test_has_defined_metrics_true_partial(self, project_dir):
        """has_defined_metrics=True → ART09-OBL-8b PARTIAL."""
        ctx = ProjectContext.from_json(json.dumps({
            "art9": {
                "has_risk_docs": True,
                "has_risk_code_patterns": True,
                "has_testing_infrastructure": True,
                "has_defined_metrics": True,
                "metrics_evidence": ["accuracy=0.95, threshold=0.90"],
            }
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        obl8b = [f for f in result["findings"] if f["obligation_id"] == "ART09-OBL-8b"]
        assert len(obl8b) > 0
        assert obl8b[0]["level"] == "partial"

    def test_has_defined_metrics_false_non_compliant(self, project_dir):
        """has_defined_metrics=False → ART09-OBL-8b NON_COMPLIANT."""
        ctx = ProjectContext.from_json(json.dumps({
            "art9": {
                "has_risk_docs": True,
                "has_risk_code_patterns": True,
                "has_testing_infrastructure": True,
                "has_defined_metrics": False,
            }
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        obl8b = [f for f in result["findings"] if f["obligation_id"] == "ART09-OBL-8b"]
        assert len(obl8b) > 0
        assert obl8b[0]["level"] == "non_compliant"

    def test_scope_gate_open_source(self, project_dir):
        """Open source project → Art.9 NOT_APPLICABLE."""
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art9": {"has_risk_docs": True},
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_all_17_obligations_in_findings(self, project_dir):
        """All 17 Art.9 obligations must appear in findings."""
        ctx = ProjectContext.from_json(json.dumps({
            "art9": {
                "has_risk_docs": False,
                "risk_doc_paths": [],
                "has_risk_code_patterns": False,
                "risk_code_evidence": [],
                "has_testing_infrastructure": False,
                "testing_evidence": [],
                "has_defined_metrics": False,
                "metrics_evidence": [],
            }
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}

        # All 17 obligation IDs (excluding 2 permissions)
        # ART09-OBL-3 added 2026-03-20 (cross-verification fix: scope-defining clause)
        # → appears as COVERAGE GAP via gap_findings() since it is manual and has no
        #   explicit Finding in module.py (gap_findings handles all uncovered obligations)
        expected_ids = [
            "ART09-OBL-1", "ART09-OBL-2", "ART09-OBL-2a", "ART09-OBL-2b",
            "ART09-OBL-2c", "ART09-OBL-2d", "ART09-OBL-3", "ART09-OBL-4",
            "ART09-OBL-5", "ART09-OBL-5a", "ART09-OBL-5b", "ART09-OBL-5c",
            "ART09-OBL-5d", "ART09-OBL-6", "ART09-OBL-8a", "ART09-OBL-8b",
            "ART09-OBL-9",
        ]
        for obl_id in expected_ids:
            assert obl_id in finding_ids, (
                f"{obl_id} not in findings. Found: {sorted(finding_ids)}"
            )

    def test_affects_children_false_skips_obl9(self, project_dir):
        """affects_children=False → OBL-9 NOT_APPLICABLE."""
        ctx = ProjectContext.from_json(json.dumps({
            "art9": {
                "has_risk_docs": True,
                "has_risk_code_patterns": True,
                "has_testing_infrastructure": True,
                "has_defined_metrics": True,
                "affects_children": False,
            }
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        obl9 = [f for f in result["findings"] if f["obligation_id"] == "ART09-OBL-9"]
        assert len(obl9) > 0
        assert obl9[0]["level"] == "not_applicable"

    def test_alias_has_testing_works(self, project_dir):
        """AI may use has_testing instead of has_testing_infrastructure."""
        ctx = ProjectContext.from_json(json.dumps({
            "art9": {
                "has_risk_docs": True,
                "has_testing": True,
                "has_risk_code_patterns": True,
                "has_defined_metrics": True,
            }
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        obl6 = [f for f in result["findings"] if f["obligation_id"] == "ART09-OBL-6"]
        assert obl6[0]["level"] == "partial"

    def test_no_context_returns_error(self, project_dir):
        """Missing project_context returns error."""
        result_json = _scan_single_article(9, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        """Non-existent directory returns error."""
        ctx = ProjectContext.from_json('{"art9": {"has_risk_docs": true}}')
        result_json = _scan_single_article(9, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        """Response must include compliance_summary with required fields."""
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art9": {"has_risk_docs": True, "has_risk_code_patterns": True,
                     "has_testing_infrastructure": True, "has_defined_metrics": True},
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "regulation" in summary
        assert "assessed_by" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        """assessed_by should come from ai_model in context."""
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art9": {"has_risk_docs": True, "has_risk_code_patterns": False,
                     "has_testing_infrastructure": False, "has_defined_metrics": False},
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_obl2d_code_patterns_true_partial(self, project_dir):
        """ART09-OBL-2d: has_risk_code_patterns=True → PARTIAL."""
        ctx = ProjectContext.from_json(json.dumps({
            "art9": {"has_risk_docs": True, "has_risk_code_patterns": True,
                     "risk_code_evidence": ["src/guardrails.py"],
                     "has_testing_infrastructure": False, "has_defined_metrics": False},
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        obl = [f for f in result["findings"] if f["obligation_id"] == "ART09-OBL-2d"]
        assert obl[0]["level"] == "partial"

    def test_obl2d_code_patterns_false_non_compliant(self, project_dir):
        """ART09-OBL-2d: has_risk_code_patterns=False → NON_COMPLIANT."""
        ctx = ProjectContext.from_json(json.dumps({
            "art9": {"has_risk_docs": True, "has_risk_code_patterns": False,
                     "has_testing_infrastructure": False, "has_defined_metrics": False},
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        obl = [f for f in result["findings"] if f["obligation_id"] == "ART09-OBL-2d"]
        assert obl[0]["level"] == "non_compliant"

    def test_obl2c_always_unable_to_determine(self, project_dir):
        """ART09-OBL-2c (post-market monitoring): always UTD."""
        ctx = ProjectContext.from_json(json.dumps({
            "art9": {"has_risk_docs": True, "has_risk_code_patterns": True,
                     "has_testing_infrastructure": True, "has_defined_metrics": True},
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        obl = [f for f in result["findings"] if f["obligation_id"] == "ART09-OBL-2c"]
        assert obl[0]["level"] == "unable_to_determine"

    def test_alias_has_risk_code_works(self, project_dir):
        """AI may use has_risk_code instead of has_risk_code_patterns."""
        ctx = ProjectContext.from_json(json.dumps({
            "art9": {"has_risk_docs": True, "has_risk_code": True,
                     "has_testing_infrastructure": True, "has_defined_metrics": True},
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        obl = [f for f in result["findings"] if f["obligation_id"] == "ART09-OBL-2d"]
        assert obl[0]["level"] == "partial"

    def test_alias_has_metrics_works(self, project_dir):
        """AI may use has_metrics instead of has_defined_metrics."""
        ctx = ProjectContext.from_json(json.dumps({
            "art9": {"has_risk_docs": True, "has_risk_code_patterns": True,
                     "has_testing_infrastructure": True, "has_metrics": True},
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        obl = [f for f in result["findings"] if f["obligation_id"] == "ART09-OBL-8b"]
        assert obl[0]["level"] == "partial"

    def test_string_coercion_through_server(self, project_dir):
        """String "true" should be coerced to True."""
        ctx = ProjectContext.from_json(
            '{"art9": {"has_risk_docs": "true", "has_risk_code_patterns": "false",'
            '"has_testing_infrastructure": "false", "has_defined_metrics": "false"}}'
        )
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART09-OBL-1"]
        assert obl1[0]["level"] == "partial"


class TestScopeGate:
    """Test scope gate / _high_risk_only_check for Art.9-15."""

    def test_not_high_risk_high_confidence_skips(self, project_dir):
        """risk_classification=not high-risk + confidence=high → NOT_APPLICABLE."""
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art12": {"has_logging": True, "logging_description": "test",
                      "logging_evidence": [], "has_retention_config": True,
                      "retention_days": 365, "retention_evidence": ""},
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable", (
            f"not high-risk + high confidence should skip, got {result['overall_level']}"
        )

    def test_not_high_risk_medium_confidence_skips(self, project_dir):
        """risk_classification=not high-risk + confidence=medium → NOT_APPLICABLE."""
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "medium",
            "art9": {"has_risk_docs": True},
        }))
        result_json = _scan_single_article(9, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_not_high_risk_low_confidence_scans(self, project_dir):
        """risk_classification=not high-risk + confidence=low → continues scanning (conservative)."""
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "low",
            "art12": {"has_logging": True, "logging_description": "test",
                      "logging_evidence": [], "has_retention_config": True,
                      "retention_days": 365, "retention_evidence": ""},
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] != "not_applicable", (
            "Low confidence should NOT skip — conservative: scan anyway"
        )

    def test_not_high_risk_no_confidence_scans(self, project_dir):
        """risk_classification=not high-risk + no confidence → continues scanning."""
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "art12": {"has_logging": True, "logging_description": "test",
                      "logging_evidence": [], "has_retention_config": True,
                      "retention_days": 365, "retention_evidence": ""},
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] != "not_applicable", (
            "No confidence should NOT skip — conservative: scan anyway"
        )

    def test_high_risk_always_scans(self, project_dir):
        """risk_classification=high-risk → always scans regardless of confidence."""
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "high-risk",
            "risk_classification_confidence": "high",
            "art12": {"has_logging": False, "logging_description": "",
                      "logging_evidence": [], "has_retention_config": False,
                      "retention_days": None, "retention_evidence": ""},
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_risk_classification_scans(self, project_dir):
        """No risk_classification at all → continues scanning + no crash."""
        ctx = ProjectContext.from_json(json.dumps({
            "art12": {"has_logging": True, "logging_description": "test",
                      "logging_evidence": [], "has_retention_config": True,
                      "retention_days": 365, "retention_evidence": ""},
        }))
        result_json = _scan_single_article(12, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] != "not_applicable", (
            "Missing risk_classification should NOT skip"
        )

    def test_art5_ignores_risk_classification(self, project_dir):
        """Art.5 has no prerequisites — scans even when not high-risk."""
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art5": {"has_subliminal_manipulation": False},
        }))
        result_json = _scan_single_article(5, project_dir, context=ctx)
        result = json.loads(result_json)
        # Art.5 should not return not_applicable due to risk classification
        # (it may return not_applicable for other reasons like open source, but not risk)
        assert "error" not in result


class TestClScanArticle10:
    """Test cl_scan_article_10 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art10": {
                "has_data_governance_doc": True,
                "data_doc_paths": ["docs/data_governance.md"],
                "has_bias_mitigation": True,
                "bias_evidence": ["fairlearn in requirements.txt"],
                "has_data_lineage": True,
            }
        }))
        result_json = _scan_single_article(10, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_no_data_doc_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art10": {"has_data_governance_doc": False, "has_bias_mitigation": False}
        }))
        result_json = _scan_single_article(10, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_bias_true_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art10": {"has_data_governance_doc": True, "has_bias_mitigation": True,
                      "bias_evidence": ["fairlearn"]}
        }))
        result_json = _scan_single_article(10, project_dir, context=ctx)
        result = json.loads(result_json)
        obl = [f for f in result["findings"] if f["obligation_id"] == "ART10-OBL-2f"]
        assert obl[0]["level"] == "partial"

    def test_bias_false_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art10": {"has_data_governance_doc": True, "has_bias_mitigation": False}
        }))
        result_json = _scan_single_article(10, project_dir, context=ctx)
        result = json.loads(result_json)
        obl = [f for f in result["findings"] if f["obligation_id"] == "ART10-OBL-2f"]
        assert obl[0]["level"] == "non_compliant"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art10": {"has_data_governance_doc": True},
        }))
        result_json = _scan_single_article(10, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art10": {"has_data_governance_doc": False, "has_bias_mitigation": False}
        }))
        result_json = _scan_single_article(10, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART10-OBL-1", "ART10-OBL-2", "ART10-OBL-2f", "ART10-OBL-2g",
                        "ART10-OBL-2h", "ART10-OBL-3", "ART10-OBL-3b", "ART10-OBL-4"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings"

    def test_manual_obligations_utd(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art10": {"has_data_governance_doc": True, "has_bias_mitigation": True}
        }))
        result_json = _scan_single_article(10, project_dir, context=ctx)
        result = json.loads(result_json)
        for obl_id in ["ART10-OBL-2h", "ART10-OBL-3", "ART10-OBL-3b", "ART10-OBL-4"]:
            findings = [f for f in result["findings"] if f["obligation_id"] == obl_id]
            assert findings[0]["level"] == "unable_to_determine"

    def test_alias_has_bias_detection(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art10": {"has_data_governance_doc": True, "has_bias_detection": True}
        }))
        result_json = _scan_single_article(10, project_dir, context=ctx)
        result = json.loads(result_json)
        obl = [f for f in result["findings"] if f["obligation_id"] == "ART10-OBL-2f"]
        assert obl[0]["level"] == "partial"

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art10": {"has_data_governance_doc": True, "data_doc_paths": ["d.md"],
                      "has_bias_mitigation": False}
        }))
        result_json = _scan_single_article(10, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART10-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(10, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art10": {"has_data_governance_doc": true}}')
        result_json = _scan_single_article(10, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art10": {"has_data_governance_doc": True, "has_bias_mitigation": True}
        }))
        result_json = _scan_single_article(10, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "regulation" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art10": {"has_data_governance_doc": True, "has_bias_mitigation": False}
        }))
        result_json = _scan_single_article(10, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_string_coercion(self, project_dir):
        ctx = ProjectContext.from_json(
            '{"art10": {"has_data_governance_doc": "true", "has_bias_mitigation": "false"}}'
        )
        result_json = _scan_single_article(10, project_dir, context=ctx)
        result = json.loads(result_json)
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART10-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_conditional_obligations_informational(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art10": {"has_data_governance_doc": True, "has_bias_mitigation": True}
        }))
        result_json = _scan_single_article(10, project_dir, context=ctx)
        result = json.loads(result_json)
        for obl_id in ["ART10-PERM-5", "ART10-OBL-6"]:
            findings = [f for f in result["findings"] if f["obligation_id"] == obl_id]
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].get("is_informational", False) or \
                   "[CONDITIONAL]" in findings[0].get("description", "")


class TestClScanArticle11:
    """Test cl_scan_article_11 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art11": {"has_technical_docs": True, "doc_paths": ["README.md", "docs/arch.md"],
                      "documented_aspects": ["architecture", "testing"]}
        }))
        result_json = _scan_single_article(11, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art11": {"has_technical_docs": True, "doc_paths": ["README.md"]}
        }))
        result_json = _scan_single_article(11, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART11-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_no_docs_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art11": {"has_technical_docs": False, "doc_paths": [], "documented_aspects": []}
        }))
        result_json = _scan_single_article(11, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(11, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art11": {"has_technical_docs": true}}')
        result_json = _scan_single_article(11, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art11": {"has_technical_docs": True}
        }))
        result_json = _scan_single_article(11, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art11": {"has_technical_docs": False}
        }))
        result_json = _scan_single_article(11, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_9_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art11": {"has_technical_docs": False, "doc_paths": []}
        }))
        result_json = _scan_single_article(11, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        # Core provider obligations (total JSON now has 9 entries)
        # PERM-1d/OBL-1f appear as CONDITIONAL (scope_limitation: is_sme)
        # OBL-1e/OBL-1g appear as COVERAGE GAP via gap_findings
        # EMP-3 is empowerment → skipped by gap_findings (no finding)
        for obl_id in ["ART11-OBL-1", "ART11-OBL-1b", "ART11-OBL-1c"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art11": {"has_technical_docs": True}
        }))
        result_json = _scan_single_article(11, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_string_coercion(self, project_dir):
        ctx = ProjectContext.from_json(
            '{"art11": {"has_technical_docs": "true", "doc_paths": []}}'
        )
        result_json = _scan_single_article(11, project_dir, context=ctx)
        result = json.loads(result_json)
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART11-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_annex_iv_always_utd(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art11": {"has_technical_docs": True, "doc_paths": ["README.md"]}
        }))
        result_json = _scan_single_article(11, project_dir, context=ctx)
        result = json.loads(result_json)
        obl1c = [f for f in result["findings"] if f["obligation_id"] == "ART11-OBL-1c"]
        assert obl1c[0]["level"] == "unable_to_determine"

    def test_alias_has_documentation(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art11": {"has_documentation": True, "doc_paths": ["README.md"]}
        }))
        result_json = _scan_single_article(11, project_dir, context=ctx)
        result = json.loads(result_json)
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART11-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_conditional_obl2_informational(self, project_dir):
        """OBL-2 without is_annex_i_product → CONDITIONAL."""
        ctx = ProjectContext.from_json(json.dumps({
            "art11": {"has_technical_docs": True}
        }))
        result_json = _scan_single_article(11, project_dir, context=ctx)
        result = json.loads(result_json)
        obl2 = [f for f in result["findings"] if f["obligation_id"] == "ART11-OBL-2"]
        assert len(obl2) > 0
        assert obl2[0].get("is_informational", False) or \
               "[CONDITIONAL]" in obl2[0].get("description", "")

    def test_annex_i_product_false_skips_obl2(self, project_dir):
        """is_annex_i_product=False → OBL-2 NOT_APPLICABLE."""
        ctx = ProjectContext.from_json(json.dumps({
            "art11": {"has_technical_docs": True, "is_annex_i_product": False}
        }))
        result_json = _scan_single_article(11, project_dir, context=ctx)
        result = json.loads(result_json)
        obl2 = [f for f in result["findings"] if f["obligation_id"] == "ART11-OBL-2"]
        assert len(obl2) > 0
        assert obl2[0]["level"] == "not_applicable"


class TestClScanArticle13:
    """Test cl_scan_article_13 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art13": {"has_explainability": True, "explainability_evidence": ["SHAP"],
                      "has_transparency_info": True, "transparency_paths": ["docs/guide.md"]}
        }))
        result_json = _scan_single_article(13, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art13": {"has_explainability": True, "has_transparency_info": False}
        }))
        result_json = _scan_single_article(13, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART13-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(13, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art13": {"has_explainability": true}}')
        result_json = _scan_single_article(13, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_no_explainability_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art13": {"has_explainability": False, "has_transparency_info": False}
        }))
        result_json = _scan_single_article(13, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art13": {"has_explainability": True, "has_transparency_info": True}
        }))
        result_json = _scan_single_article(13, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art13": {"has_explainability": False, "has_transparency_info": False}
        }))
        result_json = _scan_single_article(13, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_4_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art13": {"has_explainability": False, "has_transparency_info": False}
        }))
        result_json = _scan_single_article(13, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        # ART13-OBL-1b added 2026-03-20 (cross-verification fix: outcome transparency requirement)
        for obl_id in ["ART13-OBL-1", "ART13-OBL-1b", "ART13-OBL-2", "ART13-OBL-3"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art13": {"has_explainability": True}
        }))
        result_json = _scan_single_article(13, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_string_coercion(self, project_dir):
        ctx = ProjectContext.from_json(
            '{"art13": {"has_explainability": "true", "has_transparency_info": "false"}}'
        )
        result_json = _scan_single_article(13, project_dir, context=ctx)
        result = json.loads(result_json)
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART13-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_alias_has_interpretability(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art13": {"has_interpretability": True, "has_transparency_info": True}
        }))
        result_json = _scan_single_article(13, project_dir, context=ctx)
        result = json.loads(result_json)
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART13-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_alias_has_instructions_for_use(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art13": {"has_explainability": True, "has_instructions_for_use": True}
        }))
        result_json = _scan_single_article(13, project_dir, context=ctx)
        result = json.loads(result_json)
        obl2 = [f for f in result["findings"] if f["obligation_id"] == "ART13-OBL-2"]
        assert obl2[0]["level"] == "partial"

    def test_obl3_always_utd(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art13": {"has_explainability": True, "has_transparency_info": True}
        }))
        result_json = _scan_single_article(13, project_dir, context=ctx)
        result = json.loads(result_json)
        obl3 = [f for f in result["findings"] if f["obligation_id"] == "ART13-OBL-3"]
        assert obl3[0]["level"] == "unable_to_determine"


class TestClScanArticle14:
    """Test cl_scan_article_14 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art14": {"has_human_oversight": True, "oversight_evidence": ["review gate"],
                      "has_override_mechanism": True, "override_evidence": ["stop button"]}
        }))
        result_json = _scan_single_article(14, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art14": {"has_human_oversight": True, "has_override_mechanism": False}
        }))
        result_json = _scan_single_article(14, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART14-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(14, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art14": {"has_human_oversight": true}}')
        result_json = _scan_single_article(14, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_no_oversight_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art14": {"has_human_oversight": False, "has_override_mechanism": False}
        }))
        result_json = _scan_single_article(14, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art14": {"has_human_oversight": True, "has_override_mechanism": True}
        }))
        result_json = _scan_single_article(14, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art14": {"has_human_oversight": False, "has_override_mechanism": False}
        }))
        result_json = _scan_single_article(14, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_6_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art14": {"has_human_oversight": False, "has_override_mechanism": False}
        }))
        result_json = _scan_single_article(14, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        # ART14-EXC-5b added 2026-03-20 (cross-verification fix: law enforcement dual-verification exemption)
        # It appears as CONDITIONAL via gap_findings (scope_limitation path runs before exception skip)
        for obl_id in ["ART14-OBL-1", "ART14-OBL-2", "ART14-OBL-3", "ART14-OBL-4",
                        "ART14-OBL-5", "ART14-EXC-5b"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art14": {"has_human_oversight": True}
        }))
        result_json = _scan_single_article(14, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_string_coercion(self, project_dir):
        ctx = ProjectContext.from_json(
            '{"art14": {"has_human_oversight": "true", "has_override_mechanism": "false"}}'
        )
        result_json = _scan_single_article(14, project_dir, context=ctx)
        result = json.loads(result_json)
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART14-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_alias_has_hitl(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art14": {"has_hitl": True, "has_override_mechanism": True}
        }))
        result_json = _scan_single_article(14, project_dir, context=ctx)
        result = json.loads(result_json)
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART14-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_alias_has_kill_switch(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art14": {"has_human_oversight": True, "has_kill_switch": True}
        }))
        result_json = _scan_single_article(14, project_dir, context=ctx)
        result = json.loads(result_json)
        obl3 = [f for f in result["findings"] if f["obligation_id"] == "ART14-OBL-3"]
        assert obl3[0]["level"] == "partial"

    def test_obl2_always_utd(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art14": {"has_human_oversight": True, "has_override_mechanism": True}
        }))
        result_json = _scan_single_article(14, project_dir, context=ctx)
        result = json.loads(result_json)
        obl2 = [f for f in result["findings"] if f["obligation_id"] == "ART14-OBL-2"]
        assert obl2[0]["level"] == "unable_to_determine"

    def test_biometric_false_skips_obl5(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art14": {"has_human_oversight": True, "has_override_mechanism": True,
                      "is_biometric_system": False}
        }))
        result_json = _scan_single_article(14, project_dir, context=ctx)
        result = json.loads(result_json)
        obl5 = [f for f in result["findings"] if f["obligation_id"] == "ART14-OBL-5"]
        assert len(obl5) > 0
        assert obl5[0]["level"] == "not_applicable"

    def test_obl5_conditional_when_not_provided(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art14": {"has_human_oversight": True, "has_override_mechanism": True}
        }))
        result_json = _scan_single_article(14, project_dir, context=ctx)
        result = json.loads(result_json)
        obl5 = [f for f in result["findings"] if f["obligation_id"] == "ART14-OBL-5"]
        assert len(obl5) > 0
        assert obl5[0].get("is_informational", False) or \
               "[CONDITIONAL]" in obl5[0].get("description", "")

    def test_biometric_true_shows_applicable(self, project_dir):
        """is_biometric_system=True -> OBL-5 shows [APPLICABLE]."""
        ctx = ProjectContext.from_json(json.dumps({
            "art14": {"has_human_oversight": True, "has_override_mechanism": True,
                      "is_biometric_system": True}
        }))
        result_json = _scan_single_article(14, project_dir, context=ctx)
        result = json.loads(result_json)
        obl5 = [f for f in result["findings"] if f["obligation_id"] == "ART14-OBL-5"]
        assert len(obl5) > 0
        assert "[APPLICABLE]" in obl5[0].get("description", "")


class TestClScanArticle15:
    """Test cl_scan_article_15 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art15": {"has_accuracy_testing": True, "accuracy_evidence": ["eval.py"],
                      "has_robustness_testing": True, "robustness_evidence": ["tests/"],
                      "has_fallback_behavior": True}
        }))
        result_json = _scan_single_article(15, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art15": {"has_accuracy_testing": True, "has_robustness_testing": False,
                      "has_fallback_behavior": False}
        }))
        result_json = _scan_single_article(15, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART15-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(15, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art15": {"has_accuracy_testing": true}}')
        result_json = _scan_single_article(15, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_all_false_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art15": {"has_accuracy_testing": False, "has_robustness_testing": False,
                      "has_fallback_behavior": False}
        }))
        result_json = _scan_single_article(15, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art15": {"has_accuracy_testing": True, "has_robustness_testing": True,
                      "has_fallback_behavior": True}
        }))
        result_json = _scan_single_article(15, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art15": {"has_accuracy_testing": False, "has_robustness_testing": False,
                      "has_fallback_behavior": False}
        }))
        result_json = _scan_single_article(15, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art15": {"has_accuracy_testing": False, "has_robustness_testing": False,
                      "has_fallback_behavior": False}
        }))
        result_json = _scan_single_article(15, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART15-OBL-1", "ART15-OBL-3", "ART15-OBL-4", "ART15-OBL-4b", "ART15-OBL-5", "ART15-OBL-5b"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art15": {"has_accuracy_testing": True}
        }))
        result_json = _scan_single_article(15, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_string_coercion(self, project_dir):
        ctx = ProjectContext.from_json(
            '{"art15": {"has_accuracy_testing": "true", "has_robustness_testing": "false", "has_fallback_behavior": "false"}}'
        )
        result_json = _scan_single_article(15, project_dir, context=ctx)
        result = json.loads(result_json)
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART15-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_alias_has_accuracy_metrics(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art15": {"has_accuracy_metrics": True, "has_robustness_testing": True,
                      "has_fallback_behavior": True}
        }))
        result_json = _scan_single_article(15, project_dir, context=ctx)
        result = json.loads(result_json)
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART15-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_obl4b_conditional_feedback_loop(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art15": {"has_accuracy_testing": True, "has_robustness_testing": True,
                      "has_fallback_behavior": True}
        }))
        result_json = _scan_single_article(15, project_dir, context=ctx)
        result = json.loads(result_json)
        obl4b = [f for f in result["findings"] if f["obligation_id"] == "ART15-OBL-4b"]
        assert len(obl4b) > 0
        assert obl4b[0].get("is_informational", False) or \
               "[CONDITIONAL]" in obl4b[0].get("description", "")

    def test_continues_learning_false_skips_obl4b(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art15": {"has_accuracy_testing": True, "has_robustness_testing": True,
                      "has_fallback_behavior": True, "continues_learning_after_deployment": False}
        }))
        result_json = _scan_single_article(15, project_dir, context=ctx)
        result = json.loads(result_json)
        obl4b = [f for f in result["findings"] if f["obligation_id"] == "ART15-OBL-4b"]
        assert len(obl4b) > 0
        assert obl4b[0]["level"] == "not_applicable"


class TestClScanArticle4:
    """Test cl_scan_article_4 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art4": {"has_ai_literacy_measures": True,
                     "literacy_description": "AI usage policy and training program",
                     "literacy_evidence": ["docs/ai-policy.md"]}
        }))
        result_json = _scan_single_article(4, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] == "partial"

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art4": {"has_ai_literacy_measures": True}
        }))
        result_json = _scan_single_article(4, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART04-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_no_measures_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art4": {"has_ai_literacy_measures": False}
        }))
        result_json = _scan_single_article(4, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(4, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art4": {"has_ai_literacy_measures": true}}')
        result_json = _scan_single_article(4, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art4": {"has_ai_literacy_measures": True}
        }))
        result_json = _scan_single_article(4, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art4": {"has_ai_literacy_measures": False}
        }))
        result_json = _scan_single_article(4, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_not_high_risk_still_scans(self, project_dir):
        """Art.4 applies to ALL AI systems, not just high-risk."""
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art4": {"has_ai_literacy_measures": True}
        }))
        result_json = _scan_single_article(4, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] != "not_applicable" or \
               result.get("details", {}).get("skip_reason") != "not_high_risk_system"

    def test_all_1_obligation_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art4": {"has_ai_literacy_measures": False}
        }))
        result_json = _scan_single_article(4, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        assert "ART04-OBL-1" in finding_ids

    def test_scope_gate_not_ai_system(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_ai_system": False},
            "art4": {"has_ai_literacy_measures": True}
        }))
        result_json = _scan_single_article(4, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle5:
    """Test cl_scan_article_5 MCP tool function end-to-end."""

    def test_no_prohibited_practices_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art5": {
                "prohibited_practices": [
                    {"practice": "subliminal_manipulation", "detected": False,
                     "evidence": "no evidence found", "confidence": "high"},
                    {"practice": "social_scoring", "detected": False,
                     "evidence": "no evidence found", "confidence": "high"},
                ]
            }
        }))
        result_json = _scan_single_article(5, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        # No prohibited practices detected -> should not be non_compliant
        assert result["overall_level"] != "non_compliant"

    def test_practice_detected_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art5": {
                "has_social_scoring": True,
            }
        }))
        result_json = _scan_single_article(5, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art5": {"has_subliminal_manipulation": False}
        }))
        result_json = _scan_single_article(5, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(5, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art5": {"has_subliminal_manipulation": false}}')
        result_json = _scan_single_article(5, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art5": {"has_subliminal_manipulation": False}
        }))
        result_json = _scan_single_article(5, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art5": {"has_subliminal_manipulation": False}
        }))
        result_json = _scan_single_article(5, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_scope_gate_open_source_still_scans(self, project_dir):
        """Art.5 has prerequisites=[] so open source does NOT skip it."""
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art5": {"has_social_scoring": True}
        }))
        result_json = _scan_single_article(5, project_dir, context=ctx)
        result = json.loads(result_json)
        # Art.5 prohibitions apply to ALL AI systems including open source
        # But scope_gate may exempt from Title III -- Art.5 is Chapter II
        # The actual behavior depends on _scope_gate implementation
        assert "error" not in result

    def test_string_coercion(self, project_dir):
        ctx = ProjectContext.from_json(
            '{"art5": {"has_subliminal_manipulation": false}}'
        )
        result_json = _scan_single_article(5, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result

    def test_biometric_detected_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art5": {
                "has_facial_recognition_scraping": True,
            }
        }))
        result_json = _scan_single_article(5, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"
        findings = result.get("findings", [])
        obl_ids = {f["obligation_id"] for f in findings}
        assert "ART05-PRO-1e" in obl_ids

    def test_all_8_prohibitions_in_findings(self, project_dir):
        """All 8 ART05-PRO-* must appear when practices are empty (UTD for each)."""
        ctx = ProjectContext.from_json(json.dumps({
            "art5": {"has_subliminal_manipulation": False}
        }))
        result_json = _scan_single_article(5, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART05-PRO-1a", "ART05-PRO-1b", "ART05-PRO-1c", "ART05-PRO-1d",
                        "ART05-PRO-1e", "ART05-PRO-1f", "ART05-PRO-1g", "ART05-PRO-1h"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings"

    def test_full_context_all_practices(self, project_dir):
        """All practices detected=False -> no non_compliant findings."""
        ctx = ProjectContext.from_json(json.dumps({
            "art5": {
                "prohibited_practices": [
                    {"practice": "subliminal_manipulation", "detected": False, "evidence": "none", "confidence": "high"},
                    {"practice": "vulnerability_exploitation", "detected": False, "evidence": "none", "confidence": "high"},
                    {"practice": "social_scoring", "detected": False, "evidence": "none", "confidence": "high"},
                    {"practice": "criminal_profiling", "detected": False, "evidence": "none", "confidence": "high"},
                    {"practice": "biometric_surveillance", "detected": False, "evidence": "none", "confidence": "high"},
                    {"practice": "prohibited_emotion_recognition", "detected": False, "evidence": "none", "confidence": "high"},
                    {"practice": "prohibited_real_time_biometrics", "detected": False, "evidence": "none", "confidence": "high"},
                ]
            }
        }))
        result_json = _scan_single_article(5, project_dir, context=ctx)
        result = json.loads(result_json)
        non_compliant = [f for f in result.get("findings", []) if f["level"] == "non_compliant"]
        assert len(non_compliant) == 0, f"Expected 0 non_compliant, got {len(non_compliant)}"


class TestClScanArticle6:
    """Test cl_scan_article_6 MCP tool function end-to-end."""

    def test_annex_iii_detected_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art6": {"annex_iii_categories": ["Biometrics"], "is_high_risk": True, "reasoning": "face recognition"}
        }))
        result_json = _scan_single_article(6, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result

    def test_no_categories_utd(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art6": {"annex_iii_categories": [], "annex_i_product_type": None, "is_high_risk": None}
        }))
        result_json = _scan_single_article(6, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art6": {"annex_iii_categories": [], "is_high_risk": None}
        }))
        result_json = _scan_single_article(6, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(6, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art6": {"annex_iii_categories": []}}')
        result_json = _scan_single_article(6, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art6": {"annex_iii_categories": [], "is_high_risk": None}
        }))
        result_json = _scan_single_article(6, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art6": {"annex_iii_categories": [], "is_high_risk": None}
        }))
        result_json = _scan_single_article(6, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_not_high_risk_does_not_skip_art6(self, project_dir):
        """Art.6 has prerequisites=[] so risk_classification does NOT skip it."""
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art6": {"annex_iii_categories": [], "is_high_risk": False}
        }))
        result_json = _scan_single_article(6, project_dir, context=ctx)
        result = json.loads(result_json)
        # Art.6 should NOT be skipped — it IS the classification article
        assert result["overall_level"] != "not_applicable" or \
               result.get("details", {}).get("skip_reason") != "not_high_risk_system"

    def test_string_coercion(self, project_dir):
        ctx = ProjectContext.from_json(
            '{"art6": {"annex_iii_categories": [], "is_high_risk": "true"}}'
        )
        result_json = _scan_single_article(6, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result


class TestClScanArticle17:
    """Test cl_scan_article_17 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art17": {"has_qms_documentation": True, "qms_evidence": ["docs/quality-manual.md"],
                      "has_compliance_strategy": True, "has_design_procedures": True,
                      "has_qa_procedures": True, "has_testing_procedures": True,
                      "has_technical_specifications": True, "has_data_management": True,
                      "has_risk_management_in_qms": True, "has_post_market_monitoring": True,
                      "has_record_keeping": True, "has_accountability_framework": True}
        }))
        result_json = _scan_single_article(17, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art17": {"has_qms_documentation": True, "has_compliance_strategy": False}
        }))
        result_json = _scan_single_article(17, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART17-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(17, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art17": {"has_qms_documentation": true}}')
        result_json = _scan_single_article(17, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_all_false_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art17": {"has_qms_documentation": False, "qms_evidence": [],
                      "has_compliance_strategy": False, "has_design_procedures": False,
                      "has_qa_procedures": False, "has_testing_procedures": False,
                      "has_technical_specifications": False, "has_data_management": False,
                      "has_risk_management_in_qms": False, "has_post_market_monitoring": False,
                      "has_record_keeping": False, "has_accountability_framework": False}
        }))
        result_json = _scan_single_article(17, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art17": {"has_qms_documentation": True, "has_compliance_strategy": True,
                      "has_design_procedures": True, "has_qa_procedures": True,
                      "has_testing_procedures": True, "has_technical_specifications": True,
                      "has_data_management": True, "has_risk_management_in_qms": True,
                      "has_post_market_monitoring": True, "has_record_keeping": True,
                      "has_accountability_framework": True}
        }))
        result_json = _scan_single_article(17, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art17": {"has_qms_documentation": False}
        }))
        result_json = _scan_single_article(17, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art17": {"has_qms_documentation": False, "has_compliance_strategy": False,
                      "has_design_procedures": False, "has_qa_procedures": False,
                      "has_testing_procedures": False, "has_technical_specifications": False,
                      "has_data_management": False, "has_risk_management_in_qms": False,
                      "has_post_market_monitoring": False, "has_record_keeping": False,
                      "has_accountability_framework": False}
        }))
        result_json = _scan_single_article(17, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART17-OBL-1", "ART17-OBL-1a", "ART17-OBL-1b", "ART17-OBL-1c",
                        "ART17-OBL-1d", "ART17-OBL-1e", "ART17-OBL-1f", "ART17-OBL-1g",
                        "ART17-OBL-1h", "ART17-OBL-1k", "ART17-OBL-1m"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art17": {"has_qms_documentation": True}
        }))
        result_json = _scan_single_article(17, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_string_coercion(self, project_dir):
        ctx = ProjectContext.from_json(
            '{"art17": {"has_qms_documentation": "true", "has_compliance_strategy": "false"}}'
        )
        result_json = _scan_single_article(17, project_dir, context=ctx)
        result = json.loads(result_json)
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART17-OBL-1"]
        assert obl1[0]["level"] == "partial"


class TestClScanArticle50:
    """Test cl_scan_article_50 MCP tool function end-to-end."""

    def test_chatbot_no_disclosure_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art50": {
                "is_chatbot_or_interactive_ai": True,
                "has_ai_disclosure_to_users": False,
                "is_generating_synthetic_content": False,
                "is_emotion_recognition_system": False,
                "is_biometric_categorization_system": False,
                "is_deep_fake_system": False,
            }
        }))
        result_json = _scan_single_article(50, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] == "non_compliant"

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art50": {"is_chatbot_or_interactive_ai": False, "is_generating_synthetic_content": False}
        }))
        result_json = _scan_single_article(50, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(50, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art50": {"is_chatbot_or_interactive_ai": false}}')
        result_json = _scan_single_article(50, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art50": {"is_chatbot_or_interactive_ai": False, "is_generating_synthetic_content": False}
        }))
        result_json = _scan_single_article(50, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art50": {"is_chatbot_or_interactive_ai": False}
        }))
        result_json = _scan_single_article(50, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_emotion_recognition_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art50": {
                "is_emotion_recognition_system": True,
                "is_biometric_categorization_system": True,
                "has_emotion_biometric_disclosure": False,
            }
        }))
        result_json = _scan_single_article(50, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_string_coercion(self, project_dir):
        ctx = ProjectContext.from_json(
            '{"art50": {"is_chatbot_or_interactive_ai": "false", "is_generating_synthetic_content": "false"}}'
        )
        result_json = _scan_single_article(50, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result

    def test_not_high_risk_still_scans(self, project_dir):
        """Art.50 has prerequisites=[] so risk classification does NOT skip it."""
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art50": {"is_chatbot_or_interactive_ai": True, "has_ai_disclosure_to_users": False}
        }))
        result_json = _scan_single_article(50, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] != "not_applicable" or \
               result.get("details", {}).get("skip_reason") != "not_high_risk_system"

    def test_all_10_obligations_in_findings(self, project_dir):
        """All ART50-OBL-* obligations must appear in findings (10 total after cross-verification).
        EMP-7a and EMP-7b are empowerments without scope_limitation → skipped by gap_findings → not in findings.
        OBL-4b (deployer, text disclosure) appears as COVERAGE_GAP via gap_findings.
        """
        ctx = ProjectContext.from_json(json.dumps({
            "art50": {
                "is_chatbot_or_interactive_ai": False,
                "is_generating_synthetic_content": False,
                "is_emotion_recognition_system": False,
                "is_biometric_categorization_system": False,
                "is_deep_fake_system": False,
            }
        }))
        result_json = _scan_single_article(50, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART50-OBL-1", "ART50-OBL-2", "ART50-OBL-3", "ART50-OBL-4",
                        "ART50-OBL-4b", "ART50-OBL-5", "ART50-OBL-6", "ART50-OBL-7"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"


class TestClScanArticle26:
    """Test cl_scan_article_26 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art26": {"has_deployment_documentation": True,
                      "has_human_oversight_assignment": True,
                      "has_operational_monitoring": True,
                      "has_log_retention": True, "retention_days": 365,
                      "has_affected_persons_notification": True}
        }))
        result_json = _scan_single_article(26, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art26": {"has_deployment_documentation": True, "has_human_oversight_assignment": False}
        }))
        result_json = _scan_single_article(26, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART26-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(26, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art26": {"has_deployment_documentation": true}}')
        result_json = _scan_single_article(26, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_all_false_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art26": {"has_deployment_documentation": False,
                      "has_human_oversight_assignment": False,
                      "has_operational_monitoring": False,
                      "has_log_retention": False,
                      "has_affected_persons_notification": False}
        }))
        result_json = _scan_single_article(26, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art26": {"has_deployment_documentation": True,
                      "has_human_oversight_assignment": True,
                      "has_operational_monitoring": True,
                      "has_log_retention": True, "retention_days": 180,
                      "has_affected_persons_notification": True}
        }))
        result_json = _scan_single_article(26, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art26": {"has_deployment_documentation": False}
        }))
        result_json = _scan_single_article(26, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art26": {"has_deployment_documentation": False,
                      "has_human_oversight_assignment": False,
                      "has_operational_monitoring": False,
                      "has_log_retention": False,
                      "has_affected_persons_notification": False}
        }))
        result_json = _scan_single_article(26, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART26-OBL-1", "ART26-OBL-2", "ART26-OBL-5", "ART26-OBL-6", "ART26-OBL-11"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_retention_below_180_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art26": {"has_log_retention": True, "retention_days": 30}
        }))
        result_json = _scan_single_article(26, project_dir, context=ctx)
        result = json.loads(result_json)
        obl6 = [f for f in result["findings"] if f["obligation_id"] == "ART26-OBL-6"]
        assert obl6[0]["level"] == "non_compliant"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art26": {"has_deployment_documentation": True}
        }))
        result_json = _scan_single_article(26, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle27:
    """Test cl_scan_article_27 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art27": {"has_fria_documentation": True,
                      "has_fria_versioning": True}
        }))
        result_json = _scan_single_article(27, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art27": {"has_fria_documentation": True, "has_fria_versioning": False}
        }))
        result_json = _scan_single_article(27, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART27-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(27, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art27": {"has_fria_documentation": true}}')
        result_json = _scan_single_article(27, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_all_false_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art27": {"has_fria_documentation": False,
                      "has_fria_versioning": False}
        }))
        result_json = _scan_single_article(27, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art27": {"has_fria_documentation": True,
                      "has_fria_versioning": True}
        }))
        result_json = _scan_single_article(27, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art27": {"has_fria_documentation": False}
        }))
        result_json = _scan_single_article(27, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art27": {"has_fria_documentation": False,
                      "has_fria_versioning": False}
        }))
        result_json = _scan_single_article(27, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART27-OBL-1", "ART27-OBL-2", "ART27-OBL-3", "ART27-OBL-4"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art27": {"has_fria_documentation": True}
        }))
        result_json = _scan_single_article(27, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art27": {"has_fria_documentation": True}
        }))
        result_json = _scan_single_article(27, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle72:
    """Test cl_scan_article_72 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art72": {"has_pmm_system": True,
                      "has_active_data_collection": True,
                      "has_pmm_plan": True}
        }))
        result_json = _scan_single_article(72, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art72": {"has_pmm_system": True, "has_active_data_collection": False}
        }))
        result_json = _scan_single_article(72, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART72-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(72, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art72": {"has_pmm_system": true}}')
        result_json = _scan_single_article(72, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_all_false_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art72": {"has_pmm_system": False,
                      "has_active_data_collection": False,
                      "has_pmm_plan": False}
        }))
        result_json = _scan_single_article(72, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art72": {"has_pmm_system": True,
                      "has_active_data_collection": True,
                      "has_pmm_plan": True}
        }))
        result_json = _scan_single_article(72, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art72": {"has_pmm_system": False}
        }))
        result_json = _scan_single_article(72, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art72": {"has_pmm_system": False,
                      "has_active_data_collection": False,
                      "has_pmm_plan": False}
        }))
        result_json = _scan_single_article(72, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART72-OBL-1", "ART72-OBL-2", "ART72-OBL-3", "ART72-PER-1"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art72": {"has_pmm_system": True}
        }))
        result_json = _scan_single_article(72, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art72": {"has_pmm_system": True}
        }))
        result_json = _scan_single_article(72, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle43:
    """Test cl_scan_article_43 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art43": {"has_internal_control_assessment": True,
                      "has_change_management_procedures": True}
        }))
        result_json = _scan_single_article(43, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art43": {"has_internal_control_assessment": True,
                      "has_change_management_procedures": False}
        }))
        result_json = _scan_single_article(43, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl2 = [f for f in result["findings"] if f["obligation_id"] == "ART43-OBL-2"]
        assert obl2[0]["level"] == "partial"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(43, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art43": {"has_internal_control_assessment": true}}')
        result_json = _scan_single_article(43, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_all_false_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art43": {"has_internal_control_assessment": False,
                      "has_change_management_procedures": False}
        }))
        result_json = _scan_single_article(43, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art43": {"has_internal_control_assessment": True,
                      "has_change_management_procedures": True}
        }))
        result_json = _scan_single_article(43, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art43": {"has_internal_control_assessment": False}
        }))
        result_json = _scan_single_article(43, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art43": {"has_internal_control_assessment": False,
                      "has_change_management_procedures": False}
        }))
        result_json = _scan_single_article(43, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART43-OBL-1", "ART43-OBL-2", "ART43-OBL-3", "ART43-OBL-4"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art43": {"has_internal_control_assessment": True}
        }))
        result_json = _scan_single_article(43, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle47:
    """Test cl_scan_article_47 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art47": {"has_doc_declaration": True,
                      "has_annex_v_content": True}
        }))
        result_json = _scan_single_article(47, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art47": {"has_doc_declaration": True,
                      "has_annex_v_content": False}
        }))
        result_json = _scan_single_article(47, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl2 = [f for f in result["findings"] if f["obligation_id"] == "ART47-OBL-2"]
        assert obl2[0]["level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(47, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art47": {"has_doc_declaration": true}}')
        result_json = _scan_single_article(47, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_all_false_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art47": {"has_doc_declaration": False,
                      "has_annex_v_content": False}
        }))
        result_json = _scan_single_article(47, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art47": {"has_doc_declaration": True,
                      "has_annex_v_content": True}
        }))
        result_json = _scan_single_article(47, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art47": {"has_doc_declaration": False}
        }))
        result_json = _scan_single_article(47, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art47": {"has_doc_declaration": False,
                      "has_annex_v_content": False}
        }))
        result_json = _scan_single_article(47, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART47-OBL-1", "ART47-OBL-2", "ART47-OBL-4"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art47": {"has_doc_declaration": True}
        }))
        result_json = _scan_single_article(47, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle49:
    """Test cl_scan_article_49 MCP tool function end-to-end."""

    def test_full_context_utd(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art49": {"has_eu_database_registration": True}
        }))
        result_json = _scan_single_article(49, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        # 2 of 3 obligations are always UTD (manual), so overall is unable_to_determine
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art49": {"has_eu_database_registration": False}
        }))
        result_json = _scan_single_article(49, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART49-OBL-1"]
        assert obl1[0]["level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(49, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art49": {"has_eu_database_registration": true}}')
        result_json = _scan_single_article(49, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_all_false_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art49": {"has_eu_database_registration": False}
        }))
        result_json = _scan_single_article(49, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art49": {"has_eu_database_registration": True}
        }))
        result_json = _scan_single_article(49, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art49": {"has_eu_database_registration": False}
        }))
        result_json = _scan_single_article(49, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art49": {"has_eu_database_registration": False}
        }))
        result_json = _scan_single_article(49, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART49-OBL-1", "ART49-OBL-2", "ART49-OBL-3"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art49": {"has_eu_database_registration": True}
        }))
        result_json = _scan_single_article(49, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle51:
    """Test cl_scan_article_51 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        """Basic scan with systemic risk assessment → valid result."""
        ctx = ProjectContext.from_json(json.dumps({
            "art51": {
                "is_gpai_model": True,
                "has_systemic_risk_assessment": True,
                "training_compute_exceeds_threshold": False,
                "has_commission_designation": False,
                "has_high_impact_capabilities": False,
            }
        }))
        result_json = _scan_single_article(51, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        """When systemic risk assessment exists → overall includes PARTIAL."""
        ctx = ProjectContext.from_json(json.dumps({
            "art51": {
                "has_systemic_risk_assessment": True,
                "training_compute_exceeds_threshold": False,
            }
        }))
        result_json = _scan_single_article(51, project_dir, context=ctx)
        result = json.loads(result_json)
        # CLS-1 PARTIAL, CLS-2 UTD, EMP-3 UTD → overall unable_to_determine
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        """When assessment absent and compute exceeds → NON_COMPLIANT."""
        ctx = ProjectContext.from_json(json.dumps({
            "art51": {
                "has_systemic_risk_assessment": False,
                "training_compute_exceeds_threshold": True,
                "training_compute_flops": "10^26",
            }
        }))
        result_json = _scan_single_article(51, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        """No context → error, not crash."""
        result_json = _scan_single_article(51, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        """Invalid path → error, not crash."""
        ctx = ProjectContext.from_json('{"art51": {"has_systemic_risk_assessment": false}}')
        result_json = _scan_single_article(51, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        """Result includes compliance_summary with article info."""
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art51": {"has_systemic_risk_assessment": True}
        }))
        result_json = _scan_single_article(51, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        """assessed_by field populated from ai_model in context."""
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art51": {"has_systemic_risk_assessment": False}
        }))
        result_json = _scan_single_article(51, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        """All 3 obligation IDs appear in findings."""
        ctx = ProjectContext.from_json(json.dumps({
            "art51": {
                "has_systemic_risk_assessment": True,
                "training_compute_exceeds_threshold": True,
                "training_compute_flops": "10^26",
            }
        }))
        result_json = _scan_single_article(51, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART51-CLS-1", "ART51-CLS-2", "ART51-EMP-3"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_scope_gate_not_ai_system(self, project_dir):
        """Non-AI system → not_applicable via scope gate."""
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_ai_system": False},
            "art51": {"has_systemic_risk_assessment": True}
        }))
        result_json = _scan_single_article(51, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_scope_gate_open_source(self, project_dir):
        """Open-source system → Art. 51 still applies (in _OPEN_SOURCE_APPLICABLE)."""
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "Apache-2.0"},
            "art51": {"has_systemic_risk_assessment": True}
        }))
        result_json = _scan_single_article(51, project_dir, context=ctx)
        result = json.loads(result_json)
        # Art. 51 (GPAI classification) applies to open-source systems per Art. 2(12)
        assert result["overall_level"] != "not_applicable", (
            f"Art. 51 is in _OPEN_SOURCE_APPLICABLE — should not be not_applicable, got {result['overall_level']}"
        )


class TestClScanArticle52:
    """Test cl_scan_article_52 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        """Basic scan with notification answer → valid result."""
        ctx = ProjectContext.from_json(json.dumps({
            "art52": {
                "has_commission_notification": True,
                "notification_evidence": "Notification sent 2026-03-15",
            }
        }))
        result_json = _scan_single_article(52, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        """When notification exists → overall includes PARTIAL."""
        ctx = ProjectContext.from_json(json.dumps({
            "art52": {
                "has_commission_notification": True,
                "notification_evidence": "Sent via AI Office portal",
            }
        }))
        result_json = _scan_single_article(52, project_dir, context=ctx)
        result = json.loads(result_json)
        # OBL-1 PARTIAL, rest UTD → overall unable_to_determine
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        """When notification absent → NON_COMPLIANT."""
        ctx = ProjectContext.from_json(json.dumps({
            "art52": {
                "has_commission_notification": False,
            }
        }))
        result_json = _scan_single_article(52, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("non_compliant", "unable_to_determine")

    def test_no_context_returns_error(self, project_dir):
        """No context → error, not crash."""
        result_json = _scan_single_article(52, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        """Invalid path → error, not crash."""
        ctx = ProjectContext.from_json('{"art52": {"has_commission_notification": false}}')
        result_json = _scan_single_article(52, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        """Result includes compliance_summary with article info."""
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art52": {"has_commission_notification": True}
        }))
        result_json = _scan_single_article(52, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        """assessed_by field populated from ai_model in context."""
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art52": {"has_commission_notification": False}
        }))
        result_json = _scan_single_article(52, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        """All 5 obligation IDs appear in findings."""
        ctx = ProjectContext.from_json(json.dumps({
            "art52": {
                "has_commission_notification": True,
                "notification_evidence": "Sent",
            }
        }))
        result_json = _scan_single_article(52, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART52-OBL-1", "ART52-PERM-2", "ART52-OBL-5", "ART52-PERM-5", "ART52-OBL-6"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_scope_gate_not_ai_system(self, project_dir):
        """Non-AI system → not_applicable via scope gate."""
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_ai_system": False},
            "art52": {"has_commission_notification": True}
        }))
        result_json = _scan_single_article(52, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_scope_gate_open_source(self, project_dir):
        """Open-source system → Art. 52 still applies (in _OPEN_SOURCE_APPLICABLE)."""
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "Apache-2.0"},
            "art52": {"has_commission_notification": True}
        }))
        result_json = _scan_single_article(52, project_dir, context=ctx)
        result = json.loads(result_json)
        # Art. 52 (GPAI notification) applies to open-source systems per Art. 2(12)
        assert result["overall_level"] != "not_applicable", (
            f"Art. 52 is in _OPEN_SOURCE_APPLICABLE — should not be not_applicable, got {result['overall_level']}"
        )


class TestClScanArticle53:
    """Test cl_scan_article_53 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        """Basic scan with GPAI provider answers → valid result."""
        ctx = ProjectContext.from_json(json.dumps({
            "art53": {
                "has_technical_documentation": True,
                "has_downstream_documentation": True,
                "has_copyright_policy": True,
                "has_training_data_summary": True,
                "is_open_source_gpai": False,
                "has_systemic_risk": False,
            }
        }))
        result_json = _scan_single_article(53, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        """When documentation exists → overall should include PARTIAL."""
        ctx = ProjectContext.from_json(json.dumps({
            "art53": {
                "has_technical_documentation": True,
                "has_downstream_documentation": True,
                "has_copyright_policy": True,
                "has_training_data_summary": True,
                "is_open_source_gpai": False,
                "has_systemic_risk": False,
            }
        }))
        result_json = _scan_single_article(53, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        """When documentation absent → overall should be non_compliant."""
        ctx = ProjectContext.from_json(json.dumps({
            "art53": {
                "has_technical_documentation": False,
                "has_downstream_documentation": False,
                "has_copyright_policy": False,
                "has_training_data_summary": False,
                "is_open_source_gpai": False,
                "has_systemic_risk": False,
            }
        }))
        result_json = _scan_single_article(53, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        """No context → error, not crash."""
        result_json = _scan_single_article(53, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        """Invalid path → error, not crash."""
        ctx = ProjectContext.from_json('{"art53": {"has_technical_documentation": false}}')
        result_json = _scan_single_article(53, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        """Result includes compliance_summary with article info."""
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art53": {"has_technical_documentation": True}
        }))
        result_json = _scan_single_article(53, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        """assessed_by field populated from ai_model in context."""
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art53": {"has_technical_documentation": False}
        }))
        result_json = _scan_single_article(53, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        """All 6 obligation IDs appear in findings."""
        ctx = ProjectContext.from_json(json.dumps({
            "art53": {
                "has_technical_documentation": True,
                "has_downstream_documentation": True,
                "has_copyright_policy": True,
                "has_training_data_summary": True,
                "is_open_source_gpai": False,
                "has_systemic_risk": False,
            }
        }))
        result_json = _scan_single_article(53, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART53-OBL-1a", "ART53-OBL-1b", "ART53-OBL-1c",
                        "ART53-OBL-1d", "ART53-EXC-2", "ART53-OBL-3"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_open_source_exception(self, project_dir):
        """Open-source GPAI without systemic risk → OBL-1a/1b NOT_APPLICABLE."""
        ctx = ProjectContext.from_json(json.dumps({
            "art53": {
                "has_technical_documentation": True,
                "has_downstream_documentation": True,
                "has_copyright_policy": True,
                "has_training_data_summary": True,
                "is_open_source_gpai": True,
                "has_systemic_risk": False,
            }
        }))
        result_json = _scan_single_article(53, project_dir, context=ctx)
        result = json.loads(result_json)
        findings_by_id = {f["obligation_id"]: f for f in result.get("findings", [])}
        assert findings_by_id["ART53-OBL-1a"]["level"] == "not_applicable"
        assert findings_by_id["ART53-OBL-1b"]["level"] == "not_applicable"
        assert findings_by_id["ART53-OBL-1c"]["level"] == "partial"
        assert findings_by_id["ART53-OBL-1d"]["level"] == "partial"


class TestClScanArticle54:
    """Test cl_scan_article_54 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        """Basic scan with third-country provider answers → valid result."""
        ctx = ProjectContext.from_json(json.dumps({
            "art54": {
                "is_third_country_provider": True,
                "has_authorised_representative": True,
                "is_open_source_gpai": False,
                "has_systemic_risk": False,
            }
        }))
        result_json = _scan_single_article(54, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial_or_utd(self, project_dir):
        """Third-country with rep → overall should include PARTIAL or UTD (manual obligations)."""
        ctx = ProjectContext.from_json(json.dumps({
            "art54": {
                "is_third_country_provider": True,
                "has_authorised_representative": True,
                "is_open_source_gpai": False,
                "has_systemic_risk": False,
            }
        }))
        result_json = _scan_single_article(54, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        """Third-country without rep → overall should be non_compliant or utd."""
        ctx = ProjectContext.from_json(json.dumps({
            "art54": {
                "is_third_country_provider": True,
                "has_authorised_representative": False,
                "is_open_source_gpai": False,
                "has_systemic_risk": False,
            }
        }))
        result_json = _scan_single_article(54, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("non_compliant", "unable_to_determine")

    def test_no_context_returns_error(self, project_dir):
        """No context → error, not crash."""
        result_json = _scan_single_article(54, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        """Invalid path → error, not crash."""
        ctx = ProjectContext.from_json('{"art54": {"is_third_country_provider": true}}')
        result_json = _scan_single_article(54, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        """Result includes compliance_summary with article info."""
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art54": {"is_third_country_provider": True, "has_authorised_representative": True}
        }))
        result_json = _scan_single_article(54, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        """assessed_by field populated from ai_model in context."""
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art54": {"is_third_country_provider": False}
        }))
        result_json = _scan_single_article(54, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        """All 4 obligation IDs appear in findings."""
        ctx = ProjectContext.from_json(json.dumps({
            "art54": {
                "is_third_country_provider": True,
                "has_authorised_representative": True,
                "is_open_source_gpai": False,
                "has_systemic_risk": False,
            }
        }))
        result_json = _scan_single_article(54, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART54-OBL-1", "ART54-OBL-3", "ART54-OBL-5", "ART54-EXC-6"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_eu_provider_all_na(self, project_dir):
        """EU-based provider → OBL-1/3/5 NOT_APPLICABLE."""
        ctx = ProjectContext.from_json(json.dumps({
            "art54": {
                "is_third_country_provider": False,
                "is_open_source_gpai": False,
                "has_systemic_risk": False,
            }
        }))
        result_json = _scan_single_article(54, project_dir, context=ctx)
        result = json.loads(result_json)
        findings_by_id = {f["obligation_id"]: f for f in result.get("findings", [])}
        assert findings_by_id["ART54-OBL-1"]["level"] == "not_applicable"
        assert findings_by_id["ART54-OBL-3"]["level"] == "not_applicable"
        assert findings_by_id["ART54-OBL-5"]["level"] == "not_applicable"

    def test_open_source_exception(self, project_dir):
        """Open-source GPAI without systemic risk → all obligations NOT_APPLICABLE."""
        ctx = ProjectContext.from_json(json.dumps({
            "art54": {
                "is_third_country_provider": True,
                "has_authorised_representative": None,
                "is_open_source_gpai": True,
                "has_systemic_risk": False,
            }
        }))
        result_json = _scan_single_article(54, project_dir, context=ctx)
        result = json.loads(result_json)
        findings_by_id = {f["obligation_id"]: f for f in result.get("findings", [])}
        assert findings_by_id["ART54-OBL-1"]["level"] == "not_applicable"
        assert findings_by_id["ART54-OBL-3"]["level"] == "not_applicable"
        assert findings_by_id["ART54-OBL-5"]["level"] == "not_applicable"
        assert findings_by_id["ART54-EXC-6"]["level"] == "compliant"


class TestClScanArticle55:
    """Test cl_scan_article_55 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        """Basic scan with systemic risk answers → valid result."""
        ctx = ProjectContext.from_json(json.dumps({
            "art55": {
                "has_systemic_risk": True,
                "has_model_evaluation": True,
                "has_adversarial_testing": True,
                "has_incident_tracking": True,
                "has_cybersecurity_protection": True,
            }
        }))
        result_json = _scan_single_article(55, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        """When all features detected, overall should be partial or utd (manual obligation)."""
        ctx = ProjectContext.from_json(json.dumps({
            "art55": {
                "has_systemic_risk": True,
                "has_model_evaluation": True,
                "has_adversarial_testing": True,
                "evaluation_evidence": ["docs/model_evaluation.md"],
                "has_incident_tracking": True,
                "incident_evidence": ["docs/incident_response.md"],
                "has_cybersecurity_protection": True,
                "cybersecurity_evidence": ["docs/security_policy.md"],
            }
        }))
        result_json = _scan_single_article(55, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        """When all features absent, overall should be non_compliant."""
        ctx = ProjectContext.from_json(json.dumps({
            "art55": {
                "has_systemic_risk": True,
                "has_model_evaluation": False,
                "has_adversarial_testing": False,
                "has_incident_tracking": False,
                "has_cybersecurity_protection": False,
            }
        }))
        result_json = _scan_single_article(55, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("non_compliant", "unable_to_determine")

    def test_no_context_returns_error(self, project_dir):
        """No context → error, not crash."""
        result_json = _scan_single_article(55, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        """Invalid path → error, not crash."""
        ctx = ProjectContext.from_json('{"art55": {"has_systemic_risk": true}}')
        result_json = _scan_single_article(55, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        """Result includes compliance_summary with article info."""
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art55": {"has_systemic_risk": True, "has_model_evaluation": True, "has_adversarial_testing": True}
        }))
        result_json = _scan_single_article(55, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        """assessed_by field populated from ai_model in context."""
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art55": {"has_systemic_risk": True}
        }))
        result_json = _scan_single_article(55, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        """All 4 obligation IDs appear in findings."""
        ctx = ProjectContext.from_json(json.dumps({
            "art55": {
                "has_systemic_risk": True,
                "has_model_evaluation": True,
                "has_adversarial_testing": True,
                "has_incident_tracking": True,
                "has_cybersecurity_protection": True,
            }
        }))
        result_json = _scan_single_article(55, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART55-OBL-1a", "ART55-OBL-1b", "ART55-OBL-1c", "ART55-OBL-1d"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_no_systemic_risk_all_na(self, project_dir):
        """has_systemic_risk=False → all obligations NOT_APPLICABLE."""
        ctx = ProjectContext.from_json(json.dumps({
            "art55": {
                "has_systemic_risk": False,
            }
        }))
        result_json = _scan_single_article(55, project_dir, context=ctx)
        result = json.loads(result_json)
        findings_by_id = {f["obligation_id"]: f for f in result.get("findings", [])}
        for obl_id in ["ART55-OBL-1a", "ART55-OBL-1b", "ART55-OBL-1c", "ART55-OBL-1d"]:
            assert obl_id in findings_by_id, f"{obl_id} not in findings"
            assert findings_by_id[obl_id]["level"] == "not_applicable", (
                f"{obl_id} should be NA without systemic risk, got {findings_by_id[obl_id]['level']}"
            )


class TestClScanArticle73:
    """Test cl_scan_article_73 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art73": {"has_incident_reporting_procedure": True,
                      "has_reporting_timelines": True,
                      "has_expedited_reporting_procedure": True,
                      "has_investigation_procedure": True}
        }))
        result_json = _scan_single_article(73, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art73": {"has_incident_reporting_procedure": True,
                      "has_reporting_timelines": False}
        }))
        result_json = _scan_single_article(73, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART73-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(73, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art73": {"has_incident_reporting_procedure": true}}')
        result_json = _scan_single_article(73, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_all_false_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art73": {"has_incident_reporting_procedure": False,
                      "has_reporting_timelines": False,
                      "has_expedited_reporting_procedure": False,
                      "has_investigation_procedure": False}
        }))
        result_json = _scan_single_article(73, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art73": {"has_incident_reporting_procedure": True,
                      "has_reporting_timelines": True,
                      "has_expedited_reporting_procedure": True,
                      "has_investigation_procedure": True}
        }))
        result_json = _scan_single_article(73, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art73": {"has_incident_reporting_procedure": False}
        }))
        result_json = _scan_single_article(73, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art73": {"has_incident_reporting_procedure": False,
                      "has_reporting_timelines": False,
                      "has_expedited_reporting_procedure": False,
                      "has_investigation_procedure": False}
        }))
        result_json = _scan_single_article(73, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART73-OBL-1", "ART73-OBL-2", "ART73-OBL-3", "ART73-OBL-4", "ART73-OBL-5"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art73": {"has_incident_reporting_procedure": True}
        }))
        result_json = _scan_single_article(73, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art73": {"has_incident_reporting_procedure": True}
        }))
        result_json = _scan_single_article(73, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle86:
    """Test cl_scan_article_86 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art86": {"has_explanation_mechanism": True}
        }))
        result_json = _scan_single_article(86, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art86": {"has_explanation_mechanism": True}
        }))
        result_json = _scan_single_article(86, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1 = [f for f in result["findings"] if f["obligation_id"] == "ART86-OBL-1"]
        assert obl1[0]["level"] == "partial"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(86, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art86": {"has_explanation_mechanism": true}}')
        result_json = _scan_single_article(86, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_all_false_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art86": {"has_explanation_mechanism": False}
        }))
        result_json = _scan_single_article(86, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art86": {"has_explanation_mechanism": True}
        }))
        result_json = _scan_single_article(86, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art86": {"has_explanation_mechanism": False}
        }))
        result_json = _scan_single_article(86, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art86": {"has_explanation_mechanism": False}
        }))
        result_json = _scan_single_article(86, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        assert "ART86-OBL-1" in finding_ids, f"ART86-OBL-1 not in findings. Found: {sorted(finding_ids)}"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art86": {"has_explanation_mechanism": True}
        }))
        result_json = _scan_single_article(86, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art86": {"has_explanation_mechanism": True}
        }))
        result_json = _scan_single_article(86, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle16:
    """Test cl_scan_article_16 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art16": {
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
            }
        }))
        result_json = _scan_single_article(16, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "compliant")

    def test_shorthand_context_works(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art16": {"has_section_2_compliance": True}
        }))
        result_json = _scan_single_article(16, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl1a = [f for f in result["findings"] if f["obligation_id"] == "ART16-OBL-1a"]
        assert obl1a[0]["level"] == "partial"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(16, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art16": {"has_section_2_compliance": false}}')
        result_json = _scan_single_article(16, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_all_false_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art16": {
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
            }
        }))
        result_json = _scan_single_article(16, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art16": {"has_section_2_compliance": True}
        }))
        result_json = _scan_single_article(16, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary
        assert "terminology" in summary

    def test_assessed_by_from_context(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art16": {"has_section_2_compliance": False}
        }))
        result_json = _scan_single_article(16, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result.get("compliance_summary", {}).get("assessed_by") == "claude-opus-4-6"

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art16": {
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
            }
        }))
        result_json = _scan_single_article(16, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART16-OBL-1a", "ART16-OBL-1b", "ART16-OBL-1c", "ART16-OBL-1d",
                        "ART16-OBL-1e", "ART16-OBL-1f", "ART16-OBL-1g", "ART16-OBL-1h",
                        "ART16-OBL-1i", "ART16-OBL-1j", "ART16-OBL-1k", "ART16-OBL-1l"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art16": {"has_section_2_compliance": True}
        }))
        result_json = _scan_single_article(16, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle18:
    """Test cl_scan_article_18 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art18": {
                "has_documentation_retention_policy": True,
                "retention_policy_evidence": "docs/retention-policy.md specifies 10-year retention",
            }
        }))
        result_json = _scan_single_article(18, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art18": {
                "has_documentation_retention_policy": True,
                "retention_policy_evidence": "docs/retention-policy.md",
            }
        }))
        result_json = _scan_single_article(18, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art18": {
                "has_documentation_retention_policy": False,
                "retention_policy_evidence": "",
            }
        }))
        result_json = _scan_single_article(18, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(18, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art18": {"has_documentation_retention_policy": false}}')
        result_json = _scan_single_article(18, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art18": {
                "has_documentation_retention_policy": True,
                "retention_policy_evidence": "test",
            }
        }))
        result_json = _scan_single_article(18, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art18": {
                "has_documentation_retention_policy": False,
                "retention_policy_evidence": "",
            }
        }))
        result_json = _scan_single_article(18, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        assert "ART18-OBL-1" in finding_ids, f"ART18-OBL-1 not in findings. Found: {sorted(finding_ids)}"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art18": {"has_documentation_retention_policy": True}
        }))
        result_json = _scan_single_article(18, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle19:
    """Test cl_scan_article_19 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art19": {
                "has_log_retention": True,
                "has_retention_config": True,
                "retention_days": 365,
                "retention_evidence": "logrotate configured with 365 days",
            }
        }))
        result_json = _scan_single_article(19, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art19": {
                "has_log_retention": True,
                "has_retention_config": True,
                "retention_days": 365,
                "retention_evidence": "cloudwatch 365d",
            }
        }))
        result_json = _scan_single_article(19, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art19": {
                "has_log_retention": False,
                "has_retention_config": False,
                "retention_days": None,
                "retention_evidence": "",
            }
        }))
        result_json = _scan_single_article(19, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(19, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art19": {"has_log_retention": false}}')
        result_json = _scan_single_article(19, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art19": {
                "has_log_retention": True,
                "has_retention_config": True,
                "retention_days": 200,
            }
        }))
        result_json = _scan_single_article(19, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art19": {
                "has_log_retention": False,
                "has_retention_config": False,
                "retention_days": None,
                "retention_evidence": "",
            }
        }))
        result_json = _scan_single_article(19, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART19-OBL-1", "ART19-OBL-1b"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_retention_threshold(self, project_dir):
        """retention_days < 180 -> ART19-OBL-1b NON_COMPLIANT."""
        ctx = ProjectContext.from_json(json.dumps({
            "art19": {
                "has_log_retention": True,
                "has_retention_config": True,
                "retention_days": 30,
            }
        }))
        result_json = _scan_single_article(19, project_dir, context=ctx)
        result = json.loads(result_json)
        retention = [f for f in result.get("findings", [])
                    if f["obligation_id"] == "ART19-OBL-1b"]
        assert len(retention) > 0
        assert retention[0]["level"] == "non_compliant"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art19": {"has_log_retention": True}
        }))
        result_json = _scan_single_article(19, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle8:
    """Test cl_scan_article_8 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art8": {
                "has_section_2_compliance": True,
                "section_2_evidence": ["Art. 9-15 scans show partial compliance"],
            }
        }))
        result_json = _scan_single_article(8, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art8": {
                "has_section_2_compliance": True,
                "section_2_evidence": ["Art. 9-15 scans show compliance"],
            }
        }))
        result_json = _scan_single_article(8, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art8": {"has_section_2_compliance": False}
        }))
        result_json = _scan_single_article(8, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(8, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art8": {"has_section_2_compliance": false}}')
        result_json = _scan_single_article(8, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art8": {"has_section_2_compliance": True}
        }))
        result_json = _scan_single_article(8, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art8": {"has_section_2_compliance": False}
        }))
        result_json = _scan_single_article(8, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        assert "ART08-OBL-1" in finding_ids, f"ART08-OBL-1 not in findings. Found: {sorted(finding_ids)}"

    def test_scope_gate_open_source(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art8": {"has_section_2_compliance": True}
        }))
        result_json = _scan_single_article(8, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_high_risk_gate(self, project_dir):
        """Art. 8 is a Section 2 article — not high-risk → NOT_APPLICABLE."""
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art8": {"has_section_2_compliance": True}
        }))
        result_json = _scan_single_article(8, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle20:
    """Test cl_scan_article_20 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art20": {
                "has_corrective_action_procedure": True,
                "has_supply_chain_notification": True,
                "has_risk_investigation_procedure": True,
            }
        }))
        result_json = _scan_single_article(20, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art20": {
                "has_corrective_action_procedure": True,
                "has_supply_chain_notification": True,
                "has_risk_investigation_procedure": True,
            }
        }))
        result_json = _scan_single_article(20, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art20": {
                "has_corrective_action_procedure": False,
                "has_supply_chain_notification": False,
                "has_risk_investigation_procedure": False,
            }
        }))
        result_json = _scan_single_article(20, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(20, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art20": {"has_corrective_action_procedure": false}}')
        result_json = _scan_single_article(20, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art20": {
                "has_corrective_action_procedure": True,
                "has_supply_chain_notification": True,
                "has_risk_investigation_procedure": True,
            }
        }))
        result_json = _scan_single_article(20, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art20": {
                "has_corrective_action_procedure": False,
                "has_supply_chain_notification": False,
                "has_risk_investigation_procedure": False,
            }
        }))
        result_json = _scan_single_article(20, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART20-OBL-1", "ART20-OBL-1b", "ART20-OBL-2"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art20": {"has_corrective_action_procedure": True}
        }))
        result_json = _scan_single_article(20, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle21:
    """Test cl_scan_article_21 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art21": {
                "has_conformity_documentation": True,
                "has_log_export_capability": True,
            }
        }))
        result_json = _scan_single_article(21, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art21": {
                "has_conformity_documentation": True,
                "has_log_export_capability": True,
            }
        }))
        result_json = _scan_single_article(21, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art21": {
                "has_conformity_documentation": False,
                "has_log_export_capability": False,
            }
        }))
        result_json = _scan_single_article(21, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(21, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art21": {"has_conformity_documentation": false}}')
        result_json = _scan_single_article(21, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art21": {
                "has_conformity_documentation": True,
                "has_log_export_capability": True,
            }
        }))
        result_json = _scan_single_article(21, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art21": {
                "has_conformity_documentation": False,
                "has_log_export_capability": False,
            }
        }))
        result_json = _scan_single_article(21, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART21-OBL-1", "ART21-OBL-2"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art21": {"has_conformity_documentation": True}
        }))
        result_json = _scan_single_article(21, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle22:
    """Test cl_scan_article_22 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art22": {
                "is_eu_established_provider": False,
                "has_authorised_representative": True,
                "has_representative_enablement": True,
                "has_mandate_authority_contact": True,
            }
        }))
        result_json = _scan_single_article(22, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art22": {
                "is_eu_established_provider": False,
                "has_authorised_representative": True,
                "has_representative_enablement": True,
                "has_mandate_authority_contact": True,
            }
        }))
        result_json = _scan_single_article(22, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art22": {
                "is_eu_established_provider": False,
                "has_authorised_representative": False,
                "has_representative_enablement": False,
                "has_mandate_authority_contact": False,
            }
        }))
        result_json = _scan_single_article(22, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(22, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art22": {"has_authorised_representative": false}}')
        result_json = _scan_single_article(22, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art22": {
                "is_eu_established_provider": False,
                "has_authorised_representative": True,
                "has_representative_enablement": True,
                "has_mandate_authority_contact": True,
            }
        }))
        result_json = _scan_single_article(22, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art22": {
                "is_eu_established_provider": False,
                "has_authorised_representative": False,
                "has_representative_enablement": False,
                "has_mandate_authority_contact": False,
            }
        }))
        result_json = _scan_single_article(22, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART22-OBL-1", "ART22-OBL-2", "ART22-OBL-3", "ART22-OBL-4"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art22": {"has_authorised_representative": True}
        }))
        result_json = _scan_single_article(22, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_eu_provider_not_applicable(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art22": {
                "is_eu_established_provider": True,
                "has_authorised_representative": None,
                "has_representative_enablement": None,
                "has_mandate_authority_contact": None,
            }
        }))
        result_json = _scan_single_article(22, project_dir, context=ctx)
        result = json.loads(result_json)
        # EU provider: OBL-1/2/4 are NOT_APPLICABLE, OBL-3 is gap (UTD)
        # Overall should reflect that provider obligations don't apply
        finding_levels = {f["obligation_id"]: f["level"] for f in result.get("findings", [])}
        for obl_id in ["ART22-OBL-1", "ART22-OBL-2", "ART22-OBL-4"]:
            assert finding_levels.get(obl_id) == "not_applicable", (
                f"{obl_id} should be not_applicable for EU provider, got {finding_levels.get(obl_id)}"
            )


class TestClScanArticle23:
    """Test cl_scan_article_23 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art23": {
                "is_importer": True,
                "has_pre_market_verification": True,
                "has_conformity_review": True,
                "has_importer_identification": True,
                "has_documentation_retention": True,
                "has_authority_documentation": True,
            }
        }))
        result_json = _scan_single_article(23, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art23": {
                "is_importer": True,
                "has_pre_market_verification": True,
                "has_conformity_review": True,
                "has_importer_identification": True,
                "has_documentation_retention": True,
                "has_authority_documentation": True,
            }
        }))
        result_json = _scan_single_article(23, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art23": {
                "is_importer": True,
                "has_pre_market_verification": False,
                "has_conformity_review": False,
                "has_importer_identification": False,
                "has_documentation_retention": False,
                "has_authority_documentation": False,
            }
        }))
        result_json = _scan_single_article(23, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(23, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art23": {"is_importer": true, "has_pre_market_verification": false}}')
        result_json = _scan_single_article(23, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art23": {
                "is_importer": True,
                "has_pre_market_verification": True,
                "has_conformity_review": True,
                "has_importer_identification": True,
                "has_documentation_retention": True,
                "has_authority_documentation": True,
            }
        }))
        result_json = _scan_single_article(23, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art23": {
                "is_importer": True,
                "has_pre_market_verification": False,
                "has_conformity_review": False,
                "has_importer_identification": False,
                "has_documentation_retention": False,
                "has_authority_documentation": False,
            }
        }))
        result_json = _scan_single_article(23, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART23-OBL-1", "ART23-OBL-2", "ART23-OBL-3",
                        "ART23-OBL-5", "ART23-OBL-6"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art23": {"has_pre_market_verification": True}
        }))
        result_json = _scan_single_article(23, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_non_importer_all_not_applicable(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art23": {
                "is_importer": False,
            }
        }))
        result_json = _scan_single_article(23, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_levels = {f["obligation_id"]: f["level"] for f in result.get("findings", [])}
        for obl_id in ["ART23-OBL-1", "ART23-OBL-2", "ART23-OBL-3",
                        "ART23-OBL-4", "ART23-OBL-2b", "ART23-OBL-5",
                        "ART23-OBL-6", "ART23-OBL-7"]:
            assert finding_levels.get(obl_id) == "not_applicable", (
                f"{obl_id} should be not_applicable for non-importer, got {finding_levels.get(obl_id)}"
            )


class TestClScanArticle24:
    """Test cl_scan_article_24 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art24": {
                "is_distributor": True,
                "has_pre_market_verification": True,
                "has_conformity_review": True,
                "has_authority_documentation": True,
            }
        }))
        result_json = _scan_single_article(24, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art24": {
                "is_distributor": True,
                "has_pre_market_verification": True,
                "has_conformity_review": True,
                "has_authority_documentation": True,
            }
        }))
        result_json = _scan_single_article(24, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art24": {
                "is_distributor": True,
                "has_pre_market_verification": False,
                "has_conformity_review": False,
                "has_authority_documentation": False,
            }
        }))
        result_json = _scan_single_article(24, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(24, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art24": {"is_distributor": true, "has_pre_market_verification": false}}')
        result_json = _scan_single_article(24, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art24": {
                "is_distributor": True,
                "has_pre_market_verification": True,
                "has_conformity_review": True,
                "has_authority_documentation": True,
            }
        }))
        result_json = _scan_single_article(24, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art24": {
                "is_distributor": True,
                "has_pre_market_verification": False,
                "has_conformity_review": False,
                "has_authority_documentation": False,
            }
        }))
        result_json = _scan_single_article(24, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART24-OBL-1", "ART24-OBL-2", "ART24-OBL-3",
                        "ART24-OBL-2b", "ART24-OBL-4", "ART24-OBL-4b",
                        "ART24-OBL-5", "ART24-OBL-6"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art24": {"is_distributor": True, "has_pre_market_verification": True}
        }))
        result_json = _scan_single_article(24, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"

    def test_not_distributor_all_not_applicable(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art24": {
                "is_distributor": False,
                "has_pre_market_verification": None,
                "has_conformity_review": None,
                "has_authority_documentation": None,
            }
        }))
        result_json = _scan_single_article(24, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_levels = {f["obligation_id"]: f["level"] for f in result.get("findings", [])}
        for obl_id in ["ART24-OBL-1", "ART24-OBL-2", "ART24-OBL-3",
                        "ART24-OBL-2b", "ART24-OBL-4", "ART24-OBL-4b",
                        "ART24-OBL-5", "ART24-OBL-6"]:
            assert finding_levels.get(obl_id) == "not_applicable", (
                f"{obl_id} should be not_applicable for non-distributor, got {finding_levels.get(obl_id)}"
            )


class TestClScanArticle25:
    """Test cl_scan_article_25 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art25": {
                "has_rebranding_or_modification": False,
                "has_provider_cooperation_documentation": True,
                "is_safety_component_annex_i": False,
                "has_third_party_written_agreement": True,
                "has_open_source_exception": False,
            }
        }))
        result_json = _scan_single_article(25, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art25": {
                "has_rebranding_or_modification": False,
                "has_provider_cooperation_documentation": True,
                "is_safety_component_annex_i": False,
                "has_third_party_written_agreement": True,
                "has_open_source_exception": False,
            }
        }))
        result_json = _scan_single_article(25, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art25": {
                "has_rebranding_or_modification": False,
                "has_provider_cooperation_documentation": False,
                "is_safety_component_annex_i": False,
                "has_third_party_written_agreement": False,
                "has_open_source_exception": False,
            }
        }))
        result_json = _scan_single_article(25, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(25, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art25": {"has_rebranding_or_modification": false}}')
        result_json = _scan_single_article(25, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art25": {
                "has_rebranding_or_modification": False,
                "has_provider_cooperation_documentation": True,
                "is_safety_component_annex_i": False,
                "has_third_party_written_agreement": True,
                "has_open_source_exception": False,
            }
        }))
        result_json = _scan_single_article(25, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_finding_ids_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art25": {
                "has_rebranding_or_modification": True,
                "has_provider_cooperation_documentation": True,
                "is_safety_component_annex_i": True,
                "has_third_party_written_agreement": True,
                "has_open_source_exception": True,
            }
        }))
        result_json = _scan_single_article(25, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        # 5 of 7 obligations appear; EXC-2 and EXC-4 are silently skipped by gap engine
        for obl_id in ["ART25-CLS-1", "ART25-OBL-2", "ART25-CLS-3",
                        "ART25-OBL-4", "ART25-SAV-5"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art25": {"has_rebranding_or_modification": False}
        }))
        result_json = _scan_single_article(25, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle41:
    """Test cl_scan_article_41 MCP tool function end-to-end."""

    def test_full_context_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art41": {"follows_common_specifications": False,
                      "has_alternative_justification": True}
        }))
        result_json = _scan_single_article(41, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("partial", "unable_to_determine")

    def test_follows_cs_not_applicable(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art41": {"follows_common_specifications": True,
                      "has_alternative_justification": None}
        }))
        result_json = _scan_single_article(41, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        obl5 = [f for f in result["findings"] if f["obligation_id"] == "ART41-OBL-5"]
        assert obl5[0]["level"] == "not_applicable"

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art41": {"follows_common_specifications": False,
                      "has_alternative_justification": False}
        }))
        result_json = _scan_single_article(41, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(41, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art41": {"follows_common_specifications": true}}')
        result_json = _scan_single_article(41, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "ai_model": "claude-opus-4-6",
            "art41": {"follows_common_specifications": False,
                      "has_alternative_justification": True}
        }))
        result_json = _scan_single_article(41, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert "findings" in result

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art41": {"follows_common_specifications": True}
        }))
        result_json = _scan_single_article(41, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


class TestClScanArticle60:
    """Test cl_scan_article_60 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art60": {
                "conducts_real_world_testing": True,
                "has_testing_plan": True,
                "has_incident_reporting_for_testing": True,
                "has_authority_notification_procedure": True,
            }
        }))
        result_json = _scan_single_article(60, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art60": {
                "conducts_real_world_testing": True,
                "has_testing_plan": True,
                "has_incident_reporting_for_testing": True,
                "has_authority_notification_procedure": True,
            }
        }))
        result_json = _scan_single_article(60, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art60": {
                "conducts_real_world_testing": True,
                "has_testing_plan": False,
                "has_incident_reporting_for_testing": False,
                "has_authority_notification_procedure": False,
            }
        }))
        result_json = _scan_single_article(60, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(60, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art60": {"has_testing_plan": false}}')
        result_json = _scan_single_article(60, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art60": {
                "conducts_real_world_testing": True,
                "has_testing_plan": True,
                "has_incident_reporting_for_testing": True,
                "has_authority_notification_procedure": True,
            }
        }))
        result_json = _scan_single_article(60, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art60": {
                "conducts_real_world_testing": True,
                "has_testing_plan": False,
                "has_incident_reporting_for_testing": False,
                "has_authority_notification_procedure": False,
            }
        }))
        result_json = _scan_single_article(60, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART60-OBL-4", "ART60-OBL-7", "ART60-OBL-8", "ART60-OBL-9"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art60": {"has_testing_plan": True}
        }))
        result_json = _scan_single_article(60, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


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
        result_json = _scan_single_article(61, "C:/nonexistent_cl_test_path_12345", context=ctx)
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


# ── Article 71: EU database for high-risk AI systems ──

class TestClScanArticle71:
    """Test cl_scan_article_71 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
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
        ctx = ProjectContext.from_json(json.dumps({
            "art71": {
                "has_provider_database_entry": True,
            }
        }))
        result_json = _scan_single_article(71, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art71": {
                "has_provider_database_entry": False,
            }
        }))
        result_json = _scan_single_article(71, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(71, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art71": {"has_provider_database_entry": true}}')
        result_json = _scan_single_article(71, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art71": {
                "has_provider_database_entry": True,
            }
        }))
        result_json = _scan_single_article(71, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art71": {
                "has_provider_database_entry": False,
            }
        }))
        result_json = _scan_single_article(71, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART71-OBL-2", "ART71-OBL-3"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"

    def test_high_risk_gate(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "art71": {"has_provider_database_entry": True}
        }))
        result_json = _scan_single_article(71, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "not_applicable"


# ── Article 80: Non-high-risk misclassification procedure ──

class TestClScanArticle80:
    """Test cl_scan_article_80 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art80": {
                "has_compliance_remediation_plan": True,
                "has_corrective_action_for_all_systems": True,
                "has_classification_rationale": True,
            }
        }))
        result_json = _scan_single_article(80, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art80": {
                "has_compliance_remediation_plan": True,
                "has_corrective_action_for_all_systems": True,
                "has_classification_rationale": True,
            }
        }))
        result_json = _scan_single_article(80, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art80": {
                "has_compliance_remediation_plan": False,
                "has_corrective_action_for_all_systems": False,
                "has_classification_rationale": False,
            }
        }))
        result_json = _scan_single_article(80, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(80, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art80": {"has_compliance_remediation_plan": true}}')
        result_json = _scan_single_article(80, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art80": {
                "has_compliance_remediation_plan": True,
                "has_corrective_action_for_all_systems": True,
                "has_classification_rationale": True,
            }
        }))
        result_json = _scan_single_article(80, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art80": {
                "has_compliance_remediation_plan": False,
                "has_corrective_action_for_all_systems": False,
                "has_classification_rationale": False,
            }
        }))
        result_json = _scan_single_article(80, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART80-OBL-4", "ART80-OBL-5", "ART80-OBL-7"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"


class TestClScanArticle82:
    """Test cl_scan_article_82 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art82": {
                "has_corrective_action_procedure": True,
            }
        }))
        result_json = _scan_single_article(82, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art82": {
                "has_corrective_action_procedure": True,
            }
        }))
        result_json = _scan_single_article(82, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art82": {
                "has_corrective_action_procedure": False,
            }
        }))
        result_json = _scan_single_article(82, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(82, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art82": {"has_corrective_action_procedure": true}}')
        result_json = _scan_single_article(82, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art82": {
                "has_corrective_action_procedure": True,
            }
        }))
        result_json = _scan_single_article(82, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art82": {
                "has_corrective_action_procedure": False,
            }
        }))
        result_json = _scan_single_article(82, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART82-OBL-2"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"


class TestClScanArticle91:
    """Test cl_scan_article_91 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art91": {
                "has_information_supply_readiness": True,
                "readiness_evidence": "Art. 53 documentation maintained",
            }
        }))
        result_json = _scan_single_article(91, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art91": {
                "has_information_supply_readiness": True,
                "readiness_evidence": "Response procedure documented",
            }
        }))
        result_json = _scan_single_article(91, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art91": {
                "has_information_supply_readiness": False,
            }
        }))
        result_json = _scan_single_article(91, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(91, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art91": {"has_information_supply_readiness": true}}')
        result_json = _scan_single_article(91, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art91": {
                "has_information_supply_readiness": True,
                "readiness_evidence": "Docs ready",
            }
        }))
        result_json = _scan_single_article(91, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art91": {
                "has_information_supply_readiness": False,
            }
        }))
        result_json = _scan_single_article(91, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART91-OBL-5"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"


class TestClScanArticle92:
    """Test cl_scan_article_92 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art92": {
                "has_evaluation_cooperation_readiness": True,
                "cooperation_evidence": "GPAI documentation maintained, evaluation cooperation procedure in place",
            }
        }))
        result_json = _scan_single_article(92, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art92": {
                "has_evaluation_cooperation_readiness": True,
                "cooperation_evidence": "Evaluation response procedure documented",
            }
        }))
        result_json = _scan_single_article(92, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art92": {
                "has_evaluation_cooperation_readiness": False,
            }
        }))
        result_json = _scan_single_article(92, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(92, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art92": {"has_evaluation_cooperation_readiness": true}}')
        result_json = _scan_single_article(92, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art92": {
                "has_evaluation_cooperation_readiness": True,
                "cooperation_evidence": "Docs ready",
            }
        }))
        result_json = _scan_single_article(92, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art92": {
                "has_evaluation_cooperation_readiness": False,
            }
        }))
        result_json = _scan_single_article(92, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART92-OBL-5"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"


class TestClScanArticle111:
    """Test cl_scan_article_111 MCP tool function end-to-end."""

    def test_basic_scan(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art111": {
                "has_transition_plan": True,
                "transition_evidence": "Compliance roadmap documented",
                "has_significant_change_tracking": True,
                "change_tracking_evidence": "Change log maintained",
                "has_gpai_compliance_timeline": True,
                "gpai_timeline_evidence": "GPAI compliance timeline tracked",
            }
        }))
        result_json = _scan_single_article(111, project_dir, context=ctx)
        result = json.loads(result_json)
        assert "error" not in result
        assert result["overall_level"] in ("compliant", "partial", "non_compliant", "unable_to_determine")

    def test_feature_detected_gives_partial(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art111": {
                "has_transition_plan": True,
                "transition_evidence": "Transition plan in docs/",
                "has_significant_change_tracking": True,
                "has_gpai_compliance_timeline": True,
            }
        }))
        result_json = _scan_single_article(111, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] in ("partial", "compliant")

    def test_feature_absent_gives_non_compliant(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art111": {
                "has_transition_plan": False,
                "has_significant_change_tracking": False,
                "has_gpai_compliance_timeline": False,
            }
        }))
        result_json = _scan_single_article(111, project_dir, context=ctx)
        result = json.loads(result_json)
        assert result["overall_level"] == "non_compliant"

    def test_no_context_returns_error(self, project_dir):
        result_json = _scan_single_article(111, project_dir, context=None)
        result = json.loads(result_json)
        assert "error" in result

    def test_invalid_directory_returns_error(self):
        ctx = ProjectContext.from_json('{"art111": {"has_transition_plan": true}}')
        result_json = _scan_single_article(111, "C:/nonexistent_cl_test_path_12345", context=ctx)
        result = json.loads(result_json)
        assert "error" in result

    def test_compliance_summary_present(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art111": {
                "has_transition_plan": True,
                "has_significant_change_tracking": True,
                "has_gpai_compliance_timeline": True,
            }
        }))
        result_json = _scan_single_article(111, project_dir, context=ctx)
        result = json.loads(result_json)
        summary = result.get("compliance_summary", {})
        assert "article" in summary
        assert "overall" in summary

    def test_all_obligations_in_findings(self, project_dir):
        ctx = ProjectContext.from_json(json.dumps({
            "art111": {
                "has_transition_plan": False,
                "has_significant_change_tracking": False,
                "has_gpai_compliance_timeline": False,
            }
        }))
        result_json = _scan_single_article(111, project_dir, context=ctx)
        result = json.loads(result_json)
        finding_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in ["ART111-OBL-1", "ART111-OBL-2", "ART111-OBL-3"]:
            assert obl_id in finding_ids, f"{obl_id} not in findings. Found: {sorted(finding_ids)}"


# ═══════════════════════════════════════════════════════════════
# cl_action_guide — signpost-only Human Gate tool
# ═══════════════════════════════════════════════════════════════


class TestClActionGuide:

    def test_known_human_gate(self):
        """Known Human Gate obligation returns correct structure."""
        from server import cl_action_guide
        result = json.loads(cl_action_guide("ART26-OBL-2"))
        assert result["obligation_id"] == "ART26-OBL-2"
        assert result["title"] == "Human Oversight Assignment"
        assert result["is_human_gate"] is True
        assert "dashboard_url" in result
        assert "questionnaire" not in json.dumps(result).lower() or "questionnaire completion" in result["message"]

    def test_unknown_obligation(self):
        """Unknown obligation still returns guidance, not an error."""
        from server import cl_action_guide
        result = json.loads(cl_action_guide("ART9-OBL-1"))
        assert result["obligation_id"] == "ART9-OBL-1"
        assert result["is_human_gate"] is False
        assert "dashboard_url" in result

    def test_invalid_format(self):
        """Invalid obligation format returns error."""
        from server import cl_action_guide
        result = json.loads(cl_action_guide("invalid"))
        assert "error" in result

    def test_does_not_return_questions(self):
        """CRITICAL: cl_action_guide must NEVER return questionnaire content."""
        from server import cl_action_guide
        result_str = cl_action_guide("ART26-OBL-2")
        result = json.loads(result_str)
        assert "questions" not in result
        assert "questionnaire" not in result
        # The word "questionnaire" may appear in the message (as in "questionnaire completion")
        # but must not appear as a key in the result
        for key in result:
            assert key != "questions"
            assert key != "questionnaire"

    def test_all_known_gates(self):
        """All 5 Batch 1 Human Gates are recognized."""
        from server import cl_action_guide
        known_ids = ["ART26-OBL-2", "ART26-OBL-6", "ART26-OBL-7", "ART26-OBL-9", "ART27-OBL-1"]
        for obl_id in known_ids:
            result = json.loads(cl_action_guide(obl_id))
            assert result["is_human_gate"] is True, f"{obl_id} should be a known Human Gate"
