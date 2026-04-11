"""Tests for the Validation Gate — coerce + validate + gate logic.

Ensures 100% format correctness of compliance_answers before scanning.
"""
import os
import sys
import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.validation_gate import (
    coerce_answers,
    validate_answers,
    validate_scope,
    compute_applicable_articles,
    run_gate,
    _fuzzy_match_article_key,
    _coerce_string_to_bool,
    _SENTINEL,
)


# ═══════════════════════════════════════════════════════════════
# Fuzzy key matching
# ═══════════════════════════════════════════════════════════════


class TestFuzzyKeyMatch:

    def test_exact_match(self):
        assert _fuzzy_match_article_key("art50") == "art50"

    def test_with_underscore(self):
        assert _fuzzy_match_article_key("art_50") == "art50"

    def test_with_suffix(self):
        assert _fuzzy_match_article_key("art50_transparency") == "art50"

    def test_article_prefix(self):
        assert _fuzzy_match_article_key("article_50") == "art50"

    def test_article_no_underscore(self):
        assert _fuzzy_match_article_key("article50") == "art50"

    def test_with_spaces(self):
        assert _fuzzy_match_article_key("art 50") == "art50"

    def test_uppercase(self):
        assert _fuzzy_match_article_key("ART50") == "art50"

    def test_no_match(self):
        assert _fuzzy_match_article_key("something_random") is None

    def test_art9(self):
        assert _fuzzy_match_article_key("art9_risk_management") == "art9"

    def test_art12_logging(self):
        assert _fuzzy_match_article_key("art12_record_keeping") == "art12"

    def test_art111(self):
        assert _fuzzy_match_article_key("art111") == "art111"

    def test_scope_matched(self):
        # _scope is in _BOOL_FIELDS so it's a known key
        assert _fuzzy_match_article_key("_scope") == "_scope"


# ═══════════════════════════════════════════════════════════════
# String to bool coercion
# ═══════════════════════════════════════════════════════════════


class TestStringToBool:

    def test_true_variants(self):
        assert _coerce_string_to_bool("true") is True
        assert _coerce_string_to_bool("True") is True
        assert _coerce_string_to_bool("yes") is True
        assert _coerce_string_to_bool("1") is True

    def test_false_variants(self):
        assert _coerce_string_to_bool("false") is False
        assert _coerce_string_to_bool("False") is False
        assert _coerce_string_to_bool("no") is False
        assert _coerce_string_to_bool("0") is False

    def test_null_variants(self):
        assert _coerce_string_to_bool("null") is None
        assert _coerce_string_to_bool("None") is None
        assert _coerce_string_to_bool("") is None
        assert _coerce_string_to_bool("N/A") is None

    def test_non_compliant_string(self):
        assert _coerce_string_to_bool("NON_COMPLIANT - no logging found") is False

    def test_compliant_string(self):
        assert _coerce_string_to_bool("COMPLIANT - logging is configured") is True

    def test_partial_string(self):
        assert _coerce_string_to_bool("PARTIAL - disclosure.ts exists but not used") is True

    def test_not_applicable_string(self):
        assert _coerce_string_to_bool("NOT_APPLICABLE - not a chatbot") is None

    def test_unrecognized_string(self):
        result = _coerce_string_to_bool("some random description")
        assert result is _SENTINEL


# ═══════════════════════════════════════════════════════════════
# Coerce layer
# ═══════════════════════════════════════════════════════════════


class TestCoerceAnswers:

    def test_correct_format_unchanged(self):
        """Valid answers pass through without modification."""
        answers = {
            "art50": {
                "is_chatbot_or_interactive_ai": True,
                "has_ai_disclosure_to_users": False,
                "disclosure_evidence": ["bot.ts:10"],
            }
        }
        coerced, log = coerce_answers(answers)
        assert coerced["art50"]["is_chatbot_or_interactive_ai"] is True
        assert coerced["art50"]["has_ai_disclosure_to_users"] is False
        assert coerced["art50"]["disclosure_evidence"] == ["bot.ts:10"]

    def test_wrong_key_renamed(self):
        """art50_transparency → art50"""
        answers = {
            "art50_transparency": {
                "is_chatbot_or_interactive_ai": True,
            }
        }
        coerced, log = coerce_answers(answers)
        assert "art50" in coerced
        assert "art50_transparency" not in coerced
        assert coerced["art50"]["is_chatbot_or_interactive_ai"] is True
        assert any(l["action"] == "key_renamed" for l in log)

    def test_string_bool_coerced(self):
        """String "true" → True"""
        answers = {
            "art12": {
                "has_logging": "true",
                "has_retention_config": "false",
            }
        }
        coerced, log = coerce_answers(answers)
        assert coerced["art12"]["has_logging"] is True
        assert coerced["art12"]["has_retention_config"] is False

    def test_string_description_coerced_to_bool(self):
        """'NON_COMPLIANT - no logging' → False"""
        answers = {
            "art12": {
                "has_logging": "NON_COMPLIANT - no logging framework detected",
            }
        }
        coerced, log = coerce_answers(answers)
        assert coerced["art12"]["has_logging"] is False

    def test_string_article_value_to_dict(self):
        """'NOT_APPLICABLE - not high risk' → dict with null bools"""
        answers = {
            "art9": "NOT_APPLICABLE - Not high-risk system"
        }
        coerced, log = coerce_answers(answers)
        assert isinstance(coerced["art9"], dict)
        assert coerced["art9"]["has_risk_docs"] is None
        assert any(l["action"] == "string_to_dict" for l in log)

    def test_string_list_wrapped(self):
        """String evidence → wrapped in list"""
        answers = {
            "art50": {
                "disclosure_evidence": "found in bot.ts:33",
            }
        }
        coerced, log = coerce_answers(answers)
        assert coerced["art50"]["disclosure_evidence"] == ["found in bot.ts:33"]

    def test_internal_keys_preserved(self):
        """_scope and _scan_metadata pass through."""
        answers = {
            "_scope": {"is_ai_system": True},
            "_scan_metadata": {"files_read": ["a.py"]},
        }
        coerced, log = coerce_answers(answers)
        assert coerced["_scope"]["is_ai_system"] is True
        assert coerced["_scan_metadata"]["files_read"] == ["a.py"]

    def test_real_world_ai_output(self):
        """Reproduce the exact bug from demo-ai-chat session."""
        answers = {
            "art4_ai_literacy": None,
            "art50_transparency": {
                "art50_1_ai_disclosure": "PARTIAL - disclosure.ts exists but not used",
                "art50_2_content_marking": "PARTIAL - disclosure.ts has isAIGenerated()",
            },
            "art12_record_keeping": "NON_COMPLIANT - No logging framework detected",
            "art6_high_risk": "NOT_APPLICABLE - System is limited-risk",
        }
        coerced, log = coerce_answers(answers)

        # art50_transparency should be renamed to art50
        assert "art50" in coerced
        assert "art50_transparency" not in coerced

        # art12_record_keeping → art12
        assert "art12" in coerced
        assert isinstance(coerced["art12"], dict)
        # It should have been converted from string "NON_COMPLIANT..." to dict
        assert coerced["art12"]["has_logging"] is False

        # art6_high_risk → art6
        assert "art6" in coerced
        assert isinstance(coerced["art6"], dict)


# ═══════════════════════════════════════════════════════════════
# Validate layer
# ═══════════════════════════════════════════════════════════════


class TestValidateAnswers:

    def test_valid_answers_no_errors(self):
        answers = {
            "art50": {
                "is_chatbot_or_interactive_ai": True,
                "is_generating_synthetic_content": False,
                "has_ai_disclosure_to_users": None,
                "disclosure_evidence": [],
                "has_content_watermarking": None,
                "is_emotion_recognition_system": False,
                "is_biometric_categorization_system": False,
                "has_emotion_biometric_disclosure": None,
                "emotion_biometric_evidence": [],
                "is_deep_fake_system": False,
                "has_deep_fake_disclosure": None,
                "deep_fake_evidence": [],
            }
        }
        errors, missing = validate_answers(answers)
        assert "art50" not in errors
        assert "art50" not in missing

    def test_string_in_bool_field_rejected(self):
        answers = {
            "art50": {
                "is_chatbot_or_interactive_ai": "yes it is a chatbot",
            }
        }
        errors, missing = validate_answers(answers)
        assert "art50" in errors
        assert any(e.field == "is_chatbot_or_interactive_ai" for e in errors["art50"])

    def test_non_dict_article_rejected(self):
        answers = {
            "art12": "some string instead of dict"
        }
        errors, missing = validate_answers(answers)
        assert "art12" in errors
        assert errors["art12"][0].field == "(root)"

    def test_missing_bool_fields_reported(self):
        answers = {
            "art50": {
                # Only one field, all others missing
                "is_chatbot_or_interactive_ai": True,
            }
        }
        errors, missing = validate_answers(answers)
        assert "art50" in missing
        assert "has_ai_disclosure_to_users" in missing["art50"]

    def test_missing_article_not_error(self):
        """Articles not provided at all are NOT errors (AI may not have scanned them)."""
        answers = {}
        errors, missing = validate_answers(answers)
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════
# Full gate
# ═══════════════════════════════════════════════════════════════


class TestRunGate:

    def test_valid_format_but_missing_scope(self):
        """Valid field types but no _scope → scope error."""
        answers = {
            "art12": {
                "has_logging": True,
                "has_retention_config": False,
                "logging_evidence": [],
            }
        }
        result = run_gate(answers)
        # Format is valid but _scope is missing
        assert "art12" in result.valid_articles
        assert len(result.scope_errors) > 0
        assert result.all_valid is False

    def test_invalid_detected(self):
        answers = {
            "art12": {
                "has_logging": "Yes, we have logging",  # String in bool field
            }
        }
        result = run_gate(answers)
        # After coercion, "Yes" is coerced to True — so this should actually pass
        # Let's use something that can't be coerced
        answers2 = {
            "art12": {
                "has_logging": {"nested": "object"},  # Object in bool field
            }
        }
        result2 = run_gate(answers2)
        assert result2.all_valid is False
        assert "art12" in result2.invalid_articles

    def test_coerce_fixes_before_validate(self):
        """Coerce should fix common mistakes so validate passes."""
        answers = {
            "art50_transparency": {
                "is_chatbot_or_interactive_ai": "true",
                "has_ai_disclosure_to_users": "false",
            }
        }
        result = run_gate(answers)
        # Key should be renamed, bools should be coerced
        assert "art50" in result.valid_articles
        assert result.valid_articles["art50"]["is_chatbot_or_interactive_ai"] is True
        assert result.valid_articles["art50"]["has_ai_disclosure_to_users"] is False
        assert len(result.coerce_log) > 0

    def test_error_response_structure(self):
        answers = {
            "art12": {
                "has_logging": [1, 2, 3],  # Array in bool field - can't coerce
            }
        }
        result = run_gate(answers)
        if not result.all_valid:
            resp = result.to_error_response()
            assert resp["validation_failed"] is True
            assert isinstance(resp["errors"], list)
            assert resp["fix_instruction"]
            # Each error should have required_schema
            for err in resp["errors"]:
                assert "required_schema" in err

    def test_mixed_valid_and_invalid(self):
        """Some articles valid, some invalid — both handled."""
        answers = {
            "art12": {
                "has_logging": True,
                "has_retention_config": False,
            },
            "art50": {
                "is_chatbot_or_interactive_ai": {"complex": "object"},  # Invalid
            },
        }
        result = run_gate(answers)
        assert "art12" in result.valid_articles
        assert "art50" in result.invalid_articles

    def test_empty_answers(self):
        """Empty answers → scope error + all applicable articles missing."""
        result = run_gate({})
        assert result.all_valid is False
        assert len(result.scope_errors) > 0

    def test_demo_ai_chat_real_data(self):
        """Reproduce the exact data that caused the 231 UNABLE_TO_DETERMINE bug."""
        real_answers = {
            "art4_ai_literacy": None,
            "art5_prohibited_practices": "NOT_APPLICABLE - No dark patterns",
            "art50_transparency": {
                "art50_1_ai_disclosure": "PARTIAL - disclosure.ts exists but is dead code",
                "art50_2_content_marking": "PARTIAL - CONTENT_METADATA never applied",
                "art50_3_emotion_recognition": "NOT_APPLICABLE",
                "art50_4_deepfakes": "NOT_APPLICABLE",
            },
            "art6_high_risk": "NOT_APPLICABLE - limited-risk",
            "art9_risk_management": "NOT_APPLICABLE - Not high-risk",
            "art12_record_keeping": "NON_COMPLIANT - No logging framework",
        }

        result = run_gate(real_answers)

        # art50_transparency should be renamed to art50
        assert "art50" in result.coerced_answers
        assert "art50_transparency" not in result.coerced_answers

        # art12_record_keeping should be renamed to art12
        assert "art12" in result.coerced_answers

        # art12 should have been converted from string to dict with has_logging=False
        art12 = result.coerced_answers.get("art12", {})
        assert isinstance(art12, dict)
        assert art12.get("has_logging") is False

        # Coerce log should show the renames
        renames = [l for l in result.coerce_log if l["action"] == "key_renamed"]
        assert len(renames) >= 3  # at least art50, art12, art6


# ═══════════════════════════════════════════════════════════════
# Scope validation
# ═══════════════════════════════════════════════════════════════


class TestValidateScope:

    def test_valid_scope(self):
        scope = {
            "risk_classification": "limited-risk",
            "risk_classification_confidence": "high",
            "is_ai_system": True,
        }
        errors = validate_scope(scope)
        assert len(errors) == 0

    def test_missing_scope(self):
        errors = validate_scope(None)
        assert len(errors) == 1
        assert "_scope" in errors[0]["field"]

    def test_empty_scope(self):
        errors = validate_scope({})
        assert len(errors) >= 1  # At least one error about missing/empty _scope

    def test_missing_risk_classification(self):
        scope = {"is_ai_system": True}
        errors = validate_scope(scope)
        assert len(errors) == 1
        assert "risk_classification" in errors[0]["field"]

    def test_empty_string_risk_classification(self):
        scope = {"risk_classification": "", "is_ai_system": True}
        errors = validate_scope(scope)
        assert len(errors) == 1

    def test_null_risk_classification(self):
        scope = {"risk_classification": None, "is_ai_system": True}
        errors = validate_scope(scope)
        assert len(errors) == 1


# ═══════════════════════════════════════════════════════════════
# Applicable articles computation
# ═══════════════════════════════════════════════════════════════


class TestComputeApplicableArticles:

    def test_limited_risk_system(self):
        """Limited-risk system: high-risk articles are skipped."""
        scope = {
            "risk_classification": "limited-risk",
            "risk_classification_confidence": "high",
            "is_ai_system": True,
            "is_gpai_provider": False,
            "is_importer": False,
            "is_distributor": False,
            "_saas_settings_active": True,
        }
        applicable, skipped = compute_applicable_articles(scope)

        # Universal articles should apply
        assert "art50" in applicable
        assert "art5" in applicable
        assert "art6" in applicable

        # High-risk only articles should be skipped
        assert "art9" in skipped
        assert "art12" in skipped
        assert "art14" in skipped

        # GPAI articles skipped for non-GPAI
        assert "art51" in skipped

        # Importer/distributor articles skipped
        assert "art23" in skipped
        assert "art24" in skipped

    def test_high_risk_system(self):
        """High-risk system: high-risk articles apply, GPAI still skipped."""
        scope = {
            "risk_classification": "high-risk",
            "risk_classification_confidence": "high",
            "is_ai_system": True,
            "is_gpai_provider": False,
            "is_importer": False,
            "is_distributor": False,
            "_saas_settings_active": True,
        }
        applicable, skipped = compute_applicable_articles(scope)

        # High-risk articles should be applicable
        assert "art9" in applicable
        assert "art12" in applicable
        assert "art14" in applicable
        assert "art50" in applicable

        # GPAI skipped for non-GPAI provider
        assert "art51" in skipped

    def test_gpai_provider(self):
        """GPAI model provider: GPAI articles apply."""
        scope = {
            "risk_classification": "not high-risk",
            "risk_classification_confidence": "high",
            "is_ai_system": True,
            "is_gpai_provider": True,
            "is_importer": False,
            "is_distributor": False,
            "_saas_settings_active": True,
        }
        applicable, skipped = compute_applicable_articles(scope)

        assert "art51" in applicable
        assert "art53" in applicable
        assert "art55" in applicable

    def test_importer(self):
        scope = {
            "risk_classification": "high-risk",
            "risk_classification_confidence": "high",
            "is_ai_system": True,
            "is_importer": True,
            "is_distributor": False,
            "_saas_settings_active": True,
        }
        applicable, skipped = compute_applicable_articles(scope)
        assert "art23" in applicable

    def test_low_confidence_risk_not_skipped(self):
        """Low confidence risk classification: don't skip high-risk articles."""
        scope = {
            "risk_classification": "limited-risk",
            "risk_classification_confidence": "low",
            "is_ai_system": True,
            "_saas_settings_active": True,
        }
        applicable, skipped = compute_applicable_articles(scope)
        # Low confidence → don't skip high-risk articles (conservative)
        assert "art9" in applicable
        assert "art12" in applicable


# ═══════════════════════════════════════════════════════════════
# Gate with scope enforcement
# ═══════════════════════════════════════════════════════════════


class TestRunGateWithScope:

    def test_missing_scope_flags_error(self):
        """No _scope → scope_errors, but scan still proceeds."""
        answers = {
            "art50": {"is_chatbot_or_interactive_ai": True},
        }
        result = run_gate(answers)
        assert result.all_valid is False
        assert len(result.scope_errors) > 0

    def test_valid_scope_with_all_applicable_filled(self):
        """All applicable articles filled → all_valid = True."""
        scope = {
            "risk_classification": "limited-risk",
            "risk_classification_confidence": "high",
            "is_ai_system": True,
            "is_gpai_provider": False,
            "is_importer": False,
            "is_distributor": False,
            "_saas_settings_active": True,
        }
        # Build answers for all applicable articles
        answers = {"_scope": scope}
        applicable, _ = compute_applicable_articles(scope)
        for art_key in applicable:
            from core.context import _BOOL_FIELDS, _LIST_FIELDS
            fields = {}
            for f in _BOOL_FIELDS.get(art_key, []):
                fields[f] = None  # null is valid
            for f in _LIST_FIELDS.get(art_key, []):
                fields[f] = []
            # Articles without schema fields: provide a marker dict
            if not fields:
                fields = {"_filled": True}
            answers[art_key] = fields

        result = run_gate(answers)
        assert result.all_valid is True, f"Not valid: missing={result.missing_articles}, invalid={list(result.invalid_articles.keys())}, scope_errors={result.scope_errors}"
        assert len(result.missing_articles) == 0
        assert len(result.scope_errors) == 0

    def test_missing_applicable_article_flagged(self):
        """Applicable article not filled → missing_articles error."""
        answers = {
            "_scope": {
                "risk_classification": "limited-risk",
                "risk_classification_confidence": "high",
                "is_ai_system": True,
                "is_gpai_provider": False,
                "is_importer": False,
                "is_distributor": False,
            },
            # Only fill art50, skip other applicable articles
            "art50": {"is_chatbot_or_interactive_ai": True},
        }
        result = run_gate(answers)
        assert result.all_valid is False
        assert len(result.missing_articles) > 0
        # Art. 4, 5, 6 etc. should be in missing
        assert "art4" in result.missing_articles or "art5" in result.missing_articles

    def test_skipped_articles_not_required(self):
        """Non-applicable articles don't need to be filled."""
        answers = {
            "_scope": {
                "risk_classification": "limited-risk",
                "risk_classification_confidence": "high",
                "is_ai_system": True,
                "is_gpai_provider": False,
                "is_importer": False,
                "is_distributor": False,
                "_saas_settings_active": True,
            },
        }
        # Fill ALL applicable articles
        applicable, _ = compute_applicable_articles(answers["_scope"])
        for art_key in applicable:
            from core.context import _BOOL_FIELDS, _LIST_FIELDS
            fields = {}
            for f in _BOOL_FIELDS.get(art_key, []):
                fields[f] = False
            for f in _LIST_FIELDS.get(art_key, []):
                fields[f] = []
            if not fields:
                fields = {"_filled": True}
            answers[art_key] = fields

        result = run_gate(answers)
        assert result.all_valid is True, f"Not valid: missing={result.missing_articles}, invalid={list(result.invalid_articles.keys())}"
        # art9, art12 etc. should be in skipped, not missing
        assert "art9" in result.skipped_articles
        assert "art12" in result.skipped_articles

    def test_error_response_shows_missing(self):
        """Error response includes missing applicable articles."""
        answers = {
            "_scope": {
                "risk_classification": "limited-risk",
                "risk_classification_confidence": "high",
                "is_ai_system": True,
                "is_gpai_provider": False,
                "is_importer": False,
                "is_distributor": False,
            },
        }
        result = run_gate(answers)
        resp = result.to_error_response()
        assert resp["validation_failed"] is True
        assert resp["missing_applicable_count"] > 0
        assert "missing_applicable_articles" in resp

    def test_confidence_default_when_missing(self):
        """risk_classification without confidence → defaults to medium, skip works."""
        scope = {
            "risk_classification": "limited-risk",
            # No risk_classification_confidence!
            "is_ai_system": True,
            "is_gpai_provider": False,
            "is_importer": False,
            "is_distributor": False,
            "_saas_settings_active": True,
        }
        applicable, skipped = compute_applicable_articles(scope)
        # Should still skip high-risk articles (confidence defaults to medium)
        assert "art9" in skipped
        assert "art12" in skipped

    def test_gpai_skipped_for_non_provider(self):
        """GPAI articles skipped when is_gpai_provider=False."""
        scope = {
            "risk_classification": "limited-risk",
            "risk_classification_confidence": "high",
            "is_ai_system": True,
            "is_gpai_provider": False,
            "is_importer": False,
            "is_distributor": False,
            "_saas_settings_active": True,
        }
        applicable, skipped = compute_applicable_articles(scope)
        assert "art51" in skipped
        assert "art53" in skipped
        assert "art55" in skipped


# ═══════════════════════════════════════════════════════════════
# SaaS Settings Active — no-SaaS scenario
# ═══════════════════════════════════════════════════════════════


class TestSaasSettingsActive:

    def test_no_saas_active_skips_nothing(self):
        """Without _saas_settings_active, no articles are filtered out."""
        scope = {
            "risk_classification": "limited-risk",
            "risk_classification_confidence": "high",
            "is_ai_system": True,
            "is_gpai_provider": False,
            "is_importer": False,
            "is_distributor": False,
            # _saas_settings_active NOT set (defaults to False)
        }
        applicable, skipped = compute_applicable_articles(scope)
        # All articles should be applicable — no filtering
        assert "art9" in applicable
        assert "art12" in applicable
        assert "art23" in applicable
        assert "art24" in applicable
        assert "art51" in applicable
        assert len(skipped) == 0

    def test_saas_active_false_explicit(self):
        """Explicit _saas_settings_active=False → no filtering."""
        scope = {
            "risk_classification": "limited-risk",
            "risk_classification_confidence": "high",
            "is_ai_system": True,
            "is_gpai_provider": False,
            "is_importer": True,
            "is_distributor": True,
            "_saas_settings_active": False,
        }
        applicable, skipped = compute_applicable_articles(scope)
        # Despite is_importer/is_distributor being True, no filtering happens
        assert "art9" in applicable
        assert "art23" in applicable
        assert "art24" in applicable
        assert len(skipped) == 0

    def test_saas_active_true_enables_filtering(self):
        """_saas_settings_active=True → normal filtering behavior."""
        scope = {
            "risk_classification": "limited-risk",
            "risk_classification_confidence": "high",
            "is_ai_system": True,
            "is_gpai_provider": False,
            "is_importer": False,
            "is_distributor": False,
            "_saas_settings_active": True,
        }
        applicable, skipped = compute_applicable_articles(scope)
        # High-risk articles skipped for limited-risk
        assert "art9" in skipped
        assert "art12" in skipped
        # Importer/distributor skipped
        assert "art23" in skipped
        assert "art24" in skipped

    def test_saas_active_importer_not_skipped(self):
        """_saas_settings_active=True + is_importer=True → Art. 23 NOT skipped."""
        scope = {
            "risk_classification": "high-risk",
            "risk_classification_confidence": "high",
            "is_ai_system": True,
            "is_importer": True,
            "is_distributor": False,
            "_saas_settings_active": True,
        }
        applicable, skipped = compute_applicable_articles(scope)
        assert "art23" in applicable
        assert "art24" in skipped


# ═══════════════════════════════════════════════════════════════
# Consistency: gate scope sets must match protocol.py
# ═══════════════════════════════════════════════════════════════


class TestConsistency:

    def test_high_risk_only_matches_protocol(self):
        """_HIGH_RISK_ONLY in validation_gate must match BaseArticleModule."""
        from core.protocol import BaseArticleModule
        from core.validation_gate import _HIGH_RISK_ONLY
        assert _HIGH_RISK_ONLY == BaseArticleModule._HIGH_RISK_ONLY_ARTICLES, (
            f"MISMATCH: validation_gate has {_HIGH_RISK_ONLY - BaseArticleModule._HIGH_RISK_ONLY_ARTICLES} extra, "
            f"protocol has {BaseArticleModule._HIGH_RISK_ONLY_ARTICLES - _HIGH_RISK_ONLY} extra"
        )

    def test_all_modules_have_bool_fields(self):
        """Every article module must have at least one _BOOL_FIELDS entry."""
        from core.context import _BOOL_FIELDS
        from core.validation_gate import _ALL_ARTICLE_KEYS
        art_keys = {k for k in _ALL_ARTICLE_KEYS if k.startswith("art")}
        bool_keys = {k for k in _BOOL_FIELDS if k.startswith("art")}
        missing = art_keys - bool_keys
        assert not missing, f"Articles without _BOOL_FIELDS: {sorted(missing)}"

    def test_all_modules_have_list_fields(self):
        """Every article module must have a _LIST_FIELDS entry (even if empty)."""
        from core.context import _LIST_FIELDS
        from core.validation_gate import _ALL_ARTICLE_KEYS
        art_keys = {k for k in _ALL_ARTICLE_KEYS if k.startswith("art")}
        list_keys = {k for k in _LIST_FIELDS if k.startswith("art")}
        missing = art_keys - list_keys
        assert not missing, f"Articles without _LIST_FIELDS: {sorted(missing)}"

    def test_template_covers_all_articles(self):
        """compliance_answers_template must include all 44 articles."""
        from core.context import _build_answers_template
        from core.validation_gate import _ALL_ARTICLE_KEYS
        template = _build_answers_template()
        art_keys = {k for k in _ALL_ARTICLE_KEYS if k.startswith("art")}
        template_keys = {k for k in template if k.startswith("art")}
        missing = art_keys - template_keys
        assert not missing, f"Articles missing from template: {sorted(missing)}"
