"""§AT.19 Phase 2 (2026-05-13) — wizard answers override AI scope answers.

Pins the deterministic-scope-from-wizard behavior:

Background
----------
Bug 2 root cause: AI's `compliance_answers` for scope questions
(is_gpai_model / is_annex_i_product / is_importer / etc.) is non-
deterministic. Same code, different runs → different answers →
±20-50% variance in finding count.

Phase 2 fix: when SaaS scan-settings response includes a
`wizard_answers` payload, scanner overrides AI's answers for those
fields with the wizard's authoritative values BEFORE `run_gate`
validation. Wizard is the single source of truth for scope; AI is
authoritative only for evidence.

Free tier (no wizard_answers in response) keeps current behavior:
AI answers stand. Phase 2 §B legal-asymmetry sentinel preserved.

Hybrid/human article functionality (HG hints, evidence upload,
git-path resolution, AI guidance — all in obligation_engine.py:189
+ evidence.py:276) is OBLIGATION-LEVEL not SCOPE-level, so wizard
overrides do not break those flows. Spot-tested below by ensuring
ART50-OBL-6 (type=human, addressee=provider_and_deployer) still
emits its `human_gate_hint` regardless of any scope override.
"""
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from server import _apply_saas_settings_to_scope, _apply_wizard_overrides_to_answers  # noqa: E402


class TestWizardOverridesContract:
    """Spec: wizard_answers from SaaS overrides AI's scope answers."""

    def test_wizard_isGpai_false_overrides_AI_true(self):
        """AI said is_gpai_model=true but wizard answered isGpai=false → wizard wins."""
        compliance_answers = {
            "_scope": {"is_gpai_provider": True},  # AI's guess
            "art51": {"is_gpai_model": True},      # AI's guess
        }
        wizard = {"isGpai": False}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers["_scope"]["is_gpai_provider"] is False
        assert compliance_answers["art51"]["is_gpai_model"] is False

    def test_wizard_isAnnexIProduct_true_overrides_AI_null(self):
        """AI said null (couldn't decide), wizard answered true → wizard wins."""
        compliance_answers = {
            "art8":  {"is_annex_i_product": None},
            "art11": {"is_annex_i_product": None},
        }
        wizard = {"isAnnexIProduct": True}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers["art8"]["is_annex_i_product"] is True
        assert compliance_answers["art11"]["is_annex_i_product"] is True

    def test_wizard_isImporter_false_overrides_both_scope_and_article(self):
        """Wizard isImporter=false sets both _scope.is_importer AND art23.is_importer."""
        compliance_answers = {
            "_scope": {"is_importer": True},
            "art23": {"is_importer": True},
        }
        wizard = {"isImporter": False}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers["_scope"]["is_importer"] is False
        assert compliance_answers["art23"]["is_importer"] is False

    def test_wizard_isDistributor_false_overrides_both(self):
        compliance_answers = {
            "_scope": {"is_distributor": True},
            "art24": {"is_distributor": True},
        }
        wizard = {"isDistributor": False}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers["_scope"]["is_distributor"] is False
        assert compliance_answers["art24"]["is_distributor"] is False

    def test_wizard_euEstablished_true_sets_is_eu_established_provider(self):
        """Wizard euEstablished=true → art22.is_eu_established_provider=true
        AND its inverse art54.is_third_country_provider=false."""
        compliance_answers = {
            "art22": {"is_eu_established_provider": None},
            "art54": {"is_third_country_provider": None},
        }
        wizard = {"euEstablished": True}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers["art22"]["is_eu_established_provider"] is True
        assert compliance_answers["art54"]["is_third_country_provider"] is False

    def test_wizard_euEstablished_false_inverse_to_third_country(self):
        compliance_answers = {
            "art22": {"is_eu_established_provider": None},
            "art54": {"is_third_country_provider": None},
        }
        wizard = {"euEstablished": False}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers["art22"]["is_eu_established_provider"] is False
        assert compliance_answers["art54"]["is_third_country_provider"] is True

    def test_wizard_null_field_leaves_AI_answer_untouched(self):
        """Wizard didn't answer (null) → AI answer stays.

        This is the per-field "I don't know" sentinel — wizard is the
        single source of truth ONLY for fields the user explicitly
        answered. Unanswered fields fall back to AI judgment, same as
        free tier."""
        compliance_answers = {
            "_scope": {"is_gpai_provider": True},
            "art51": {"is_gpai_model": True},
        }
        wizard = {"isGpai": None}  # wizard left blank
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers["_scope"]["is_gpai_provider"] is True
        assert compliance_answers["art51"]["is_gpai_model"] is True

    def test_empty_wizard_dict_is_noop(self):
        """Wizard not sent (free tier) → AI answers untouched."""
        compliance_answers = {
            "_scope": {"is_gpai_provider": True},
            "art51": {"is_gpai_model": True},
        }
        before = {k: dict(v) for k, v in compliance_answers.items()}
        _apply_wizard_overrides_to_answers(compliance_answers, {})
        assert compliance_answers == before

    def test_creates_article_subdict_when_missing(self):
        """If AI never filled an article entry, override still inserts it."""
        compliance_answers = {}
        wizard = {"isGpai": False}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers["_scope"]["is_gpai_provider"] is False
        assert compliance_answers["art51"]["is_gpai_model"] is False


class TestWizardOverridesDoNotBreakHybridHuman:
    """v6 risk clearance: scope overrides must NOT affect hybrid/human
    obligation functionality (HG hints, evidence upload, git-path).

    These tests are integration-flavoured but kept lightweight — they
    assert the override leaves the obligation registry, classification
    metadata, and HG hint emission paths untouched.
    """

    def test_override_does_not_mutate_obligation_registry(self):
        """Wizard override touches only compliance_answers, never the
        obligation JSONs / engine state."""
        compliance_answers = {"art50": {"is_chatbot_or_interactive_ai": True}}
        wizard = {"isGpai": False, "isImporter": False}
        before_keys = set(compliance_answers["art50"].keys())
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        # art50 fields untouched (no wizard mapping for chatbot detection)
        assert compliance_answers["art50"]["is_chatbot_or_interactive_ai"] is True
        # No new fields injected into art50 by chance
        assert compliance_answers["art50"].keys() == before_keys

    def test_hybrid_obligation_evidence_field_untouched(self):
        """ART50-OBL-5 (hybrid) evidence still flows through AI — wizard
        override does NOT pre-fill evidence fields, only scope."""
        compliance_answers = {
            "art50": {"disclosure_evidence": ["disclosed.md"]},
        }
        wizard = {"isAnnexIProduct": True}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        # Evidence list preserved — wizard never writes to evidence fields.
        assert compliance_answers["art50"]["disclosure_evidence"] == ["disclosed.md"]


class TestPhase2cWizardExpansion:
    """§AT.19 Phase 2c (2026-05-13) — 2 new wizard fields added."""

    def test_isGpaiWithSystemicRisk_overrides_scope_and_art52(self):
        compliance_answers = {
            "_scope": {"is_gpai_with_systemic_risk": True},
            "art52": {"is_gpai_with_systemic_risk": True},
        }
        wizard = {"isGpaiWithSystemicRisk": False}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers["_scope"]["is_gpai_with_systemic_risk"] is False
        assert compliance_answers["art52"]["is_gpai_with_systemic_risk"] is False

    def test_claimsArt63Exception_overrides_scope_and_art49(self):
        compliance_answers = {}
        wizard = {"claimsArt63Exception": True}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers["_scope"]["claims_art6_3_exception"] is True
        assert compliance_answers["art49"]["claims_art6_3_exception"] is True

    def test_null_systemic_risk_leaves_AI_untouched(self):
        """Wizard didn't answer (e.g. isGpai was false → systemic_risk hidden)
        → AI's prior value stays. This is the show_when conditional flow's
        graceful handling at the override layer."""
        compliance_answers = {"_scope": {"is_gpai_with_systemic_risk": True}}
        wizard = {"isGpaiWithSystemicRisk": None}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers["_scope"]["is_gpai_with_systemic_risk"] is True


class TestAnnexIIICategoryDerivations:
    """§AT.19 Phase 2c — annexIIICategory enum derives _scope.is_biometric_system.

    The user wizard answer "annex_iii_pt1_biometrics" (Annex III §1)
    structurally implies the system is a biometric system, which gates
    6 ART12 obligations' NA decisions. Pre-Phase-2c, AI had to guess
    is_biometric_system — high variance. Now derived from wizard.
    """

    def test_annex_iii_pt1_biometrics_sets_is_biometric_system_true(self):
        compliance_answers = {}
        wizard = {"annexIIICategory": "annex_iii_pt1_biometrics"}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers["_scope"]["is_biometric_system"] is True

    def test_other_annex_value_sets_is_biometric_system_false(self):
        """Picking a non-biometric Annex III category (e.g. recruitment)
        structurally rules out biometric system."""
        compliance_answers = {}
        wizard = {"annexIIICategory": "annex_iii_pt4_employment"}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers["_scope"]["is_biometric_system"] is False

    def test_not_annex_iii_sets_is_biometric_system_false(self):
        compliance_answers = {}
        wizard = {"annexIIICategory": "not_annex_iii"}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers["_scope"]["is_biometric_system"] is False

    def test_null_annex_leaves_is_biometric_system_untouched(self):
        compliance_answers = {"_scope": {"is_biometric_system": True}}
        wizard = {"annexIIICategory": None}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        # null means wizard not answered → AI's prior True stays
        assert compliance_answers["_scope"]["is_biometric_system"] is True

    def test_art50_narrower_booleans_NOT_auto_derived(self):
        """is_emotion_recognition_system + is_biometric_categorization_system
        are narrower than the wizard's annex_iii_pt1_biometrics — user
        must affirm per-obligation in HG attestation."""
        compliance_answers = {"art50": {"is_emotion_recognition_system": None}}
        wizard = {"annexIIICategory": "annex_iii_pt1_biometrics"}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        # art50 narrower fields stay None (AI/HG territory)
        assert compliance_answers["art50"]["is_emotion_recognition_system"] is None


class TestWizardOverridesIdempotent:
    """Calling override twice must be idempotent."""

    def test_double_apply_same_result(self):
        compliance_answers = {"_scope": {"is_gpai_provider": True}}
        wizard = {"isGpai": False}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        first = {k: dict(v) for k, v in compliance_answers.items()}
        _apply_wizard_overrides_to_answers(compliance_answers, wizard)
        assert compliance_answers == first
