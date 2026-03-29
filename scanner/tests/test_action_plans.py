"""Action plan tests: verify action_plan() generates recommendations correctly.

These tests ensure that:
1. action_plan() reads the correct keys from the details dict
2. When compliance gaps exist, recommendations are generated
3. When everything is compliant, no critical recommendations are generated
4. Details keys set by scan() match what action_plan() expects
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


def _base_answers():
    return {
        "_scope": {"is_ai_system": True, "is_open_source": False,
                    "is_military_defense": False, "is_research_only": False},
        "art5": {"prohibited_practices": []},
        "art6": {"annex_iii_categories": [], "annex_i_product_type": None,
                 "is_high_risk": True, "reasoning": "test"},
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


def _make_ctx(answers, risk="likely high-risk", risk_conf="high"):
    return ProjectContext(
        primary_language="python",
        risk_classification=risk,
        risk_classification_confidence=risk_conf,
        compliance_answers=answers,
    )


def _scan_and_plan(module_dir: str, ctx_answers: dict, tmp_path):
    """Scan then generate action plan, return both.

    ctx_answers: full compliance_answers dict (not article key).
    """
    mod = _load_module(module_dir)
    ctx = _make_ctx(ctx_answers)
    BaseArticleModule.set_context(ctx)
    BaseArticleModule.set_config(None)
    result = mod.scan(str(tmp_path))
    plan = mod.action_plan(result)
    BaseArticleModule.set_context(None)
    return result, plan


# ── Details dict consistency: scan() keys must include action_plan() keys ──

MODULES_WITH_ACTION_PLANS = [
    ("art09-risk-management", "art9"),
    ("art10-data-governance", "art10"),
    ("art11-technical-documentation", "art11"),
    ("art12-record-keeping", "art12"),
    ("art13-transparency", "art13"),
    ("art14-human-oversight", "art14"),
    ("art15-accuracy-robustness", "art15"),
    ("art50-transparency-obligations", "art50"),
]


@pytest.mark.parametrize("module_dir,article_key", MODULES_WITH_ACTION_PLANS)
def test_action_plan_runs_without_error(module_dir, article_key, tmp_path):
    """Every module's action_plan() must execute without KeyError or crash."""
    answers = _base_answers()
    _, plan = _scan_and_plan(module_dir, answers, tmp_path)
    assert plan is not None
    assert hasattr(plan, "actions")


# ── action_plan generates recommendations when gaps exist ──

class TestActionPlanGeneratesRecommendations:
    """When compliance_answers indicate gaps, action_plan must produce actions."""

    def test_art09_no_risk_docs_generates_action(self, tmp_path):
        answers = _base_answers()
        answers["art9"]["has_risk_docs"] = False
        _, plan = _scan_and_plan("art09-risk-management", answers, tmp_path)
        assert len(plan.actions) > 0, "Art.9 action_plan should recommend risk docs when missing"

    def test_art10_no_bias_generates_action(self, tmp_path):
        answers = _base_answers()
        answers["art10"]["has_bias_mitigation"] = False
        answers["art10"]["has_data_governance_doc"] = False
        _, plan = _scan_and_plan("art10-data-governance", answers, tmp_path)
        assert len(plan.actions) > 0, "Art.10 action_plan should recommend bias mitigation"

    def test_art12_no_logging_generates_action(self, tmp_path):
        answers = _base_answers()
        answers["art12"]["has_logging"] = False
        _, plan = _scan_and_plan("art12-record-keeping", answers, tmp_path)
        critical = [a for a in plan.actions if a.priority == "CRITICAL"]
        assert len(critical) > 0, "Art.12 action_plan should have CRITICAL action for missing logging"

    def test_art13_no_docs_generates_action(self, tmp_path):
        answers = _base_answers()
        answers["art13"]["has_transparency_info"] = False
        answers["art13"]["has_explainability"] = False
        _, plan = _scan_and_plan("art13-transparency", answers, tmp_path)
        assert len(plan.actions) > 0, "Art.13 action_plan should recommend transparency docs"

    def test_art14_no_oversight_generates_action(self, tmp_path):
        answers = _base_answers()
        answers["art14"]["has_human_oversight"] = False
        answers["art14"]["has_override_mechanism"] = False
        _, plan = _scan_and_plan("art14-human-oversight", answers, tmp_path)
        assert len(plan.actions) > 0, "Art.14 action_plan should recommend oversight mechanisms"

    def test_art15_no_testing_generates_action(self, tmp_path):
        answers = _base_answers()
        answers["art15"]["has_accuracy_testing"] = False
        answers["art15"]["has_robustness_testing"] = False
        _, plan = _scan_and_plan("art15-accuracy-robustness", answers, tmp_path)
        assert len(plan.actions) > 0, "Art.15 action_plan should recommend testing"


# ── action_plan suppresses recommendations when compliant ──

class TestActionPlanSuppressesWhenCompliant:
    """When compliance_answers indicate compliance, fewer/no critical actions."""

    def test_art12_with_logging_no_critical_logging_action(self, tmp_path):
        answers = _base_answers()
        answers["art12"]["has_logging"] = True
        answers["art12"]["has_retention_config"] = True
        answers["art12"]["retention_days"] = 365
        _, plan = _scan_and_plan("art12-record-keeping", answers, tmp_path)
        critical_logging = [a for a in plan.actions
                           if a.priority == "CRITICAL" and "logging" in a.action.lower()]
        assert len(critical_logging) == 0, (
            "Art.12 should NOT recommend implementing logging when it already exists"
        )

    def test_art09_with_risk_docs_no_critical_docs_action(self, tmp_path):
        answers = _base_answers()
        answers["art9"]["has_risk_docs"] = True
        answers["art9"]["risk_doc_paths"] = ["docs/risk.md"]
        answers["art9"]["has_testing_infrastructure"] = True
        answers["art9"]["has_risk_code_patterns"] = True
        _, plan = _scan_and_plan("art09-risk-management", answers, tmp_path)
        critical_docs = [a for a in plan.actions
                        if a.priority == "CRITICAL" and "risk" in a.action.lower()]
        assert len(critical_docs) == 0, (
            "Art.9 should NOT recommend creating risk docs when they exist"
        )

    def test_art10_with_governance_no_critical_action(self, tmp_path):
        answers = _base_answers()
        answers["art10"]["has_data_governance_doc"] = True
        answers["art10"]["has_bias_mitigation"] = True
        answers["art10"]["has_data_lineage"] = True
        _, plan = _scan_and_plan("art10-data-governance", answers, tmp_path)
        critical = [a for a in plan.actions if a.priority == "CRITICAL"]
        assert len(critical) == 0, (
            "Art.10 should NOT have CRITICAL actions when governance is complete"
        )

    def test_art13_with_docs_no_critical_action(self, tmp_path):
        answers = _base_answers()
        answers["art13"]["has_transparency_info"] = True
        answers["art13"]["has_explainability"] = True
        _, plan = _scan_and_plan("art13-transparency", answers, tmp_path)
        critical = [a for a in plan.actions
                   if a.priority == "CRITICAL" and "instructions" in a.action.lower()]
        assert len(critical) == 0, (
            "Art.13 should NOT recommend creating docs when they exist"
        )

    def test_art14_with_oversight_no_critical_action(self, tmp_path):
        answers = _base_answers()
        answers["art14"]["has_human_oversight"] = True
        answers["art14"]["has_override_mechanism"] = True
        _, plan = _scan_and_plan("art14-human-oversight", answers, tmp_path)
        critical = [a for a in plan.actions if a.priority == "CRITICAL"]
        assert len(critical) == 0, (
            "Art.14 should NOT have CRITICAL actions when oversight exists"
        )

    def test_art15_with_testing_no_critical_action(self, tmp_path):
        answers = _base_answers()
        answers["art15"]["has_accuracy_testing"] = True
        answers["art15"]["has_robustness_testing"] = True
        answers["art15"]["has_fallback_behavior"] = True
        _, plan = _scan_and_plan("art15-accuracy-robustness", answers, tmp_path)
        critical = [a for a in plan.actions if a.priority == "CRITICAL"]
        assert len(critical) == 0, (
            "Art.15 should NOT have CRITICAL actions when all testing exists"
        )
