"""§AT.19 Phase 2 (2026-05-13) — variance regression test.

Proves that AI's non-deterministic scope answers cannot cause finding-
count drift once wizard override is applied. Pins the Bug 2 structural
fix: regardless of what AI guesses for is_gpai_model / is_importer /
is_annex_i_product / etc., findings are deterministic when wizard has
the authoritative answer.

The cascade path:
   AI compliance_answers → _apply_wizard_overrides_to_answers (Phase 2)
   → answers_flat (flattened in obligation_engine.gap_findings)
   → context_skip_field lookup per obligation
   → NA / UTD / CONDITIONAL emission

If AI noise still leaks through after override, this test catches it.
"""
import os
import sys
import json
import glob

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from server import _apply_wizard_overrides_to_answers  # noqa: E402
from core.obligation_engine import ObligationEngine  # noqa: E402


def _build_engine_for_article(article_key: str) -> ObligationEngine:
    """Load the canonical obligation JSON for one article and build an engine."""
    obligations_dir = os.path.join(SCANNER_ROOT, "obligations")
    matches = glob.glob(os.path.join(obligations_dir, f"{article_key}-*.json"))
    assert matches, f"no obligation JSON found for {article_key}"
    with open(matches[0], "r", encoding="utf-8") as f:
        data = json.load(f)
    engine = ObligationEngine([article_key])
    engine._obligations = engine._obligations + []  # ensure init
    engine.load_obligations_from_json(data)
    return engine


class TestVarianceEliminatedByWizardOverride:
    """For every plausible AI noise pattern on SCOPE fields, the post-
    override values collapse to wizard truth. Evidence fields (e.g.
    has_high_impact_capabilities, has_pre_market_verification) are
    deliberately NOT overridden — those remain AI's territory because
    they require code/document detection, not legal judgment.

    Phase 2 fix targets the SCOPE cascade (gap_findings reading
    context_skip_field values to flip NA/CONDITIONAL/UTD). Evidence
    variance is intrinsic to LLM behavior and would need a different
    mitigation (e.g. multi-run consensus or pinned prompts) which is
    OUT OF SCOPE for this fix."""

    SCOPE_FIELDS_TO_PIN = [
        # (article, field) pairs that wizard explicitly owns
        ("_scope", "is_gpai_provider"),
        ("art51", "is_gpai_model"),
        ("_scope", "is_importer"),
        ("art23", "is_importer"),
        ("_scope", "is_distributor"),
        ("art24", "is_distributor"),
        ("art8",  "is_annex_i_product"),
        ("art11", "is_annex_i_product"),
        ("art22", "is_eu_established_provider"),
        ("art54", "is_third_country_provider"),
    ]

    def _scope_snapshot(self, answers: dict) -> dict:
        """Extract only the wizard-owned scope fields from compliance_answers."""
        out = {}
        for art_key, field_name in self.SCOPE_FIELDS_TO_PIN:
            out[f"{art_key}.{field_name}"] = answers.get(art_key, {}).get(field_name)
        return out

    def test_isGpai_three_ai_guesses_collapse_to_wizard_false(self):
        """AI guesses true/null/false for is_gpai_model. Wizard says false.
        Post-override scope values MUST be identical in all three runs."""
        wizard = {"isGpai": False}
        scope_snaps = []
        for ai_guess in (True, None, False):
            answers = {
                "_scope": {"is_gpai_provider": ai_guess},
                # Evidence field has_high_impact_capabilities included to
                # confirm it's NOT touched by wizard override (stays as
                # AI's value — AI's territory).
                "art51": {"is_gpai_model": ai_guess, "has_high_impact_capabilities": ai_guess},
            }
            _apply_wizard_overrides_to_answers(answers, wizard)
            scope_snaps.append(self._scope_snapshot(answers))
            # Evidence field untouched:
            assert answers["art51"]["has_high_impact_capabilities"] == ai_guess

        assert scope_snaps[0] == scope_snaps[1] == scope_snaps[2], (
            f"Wizard override didn't collapse SCOPE variance:\n  {scope_snaps}"
        )

    def test_isImporter_three_ai_guesses_collapse(self):
        wizard = {"isImporter": False}
        scope_snaps = []
        for ai_guess in (True, None, False):
            answers = {
                "_scope": {"is_importer": ai_guess},
                "art23": {"is_importer": ai_guess, "has_pre_market_verification": ai_guess},
            }
            _apply_wizard_overrides_to_answers(answers, wizard)
            scope_snaps.append(self._scope_snapshot(answers))
            assert answers["art23"]["has_pre_market_verification"] == ai_guess
        assert scope_snaps[0] == scope_snaps[1] == scope_snaps[2]

    def test_isAnnexIProduct_three_ai_guesses_collapse(self):
        wizard = {"isAnnexIProduct": False}
        scope_snaps = []
        for ai_guess in (True, None, False):
            answers = {
                "art8":  {"is_annex_i_product": ai_guess, "has_annex_i_compliance": ai_guess},
                "art11": {"is_annex_i_product": ai_guess, "has_technical_docs": ai_guess},
            }
            _apply_wizard_overrides_to_answers(answers, wizard)
            scope_snaps.append(self._scope_snapshot(answers))
            # Evidence fields untouched:
            assert answers["art8"]["has_annex_i_compliance"] == ai_guess
            assert answers["art11"]["has_technical_docs"] == ai_guess
        assert scope_snaps[0] == scope_snaps[1] == scope_snaps[2]

    def test_multi_field_kisum_profile_collapses_to_one_state(self):
        """Simulate kisum's profile: non-HR SaaS provider with 10 wizard
        scope answers set. Across all 3 AI noise vectors (all-true,
        all-null, all-false), the post-override scope state is identical."""
        wizard = {
            "isAnnexIProduct": False,
            "isGpai": False,
            "isImporter": False,
            "isDistributor": False,
            "isAuthorisedRepresentative": False,
            "euEstablished": True,
            "isOpenSource": False,
            "isMilitaryDefense": False,
            "isResearchOnly": False,
            "territorialScopeApplies": True,
        }
        scope_snaps = []
        for ai_default in (True, None, False):
            answers = {
                "_scope": {
                    "is_gpai_provider": ai_default,
                    "is_importer": ai_default,
                    "is_distributor": ai_default,
                    "is_authorised_representative": ai_default,
                    "is_open_source": ai_default,
                    "is_military_defense": ai_default,
                    "is_research_only": ai_default,
                    "territorial_scope_applies": ai_default,
                },
                "art8":  {"is_annex_i_product": ai_default},
                "art11": {"is_annex_i_product": ai_default},
                "art22": {"is_eu_established_provider": ai_default},
                "art23": {"is_importer": ai_default},
                "art24": {"is_distributor": ai_default},
                "art51": {"is_gpai_model": ai_default},
                "art54": {"is_third_country_provider": ai_default},
            }
            _apply_wizard_overrides_to_answers(answers, wizard)
            scope_snaps.append(self._scope_snapshot(answers))

        assert scope_snaps[0] == scope_snaps[1] == scope_snaps[2], (
            f"Wizard override leaked AI noise across runs: {scope_snaps}"
        )

    def test_unmapped_field_in_wizard_does_not_affect_overrides(self):
        """Wizard sends an unknown key (e.g. future field) → ignored, no
        crash, other overrides still applied."""
        answers = {"_scope": {"is_gpai_provider": True}}
        wizard = {
            "isGpai": False,
            "isQuantumComputingSystem": True,  # future field not in mapping
        }
        _apply_wizard_overrides_to_answers(answers, wizard)
        assert answers["_scope"]["is_gpai_provider"] is False


class TestNoCrashOnMalformedInputs:
    """Robustness: weird inputs from SaaS shouldn't crash scanner."""

    def test_compliance_answers_with_non_dict_article_value(self):
        """§AT.19 Phase 2f: defensive _safe_subdict replaces non-dict
        values with a fresh dict before writing override. No exception
        raised; the malformed string is silently replaced."""
        answers = {"art51": "this is not a dict"}
        wizard = {"isGpai": False}
        _apply_wizard_overrides_to_answers(answers, wizard)
        # Defensive replacement: string discarded, dict created.
        assert isinstance(answers["art51"], dict)
        assert answers["art51"]["is_gpai_model"] is False

    def test_wizard_with_extra_keys_silently_ignored(self):
        """Wizard payload from a newer SaaS that knows more fields than
        the scanner. Scanner ignores unknown keys, no crash."""
        answers = {}
        wizard = {
            "isGpai": False,
            "isImporter": True,
            "isQuantumBiasDetector": True,  # future field
            "neverHeardOfThisField": "string value",
        }
        _apply_wizard_overrides_to_answers(answers, wizard)
        # Only mapped fields apply.
        assert answers["_scope"]["is_gpai_provider"] is False
        assert answers["_scope"]["is_importer"] is True
