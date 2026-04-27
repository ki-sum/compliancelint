"""Unit tests for _apply_saas_settings_to_scope — F6/F7/F8 follow-up.

The 2026-04-26 hostile audit (§2.Z launch-checklist) flagged that the
inline role-extraction in cl_scan_all only mirrored 2 of 4 supported
roles into the scanner's _scope dict. Refactored into a pure helper +
covered here, including the new authorised_representative role added
to the SaaS-side role select on the same date.

Replaces the more-expensive idea of building a full AR archetype
fixture — the 5 role flags + risk classification merge are the only
behaviour the SaaS→scanner protocol requires; full per-article scan
behaviour is already covered by the existing 12 archetypes."""
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from server import _apply_saas_settings_to_scope


class TestRoleFlagExtraction:
    """Cover the 5 EU AI Act Art 3 operator roles."""

    def test_provider_only(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, {"roles": ["provider"]})
        assert scope["is_provider"] is True
        assert scope["is_deployer"] is False
        assert scope["is_importer"] is False
        assert scope["is_distributor"] is False
        assert scope["is_authorised_representative"] is False

    def test_authorised_representative_only(self):
        # Today's regression bug: AR was not extracted before F6 fix.
        scope = {}
        _apply_saas_settings_to_scope(
            scope, {"roles": ["authorised_representative"]}
        )
        assert scope["is_authorised_representative"] is True
        assert scope["is_provider"] is False
        assert scope["is_deployer"] is False

    def test_multi_role_provider_and_ar(self):
        # Realistic case — non-EU AI provider whose subsidiary IS the AR.
        scope = {}
        _apply_saas_settings_to_scope(
            scope, {"roles": ["provider", "authorised_representative"]}
        )
        assert scope["is_provider"] is True
        assert scope["is_authorised_representative"] is True
        assert scope["is_deployer"] is False

    def test_all_five_roles(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, {"roles": [
            "provider",
            "deployer",
            "authorised_representative",
            "importer",
            "distributor",
        ]})
        assert scope["is_provider"] is True
        assert scope["is_deployer"] is True
        assert scope["is_authorised_representative"] is True
        assert scope["is_importer"] is True
        assert scope["is_distributor"] is True

    def test_empty_roles_list(self):
        # Should set all five flags to False (not raise / not skip).
        scope = {}
        _apply_saas_settings_to_scope(scope, {"roles": []})
        for flag in ("is_provider", "is_deployer", "is_importer",
                     "is_distributor", "is_authorised_representative"):
            assert scope[flag] is False, flag

    def test_missing_roles_key(self):
        # SaaS could send response without roles[] (legacy / partial).
        # Should default to empty list semantically.
        scope = {}
        _apply_saas_settings_to_scope(scope, {})
        for flag in ("is_provider", "is_deployer", "is_importer",
                     "is_distributor", "is_authorised_representative"):
            assert scope[flag] is False, flag

    def test_null_roles_value(self):
        # Defensive: if roles is JSON null (None in Python), should not
        # raise. Treat as empty.
        scope = {}
        _apply_saas_settings_to_scope(scope, {"roles": None})
        for flag in ("is_provider", "is_deployer", "is_importer",
                     "is_distributor", "is_authorised_representative"):
            assert scope[flag] is False, flag

    def test_unknown_role_silently_ignored(self):
        # API client typo or future role — known roles still control,
        # unknown adds no scope.
        scope = {}
        _apply_saas_settings_to_scope(
            scope, {"roles": ["provider", "operator", "manufacturer"]}
        )
        assert scope["is_provider"] is True  # known role still works
        # No "is_operator" or "is_manufacturer" key created.
        assert "is_operator" not in scope
        assert "is_manufacturer" not in scope


class TestSaasSettingsActive:
    def test_always_sets_saas_settings_active(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, {})
        assert scope["_saas_settings_active"] is True

    def test_returns_same_scope_dict(self):
        scope = {"existing": "preserved"}
        result = _apply_saas_settings_to_scope(scope, {"roles": ["provider"]})
        assert result is scope
        assert scope["existing"] == "preserved"
        assert scope["is_provider"] is True


class TestRiskClassificationMerge:
    def test_high_risk_sets_confidence(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, {"riskClassification": "high-risk"})
        assert scope["risk_classification"] == "high-risk"
        assert scope["risk_classification_confidence"] == "high"

    def test_no_risk_does_not_overwrite_existing(self):
        scope = {"risk_classification": "limited-risk", "risk_classification_confidence": "medium"}
        _apply_saas_settings_to_scope(scope, {"roles": ["provider"]})
        # No riskClassification in saas_settings → existing values preserved.
        assert scope["risk_classification"] == "limited-risk"
        assert scope["risk_classification_confidence"] == "medium"

    def test_empty_string_risk_does_not_overwrite(self):
        scope = {"risk_classification": "limited-risk"}
        _apply_saas_settings_to_scope(scope, {"riskClassification": ""})
        # Empty string is falsy → preserve existing.
        assert scope["risk_classification"] == "limited-risk"


class TestModernResponseShape:
    """R5-F2 (2026-04-27) — modern scan-settings response includes
    pre-computed effective role flags. Server merges roles[] with the
    per-role wizard booleans (compliance-profile isImporter etc.) using
    OR. Three-state semantics: true | false | null.
    Null = user has not confirmed → leave AI's _scope value alone.
    """

    def test_modern_provider_only_overrides_ai(self):
        # Wizard untouched, roles=[provider]. Server returns provider=true,
        # all others null (= "user did not confirm"). Scanner should NOT
        # overwrite AI-supplied is_deployer/is_importer/etc. with False.
        scope = {"is_deployer": True}  # AI thought user is also deployer
        _apply_saas_settings_to_scope(scope, {
            "roles": ["provider"],
            "is_provider": True,
            "is_deployer": None,
            "is_importer": None,
            "is_distributor": None,
            "is_authorised_representative": None,
        })
        assert scope["is_provider"] is True
        # AI's value preserved — server did not say "no", just "unconfirmed".
        assert scope["is_deployer"] is True
        # Other unset → not added by helper
        assert "is_importer" not in scope
        assert "is_distributor" not in scope
        assert "is_authorised_representative" not in scope

    def test_modern_wizard_importer_without_role_selector_is_recognised(self):
        # The bug R5-F2 was about: user filled wizard isImporter=true but
        # never ticked "importer" in role selector → roles=["provider"].
        # Pre-fix scanner forced is_importer=False from roles[] alone.
        # Post-fix: server emits is_importer=true (OR of wizard + roles)
        # and scanner honours it.
        scope = {}
        _apply_saas_settings_to_scope(scope, {
            "roles": ["provider"],
            "is_provider": True,
            "is_deployer": None,
            "is_importer": True,         # ← wizard said yes
            "is_distributor": None,
            "is_authorised_representative": None,
        })
        assert scope["is_importer"] is True
        assert scope["is_provider"] is True

    def test_modern_explicit_false_still_overrides(self):
        # Wizard isImporter=false AND role not in roles[] → server emits
        # is_importer=false. Scanner DOES override AI value with False.
        scope = {"is_importer": True}  # AI claim
        _apply_saas_settings_to_scope(scope, {
            "roles": ["provider"],
            "is_provider": True,
            "is_deployer": None,
            "is_importer": False,        # ← user explicitly denied
            "is_distributor": None,
            "is_authorised_representative": None,
        })
        assert scope["is_importer"] is False  # user-confirmed denial wins

    def test_modern_response_detected_by_any_is_role_key(self):
        # Detection of "modern" shape is presence of ANY is_<role> key.
        # Even one key flips the helper into modern mode for ALL roles.
        scope = {}
        _apply_saas_settings_to_scope(scope, {
            "roles": ["provider", "importer"],
            "is_provider": True,
            # is_deployer absent — modern detection still fires; legacy
            # fallback per-role does NOT happen for the missing keys.
        })
        assert scope["is_provider"] is True
        # Legacy roles-derived booleans are NOT computed when modern
        # response shape is in use, even though "importer" is in roles[].
        # (The server is the authority; if it didn't include is_importer,
        # we leave scope alone.)
        assert "is_importer" not in scope


class TestArOnlyUserScenario:
    """Specific scenario: an AR-only user runs cl_scan. F6 ensures the
    is_authorised_representative flag is captured so downstream module
    code can branch on it. F7 (article filter) is intentionally not
    implemented because no Art 3 article is exclusively AR-addressed."""

    def test_ar_only_scope_has_is_ar_true(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, {
            "roles": ["authorised_representative"],
            "riskClassification": "high-risk",
        })
        assert scope["is_authorised_representative"] is True
        assert scope["risk_classification"] == "high-risk"
        # Conservative — AR isn't a provider, so is_provider=False
        assert scope["is_provider"] is False
