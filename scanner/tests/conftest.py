"""Shared pytest configuration and fixtures.

New architecture: tests inject mock ComplianceAnswers into ProjectContext.
The scanner does NO detection — it only maps AI answers to obligation findings.
All tests use tmp_path (pytest builtin) instead of fixture files.
"""
import os
import sys
import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


@pytest.fixture(autouse=True)
def minimal_ai_context():
    """Provide a minimal AI context for all tests.

    Sets compliance_answers to all-null (AI could not determine anything).
    Individual tests override this by calling BaseArticleModule.set_context()
    with a ProjectContext that has specific compliance_answers.
    """
    from core.protocol import BaseArticleModule
    from core.context import ProjectContext

    ctx = ProjectContext(
        primary_language="python",
        risk_classification="likely high-risk",
        risk_classification_confidence="medium",
        compliance_answers={
            "art5": {"prohibited_practices": [], "is_realtime_processing": None, "processing_mode_evidence": ""},
            "art6": {"annex_iii_categories": [], "annex_i_product_type": None, "is_high_risk": None, "reasoning": ""},
            "art9": {"has_risk_docs": None, "risk_doc_paths": [], "has_testing_infrastructure": None, "testing_evidence": [], "has_risk_code_patterns": None, "risk_code_evidence": [], "has_defined_metrics": None, "metrics_evidence": [], "affects_children": None},
            "art10": {"has_data_governance_doc": None, "data_doc_paths": [], "has_bias_mitigation": None, "bias_evidence": [], "has_data_lineage": None, "processes_special_category_data": None},
            "art11": {"has_technical_docs": None, "doc_paths": [], "documented_aspects": [], "is_annex_i_product": None},
            "art12": {"has_logging": None, "logging_description": "", "logging_evidence": [], "has_retention_config": None, "retention_days": None, "retention_evidence": ""},
            "art13": {"has_explainability": None, "explainability_evidence": [], "has_transparency_info": None, "transparency_paths": []},
            "art14": {"has_human_oversight": None, "oversight_evidence": [], "has_override_mechanism": None, "override_evidence": []},
            "art15": {"has_accuracy_testing": None, "accuracy_evidence": [], "has_robustness_testing": None, "robustness_evidence": [], "has_fallback_behavior": None, "continues_learning_after_deployment": None},
            "art50": {"is_chatbot_or_interactive_ai": None, "is_generating_synthetic_content": None, "has_ai_disclosure_to_users": None, "disclosure_evidence": [], "has_content_watermarking": None, "is_emotion_recognition_system": None, "is_biometric_categorization_system": None, "has_emotion_biometric_disclosure": None, "emotion_biometric_evidence": [], "is_deep_fake_system": None, "has_deep_fake_disclosure": None, "deep_fake_evidence": []},
        },
    )
    BaseArticleModule.set_context(ctx)
    BaseArticleModule.set_config(None)
    yield
    BaseArticleModule.set_context(None)
    BaseArticleModule.set_config(None)


def _load_module(article_dir_name: str):
    """Load a scanner module by directory name."""
    import importlib.util
    from core.protocol import BaseArticleModule

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


def _ctx_with(article_key: str, answers: dict):
    """Return a ProjectContext with specific compliance answers for one article."""
    from core.context import ProjectContext

    base_answers = {
        "art5": {"prohibited_practices": [], "is_realtime_processing": None, "processing_mode_evidence": ""},
        "art6": {"annex_iii_categories": [], "annex_i_product_type": None, "is_high_risk": None, "reasoning": ""},
        "art9": {"has_risk_docs": None, "risk_doc_paths": [], "has_testing_infrastructure": None, "testing_evidence": [], "has_risk_code_patterns": None, "risk_code_evidence": [], "has_defined_metrics": None, "metrics_evidence": [], "affects_children": None},
        "art10": {"has_data_governance_doc": None, "data_doc_paths": [], "has_bias_mitigation": None, "bias_evidence": [], "has_data_lineage": None, "processes_special_category_data": None},
        "art11": {"has_technical_docs": None, "doc_paths": [], "documented_aspects": [], "is_annex_i_product": None},
        "art12": {"has_logging": None, "logging_description": "", "logging_evidence": [], "has_retention_config": None, "retention_days": None, "retention_evidence": ""},
        "art13": {"has_explainability": None, "explainability_evidence": [], "has_transparency_info": None, "transparency_paths": []},
        "art14": {"has_human_oversight": None, "oversight_evidence": [], "has_override_mechanism": None, "override_evidence": []},
        "art15": {"has_accuracy_testing": None, "accuracy_evidence": [], "has_robustness_testing": None, "robustness_evidence": [], "has_fallback_behavior": None, "continues_learning_after_deployment": None},
        "art50": {"is_chatbot_or_interactive_ai": None, "is_generating_synthetic_content": None, "has_ai_disclosure_to_users": None, "disclosure_evidence": [], "has_content_watermarking": None, "is_emotion_recognition_system": None, "is_biometric_categorization_system": None, "has_emotion_biometric_disclosure": None, "emotion_biometric_evidence": [], "is_deep_fake_system": None, "has_deep_fake_disclosure": None, "deep_fake_evidence": []},
    }
    base_answers[article_key] = answers
    return ProjectContext(
        primary_language="python",
        risk_classification="likely high-risk",
        compliance_answers=base_answers,
    )


# ── Module fixtures ──

@pytest.fixture
def art05_module():
    return _load_module("art05-prohibited-practices")

@pytest.fixture
def art06_module():
    return _load_module("art06-risk-classification")

@pytest.fixture
def art09_module():
    return _load_module("art09-risk-management")

@pytest.fixture
def art10_module():
    return _load_module("art10-data-governance")

@pytest.fixture
def art11_module():
    return _load_module("art11-technical-documentation")

@pytest.fixture
def art12_module():
    return _load_module("art12-record-keeping")

@pytest.fixture
def art13_module():
    return _load_module("art13-transparency")

@pytest.fixture
def art14_module():
    return _load_module("art14-human-oversight")

@pytest.fixture
def art15_module():
    return _load_module("art15-accuracy-robustness")

@pytest.fixture
def art50_module():
    return _load_module("art50-transparency-obligations")
