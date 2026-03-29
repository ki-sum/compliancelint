"""Edge case tests for ComplianceLint scanner.

Tests boundary conditions, type coercion, and unusual inputs
that could cause silent failures.
"""
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


class TestTypeCoercion:
    """Test that string/int values are correctly coerced to bool/None."""

    def test_string_1_coerced_to_true(self):
        ctx = ProjectContext(
            primary_language="python",
            compliance_answers={"art12": {"has_logging": "1"}},
        )
        answers = ctx.get_article_answers("art12")
        assert answers["has_logging"] is True

    def test_string_0_coerced_to_false(self):
        ctx = ProjectContext(
            primary_language="python",
            compliance_answers={"art12": {"has_logging": "0"}},
        )
        answers = ctx.get_article_answers("art12")
        assert answers["has_logging"] is False

    def test_string_yes_coerced_to_true(self):
        ctx = ProjectContext(
            primary_language="python",
            compliance_answers={"art12": {"has_logging": "yes"}},
        )
        answers = ctx.get_article_answers("art12")
        assert answers["has_logging"] is True

    def test_string_no_coerced_to_false(self):
        ctx = ProjectContext(
            primary_language="python",
            compliance_answers={"art12": {"has_logging": "no"}},
        )
        answers = ctx.get_article_answers("art12")
        assert answers["has_logging"] is False

    def test_string_null_coerced_to_none(self):
        ctx = ProjectContext(
            primary_language="python",
            compliance_answers={"art12": {"has_logging": "null"}},
        )
        answers = ctx.get_article_answers("art12")
        assert answers["has_logging"] is None

    def test_string_none_coerced_to_none(self):
        ctx = ProjectContext(
            primary_language="python",
            compliance_answers={"art12": {"has_logging": "None"}},
        )
        answers = ctx.get_article_answers("art12")
        assert answers["has_logging"] is None

    def test_int_1_coerced_to_true(self):
        ctx = ProjectContext(
            primary_language="python",
            compliance_answers={"art12": {"has_logging": 1}},
        )
        answers = ctx.get_article_answers("art12")
        assert answers["has_logging"] is True

    def test_int_0_coerced_to_false(self):
        ctx = ProjectContext(
            primary_language="python",
            compliance_answers={"art12": {"has_logging": 0}},
        )
        answers = ctx.get_article_answers("art12")
        assert answers["has_logging"] is False

    def test_string_list_coerced_to_list(self):
        ctx = ProjectContext(
            primary_language="python",
            compliance_answers={"art12": {"logging_evidence": "single_value"}},
        )
        answers = ctx.get_article_answers("art12")
        assert answers["logging_evidence"] == ["single_value"]

    def test_empty_string_coerced_to_none(self):
        ctx = ProjectContext(
            primary_language="python",
            compliance_answers={"art12": {"has_logging": ""}},
        )
        answers = ctx.get_article_answers("art12")
        assert answers["has_logging"] is None


class TestEmptyAndMissingInputs:
    """Test scanner behavior with empty or missing compliance_answers."""

    @pytest.mark.parametrize("module_dir", [
        "art05-prohibited-practices",
        "art06-risk-classification",
        "art09-risk-management",
        "art10-data-governance",
        "art11-technical-documentation",
        "art12-record-keeping",
        "art13-transparency",
        "art14-human-oversight",
        "art15-accuracy-robustness",
        "art50-transparency-obligations",
    ])
    def test_empty_compliance_answers_no_crash(self, module_dir, tmp_path):
        """Every module must handle empty compliance_answers without crashing."""
        ctx = ProjectContext(
            primary_language="python",
            risk_classification="likely high-risk",
            risk_classification_confidence="high",
            compliance_answers={},
        )
        mod = _load_module(module_dir)
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        result = mod.scan(str(tmp_path))
        BaseArticleModule.set_context(None)
        assert result is not None
        assert len(result.findings) > 0

    def test_unknown_keys_silently_ignored(self):
        ctx = ProjectContext(
            primary_language="python",
            compliance_answers={
                "art12": {
                    "has_logging": True,
                    "unknown_key": "should be ignored",
                    "another_unknown": 42,
                },
            },
        )
        answers = ctx.get_article_answers("art12")
        assert answers["has_logging"] is True
        # Unknown keys pass through but don't cause errors
        assert answers.get("unknown_key") == "should be ignored"


class TestArt50AllParagraphsActive:
    """Test Art.50 when ALL paragraphs are simultaneously active."""

    def test_all_paragraphs_non_compliant(self, tmp_path):
        """Chatbot + synthetic + emotion + deep fake, all without disclosure."""
        ctx = ProjectContext(
            primary_language="python",
            risk_classification="likely high-risk",
            risk_classification_confidence="high",
            compliance_answers={
                "art50": {
                    "is_chatbot_or_interactive_ai": True,
                    "is_generating_synthetic_content": True,
                    "has_ai_disclosure_to_users": False,
                    "disclosure_evidence": [],
                    "has_content_watermarking": False,
                    "is_emotion_recognition_system": True,
                    "is_biometric_categorization_system": True,
                    "has_emotion_biometric_disclosure": False,
                    "emotion_biometric_evidence": [],
                    "is_deep_fake_system": True,
                    "has_deep_fake_disclosure": False,
                    "deep_fake_evidence": [],
                },
            },
        )
        mod = _load_module("art50-transparency-obligations")
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        result = mod.scan(str(tmp_path))
        BaseArticleModule.set_context(None)

        found_ids = {f.obligation_id for f in result.findings}
        # All 4 main obligations should be present
        assert "ART50-OBL-1" in found_ids, "Missing chatbot disclosure (OBL-1)"
        assert "ART50-OBL-2" in found_ids, "Missing synthetic content (OBL-2)"
        assert "ART50-OBL-3" in found_ids, "Missing emotion/biometric (OBL-3)"
        assert "ART50-OBL-4" in found_ids, "Missing deep fake (OBL-4)"

        # All should be NON_COMPLIANT (no disclosures)
        non_compliant_ids = {f.obligation_id for f in result.findings
                            if f.level == ComplianceLevel.NON_COMPLIANT}
        assert "ART50-OBL-1" in non_compliant_ids
        assert "ART50-OBL-3" in non_compliant_ids
        assert "ART50-OBL-4" in non_compliant_ids

    def test_all_paragraphs_compliant(self, tmp_path):
        """Same as above but with all disclosures present."""
        ctx = ProjectContext(
            primary_language="python",
            risk_classification="likely high-risk",
            risk_classification_confidence="high",
            compliance_answers={
                "art50": {
                    "is_chatbot_or_interactive_ai": True,
                    "is_generating_synthetic_content": True,
                    "has_ai_disclosure_to_users": True,
                    "disclosure_evidence": ["banner.tsx"],
                    "has_content_watermarking": True,
                    "is_emotion_recognition_system": True,
                    "is_biometric_categorization_system": True,
                    "has_emotion_biometric_disclosure": True,
                    "emotion_biometric_evidence": ["notice.py"],
                    "is_deep_fake_system": True,
                    "has_deep_fake_disclosure": True,
                    "deep_fake_evidence": ["disclosure.py"],
                },
            },
        )
        mod = _load_module("art50-transparency-obligations")
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        result = mod.scan(str(tmp_path))
        BaseArticleModule.set_context(None)

        # No NON_COMPLIANT findings (all disclosures present)
        non_compliant = [f for f in result.findings
                        if f.level == ComplianceLevel.NON_COMPLIANT
                        and not f.is_informational]
        assert len(non_compliant) == 0, (
            f"Should have no NON_COMPLIANT with all disclosures. "
            f"Found: {[(f.obligation_id, f.level.value) for f in non_compliant]}"
        )


class TestScopeConflicts:
    """Test _scope with conflicting or unusual flag combinations."""

    def test_not_ai_overrides_open_source(self, tmp_path):
        """is_ai_system=false should take precedence over is_open_source=true."""
        ctx = ProjectContext(
            primary_language="python",
            risk_classification="likely high-risk",
            risk_classification_confidence="high",
            compliance_answers={
                "_scope": {
                    "is_ai_system": False,
                    "is_ai_system_reasoning": "Calculator",
                    "is_open_source": True,
                    "open_source_license": "MIT",
                },
                "art9": {"has_risk_docs": None},
            },
        )
        mod = _load_module("art09-risk-management")
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        result = mod.scan(str(tmp_path))
        BaseArticleModule.set_context(None)

        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE
        assert "Art. 3(1)" in result.findings[0].description
