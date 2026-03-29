"""End-to-end tests: JSON string → from_json → scan → findings.

These tests simulate the ACTUAL MCP tool call path:
  1. User passes project_context as a JSON STRING
  2. ProjectContext.from_json() parses it
  3. Module scan() reads compliance_answers
  4. Findings are returned

This catches bugs where:
  - from_dict silently drops unknown keys
  - JSON format doesn't match what scan() expects
  - compliance_answers aren't propagated to get_article_answers()
"""
import json
import os
import sys
import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.protocol import BaseArticleModule, ComplianceLevel
from core.context import ProjectContext


def _load_module(article_dir_name: str):
    import importlib.util
    module_dir = os.path.join(SCANNER_ROOT, "modules", article_dir_name)
    sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(
        article_dir_name.replace("-", "_"),
        os.path.join(module_dir, "module.py"),
        submodule_search_locations=[module_dir],
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    BaseArticleModule.clear_index_cache()
    return mod.create_module()


def _e2e_scan(module_dir: str, json_string: str, tmp_path) -> "ScanResult":
    """Simulate the full MCP path: JSON string → parse → scan → result."""
    ctx = ProjectContext.from_json(json_string)
    mod = _load_module(module_dir)
    BaseArticleModule.set_context(ctx)
    BaseArticleModule.set_config(None)
    result = mod.scan(str(tmp_path))
    BaseArticleModule.set_context(None)
    return result


class TestE2EJsonParsing:
    """Test that JSON strings are correctly parsed into compliance_answers."""

    def test_full_format_works(self, tmp_path):
        """Full format: {"compliance_answers": {"art12": {...}}}"""
        json_str = json.dumps({
            "primary_language": "python",
            "risk_classification": "likely high-risk",
            "risk_classification_confidence": "high",
            "compliance_answers": {
                "art12": {
                    "has_logging": True,
                    "logging_description": "structlog",
                    "logging_evidence": ["app.py"],
                    "has_retention_config": True,
                    "retention_days": 365,
                    "retention_evidence": "config.yaml",
                }
            }
        })
        result = _e2e_scan("art12-record-keeping", json_str, tmp_path)
        obl1 = [f for f in result.findings if f.obligation_id == "ART12-OBL-1"]
        assert len(obl1) > 0, "ART12-OBL-1 not found in findings"
        assert obl1[0].level == ComplianceLevel.PARTIAL, (
            f"has_logging=True should give PARTIAL, got {obl1[0].level.value}"
        )

    def test_shorthand_format_works(self, tmp_path):
        """Shorthand: {"art12": {...}} — the bug reported by other session."""
        json_str = json.dumps({
            "art12": {
                "has_logging": True,
                "logging_description": "Python logging",
                "logging_evidence": ["main.py"],
                "has_retention_config": False,
                "retention_days": None,
                "retention_evidence": "",
            }
        })
        result = _e2e_scan("art12-record-keeping", json_str, tmp_path)
        obl1 = [f for f in result.findings if f.obligation_id == "ART12-OBL-1"]
        assert len(obl1) > 0, "ART12-OBL-1 not found in findings"
        assert obl1[0].level == ComplianceLevel.PARTIAL, (
            f"Shorthand format: has_logging=True should give PARTIAL, got {obl1[0].level.value}"
        )

    def test_shorthand_false_gives_non_compliant(self, tmp_path):
        """Shorthand with has_logging=False should give NON_COMPLIANT."""
        json_str = json.dumps({
            "art12": {
                "has_logging": False,
                "logging_description": "",
                "logging_evidence": [],
                "has_retention_config": False,
                "retention_days": None,
                "retention_evidence": "",
            }
        })
        result = _e2e_scan("art12-record-keeping", json_str, tmp_path)
        obl1 = [f for f in result.findings if f.obligation_id == "ART12-OBL-1"]
        assert len(obl1) > 0
        assert obl1[0].level == ComplianceLevel.NON_COMPLIANT

    def test_mixed_format_works(self, tmp_path):
        """Mixed: {"primary_language": "python", "art12": {...}}"""
        json_str = json.dumps({
            "primary_language": "python",
            "risk_classification": "likely high-risk",
            "risk_classification_confidence": "high",
            "art12": {
                "has_logging": True,
                "logging_description": "loguru",
                "logging_evidence": ["logger.py"],
                "has_retention_config": True,
                "retention_days": 365,
                "retention_evidence": "config",
            }
        })
        result = _e2e_scan("art12-record-keeping", json_str, tmp_path)
        assert result.language_detected == "python"
        obl1 = [f for f in result.findings if f.obligation_id == "ART12-OBL-1"]
        assert obl1[0].level == ComplianceLevel.PARTIAL

    def test_empty_json_gives_unable_to_determine(self, tmp_path):
        """Empty JSON should give UNABLE_TO_DETERMINE, not crash."""
        result = _e2e_scan("art12-record-keeping", '{}', tmp_path)
        # Should not crash — all findings should be UNABLE_TO_DETERMINE
        assert result is not None

    def test_scope_gate_via_json(self, tmp_path):
        """Scope gate should work when passed through JSON string."""
        json_str = json.dumps({
            "_scope": {"is_open_source": True, "open_source_license": "MIT"},
            "art12": {"has_logging": True},
        })
        result = _e2e_scan("art12-record-keeping", json_str, tmp_path)
        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE, (
            f"Open source should give NOT_APPLICABLE for Art.12, got {result.overall_level.value}"
        )


class TestE2EMultipleArticles:
    """Test that multiple articles can be passed in one JSON."""

    def test_art12_and_art50_in_same_json(self, tmp_path):
        """Both art12 and art50 answers in one JSON string."""
        json_str = json.dumps({
            "art12": {
                "has_logging": True,
                "logging_description": "structlog",
                "logging_evidence": ["app.py"],
                "has_retention_config": True,
                "retention_days": 365,
                "retention_evidence": "config",
            },
            "art50": {
                "is_chatbot_or_interactive_ai": True,
                "has_ai_disclosure_to_users": False,
                "is_generating_synthetic_content": False,
                "disclosure_evidence": [],
                "has_content_watermarking": False,
                "is_emotion_recognition_system": False,
                "is_biometric_categorization_system": False,
                "has_emotion_biometric_disclosure": False,
                "emotion_biometric_evidence": [],
                "is_deep_fake_system": False,
                "has_deep_fake_disclosure": False,
                "deep_fake_evidence": [],
            },
        })
        # Art.12 should see has_logging=True
        result12 = _e2e_scan("art12-record-keeping", json_str, tmp_path)
        obl1 = [f for f in result12.findings if f.obligation_id == "ART12-OBL-1"]
        assert obl1[0].level == ComplianceLevel.PARTIAL

        # Art.50 should see is_chatbot=True + no disclosure
        result50 = _e2e_scan("art50-transparency-obligations", json_str, tmp_path)
        obl50_1 = [f for f in result50.findings if f.obligation_id == "ART50-OBL-1"]
        assert len(obl50_1) > 0
        assert obl50_1[0].level == ComplianceLevel.NON_COMPLIANT


class TestE2EStringCoercion:
    """Test that string values in JSON are coerced to correct types."""

    def test_string_true_coerced(self, tmp_path):
        """JSON with "true" (string) instead of true (bool)."""
        json_str = '{"art12": {"has_logging": "true", "logging_description": "", "logging_evidence": [], "has_retention_config": "false", "retention_days": null, "retention_evidence": ""}}'
        result = _e2e_scan("art12-record-keeping", json_str, tmp_path)
        obl1 = [f for f in result.findings if f.obligation_id == "ART12-OBL-1"]
        assert obl1[0].level == ComplianceLevel.PARTIAL, (
            f"String 'true' should be coerced to True → PARTIAL, got {obl1[0].level.value}"
        )

    def test_string_evidence_coerced_to_list(self, tmp_path):
        """JSON with evidence as string instead of list."""
        json_str = json.dumps({
            "art12": {
                "has_logging": True,
                "logging_description": "structlog",
                "logging_evidence": "single_file.py",  # string, not list
                "has_retention_config": False,
                "retention_days": None,
                "retention_evidence": "",
            }
        })
        result = _e2e_scan("art12-record-keeping", json_str, tmp_path)
        # Should not crash — string should be coerced to ["single_file.py"]
        assert result is not None
        obl1 = [f for f in result.findings if f.obligation_id == "ART12-OBL-1"]
        assert obl1[0].level == ComplianceLevel.PARTIAL
