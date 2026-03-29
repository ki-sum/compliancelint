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
            "art4": {"has_ai_literacy_measures": None, "literacy_description": "", "literacy_evidence": []},
            "art8": {"has_section_2_compliance": None, "section_2_evidence": [], "is_annex_i_product": None, "has_annex_i_compliance": None},
            "art5": {"prohibited_practices": [], "is_realtime_processing": None, "processing_mode_evidence": ""},
            "art6": {"annex_iii_categories": [], "annex_i_product_type": None, "is_high_risk": None, "reasoning": ""},
            "art9": {"has_risk_docs": None, "risk_doc_paths": [], "has_testing_infrastructure": None, "testing_evidence": [], "has_risk_code_patterns": None, "risk_code_evidence": [], "has_defined_metrics": None, "metrics_evidence": [], "affects_children": None},
            "art10": {"has_data_governance_doc": None, "data_doc_paths": [], "has_bias_mitigation": None, "bias_evidence": [], "has_data_lineage": None, "processes_special_category_data": None},
            "art11": {"has_technical_docs": None, "doc_paths": [], "documented_aspects": [], "is_annex_i_product": None},
            "art12": {"has_logging": None, "logging_description": "", "logging_evidence": [], "has_retention_config": None, "retention_days": None, "retention_evidence": ""},
            "art13": {"has_explainability": None, "explainability_evidence": [], "has_transparency_info": None, "transparency_paths": []},
            "art14": {"has_human_oversight": None, "oversight_evidence": [], "has_override_mechanism": None, "override_evidence": []},
            "art15": {"has_accuracy_testing": None, "accuracy_evidence": [], "has_robustness_testing": None, "robustness_evidence": [], "has_fallback_behavior": None, "continues_learning_after_deployment": None},
            "art17": {"has_qms_documentation": None, "qms_evidence": [], "has_compliance_strategy": None, "has_design_procedures": None, "has_qa_procedures": None, "has_testing_procedures": None, "has_technical_specifications": None, "has_data_management": None, "has_risk_management_in_qms": None, "has_post_market_monitoring": None, "has_record_keeping": None, "has_accountability_framework": None},
            "art16": {"has_section_2_compliance": None, "has_provider_identification": None, "has_qms": None, "has_documentation_kept": None, "has_log_retention": None, "has_conformity_assessment": None, "has_eu_declaration": None, "has_ce_marking": None, "has_registration": None, "has_corrective_actions_process": None, "has_conformity_evidence": None, "has_accessibility_compliance": None},
            "art18": {"has_documentation_retention_policy": None, "retention_policy_evidence": ""},
            "art19": {"has_log_retention": None, "has_retention_config": None, "retention_days": None, "retention_evidence": ""},
            "art26": {"has_deployment_documentation": None, "has_human_oversight_assignment": None, "has_operational_monitoring": None, "has_log_retention": None, "retention_days": None, "retention_evidence": "", "has_affected_persons_notification": None},
            "art43": {"has_internal_control_assessment": None, "has_change_management_procedures": None},
            "art47": {"has_doc_declaration": None, "has_annex_v_content": None},
            "art49": {"has_eu_database_registration": None},
            "art50": {"is_chatbot_or_interactive_ai": None, "is_generating_synthetic_content": None, "has_ai_disclosure_to_users": None, "disclosure_evidence": [], "has_content_watermarking": None, "is_emotion_recognition_system": None, "is_biometric_categorization_system": None, "has_emotion_biometric_disclosure": None, "emotion_biometric_evidence": [], "is_deep_fake_system": None, "has_deep_fake_disclosure": None, "deep_fake_evidence": []},
            "art51": {"is_gpai_model": None, "has_high_impact_capabilities": None, "training_compute_exceeds_threshold": None, "training_compute_flops": None, "has_commission_designation": None, "has_systemic_risk_assessment": None, "reasoning": ""},
            "art52": {"has_commission_notification": None, "notification_evidence": ""},
            "art53": {"has_technical_documentation": None, "has_downstream_documentation": None, "has_copyright_policy": None, "has_training_data_summary": None, "is_open_source_gpai": None, "has_systemic_risk": None},
            "art54": {"is_third_country_provider": None, "has_authorised_representative": None, "representative_evidence": [], "has_written_mandate": None, "mandate_evidence": [], "is_open_source_gpai": None, "has_systemic_risk": None},
            "art55": {"has_systemic_risk": None, "has_model_evaluation": None, "has_adversarial_testing": None, "evaluation_evidence": [], "has_incident_tracking": None, "incident_evidence": [], "has_cybersecurity_protection": None, "cybersecurity_evidence": []},
            "art27": {"has_fria_documentation": None, "has_fria_versioning": None},
            "art72": {"has_pmm_system": None, "has_active_data_collection": None, "has_pmm_plan": None},
            "art20": {"has_corrective_action_procedure": None, "has_supply_chain_notification": None, "has_risk_investigation_procedure": None},
            "art73": {"has_incident_reporting_procedure": None, "has_reporting_timelines": None, "has_expedited_reporting_procedure": None, "has_investigation_procedure": None},
            "art86": {"has_explanation_mechanism": None, "explanation_evidence": []},
            "art21": {"has_conformity_documentation": None, "has_log_export_capability": None},
            "art22": {"is_eu_established_provider": None, "has_authorised_representative": None, "has_representative_enablement": None, "has_mandate_authority_contact": None},
            "art23": {"is_importer": None, "has_pre_market_verification": None, "has_conformity_review": None, "has_importer_identification": None, "has_documentation_retention": None, "has_authority_documentation": None},
            "art24": {"is_distributor": None, "has_pre_market_verification": None, "has_conformity_review": None, "has_authority_documentation": None},
            "art25": {"has_rebranding_or_modification": None, "has_provider_cooperation_documentation": None, "is_safety_component_annex_i": None, "has_third_party_written_agreement": None, "has_open_source_exception": None},
            "art41": {"follows_common_specifications": None, "has_alternative_justification": None},
            "art60": {"conducts_real_world_testing": None, "has_testing_plan": None, "has_incident_reporting_for_testing": None, "has_authority_notification_procedure": None},
            "art61": {"conducts_real_world_testing": None, "has_informed_consent_procedure": None, "has_consent_documentation": None},
            "art71": {"has_provider_database_entry": None},
            "art80": {"has_compliance_remediation_plan": None, "has_corrective_action_for_all_systems": None, "has_classification_rationale": None},
            "art82": {"has_corrective_action_procedure": None},
            "art91": {"has_information_supply_readiness": None, "readiness_evidence": ""},
            "art92": {"has_evaluation_cooperation_readiness": None, "cooperation_evidence": ""},
            "art111": {"has_transition_plan": None, "transition_evidence": "", "has_significant_change_tracking": None, "change_tracking_evidence": "", "has_gpai_compliance_timeline": None, "gpai_timeline_evidence": ""},
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
        "art4": {"has_ai_literacy_measures": None, "literacy_description": "", "literacy_evidence": []},
        "art8": {"has_section_2_compliance": None, "section_2_evidence": [], "is_annex_i_product": None, "has_annex_i_compliance": None},
        "art5": {"prohibited_practices": [], "is_realtime_processing": None, "processing_mode_evidence": ""},
        "art6": {"annex_iii_categories": [], "annex_i_product_type": None, "is_high_risk": None, "reasoning": ""},
        "art9": {"has_risk_docs": None, "risk_doc_paths": [], "has_testing_infrastructure": None, "testing_evidence": [], "has_risk_code_patterns": None, "risk_code_evidence": [], "has_defined_metrics": None, "metrics_evidence": [], "affects_children": None},
        "art10": {"has_data_governance_doc": None, "data_doc_paths": [], "has_bias_mitigation": None, "bias_evidence": [], "has_data_lineage": None, "processes_special_category_data": None},
        "art11": {"has_technical_docs": None, "doc_paths": [], "documented_aspects": [], "is_annex_i_product": None},
        "art12": {"has_logging": None, "logging_description": "", "logging_evidence": [], "has_retention_config": None, "retention_days": None, "retention_evidence": ""},
        "art13": {"has_explainability": None, "explainability_evidence": [], "has_transparency_info": None, "transparency_paths": []},
        "art14": {"has_human_oversight": None, "oversight_evidence": [], "has_override_mechanism": None, "override_evidence": []},
        "art15": {"has_accuracy_testing": None, "accuracy_evidence": [], "has_robustness_testing": None, "robustness_evidence": [], "has_fallback_behavior": None, "continues_learning_after_deployment": None},
        "art17": {"has_qms_documentation": None, "qms_evidence": [], "has_compliance_strategy": None, "has_design_procedures": None, "has_qa_procedures": None, "has_testing_procedures": None, "has_technical_specifications": None, "has_data_management": None, "has_risk_management_in_qms": None, "has_post_market_monitoring": None, "has_record_keeping": None, "has_accountability_framework": None},
        "art16": {"has_section_2_compliance": None, "has_provider_identification": None, "has_qms": None, "has_documentation_kept": None, "has_log_retention": None, "has_conformity_assessment": None, "has_eu_declaration": None, "has_ce_marking": None, "has_registration": None, "has_corrective_actions_process": None, "has_conformity_evidence": None, "has_accessibility_compliance": None},
        "art18": {"has_documentation_retention_policy": None, "retention_policy_evidence": ""},
        "art19": {"has_log_retention": None, "log_retention_evidence": "", "has_retention_config": None, "retention_days": None, "retention_evidence": ""},
        "art26": {"has_deployment_documentation": None, "has_human_oversight_assignment": None, "has_operational_monitoring": None, "has_log_retention": None, "retention_days": None, "retention_evidence": "", "has_affected_persons_notification": None},
        "art43": {"has_internal_control_assessment": None, "has_change_management_procedures": None},
        "art47": {"has_doc_declaration": None, "has_annex_v_content": None},
        "art49": {"has_eu_database_registration": None},
        "art50": {"is_chatbot_or_interactive_ai": None, "is_generating_synthetic_content": None, "has_ai_disclosure_to_users": None, "disclosure_evidence": [], "has_content_watermarking": None, "is_emotion_recognition_system": None, "is_biometric_categorization_system": None, "has_emotion_biometric_disclosure": None, "emotion_biometric_evidence": [], "is_deep_fake_system": None, "has_deep_fake_disclosure": None, "deep_fake_evidence": []},
        "art51": {"is_gpai_model": None, "has_high_impact_capabilities": None, "training_compute_exceeds_threshold": None, "training_compute_flops": None, "has_commission_designation": None, "has_systemic_risk_assessment": None, "reasoning": ""},
        "art53": {"has_technical_documentation": None, "has_downstream_documentation": None, "has_copyright_policy": None, "has_training_data_summary": None, "is_open_source_gpai": None, "has_systemic_risk": None},
        "art54": {"is_third_country_provider": None, "has_authorised_representative": None, "representative_evidence": [], "has_written_mandate": None, "mandate_evidence": [], "is_open_source_gpai": None, "has_systemic_risk": None},
        "art55": {"has_systemic_risk": None, "has_model_evaluation": None, "has_adversarial_testing": None, "evaluation_evidence": [], "has_incident_tracking": None, "incident_evidence": [], "has_cybersecurity_protection": None, "cybersecurity_evidence": []},
        "art27": {"has_fria_documentation": None, "has_fria_versioning": None},
        "art72": {"has_pmm_system": None, "has_active_data_collection": None, "has_pmm_plan": None},
        "art20": {"has_corrective_action_procedure": None, "has_supply_chain_notification": None, "has_risk_investigation_procedure": None},
            "art73": {"has_incident_reporting_procedure": None, "has_reporting_timelines": None, "has_expedited_reporting_procedure": None, "has_investigation_procedure": None},
        "art86": {"has_explanation_mechanism": None, "explanation_evidence": []},
        "art21": {"has_conformity_documentation": None, "has_log_export_capability": None},
        "art22": {"is_eu_established_provider": None, "has_authorised_representative": None, "has_representative_enablement": None, "has_mandate_authority_contact": None},
        "art23": {"is_importer": None, "has_pre_market_verification": None, "has_conformity_review": None, "has_importer_identification": None, "has_documentation_retention": None, "has_authority_documentation": None},
        "art24": {"is_distributor": None, "has_pre_market_verification": None, "has_conformity_review": None, "has_authority_documentation": None},
        "art25": {"has_rebranding_or_modification": None, "has_provider_cooperation_documentation": None, "is_safety_component_annex_i": None, "has_third_party_written_agreement": None, "has_open_source_exception": None},
        "art41": {"follows_common_specifications": None, "has_alternative_justification": None},
        "art60": {"conducts_real_world_testing": None, "has_testing_plan": None, "has_incident_reporting_for_testing": None, "has_authority_notification_procedure": None},
        "art61": {"conducts_real_world_testing": None, "has_informed_consent_procedure": None, "has_consent_documentation": None},
        "art71": {"has_provider_database_entry": None},
        "art80": {"has_compliance_remediation_plan": None, "has_corrective_action_for_all_systems": None, "has_classification_rationale": None},
        "art82": {"has_corrective_action_procedure": None},
        "art92": {"has_evaluation_cooperation_readiness": None, "cooperation_evidence": ""},
        "art111": {"has_transition_plan": None, "transition_evidence": "", "has_significant_change_tracking": None, "change_tracking_evidence": "", "has_gpai_compliance_timeline": None, "gpai_timeline_evidence": ""},
    }
    base_answers[article_key] = answers
    return ProjectContext(
        primary_language="python",
        risk_classification="likely high-risk",
        compliance_answers=base_answers,
    )


# ── Module fixtures ──

@pytest.fixture
def art04_module():
    return _load_module("art04-ai-literacy")

@pytest.fixture
def art08_module():
    return _load_module("art08-compliance-with-requirements")

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
def art16_module():
    return _load_module("art16-provider-obligations")

@pytest.fixture
def art17_module():
    return _load_module("art17-quality-management")

@pytest.fixture
def art18_module():
    return _load_module("art18-documentation-keeping")

@pytest.fixture
def art19_module():
    return _load_module("art19-automatically-generated-logs")

@pytest.fixture
def art26_module():
    return _load_module("art26-deployer-obligations")

@pytest.fixture
def art43_module():
    return _load_module("art43-conformity-assessment")

@pytest.fixture
def art47_module():
    return _load_module("art47-declaration-of-conformity")

@pytest.fixture
def art49_module():
    return _load_module("art49-registration")

@pytest.fixture
def art50_module():
    return _load_module("art50-transparency-obligations")

@pytest.fixture
def art51_module():
    return _load_module("art51-gpai-classification")

@pytest.fixture
def art52_module():
    return _load_module("art52-classification-notification")

@pytest.fixture
def art53_module():
    return _load_module("art53-obligations-gpai-providers")

@pytest.fixture
def art54_module():
    return _load_module("art54-gpai-authorised-representatives")

@pytest.fixture
def art55_module():
    return _load_module("art55-gpai-systemic-risk")

@pytest.fixture
def art27_module():
    return _load_module("art27-fundamental-rights-impact")

@pytest.fixture
def art72_module():
    return _load_module("art72-post-market-monitoring")

@pytest.fixture
def art73_module():
    return _load_module("art73-serious-incident-reporting")

@pytest.fixture
def art20_module():
    return _load_module("art20-corrective-actions")

@pytest.fixture
def art86_module():
    return _load_module("art86-right-to-explanation")

@pytest.fixture
def art21_module():
    return _load_module("art21-cooperation-with-authorities")

@pytest.fixture
def art22_module():
    return _load_module("art22-authorised-representatives")

@pytest.fixture
def art23_module():
    return _load_module("art23-obligations-of-importers")

@pytest.fixture
def art24_module():
    return _load_module("art24-obligations-of-distributors")

@pytest.fixture
def art25_module():
    return _load_module("art25-value-chain-responsibilities")

@pytest.fixture
def art41_module():
    return _load_module("art41-common-specifications")

@pytest.fixture
def art60_module():
    return _load_module("art60-real-world-testing")

@pytest.fixture
def art61_module():
    return _load_module("art61-informed-consent-testing")

@pytest.fixture
def art71_module():
    return _load_module("art71-eu-database")

@pytest.fixture
def art80_module():
    return _load_module("art80-non-high-risk-misclassification")

@pytest.fixture
def art82_module():
    return _load_module("art82-compliant-ai-presenting-risk")

@pytest.fixture
def art91_module():
    return _load_module("art91-documentation-duty")

@pytest.fixture
def art92_module():
    return _load_module("art92-cooperation-with-evaluations")

@pytest.fixture
def art111_module():
    return _load_module("art111-transitional-provisions")
