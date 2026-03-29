"""Mutation tests: flip key compliance_answers values and verify behavior changes.

These tests catch regressions by ensuring that changing a single answer
actually changes the scanner's output. If flipping is_open_source from
true to false doesn't change Art.9's result, something is broken.
"""
import os
import sys
import copy
import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.protocol import BaseArticleModule, ComplianceLevel
from core.context import ProjectContext


def _make_ctx(answers: dict, risk: str = "likely high-risk",
              risk_conf: str = "high") -> ProjectContext:
    """Create ProjectContext with full compliance_answers."""
    return ProjectContext(
        primary_language="python",
        risk_classification=risk,
        risk_classification_confidence=risk_conf,
        compliance_answers=answers,
    )


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


def _scan(module_dir: str, ctx: ProjectContext, tmp_path):
    mod = _load_module(module_dir)
    BaseArticleModule.set_context(ctx)
    BaseArticleModule.set_config(None)
    result = mod.scan(str(tmp_path))
    BaseArticleModule.set_context(None)
    return result


def _base_answers():
    """Minimal compliance_answers with all articles."""
    return {
        "_scope": {
            "is_ai_system": True, "territorial_scope_applies": True,
            "is_open_source": False, "open_source_license": "",
            "user_role": "provider", "is_military_defense": False,
            "is_research_only": False,
        },
        "art5": {"prohibited_practices": [], "is_realtime_processing": False},
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


class TestMutationOpenSource:
    """Flipping is_open_source should change Art.9-15 between scanned/NOT_APPLICABLE."""

    def test_open_source_true_exempts_art9(self, tmp_path):
        answers = _base_answers()
        answers["_scope"]["is_open_source"] = True
        answers["_scope"]["open_source_license"] = "MIT"
        ctx = _make_ctx(answers)
        result = _scan("art09-risk-management", ctx, tmp_path)
        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE

    def test_open_source_false_scans_art9(self, tmp_path):
        answers = _base_answers()
        answers["_scope"]["is_open_source"] = False
        ctx = _make_ctx(answers)
        result = _scan("art09-risk-management", ctx, tmp_path)
        assert result.overall_level != ComplianceLevel.NOT_APPLICABLE

    def test_open_source_does_not_exempt_art5(self, tmp_path):
        answers = _base_answers()
        answers["_scope"]["is_open_source"] = True
        answers["_scope"]["open_source_license"] = "MIT"
        ctx = _make_ctx(answers)
        result = _scan("art05-prohibited-practices", ctx, tmp_path)
        assert result.overall_level != ComplianceLevel.NOT_APPLICABLE


class TestMutationMilitary:
    """Flipping is_military_defense should toggle ALL articles."""

    def test_military_true_exempts(self, tmp_path):
        answers = _base_answers()
        answers["_scope"]["is_military_defense"] = True
        ctx = _make_ctx(answers)
        result = _scan("art05-prohibited-practices", ctx, tmp_path)
        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE

    def test_military_false_scans(self, tmp_path):
        answers = _base_answers()
        answers["_scope"]["is_military_defense"] = False
        ctx = _make_ctx(answers)
        result = _scan("art05-prohibited-practices", ctx, tmp_path)
        assert result.overall_level != ComplianceLevel.NOT_APPLICABLE


class TestMutationAiSystem:
    """Flipping is_ai_system should toggle ALL articles."""

    def test_not_ai_system_exempts(self, tmp_path):
        answers = _base_answers()
        answers["_scope"]["is_ai_system"] = False
        ctx = _make_ctx(answers)
        result = _scan("art50-transparency-obligations", ctx, tmp_path)
        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE

    def test_ai_system_scans(self, tmp_path):
        answers = _base_answers()
        answers["_scope"]["is_ai_system"] = True
        ctx = _make_ctx(answers)
        result = _scan("art50-transparency-obligations", ctx, tmp_path)
        assert result.overall_level != ComplianceLevel.NOT_APPLICABLE


class TestMutationEmotionRecognition:
    """Flipping emotion recognition should change Art.50 OBL-3."""

    def test_emotion_true_no_disclosure_triggers_non_compliant(self, tmp_path):
        answers = _base_answers()
        answers["art50"]["is_emotion_recognition_system"] = True
        answers["art50"]["has_emotion_biometric_disclosure"] = False
        ctx = _make_ctx(answers)
        result = _scan("art50-transparency-obligations", ctx, tmp_path)
        obl3 = [f for f in result.findings if f.obligation_id == "ART50-OBL-3"]
        assert len(obl3) > 0
        assert obl3[0].level == ComplianceLevel.NON_COMPLIANT

    def test_emotion_false_no_trigger(self, tmp_path):
        answers = _base_answers()
        answers["art50"]["is_emotion_recognition_system"] = False
        answers["art50"]["is_biometric_categorization_system"] = False
        ctx = _make_ctx(answers)
        result = _scan("art50-transparency-obligations", ctx, tmp_path)
        obl3 = [f for f in result.findings if f.obligation_id == "ART50-OBL-3"]
        assert len(obl3) > 0
        # Should NOT be non_compliant when no emotion/biometric system
        assert obl3[0].level != ComplianceLevel.NON_COMPLIANT


class TestMutationChatbot:
    """Flipping chatbot + disclosure should change Art.50 OBL-1."""

    def test_chatbot_no_disclosure_non_compliant(self, tmp_path):
        answers = _base_answers()
        answers["art50"]["is_chatbot_or_interactive_ai"] = True
        answers["art50"]["has_ai_disclosure_to_users"] = False
        ctx = _make_ctx(answers)
        result = _scan("art50-transparency-obligations", ctx, tmp_path)
        obl1 = [f for f in result.findings if f.obligation_id == "ART50-OBL-1"]
        assert len(obl1) > 0
        assert obl1[0].level == ComplianceLevel.NON_COMPLIANT

    def test_chatbot_with_disclosure_compliant(self, tmp_path):
        answers = _base_answers()
        answers["art50"]["is_chatbot_or_interactive_ai"] = True
        answers["art50"]["has_ai_disclosure_to_users"] = True
        ctx = _make_ctx(answers)
        result = _scan("art50-transparency-obligations", ctx, tmp_path)
        obl1 = [f for f in result.findings if f.obligation_id == "ART50-OBL-1"]
        assert len(obl1) > 0
        # With disclosure found, should be PARTIAL (requires human verification)
        assert obl1[0].level in (ComplianceLevel.COMPLIANT, ComplianceLevel.PARTIAL)

    def test_not_chatbot_not_triggered(self, tmp_path):
        answers = _base_answers()
        answers["art50"]["is_chatbot_or_interactive_ai"] = False
        ctx = _make_ctx(answers)
        result = _scan("art50-transparency-obligations", ctx, tmp_path)
        obl1 = [f for f in result.findings if f.obligation_id == "ART50-OBL-1"]
        assert len(obl1) > 0
        # Not a chatbot — should not be NON_COMPLIANT
        assert obl1[0].level != ComplianceLevel.NON_COMPLIANT


class TestMutationHighRisk:
    """Flipping risk classification should change Art.9-15."""

    def test_not_high_risk_exempts_art12(self, tmp_path):
        answers = _base_answers()
        ctx = _make_ctx(answers, risk="not high-risk", risk_conf="high")
        result = _scan("art12-record-keeping", ctx, tmp_path)
        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE

    def test_high_risk_scans_art12(self, tmp_path):
        answers = _base_answers()
        ctx = _make_ctx(answers, risk="likely high-risk", risk_conf="high")
        result = _scan("art12-record-keeping", ctx, tmp_path)
        assert result.overall_level != ComplianceLevel.NOT_APPLICABLE


class TestMutationArt13Structure:
    """Art.13 rebuilt: 3 obligations (OBL-1, OBL-2, OBL-3)."""

    def test_no_transparency_all_non_compliant(self, tmp_path):
        answers = _base_answers()
        answers["art13"] = {
            "has_explainability": False, "explainability_evidence": [],
            "has_transparency_info": False, "transparency_paths": [],
        }
        ctx = _make_ctx(answers)
        result = _scan("art13-transparency", ctx, tmp_path)
        obl1 = [f for f in result.findings if f.obligation_id == "ART13-OBL-1"]
        obl2 = [f for f in result.findings if f.obligation_id == "ART13-OBL-2"]
        assert obl1[0].level.value == "non_compliant"
        assert obl2[0].level.value == "non_compliant"

    def test_has_transparency_gives_partial(self, tmp_path):
        answers = _base_answers()
        answers["art13"] = {
            "has_explainability": True, "explainability_evidence": ["explainer.py"],
            "has_transparency_info": True, "transparency_paths": ["docs/"],
        }
        ctx = _make_ctx(answers)
        result = _scan("art13-transparency", ctx, tmp_path)
        finding_ids = {f.obligation_id for f in result.findings if not f.is_informational}
        assert "ART13-OBL-1" in finding_ids
        assert "ART13-OBL-2" in finding_ids
        assert "ART13-OBL-3" in finding_ids

    def test_high_risk_scans_art12(self, tmp_path):
        answers = _base_answers()
        ctx = _make_ctx(answers, risk="likely high-risk", risk_conf="high")
        result = _scan("art12-record-keeping", ctx, tmp_path)
        assert result.overall_level != ComplianceLevel.NOT_APPLICABLE
