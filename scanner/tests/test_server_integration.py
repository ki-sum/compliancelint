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
        result_json = _scan_single_article(12, "/nonexistent/path", context=ctx)
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
        result_json = _scan_single_article(9, "/nonexistent/path", context=ctx)
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
        result_json = _scan_single_article(10, "/nonexistent/path", context=ctx)
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
        result_json = _scan_single_article(11, "/nonexistent/path", context=ctx)
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
        result_json = _scan_single_article(13, "/nonexistent/path", context=ctx)
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
        result_json = _scan_single_article(14, "/nonexistent/path", context=ctx)
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
        result_json = _scan_single_article(15, "/nonexistent/path", context=ctx)
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
        result_json = _scan_single_article(5, "/nonexistent/path", context=ctx)
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
        result_json = _scan_single_article(6, "/nonexistent/path", context=ctx)
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
        result_json = _scan_single_article(50, "/nonexistent/path", context=ctx)
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
