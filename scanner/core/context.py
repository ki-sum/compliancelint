"""
AI-First Project Context — the bridge between AI understanding and rule-based scanning.

Architecture principle: AI is the eyes, Scanner is the rule engine.

The AI client (Claude in MCP mode) reads the project and fills
in two things:
  1. ProjectStructure — what kind of project this is, what files exist
  2. ComplianceAnswers — per-article answers to specific compliance questions

The scanner modules receive this context and do ONLY obligation mapping:
  AI answer → legal obligation → Finding (COMPLIANT / NON_COMPLIANT / UNABLE_TO_DETERMINE)

There is NO regex detection in scanner modules. Detection is 100% the AI's job.
This means the scanner works for any language, any encoding, any naming convention.

Note: ComplianceLint is MCP-only. There is no CLI or offline mode.

There is NO offline fallback. AI is required.
"""

import json
import re
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


# Fields that must be lists (never strings) per article — used by get_article_answers()
_LIST_FIELDS: dict = {
    "art8":  ["section_2_evidence"],
    "art5":  [],
    "art6":  ["annex_iii_categories"],
    "art9":  ["risk_doc_paths", "testing_evidence", "risk_code_evidence", "metrics_evidence"],
    "art10": ["data_doc_paths", "bias_evidence"],
    "art11": ["doc_paths", "documented_aspects"],
    "art12": ["logging_evidence"],
    "art13": ["explainability_evidence", "transparency_paths"],
    "art14": ["oversight_evidence", "override_evidence"],
    "art15": ["accuracy_evidence", "robustness_evidence"],
    "art17": ["qms_evidence"],
    "art18": [],
    "art19": [],
    "art20": [],
    "art21": [],
    "art43": [],
    "art47": [],
    "art48": [],
    "art50": ["disclosure_evidence", "emotion_biometric_evidence", "deep_fake_evidence"],
    "art4":  ["literacy_evidence"],
    "art16": [],
    "art22": [],
    "art23": [],
    "art24": [],
    "art25": [],
    "art26": [],
    "art27": [],
    "art41": [],
    "art49": [],
    "art51": [],
    "art52": [],
    "art53": ["documentation_evidence", "downstream_doc_evidence"],
    "art54": ["representative_evidence"],
    "art55": ["evaluation_evidence"],
    "art60": [],
    "art61": [],
    "art71": [],
    "art72": [],
    "art73": [],
    "art80": [],
    "art82": [],
    "art86": [],
    "art91": [],
    "art92": [],
    "art111": [],
}

# Fields that must be bool or None (never strings like "true")
_BOOL_FIELDS: dict = {
    "art8":  ["has_section_2_compliance", "is_annex_i_product", "has_annex_i_compliance"],
    "art5":  [# Read by modules/art05-prohibited-practices/module.py _PROHIBITION_FIELDS
              "has_subliminal_manipulation", "has_exploitation_of_vulnerabilities",
              "has_social_scoring", "has_predictive_policing",
              "has_facial_recognition_scraping", "has_emotion_recognition_workplace",
              "has_biometric_categorization", "has_real_time_biometric_id",
              # Art. 5(1)(ba)/(bb), Reg (EU) 2026/1744 — apply from 2026-12-02
              "has_ncii_generation", "has_csam_generation"],
    "art6":  ["is_high_risk"],
    "art9":  ["has_risk_docs", "has_testing_infrastructure", "has_risk_code_patterns", "has_defined_metrics", "affects_children"],
    "art10": ["has_data_governance_doc", "has_bias_mitigation", "has_data_lineage", "processes_special_category_data"],
    "art11": ["has_technical_docs", "is_annex_i_product"],
    "art12": ["has_logging", "has_retention_config"],
    "art13": ["has_explainability", "has_transparency_info"],
    "art14": ["has_human_oversight", "has_override_mechanism"],
    "art15": ["has_accuracy_testing", "has_robustness_testing", "has_fallback_behavior", "continues_learning_after_deployment"],
    "art17": ["has_qms_documentation", "has_compliance_strategy", "has_design_procedures",
              "has_qa_procedures", "has_testing_procedures", "has_technical_specifications",
              "has_data_management", "has_risk_management_in_qms", "has_post_market_monitoring",
              "has_record_keeping", "has_accountability_framework"],
    "art18": ["has_documentation_retention_policy"],
    "art19": ["has_log_retention", "has_retention_config"],
    "art43": ["has_internal_control_assessment", "has_change_management_procedures"],
    "art47": ["has_doc_declaration", "has_annex_v_content"],
    # Art. 48 (CE marking): seven result fields (one per record) and four condition fields
    # (is_provided_digitally, has_notified_body_assessment, is_subject_to_other_ce_marking_law,
    # has_ce_marking_promotional_material) that decide whether Art. 48(2), (4) and (5) apply at all.
    "art48": ["has_ce_marking", "has_digital_ce_marking", "has_notified_body_number",
              "has_notified_body_number_in_promotion", "follows_general_ce_marking_principles",
              "notified_body_number_affixed_by_permitted_actor",
              "ce_marking_indicates_other_union_law_compliance", "is_provided_digitally",
              "has_notified_body_assessment", "is_subject_to_other_ce_marking_law",
              "has_ce_marking_promotional_material"],
    "art50": ["is_chatbot_or_interactive_ai", "is_generating_synthetic_content",
              "has_ai_disclosure_to_users", "has_content_watermarking",
              "is_emotion_recognition_system", "is_biometric_categorization_system",
              "has_emotion_biometric_disclosure", "is_deep_fake_system",
              "has_deep_fake_disclosure",
              # Art. 50(4) second subparagraph (acceptance round 2, 2026-10-09)
              "publishes_public_interest_text"],
    "art20": ["has_corrective_action_procedure", "has_supply_chain_notification",
              "has_risk_investigation_procedure"],
    "art72": ["has_pmm_system", "has_active_data_collection", "has_pmm_plan"],
    "art73": ["has_incident_reporting_procedure", "has_reporting_timelines",
              "has_expedited_reporting_procedure", "has_investigation_procedure"],
    "art86": ["has_explanation_mechanism"],
    "art21": ["has_conformity_documentation", "has_log_export_capability"],
    "art23": ["is_importer", "has_pre_market_verification", "has_conformity_review",
              "has_importer_identification", "has_documentation_retention",
              "has_authority_documentation"],
    "art24": ["is_distributor", "has_pre_market_verification", "has_conformity_review",
              "has_authority_documentation"],
    "art91": ["has_information_supply_readiness"],
    "art92": ["has_evaluation_cooperation_readiness"],
    "art111": ["has_transition_plan", "has_significant_change_tracking", "has_gpai_compliance_timeline"],
    "art4":  ["has_ai_literacy_measures"],
    "art16": ["has_section_2_compliance", "has_provider_identification", "has_qms"],
    "art22": ["is_eu_established_provider", "has_authorised_representative", "has_representative_enablement"],
    "art25": ["has_rebranding_or_modification", "has_provider_cooperation_documentation", "is_safety_component_annex_i"],
    "art26": ["has_deployment_documentation", "has_human_oversight_assignment", "has_operational_monitoring"],
    "art27": ["has_fria_documentation", "has_fria_versioning"],
    "art41": ["follows_common_specifications", "has_alternative_justification"],
    "art49": ["has_eu_database_registration"],
    "art51": ["is_gpai_model", "has_high_impact_capabilities", "training_compute_exceeds_threshold"],
    "art52": ["has_commission_notification"],
    "art53": ["has_technical_documentation", "has_downstream_documentation"],
    "art54": ["is_third_country_provider", "has_authorised_representative", "has_written_mandate"],
    "art55": ["has_systemic_risk", "has_model_evaluation", "has_adversarial_testing"],
    "art60": ["has_testing_plan", "has_incident_reporting_for_testing", "has_authority_notification_procedure"],
    "art61": ["has_informed_consent_procedure", "has_consent_documentation"],
    "art71": ["has_provider_database_entry"],
    "art80": ["has_compliance_remediation_plan", "has_corrective_action_for_all_systems", "has_classification_rationale"],
    "art82": ["has_corrective_action_procedure"],
    "_scope": ["is_ai_system", "territorial_scope_applies", "is_open_source",
               "is_military_defense", "is_research_only",
               "is_biometric_system", "is_financial_institution", "is_distributor",
               "is_importer", "is_gpai_provider",
               # 2026-04-29 Phase 3 §E — schema sync. AR was added to SaaS UI
               # + DB + scan-settings API on 2026-04-26 (commits 541dfcf,
               # 28d3fcd) but the scanner _scope schema was never updated.
               # Free MCP without SaaS connection had AI-supplied
               # is_authorised_representative silently dropped because the
               # schema didn't recognize the field.
               "is_authorised_representative"],
    # NOTE on sme_status: this is a STRING enum (microenterprise/small/
    # medium per Recommendation 2003/361/EC, small_mid_cap per
    # Recommendation (EU) 2025/1099, large), NOT a bool. It MUST
    # NOT live in _BOOL_FIELDS — the coerce step would try to map the
    # string to bool/None and silently destroy it. Like risk_classification,
    # sme_status is read directly from _scope when needed and is populated
    # by _apply_saas_settings_to_scope on paid tiers (Phase 2 §B). No
    # standalone validation is needed at the AI-template stage; the SaaS
    # response is the authority for paid users, and scanner falls back to
    # absent/None for free + offline.
}


# Keys article modules read that are neither bool- nor list-validated:
# free-text evidence strings and legacy aliases (fallbacks — the canonical
# field wins in the module). validation_gate must never fuzzy-rename these
# onto a schema field: the rename overwrote the boolean with the evidence
# string (Art 5) or the canonical answer with the alias (self-audit A1,
# 2026-10-02). tests/test_validation_gate_aux_fields.py keeps this in sync
# with every `answers.get("...")` in modules/.
# Number answers (int or float; null when unknown) — template-gap task 2026-10-04. Coerced from numeric
# strings by the validation gate; anything else is a validation error (never renamed or turned into a bool).
_NUMBER_FIELDS: dict = {}

_NUMBER_RE = re.compile(
    r"^\s*(?:(?P<mant>[-+]?\d+(?:\.\d+)?)\s*(?:x|×|\*)\s*)?10\s*\^\s*(?P<exp>[-+]?\d+)\s*[a-zA-Z ]*$"
    r"|^\s*(?P<plain>[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?)\s*[a-zA-Z ]*$"
)


def _parse_number(val):
    """A number answer: int / float as is; a string such as "180", "180 days", "1e25", "1.5e25 FLOPs",
    "10^26" or "3.5 x 10^26" → int / float; anything else (bool, text, list, NaN, inf) → None."""
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return val if val == val and val not in (float("inf"), float("-inf")) else None
    if not isinstance(val, str):
        return None
    m = _NUMBER_RE.match(val)
    if not m:
        return None
    if m.group("plain") is not None:
        text = m.group("plain")
        return int(text) if re.fullmatch(r"[-+]?\d+", text) else float(text)
    return float(m.group("mant") or 1) * 10.0 ** int(m.group("exp"))

_AUX_FIELDS: dict = {
    # module.py reads `<has_ field minus "has_">_evidence` next to each boolean
    "art5":  ["subliminal_manipulation_evidence", "exploitation_of_vulnerabilities_evidence",
              "social_scoring_evidence", "predictive_policing_evidence",
              "facial_recognition_scraping_evidence", "emotion_recognition_workplace_evidence",
              "biometric_categorization_evidence", "real_time_biometric_id_evidence",
              "ncii_generation_evidence", "csam_generation_evidence"],
    # The legacy aliases (art9 has_risk_code / has_metrics / has_testing, art10 has_bias_detection,
    # art12 / art19 has_retention_policy, art15 has_accuracy_metrics, + 8 unregistered ones) were removed
    # 2026-10-04 (template-gap T1): modules read only template fields; free-text slots are added below.
}


def _art5_ba_bb_from() -> str:
    from core.application_dates import article
    return article(5)["exceptions"][0]["applicable_from"]


_ANSWER_KEY = " false if it does not; null if you cannot determine it from the project."
# Art. 5(1a) test — wording verified by o3 (Prompt D, D55, 2026-10-02)
_ART5_1A = (
    "For placing on the market or putting into service (Art. 5(1a)(a)), true only if (1) that generation or "
    "manipulation is the intended purpose, or (2) the system's design, training, architecture, capabilities or "
    "user-facing functionalities make it a reasonably foreseeable and reproducible outcome without requiring "
    "significant technical modification and the system does not have reasonable and adequate technical safety "
    "measures and other safeguards that reliably prevent it, taking into account reasonably foreseeable misuse, "
    "and correct observed or reported misuse. For use (Art. 5(1a)(b)), true only where the deployer uses the "
    "system for that purpose."
)

# What each answer field means — returned by cl_analyze_project as
# compliance_answers_field_descriptions (self-audit B2, 2026-10-02). "true" for an
# Art. 5 field means the prohibited practice IS present (a violation signal).
_SCOPE_RISK_FIELDS = ("risk_classification", "risk_classification_confidence", "risk_reasoning",
                      # Text slot read by the Art. 2(12) reason (acceptance round 2, 2026-10-09).
                      "open_source_license")

_FIELD_DESCRIPTIONS: dict = {
    "_scope": {
        "risk_classification": (
            "REQUIRED. The EU AI Act risk class of the system, one of: 'prohibited' (an Art. 5 practice), "
            "'high-risk' (Art. 6: a safety component / product under Annex I, or an Annex III use case), "
            "'limited-risk' (only the Art. 50 transparency obligations), 'minimal-risk' (none of these). Put any "
            "uncertainty in risk_classification_confidence, not in this value."
        ),
        "risk_classification_confidence": (
            "'high', 'medium' or 'low' — how certain the risk_classification is. With 'low', the articles that "
            "apply only to high-risk systems are still scanned."
        ),
        "risk_reasoning": "One or two sentences on why the system has this risk class (cite the files you read).",
        # Answer-template key fixes before release (acceptance run A, 2026-10-08): these fields drive the scope gates.
        "is_biometric_system": (
            "true only if the system is a remote biometric identification system referred to in Annex III point 1(a) "
            "— the Art. 12(3) logging and Art. 14(5) separate-verification duties apply only to these. false for "
            "biometric verification whose sole purpose is to confirm that a specific person is who they claim to be, "
            "and for every other system; null if you cannot determine it from the project."
        ),
        "open_source_license": (
            "Text: the SPDX identifier of the licence the system is released under (e.g. \"MIT\", \"Apache-2.0\"); "
            "empty if it is not released under a free and open-source licence."
        ),
        "is_open_source": (
            "true only if the system is released under a free and open-source licence AND it is not high-risk "
            "(Art. 6), involves no Art. 5 practice and does not fall under Art. 50 — Art. 2(12) then excludes the AI "
            "system from the Regulation; obligations for general-purpose AI models (Art. 51-55) are assessed "
            "separately. false for proprietary or source-available-but-restricted licences, or if any of these "
            "exceptions applies; null if you cannot determine it from the project."
        ),
        "is_gpai_provider": (
            "true if this organisation is a provider within Art. 3(3) of a general-purpose AI model within Art. 3(63) "
            "— it develops the model, or has it developed, and places it on the market under its own name or "
            "trademark; false if it is not; null if you cannot determine it from the project."
        ),
        "is_authorised_representative": (
            "true if this organisation is established in the Union, has received and accepted a written mandate "
            "within Art. 3(5), and the appointing provider is established in a third country; for a high-risk AI "
            "system the Art. 22 duties apply, and for a general-purpose AI model the Art. 54 duties apply; false if "
            "these conditions are not met; null if you cannot determine it from the project."
        ),
    },
    "art5": {
        "has_subliminal_manipulation": (
            "true if the system deploys subliminal techniques beyond a person's consciousness, or purposefully "
            "manipulative or deceptive techniques, with the objective or effect of materially distorting "
            "behaviour by appreciably impairing the ability to make an informed decision, thereby causing the "
            "person or group to take a decision they would not otherwise have taken, in a manner that causes or "
            "is reasonably likely to cause significant harm (Art. 5(1)(a));" + _ANSWER_KEY),
        "has_exploitation_of_vulnerabilities": (
            "true if the system exploits vulnerabilities of a person or group due to their age, disability or a "
            "specific social or economic situation, with the objective or effect of materially distorting their "
            "behaviour in a manner that causes or is reasonably likely to cause significant harm "
            "(Art. 5(1)(b));" + _ANSWER_KEY),
        "has_social_scoring": (
            "true if the system evaluates or classifies natural persons or groups over a certain period of time "
            "based on their social behaviour or known, inferred or predicted personal or personality "
            "characteristics, with the score leading to detrimental or unfavourable treatment in unrelated "
            "social contexts or treatment that is unjustified or disproportionate (Art. 5(1)(c));" + _ANSWER_KEY),
        "has_predictive_policing": (
            "true if the system assesses or predicts the risk of a natural person committing a criminal offence "
            "based solely on profiling or on assessing personality traits and characteristics (Art. 5(1)(d)); "
            "supporting a human assessment already based on objective and verifiable facts directly linked to "
            "a criminal activity does not count;" + _ANSWER_KEY),
        "has_facial_recognition_scraping": (
            "true if the system creates or expands facial recognition databases through the untargeted scraping "
            "of facial images from the internet or CCTV footage (Art. 5(1)(e));" + _ANSWER_KEY),
        "has_emotion_recognition_workplace": (
            "true if the system infers emotions of natural persons in the areas of workplace or education "
            "institutions, unless it is intended to be put in place or into the market for medical or safety "
            "reasons (Art. 5(1)(f));" + _ANSWER_KEY),
        "has_biometric_categorization": (
            "true if the system categorises individual natural persons based on their biometric data to deduce "
            "or infer their race, political opinions, trade union membership, religious or philosophical "
            "beliefs, sex life or sexual orientation (Art. 5(1)(g)); labelling or filtering of lawfully acquired "
            "biometric datasets and categorising biometric data in the area of law enforcement do not count;"
            + _ANSWER_KEY),
        "has_real_time_biometric_id": (
            "true if the system is used for 'real-time' remote biometric identification in publicly accessible "
            "spaces for law-enforcement purposes (Art. 5(1)(h)), unless the use is strictly necessary for one of "
            "the objectives in Art. 5(1)(h)(i)-(iii) and complies with the applicable conditions in Art. 5(2)-(5), "
            "including the authorisation rule and urgency procedure in Art. 5(3) and the Member State's "
            "national-law framework under Art. 5(5); Art. 5(6)-(7) concern reporting;" + _ANSWER_KEY),
        "has_ncii_generation": (
            "Art. 5(1)(ba) — realistic images, videos, audio or similar material of an identifiable person's "
            "intimate parts, or of an identifiable person engaged in sexually explicit activities, without that "
            "person's freely-given, specific, informed, unambiguous and explicit consent. " + _ART5_1A + " "
            "For manipulation, Art. 5(1b) also applies: conduct that neither increases exposure of depicted "
            "intimate parts nor alters the nature of depicted sexually explicit activities is not manipulation "
            "for this prohibition. Mere capability to generate images is not enough. Applies from "
            + _art5_ba_bb_from() + ";" + _ANSWER_KEY),
        "has_csam_generation": (
            "Art. 5(1)(bb) — material or performance within Article 2(c) and (e) of Directive 2011/93/EU, unless "
            "a 'without right' defence applies under national law. " + _ART5_1A + " Mere capability is not "
            "enough. Applies from " + _art5_ba_bb_from() + ";" + _ANSWER_KEY),
    },
}
for _has in list(_FIELD_DESCRIPTIONS["art5"]):
    _FIELD_DESCRIPTIONS["art5"][_has.replace("has_", "") + "_evidence"] = (
        f"Free text: what you found (files, functions, configuration, documentation) that supports your "
        f"answer to {_has}. Leave empty if there is nothing to report."
    )

# Template-gap task (2026-10-04): answer keys the article modules read that were missing from the template —
# the AI was never asked for them, so the obligations they decide were always UNABLE_TO_DETERMINE.
# Descriptions (o3-verified) live in data/answer_field_descriptions.json; tests/test_template_gap.py also
# fails when a module reads a key that is not in the template.
_TEMPLATE_GAP_FIELDS: dict = {
    "bool": {
        "art6": ["has_risk_classification_doc"], "art10": ["uses_model_training"],
        "art16": ["has_documentation_kept", "has_log_retention", "has_conformity_assessment", "has_eu_declaration",
                  "has_ce_marking", "has_registration", "has_corrective_actions_process", "has_conformity_evidence",
                  "has_accessibility_compliance"],
        "art22": ["has_mandate_authority_contact"],
        "art25": ["has_third_party_written_agreement", "has_open_source_exception"],
        "art26": ["has_log_retention", "has_affected_persons_notification"],
        # Applicability answers of ART49-OBL-2 and of the conditional Art. 52 records. Until 2026-10-12 only the
        # dashboard's settings supplied them, so without a dashboard those records could not be decided.
        "art49": ["claims_art6_3_exception"],
        "art51": ["has_systemic_risk_assessment", "has_commission_designation"],
        "art52": ["is_gpai_with_systemic_risk"],
        "art53": ["has_copyright_policy", "has_training_data_summary", "training_data_summary_public",
                  "is_open_source_gpai", "has_systemic_risk"],
        "art54": ["is_open_source_gpai", "has_systemic_risk"],
        "art55": ["has_incident_tracking", "has_cybersecurity_protection"],
    },
    "list": {
        "art53": ["copyright_policy_evidence", "training_data_evidence"], "art54": ["mandate_evidence"],
        "art55": ["incident_evidence", "cybersecurity_evidence"], "art86": ["explanation_evidence"],
    },
    "number": {"art12": ["retention_days"], "art19": ["retention_days"], "art26": ["retention_days"],
               "art51": ["training_compute_flops"]},
    "text": {
        "art4": ["literacy_description"], "art6": ["annex_i_product_type", "reasoning"],
        "art12": ["logging_description", "retention_evidence"], "art18": ["retention_policy_evidence"],
        "art19": ["retention_evidence"], "art26": ["retention_evidence"], "art51": ["reasoning"],
        "art52": ["notification_evidence"], "art91": ["readiness_evidence"], "art92": ["cooperation_evidence"],
        "art111": ["transition_evidence", "change_tracking_evidence", "gpai_timeline_evidence"],
    },
}
for _kind, _registry in (("bool", _BOOL_FIELDS), ("list", _LIST_FIELDS), ("number", _NUMBER_FIELDS),
                         ("text", _AUX_FIELDS)):
    for _art, _keys in _TEMPLATE_GAP_FIELDS[_kind].items():
        _registry.setdefault(_art, [])
        _registry[_art].extend(k for k in _keys if k not in _registry[_art])

with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data",
                       "answer_field_descriptions.json"), encoding="utf-8") as _f:
    for _art, _descs in json.load(_f).items():
        if not _art.startswith("_"):
            _FIELD_DESCRIPTIONS.setdefault(_art, {}).update(_descs)


# Art. 50(4) second subparagraph had no answer field, so ART50-OBL-4b — and with it Art. 50(5) — could never be
# settled, and the Art. 2(12) contradiction check missed that Art. 50 case (acceptance round 2, 2026-10-09).
_FIELD_DESCRIPTIONS.setdefault("art50", {})["publishes_public_interest_text"] = (
    "true if the system generates or manipulates text that is published with the purpose of informing the public on "
    "matters of public interest (Art. 50(4), second subparagraph); false if it does not; null if you cannot determine "
    "it from the project."
)


def _fill_application_date_placeholders() -> None:
    """Art. 113 dates are never typed into texts (template check 9): the data file holds placeholders."""
    from core.application_dates import chapter_iii_dates, long_date
    dates = chapter_iii_dates()
    values = {"{chapter_iii_annex_iii}": long_date(dates["annex_iii"]),
              "{chapter_iii_annex_i}": long_date(dates["annex_i"])}
    for _descs in _FIELD_DESCRIPTIONS.values():
        for _key, _text in list(_descs.items()):
            for token, value in values.items():
                _text = _text.replace(token, value)
            _descs[_key] = _text


_fill_application_date_placeholders()


@dataclass
class ProjectContext:
    """AI-provided understanding of a project.

    The AI fills this in after reading project files.
    The scanner uses this instead of hardcoded assumptions.

    compliance_answers is the key new field: per-article answers to compliance
    questions. Each article reads its own sub-dict from here.

    Schema for compliance_answers:
    {
      "art5": {
        # one pair per prohibition; true = the practice IS present (see
        # compliance_answers_field_descriptions returned by cl_analyze_project)
        "has_subliminal_manipulation": true | false | null,
        "subliminal_manipulation_evidence": "what was found, or empty string",
        "has_exploitation_of_vulnerabilities": true | false | null,
        "exploitation_of_vulnerabilities_evidence": "what was found, or empty string",
        "has_social_scoring": true | false | null,
        "social_scoring_evidence": "what was found, or empty string",
        "has_predictive_policing": true | false | null,
        "predictive_policing_evidence": "what was found, or empty string",
        "has_facial_recognition_scraping": true | false | null,
        "facial_recognition_scraping_evidence": "what was found, or empty string",
        "has_emotion_recognition_workplace": true | false | null,
        "emotion_recognition_workplace_evidence": "what was found, or empty string",
        "has_biometric_categorization": true | false | null,
        "biometric_categorization_evidence": "what was found, or empty string",
        "has_real_time_biometric_id": true | false | null,
        "real_time_biometric_id_evidence": "what was found, or empty string",
        "has_ncii_generation": true | false | null,
        "ncii_generation_evidence": "what was found, or empty string",
        "has_csam_generation": true | false | null,
        "csam_generation_evidence": "what was found, or empty string",
      },
      "art6": {
        "annex_iii_categories": ["1(a)", "4(a)", ...],  # Annex III points, point + letter
        "annex_i_product_type": null | "Medical device" | ...,
        "is_high_risk": true | false | null,
        "reasoning": "one sentence explanation"
      },
      "art9": {
        "has_risk_docs": true | false | null,
        "risk_doc_paths": ["docs/risk_assessment.md", ...],
        "has_testing_infrastructure": true | false | null,
        "testing_evidence": ["tests/", "benchmarks/", ...],
        "has_risk_code_patterns": true | false | null,
        "risk_code_evidence": ["description of what was found"]
      },
      "art10": {
        "has_data_governance_doc": true | false | null,
        "data_doc_paths": ["docs/data_sheet.md", ...],
        "has_bias_mitigation": true | false | null,
        "bias_evidence": ["description"],
        "has_data_lineage": true | false | null
      },
      "art11": {
        "has_technical_docs": true | false | null,
        "doc_paths": ["docs/architecture.md", ...],
        "documented_aspects": ["model architecture", "training data", "performance metrics", ...]
      },
      "art12": {
        "has_logging": true | false | null,
        "logging_description": "e.g. uses structlog with JSON output",
        "logging_evidence": ["src/logging_config.py:5", ...],
        "has_retention_config": true | false | null,
        "retention_days": null | 180 | 365,
        "retention_evidence": "description of where retention is configured"
      },
      "art13": {
        "has_explainability": true | false | null,
        "explainability_evidence": ["description"],
        "has_transparency_info": true | false | null,
        "transparency_paths": ["docs/model_card.md", ...]
      },
      "art14": {
        "has_human_oversight": true | false | null,
        "oversight_evidence": ["description of approval flow, review gates, etc."],
        "has_override_mechanism": true | false | null,
        "override_evidence": ["description"]
      },
      "art15": {
        "has_accuracy_testing": true | false | null,
        "accuracy_evidence": ["tests/test_accuracy.py", ...],
        "has_robustness_testing": true | false | null,
        "robustness_evidence": ["description"],
        "has_fallback_behavior": true | false | null
      },
      "art50": {
        "is_chatbot_or_interactive_ai": true | false | null,
        "is_generating_synthetic_content": true | false | null,
        "has_ai_disclosure_to_users": true | false | null,
        "disclosure_evidence": ["description"],
        "has_content_watermarking": true | false | null
      }
    }
    """

    # ── Project identity ──
    primary_language: str = ""           # e.g. "python", "typescript", "java"
    language_confidence: str = ""        # "high" | "medium" | "low"
    languages: list = field(default_factory=list)  # all languages found
    framework: str = ""                  # e.g. "Next.js 14", "FastAPI", "Spring Boot"
    project_type: str = ""               # e.g. "web app", "ML training pipeline", "CLI tool"

    # ── AI classification ──
    # risk_classification holds the EU AI Act legal category. The 4 canonical
    # values map 1:1 to dashboard RISK_OPTIONS and to the law itself:
    #   - prohibited (Art. 5)
    #   - high-risk (Art. 6 + Annex III)
    #   - limited-risk (Art. 50 transparency obligations)
    #   - minimal-risk (no specific obligations)
    # AI uncertainty about WHICH category applies goes in the separate
    # `risk_classification_confidence` field, NOT mixed into the value (i.e.
    # "likely high-risk" is no longer accepted — use risk_classification="high-risk"
    # plus risk_classification_confidence="medium" instead).
    risk_classification: str = ""        # one of: prohibited | high-risk | limited-risk | minimal-risk | "" (empty when AI cannot determine)
    risk_reasoning: str = ""             # Why the AI thinks so (free text)
    risk_classification_confidence: str = ""  # "high" | "medium" | "low"
    ai_libraries: list = field(default_factory=list)  # e.g. ["openai", "transformers"]

    # ── File classification (AI decides, not hardcoded) ──
    source_dirs: list = field(default_factory=list)
    test_dirs: list = field(default_factory=list)
    generated_files: list = field(default_factory=list)
    config_files: list = field(default_factory=list)
    doc_files: list = field(default_factory=list)

    # ── Infrastructure (AI identifies, not hardcoded lists) ──
    logging_framework: str = ""
    logging_framework_confidence: str = ""
    logging_config_file: str = ""
    monitoring_tools: list = field(default_factory=list)
    monitoring_tools_confidence: str = ""
    monitoring_files: list = field(default_factory=list)
    test_framework: str = ""

    # ── AI attribution (audit trail) ──
    # Which AI model assessed this project. Appended to every finding description
    # so reviewers know whether to trust the result or re-run with a better model.
    # Format: "claude-opus-4-6", "gpt-4o", "mistral-large-latest", etc.
    # Set by the AI client in compliance_answers.
    ai_model: str = ""

    # ── Per-article compliance answers (THE KEY NEW FIELD) ──
    # AI reads source code and answers compliance questions per article.
    # Scanner modules read from here instead of running their own detection.
    compliance_answers: dict = field(default_factory=dict)



    # ── AI disambiguation cache ──
    disambiguations: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectContext":
        """Create from dict, ignoring unknown keys for forward compatibility.

        Smart detection: if top-level keys look like article answers (e.g., "art12"),
        auto-wrap them into compliance_answers. This handles the common case where
        users pass {"art12": {...}} instead of {"compliance_answers": {"art12": {...}}}.
        """
        known_fields = {f for f in cls.__dataclass_fields__}

        # Check if user passed article answers at top level instead of nested
        article_keys = {k for k in data if k.startswith("art") or k.startswith("_scope") or k.startswith("_scan")}
        non_field_articles = article_keys - known_fields
        if non_field_articles and "compliance_answers" not in data:
            # User passed {"art12": {...}} directly — wrap into compliance_answers
            compliance = {}
            other = {}
            for k, v in data.items():
                if k.startswith("art") or k.startswith("_scope") or k.startswith("_scan"):
                    compliance[k] = v
                else:
                    other[k] = v
            other["compliance_answers"] = compliance
            data = other

        filtered = {k: v for k, v in data.items() if k in known_fields}
        ctx = cls(**filtered)

        # S-B15 (2026-10-07): cl_scan's gate requires the risk class in compliance_answers._scope (where the
        # answers template puts it), but only cl_scan_all copied it onto the context before the modules'
        # high-risk-only check — a single-article cl_scan saw "" and scanned the 28 high-risk-only articles of a
        # minimal-risk project. Take the _scope values here when the top-level fields are absent (the top-level
        # fields and .compliancelintrc overrides still win).
        scope = ctx.compliance_answers.get("_scope") if isinstance(ctx.compliance_answers, dict) else None
        if isinstance(scope, dict) and not ctx.risk_classification and scope.get("risk_classification"):
            ctx.risk_classification = str(scope["risk_classification"])
            if not ctx.risk_classification_confidence:
                ctx.risk_classification_confidence = str(scope.get("risk_classification_confidence") or "")
            if not ctx.risk_reasoning:
                ctx.risk_reasoning = str(scope.get("risk_reasoning") or "")
        return ctx

    @classmethod
    def from_json(cls, json_str: str) -> "ProjectContext":
        return cls.from_dict(json.loads(json_str))

    @property
    def is_empty(self) -> bool:
        """Check if this context has been populated by AI."""
        return not self.primary_language and not self.compliance_answers

    def get_article_answers(self, article_key: str) -> dict:
        """Get compliance answers for a specific article, with type coercion.

        Coerces common AI output errors:
          - List fields that are strings → wrapped in a list
          - Bool fields that are "true"/"false" strings → proper bool
          - Bool fields that are 1/0 integers → proper bool

        Args:
            article_key: e.g. "art9", "art12", "art50"

        Returns:
            dict of answers (type-safe), empty dict if not provided.
        """
        raw = self.compliance_answers.get(article_key, {})
        if not raw:
            return raw
        result = dict(raw)

        # Coerce list fields
        for field in _LIST_FIELDS.get(article_key, []):
            if field in result and not isinstance(result[field], list):
                val = result[field]
                result[field] = [val] if val else []

        # Coerce bool fields: string → bool/None, int → bool
        for field in _BOOL_FIELDS.get(article_key, []):
            if field in result:
                val = result[field]
                if isinstance(val, str):
                    low = val.lower().strip()
                    if low in ("true", "yes", "1"):
                        result[field] = True
                    elif low in ("false", "no", "0"):
                        result[field] = False
                    elif low in ("null", "none", ""):
                        result[field] = None
                elif isinstance(val, int) and not isinstance(val, bool):
                    result[field] = bool(val)

        # Number fields: a numeric string → int / float; any other non-number → None (unknown), so a module
        # comparing e.g. retention_days >= 180 never meets a string (the validation gate reports the bad value).
        for field in _NUMBER_FIELDS.get(article_key, []):
            if field in result:
                result[field] = _parse_number(result[field])

        return result


def _build_answers_template() -> dict:
    """Build a complete empty compliance_answers template from _BOOL_FIELDS and _LIST_FIELDS.

    Every article key with all its fields pre-set to null (bools) or [] (lists).
    The AI fills in values; unfilled fields remain null → UNABLE_TO_DETERMINE.

    This is returned by cl_analyze_project() so the AI has an exact template
    to fill rather than inventing its own keys.
    """
    template = {}
    all_articles = sorted(set(_BOOL_FIELDS.keys()) | set(_LIST_FIELDS.keys()))
    for art_key in all_articles:
        if art_key.startswith("_"):
            continue  # _scope is handled separately
        fields = {}
        for field_name in _BOOL_FIELDS.get(art_key, []):
            fields[field_name] = None
        for field_name in _LIST_FIELDS.get(art_key, []):
            fields[field_name] = []
        for field_name in _NUMBER_FIELDS.get(art_key, []):
            fields[field_name] = None
        # Free-text slots the module reads (evidence, reasoning, descriptions) — the ones with a description;
        # legacy aliases have none and stay out of the template.
        for field_name in _AUX_FIELDS.get(art_key, []):
            if field_name in _FIELD_DESCRIPTIONS.get(art_key, {}):
                fields[field_name] = ""
        template[art_key] = fields

    # Add _scope separately
    template["_scope"] = {}
    for field_name in _BOOL_FIELDS.get("_scope", []):
        template["_scope"][field_name] = None
    # The risk class is required by validation_gate.validate_scope; it was missing from the template, so an AI that
    # filled the template exactly hit the scope error (acceptance run A1, 2026-10-07).
    for field_name in _SCOPE_RISK_FIELDS:
        template["_scope"][field_name] = ""

    # B1 self-audit follow-up 2026-04-30 — _oid_answers field for
    # per-obligation questionnaire answers (paid feature). When SaaS
    # narrows applicable_obligations, AI client MUST fill an answer
    # for each OID listed in `_saas_questionnaire`:
    #   "_oid_answers": {
    #     "ART9-OBL-1": true,    # answered yes (compliant)
    #     "ART9-OBL-3": false,   # answered no (non-compliant)
    #     "ART11-OBL-1": null    # cannot determine (skipped)
    #   }
    # Free tier (no SaaS questionnaire) → leave as null. Strict mode
    # without per-OID answers blocks the scan with `missing: answer`
    # in pending_obligations — false-COMPLIANT pre-B1 bug class.
    template["_oid_answers"] = None

    return template


def _build_scanning_strategy() -> dict:
    """Build per-article scanning guidance from the obligation rows.

    Detection hints (automation_assessment.detection_method / what_to_scan) are not in
    the public obligation JSONs since §AA (2026-05-02); obligation_lookup merges them in
    from the SaaS classification API. Without that metadata the strategy is empty and
    says why (self-audit B2, 2026-10-02 — it used to be silently empty for all articles).
    """
    from core import obligation_lookup

    per_article: dict = {}
    for row in obligation_lookup.iter_obligation_rows():
        m = re.match(r"ART0*(\d+)-", row.get("id", ""))
        auto = row.get("automation_assessment") or {}
        method = auto.get("detection_method", "")
        if not m or not method or method == "N/A" or "permission" in method.lower():
            continue
        entry = per_article.setdefault(f"art{m.group(1)}", {"what_to_scan": set(), "detection_hints": []})
        entry["detection_hints"].append(method)
        entry["what_to_scan"].update(auto.get("what_to_scan", []))

    articles = {
        key: {"what_to_scan": sorted(v["what_to_scan"]), "detection_hints": v["detection_hints"][:5]}
        for key, v in sorted(per_article.items(), key=lambda kv: int(kv[0][3:]))
    }
    strategy = {
        "instruction": (
            "For each article below, use Grep to search the ENTIRE codebase "
            "for relevant patterns based on the detection_hints. Then Read only "
            "the files that match. Use your knowledge of the project's language "
            "and framework to choose appropriate search terms — the hints describe "
            "WHAT to look for, not the exact regex. "
            "Report progress to the user every ~20 files read."
        ),
        "articles": articles,
    }
    if not articles:
        strategy["note"] = (
            "No detection hints available: they come from the ComplianceLint classification "
            "metadata, which is fetched once this project is connected to the dashboard (free). "
            "Use compliance_answers_field_descriptions to decide each answer."
        )
    return strategy


def analyze_project_metadata(project_path: str) -> dict:
    """Collect project metadata for AI to analyze.

    This function reads metadata files and samples source code.
    Designed to give the AI enough to answer both structural AND compliance questions.

    The AI client should:
    1. Call this function to get metadata + source samples
    2. Read the project files listed in the metadata
    3. Fill in ProjectContext including compliance_answers
    4. Pass the context to the scanner

    Returns a dict with project metadata + source code samples.
    """
    project_path = os.path.abspath(project_path)

    _SKIP_DIRS = frozenset({
        'node_modules', '__pycache__', '.git', 'venv', '.venv',
        'target', 'build', 'dist', '.next', '.nuxt', 'site-packages',
    })

    # ── 1. Directory tree (top 2 levels) ──
    top_dirs = []
    top_files = []
    for item in sorted(os.listdir(project_path)):
        full = os.path.join(project_path, item)
        if os.path.isdir(full):
            if item.startswith('.') and item not in ('.github', '.vscode'):
                continue
            if item in _SKIP_DIRS:
                top_dirs.append(f"{item}/ (skipped)")
                continue
            try:
                children = os.listdir(full)
                child_dirs = [c for c in children if os.path.isdir(os.path.join(full, c))]
                child_files = [c for c in children if os.path.isfile(os.path.join(full, c))]
                top_dirs.append(f"{item}/ ({len(child_dirs)} dirs, {len(child_files)} files)")
            except PermissionError:
                top_dirs.append(f"{item}/ (no access)")
        elif os.path.isfile(full):
            top_files.append(item)

    # ── 2. File type counts ──
    ext_counts = {}
    total_files = 0
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
                total_files += 1

    sorted_exts = sorted(ext_counts.items(), key=lambda x: -x[1])[:15]

    # ── 3. Read manifest/config files ──
    config_contents = {}
    manifest_files = [
        'package.json', 'requirements.txt', 'pyproject.toml', 'setup.py', 'setup.cfg',
        'Pipfile', 'Cargo.toml', 'go.mod', 'pom.xml', 'build.gradle',
        'build.gradle.kts', 'composer.json', 'Gemfile', '*.csproj',
    ]

    for mf in manifest_files:
        if mf.startswith('*'):
            import glob
            matches = glob.glob(os.path.join(project_path, mf))
            if not matches:
                matches = glob.glob(os.path.join(project_path, '*', mf))
            for match in matches[:1]:
                rel = os.path.relpath(match, project_path)
                try:
                    with open(match, 'r', encoding='utf-8', errors='ignore') as f:
                        config_contents[rel] = f.read(3000)
                except (OSError, PermissionError):
                    pass
        else:
            fpath = os.path.join(project_path, mf)
            if os.path.isfile(fpath):
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        config_contents[mf] = f.read(3000)
                except (OSError, PermissionError):
                    pass
            else:
                import glob
                matches = glob.glob(os.path.join(project_path, '*', mf))
                for match in matches[:2]:
                    rel = os.path.relpath(match, project_path)
                    try:
                        with open(match, 'r', encoding='utf-8', errors='ignore') as f:
                            config_contents[rel] = f.read(3000)
                    except (OSError, PermissionError):
                        pass

    # ── 4. README snippet ──
    readme_snippet = ""
    for readme_name in ['README.md', 'README.rst', 'README.txt', 'README']:
        rpath = os.path.join(project_path, readme_name)
        if os.path.isfile(rpath):
            try:
                with open(rpath, 'r', encoding='utf-8', errors='ignore') as f:
                    readme_snippet = f.read(500)
            except (OSError, PermissionError):
                pass
            break

    # ── 5. Sample source files (key for compliance detection) ──
    # AI needs to see actual code to answer compliance questions.
    # Sample up to 5 source files, 2KB each.
    source_samples = {}
    source_exts = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cs', '.rb', '.php'}
    sample_count = 0
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for fname in files:
            if sample_count >= 5:
                break
            ext = os.path.splitext(fname)[1].lower()
            if ext in source_exts:
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, project_path)
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        source_samples[rel] = f.read(2000)
                    sample_count += 1
                except (OSError, PermissionError):
                    pass
        if sample_count >= 5:
            break

    # ── 6. CI/CD detection ──
    ci_configs = []
    for cp in ['.github/workflows', '.gitlab-ci.yml', '.circleci/config.yml',
               'Jenkinsfile', '.travis.yml', 'azure-pipelines.yml']:
        if os.path.exists(os.path.join(project_path, cp)):
            ci_configs.append(cp)

    # ── 7. Scanning strategy (dynamic from obligation JSONs) ──
    # The project settings first: loading them hands the project's API key to the classification client, without
    # which the strategy has no detection hints (found on the production site, 2026-10-21: built before step 9 loaded them).
    from core.config import ProjectConfig
    config = ProjectConfig.load(project_path)
    scanning_strategy = _build_scanning_strategy()

    # ── 8. Empty compliance_answers template ──
    # Provide a pre-built template with ALL article keys and their fields set to null/[].
    # This forces the AI to fill every field — not just the ones it thinks are relevant.
    answers_template = _build_answers_template()

    # ── 9. Configuration status check ──
    # Detect missing setup so AI can guide user proactively.
    setup_warnings = []
    if not config.saas_api_key:
        setup_warnings.append(
            "No dashboard connection. Ask your AI: \"Set up ComplianceLint "
            "for this project\" to link to the dashboard for tracking and "
            "reporting."
        )
    if not config.attester_name or not config.attester_email:
        setup_warnings.append(
            "No attester identity configured. This is needed for submitting "
            "evidence. It will be auto-set when you connect this project to "
            "the dashboard, or you can add attester_name and attester_email "
            "to .compliancelintrc manually."
        )

    return {
        "project_path": project_path,
        "directory_tree": {"directories": top_dirs, "root_files": top_files},
        "file_types": dict(sorted_exts),
        "total_files": total_files,
        "config_contents": config_contents,
        "readme_snippet": readme_snippet,
        "source_samples": source_samples,
        "ci_configs": ci_configs,
        "scanning_strategy": scanning_strategy,
        "compliance_answers_template": answers_template,
        "compliance_answers_field_descriptions": _FIELD_DESCRIPTIONS,
        "setup_warnings": setup_warnings if setup_warnings else None,
    }


# ── compliance_answers Schema Reference ──
#
# The schema is NOT hardcoded here. It is dynamically generated from
# _BOOL_FIELDS and _LIST_FIELDS by _build_answers_template().
#
# cl_analyze_project() returns the template in its response as
# "compliance_answers_template". The AI copies this template and fills
# in values. The validation gate enforces correctness.
#
# Single source of truth: _BOOL_FIELDS + _LIST_FIELDS (above), with
# _FIELD_DESCRIPTIONS for what each field means and _AUX_FIELDS for
# module-read keys outside the bool/list schema.


# generate_context_via_api() removed — ComplianceLint is MCP-only.
# In MCP mode, Claude reads the project directly using its own file tools.
# There is no API-based CLI mode. See CLAUDE.md for the architectural decision.
