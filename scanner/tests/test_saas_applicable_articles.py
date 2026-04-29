"""Phase 1 Task 2 — RED contract test for scanner-side honoring of the
extended SaaS scan-settings response (Spec §B,
2026-04-29-pre-launch-paid-engine-spec).

Spec §B moves ALL article + obligation filtering from scanner to SaaS.
After Phase 2 task 8 ships, the SaaS API returns:

    {
      applicable_articles:    ["art6", "art9", ...] | null,
      applicable_obligations: ["ART9-OBL-1", ...]    | null,
      questionnaire:          { obligation_id: {...} } | null,
      enforcement_mode:       "strict" | "lenient",
      tier_at_scan:           "free" | "starter" | "pro" | "business" | "enterprise",
      _engine_version:        "v2.5.1",
      ...existing roles + riskClassification + is_<role> flags
    }

The scanner must:
  1. Propagate these 6 NEW keys from SaaS response into the `_scope` dict
     so downstream filtering / enforcement / questionnaire surfacing can
     read them.
  2. When `_applicable_articles_from_saas` is set, `compute_applicable_
     articles` returns exactly that set (NOT re-derived from is_<role>
     flags). This is the IP-protection move — local re-derivation is
     fallback only.
  3. SAFE FALLBACK: when SaaS returns `applicable_articles=null` (free
     tier sees all), the scope key stays `None` and the scanner returns
     all 44 articles. NEVER fall back to empty set — would silently
     hide obligations.
  4. Legacy SaaS (no enforcement_mode key) defaults to "lenient" — never
     escalate enforcement on a SaaS that doesn't explicitly opt in.

THIS TEST MUST FAIL AT WRITE TIME. Phase 2 task 8 will turn it green.
"""
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from server import _apply_saas_settings_to_scope
from core.validation_gate import compute_applicable_articles


# ──────────────────────────────────────────────────────────────────────
# Class 1 — _apply_saas_settings_to_scope propagates the 6 NEW keys
# ──────────────────────────────────────────────────────────────────────


class TestExtendedResponsePropagation:
    """The 2026-04-29 §B response shape adds 6 keys on top of the R5-F2
    modern shape. The merge helper must surface each into `_scope` under
    a canonical name so the rest of the scanner can read it."""

    def _full_phase2_response(self):
        return {
            "roles": ["provider"],
            "riskClassification": "high-risk",
            "is_provider": True,
            "is_deployer": None,
            "is_importer": None,
            "is_distributor": None,
            "is_authorised_representative": None,
            # ─ NEW Phase 2 §B keys ─
            "applicable_articles": ["art6", "art9", "art10", "art11"],
            "applicable_obligations": ["ART9-OBL-1", "ART11-OBL-1"],
            "questionnaire": {
                "ART9-OBL-1": {
                    "prompt": "Has a risk management system been established?",
                    "evidence_min": 1,
                    "completion_required": True,
                }
            },
            "enforcement_mode": "strict",
            "tier_at_scan": "pro",
            "_engine_version": "v2.5.1",
        }

    def test_applicable_articles_propagated(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, self._full_phase2_response())
        # Spec §B: scanner stores the SaaS-supplied list under a name
        # prefixed with "_" + "_from_saas" suffix to mark provenance.
        assert scope["_applicable_articles_from_saas"] == [
            "art6",
            "art9",
            "art10",
            "art11",
        ]

    def test_applicable_obligations_propagated(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, self._full_phase2_response())
        assert scope["_applicable_obligations_from_saas"] == [
            "ART9-OBL-1",
            "ART11-OBL-1",
        ]

    def test_questionnaire_propagated(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, self._full_phase2_response())
        q = scope["_saas_questionnaire"]
        assert isinstance(q, dict)
        assert "ART9-OBL-1" in q
        assert q["ART9-OBL-1"]["evidence_min"] == 1
        assert q["ART9-OBL-1"]["completion_required"] is True

    def test_enforcement_mode_propagated(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, self._full_phase2_response())
        assert scope["_saas_enforcement_mode"] == "strict"

    def test_tier_at_scan_propagated(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, self._full_phase2_response())
        assert scope["_saas_tier_at_scan"] == "pro"

    def test_engine_version_propagated(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, self._full_phase2_response())
        assert scope["_saas_engine_version"] == "v2.5.1"


# ──────────────────────────────────────────────────────────────────────
# Class 2 — Free-tier null-list semantics (legal-safe default)
# ──────────────────────────────────────────────────────────────────────


class TestFreeTierNullSemantics:
    """Spec §B: free tier gets `applicable_articles=null` (sees all 44),
    NOT `[]` (sees none). Hiding obligations from free users is 100x
    worse than over-reporting (legal-risk asymmetry)."""

    def _free_tier_response(self):
        return {
            "roles": ["provider"],
            "riskClassification": None,
            "is_provider": True,
            "applicable_articles": None,
            "applicable_obligations": None,
            "questionnaire": None,
            "enforcement_mode": "lenient",
            "tier_at_scan": "free",
            "_engine_version": "v2.5.1",
        }

    def test_null_articles_propagates_as_none(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, self._free_tier_response())
        # Phase 2 contract: null from SaaS → None in scope (NOT [],
        # NOT key missing). This is the explicit "all-44" sentinel.
        assert "_applicable_articles_from_saas" in scope
        assert scope["_applicable_articles_from_saas"] is None

    def test_null_obligations_propagates_as_none(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, self._free_tier_response())
        assert "_applicable_obligations_from_saas" in scope
        assert scope["_applicable_obligations_from_saas"] is None

    def test_null_questionnaire_propagates_as_none(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, self._free_tier_response())
        assert "_saas_questionnaire" in scope
        assert scope["_saas_questionnaire"] is None

    def test_free_tier_recorded_as_lenient(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, self._free_tier_response())
        assert scope["_saas_enforcement_mode"] == "lenient"
        assert scope["_saas_tier_at_scan"] == "free"


# ──────────────────────────────────────────────────────────────────────
# Class 3 — Legacy SaaS response (Phase 1 deployments) safe defaults
# ──────────────────────────────────────────────────────────────────────


class TestLegacySafeFallback:
    """Older SaaS deployments (pre-Phase-2) won't include the 6 new keys.
    The scanner MUST NOT treat their absence as 'see nothing' — that
    would brick existing customers on the day Phase 2 ships. Defaults:
        applicable_*           → None  (= all 44 / all 247)
        questionnaire          → None
        enforcement_mode       → "lenient" (never escalate silently)
        tier_at_scan           → "free"  (conservative)
        _engine_version        → None
    """

    def _legacy_response(self):
        return {
            "roles": ["provider"],
            "riskClassification": "high-risk",
            "is_provider": True,
            "is_deployer": None,
            "is_importer": None,
            "is_distributor": None,
            "is_authorised_representative": None,
        }

    def test_legacy_missing_articles_defaults_to_none(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, self._legacy_response())
        assert scope.get("_applicable_articles_from_saas") is None

    def test_legacy_missing_enforcement_defaults_to_lenient(self):
        scope = {}
        _apply_saas_settings_to_scope(scope, self._legacy_response())
        # Critical: never escalate silently. A legacy deployment must
        # behave as it did before Phase 2 — no enforcement.
        assert scope.get("_saas_enforcement_mode") == "lenient"


# ──────────────────────────────────────────────────────────────────────
# Class 4 — compute_applicable_articles honors SaaS list when present
# ──────────────────────────────────────────────────────────────────────


class TestComputeApplicableUsesSaasList:
    """The actual filtering authority moves to SaaS in Phase 2. When
    `_applicable_articles_from_saas` is a concrete list, scanner returns
    EXACTLY that set; the local roles+risk derivation becomes fallback."""

    def test_saas_list_wins_over_local_derivation(self):
        # Local derivation would normally include all high-risk articles
        # for a provider with risk=high-risk. SaaS narrows it to 4.
        scope = {
            "_saas_settings_active": True,
            "is_provider": True,
            "is_deployer": False,
            "is_importer": False,
            "is_distributor": False,
            "risk_classification": "high-risk",
            "risk_classification_confidence": "high",
            "_applicable_articles_from_saas": ["art6", "art9", "art10", "art11"],
        }
        applicable, skipped = compute_applicable_articles(scope)
        # Scanner must echo the SaaS list verbatim (set semantics OK).
        assert applicable == {"art6", "art9", "art10", "art11"}
        # Other articles must be in skipped with a SaaS-attribution
        # reason so the audit trail traces back to the engine that
        # decided.
        assert "art4" in skipped
        assert "saas" in skipped["art4"].lower()

    def test_saas_list_none_falls_back_to_all_44(self):
        # Free tier: null from SaaS = explicit "see everything".
        # MUST NOT be treated as empty set.
        scope = {
            "_saas_settings_active": True,
            "is_provider": True,
            "risk_classification": "high-risk",
            "risk_classification_confidence": "high",
            "_applicable_articles_from_saas": None,
        }
        applicable, _ = compute_applicable_articles(scope)
        # Number is exact: ComplianceLint covers exactly 44 articles.
        assert len(applicable) == 44

    def test_saas_list_empty_treated_as_all_44_not_zero(self):
        # Defensive: even if SaaS sends `[]` (which it shouldn't),
        # scanner falls back to all-44 rather than scanning nothing.
        # Empty-set scan would mean "0 obligations checked, 0 violations
        # reported" — silently incorrect for the customer.
        scope = {
            "_saas_settings_active": True,
            "is_provider": True,
            "risk_classification": "high-risk",
            "risk_classification_confidence": "high",
            "_applicable_articles_from_saas": [],
        }
        applicable, _ = compute_applicable_articles(scope)
        assert len(applicable) == 44
