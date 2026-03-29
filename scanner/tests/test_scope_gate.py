"""Scope gate boundary tests.

Tests the _scope_gate() method in BaseArticleModule with edge cases:
- Missing _scope section (should proceed with scan)
- Partial _scope (some fields null)
- Open source + Art.5/50 (should NOT be exempted)
- Open source + Art.9-15 (SHOULD be exempted)
- Conflicting scope flags
"""
import os
import sys
import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.protocol import BaseArticleModule, ComplianceLevel
from core.context import ProjectContext


def _make_ctx(scope: dict = None, risk: str = "likely high-risk",
              risk_conf: str = "high") -> ProjectContext:
    """Create a ProjectContext with given _scope and minimal answers."""
    answers = {
        "art5": {"prohibited_practices": []},
        "art6": {"annex_iii_categories": [], "annex_i_product_type": None,
                 "is_high_risk": None, "reasoning": ""},
        "art9": {"has_risk_docs": None, "risk_doc_paths": [],
                 "has_testing_infrastructure": None, "testing_evidence": [],
                 "has_risk_code_patterns": None, "risk_code_evidence": []},
        "art10": {"has_data_governance_doc": None, "data_doc_paths": [],
                  "has_bias_mitigation": None, "bias_evidence": [],
                  "has_data_lineage": None},
        "art11": {"has_technical_docs": None, "doc_paths": [],
                  "documented_aspects": []},
        "art12": {"has_logging": None, "logging_description": "",
                  "logging_evidence": [], "has_retention_config": None,
                  "retention_days": None, "retention_evidence": ""},
        "art13": {"has_explainability": None, "explainability_evidence": [],
                  "has_transparency_info": None, "transparency_paths": []},
        "art14": {"has_human_oversight": None, "oversight_evidence": [],
                  "has_override_mechanism": None, "override_evidence": []},
        "art15": {"has_accuracy_testing": None, "accuracy_evidence": [],
                  "has_robustness_testing": None, "robustness_evidence": [],
                  "has_fallback_behavior": None},
        "art50": {"is_chatbot_or_interactive_ai": None,
                  "is_generating_synthetic_content": None,
                  "has_ai_disclosure_to_users": None, "disclosure_evidence": [],
                  "has_content_watermarking": None,
                  "is_emotion_recognition_system": None,
                  "is_biometric_categorization_system": None,
                  "has_emotion_biometric_disclosure": None,
                  "emotion_biometric_evidence": [],
                  "is_deep_fake_system": None,
                  "has_deep_fake_disclosure": None,
                  "deep_fake_evidence": []},
    }
    if scope is not None:
        answers["_scope"] = scope
    return ProjectContext(
        primary_language="python",
        risk_classification=risk,
        risk_classification_confidence=risk_conf,
        compliance_answers=answers,
    )


def _load_module(article_dir_name: str):
    """Load a scanner module by directory name."""
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


class TestScopeGateNotAiSystem:
    """Art. 3(1): is_ai_system=false → ALL articles NOT_APPLICABLE."""

    @pytest.mark.parametrize("article_dir", [
        "art05-prohibited-practices",
        "art09-risk-management",
        "art12-record-keeping",
        "art50-transparency-obligations",
    ])
    def test_not_ai_system_returns_not_applicable(self, article_dir, tmp_path):
        ctx = _make_ctx(scope={
            "is_ai_system": False,
            "is_ai_system_reasoning": "Simple calculator app",
        })
        mod = _load_module(article_dir)
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        result = mod.scan(str(tmp_path))
        BaseArticleModule.set_context(None)

        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE
        assert "Art. 3(1)" in result.findings[0].description


class TestScopeGateMilitary:
    """Art. 2(3): is_military_defense=true → ALL NOT_APPLICABLE."""

    def test_military_exemption(self, tmp_path):
        ctx = _make_ctx(scope={"is_military_defense": True})
        mod = _load_module("art09-risk-management")
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        result = mod.scan(str(tmp_path))
        BaseArticleModule.set_context(None)

        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE
        assert "Art. 2(3)" in result.findings[0].description


class TestScopeGateResearch:
    """Art. 2(6): is_research_only=true → ALL NOT_APPLICABLE."""

    def test_research_exemption(self, tmp_path):
        ctx = _make_ctx(scope={"is_research_only": True})
        mod = _load_module("art12-record-keeping")
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        result = mod.scan(str(tmp_path))
        BaseArticleModule.set_context(None)

        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE
        assert "Art. 2(6)" in result.findings[0].description


class TestScopeGateOpenSource:
    """Art. 2(12): open source exempts Title III but NOT Art.5/50."""

    @pytest.mark.parametrize("article_dir", [
        "art09-risk-management",
        "art10-data-governance",
        "art11-technical-documentation",
        "art12-record-keeping",
        "art13-transparency",
        "art14-human-oversight",
        "art15-accuracy-robustness",
    ])
    def test_open_source_exempts_title_iii(self, article_dir, tmp_path):
        ctx = _make_ctx(scope={
            "is_open_source": True,
            "open_source_license": "Apache-2.0",
        })
        mod = _load_module(article_dir)
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        result = mod.scan(str(tmp_path))
        BaseArticleModule.set_context(None)

        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE
        assert "Art. 2(12)" in result.findings[0].description

    @pytest.mark.parametrize("article_dir", [
        "art05-prohibited-practices",
        "art50-transparency-obligations",
    ])
    def test_open_source_does_not_exempt_art5_art50(self, article_dir, tmp_path):
        ctx = _make_ctx(scope={
            "is_open_source": True,
            "open_source_license": "MIT",
        })
        mod = _load_module(article_dir)
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        result = mod.scan(str(tmp_path))
        BaseArticleModule.set_context(None)

        # Art.5 and Art.50 should NOT be NOT_APPLICABLE for open source
        assert result.overall_level != ComplianceLevel.NOT_APPLICABLE


class TestScopeGateTerritorial:
    """Art. 2(1): territorial_scope_applies=false → NOT_APPLICABLE."""

    def test_outside_eu_scope(self, tmp_path):
        ctx = _make_ctx(scope={
            "territorial_scope_applies": False,
            "territorial_scope_reasoning": "Domestic Japan only",
        })
        mod = _load_module("art05-prohibited-practices")
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        result = mod.scan(str(tmp_path))
        BaseArticleModule.set_context(None)

        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE
        assert "Art. 2(1)" in result.findings[0].description


class TestScopeGateNoScope:
    """No _scope section → proceed with normal scan (no exemption)."""

    def test_missing_scope_proceeds_normally(self, tmp_path):
        ctx = _make_ctx(scope=None)  # No _scope in compliance_answers
        mod = _load_module("art12-record-keeping")
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        result = mod.scan(str(tmp_path))
        BaseArticleModule.set_context(None)

        # Should NOT be NOT_APPLICABLE — should proceed with scan
        assert result.overall_level != ComplianceLevel.NOT_APPLICABLE


class TestScopeGatePartialScope:
    """Partial _scope (only some fields) → only check what's provided."""

    def test_partial_scope_only_checks_provided(self, tmp_path):
        # Only is_open_source=true, nothing else
        ctx = _make_ctx(scope={"is_open_source": True, "open_source_license": "GPL-3.0"})
        mod = _load_module("art09-risk-management")
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        result = mod.scan(str(tmp_path))
        BaseArticleModule.set_context(None)

        # Should be NOT_APPLICABLE (open source + Title III article)
        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE

    def test_partial_scope_no_exemption_for_unset(self, tmp_path):
        # Only user_role set, nothing else → should proceed
        ctx = _make_ctx(scope={"user_role": "deployer"})
        mod = _load_module("art12-record-keeping")
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        result = mod.scan(str(tmp_path))
        BaseArticleModule.set_context(None)

        assert result.overall_level != ComplianceLevel.NOT_APPLICABLE
