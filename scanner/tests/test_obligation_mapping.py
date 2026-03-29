"""Per-obligation mapping tests: verify every scannable obligation_id appears in findings.

For each article, loads obligation IDs from the obligation JSON (single source of truth),
runs scan with all-false and all-true compliance_answers, and verifies:
- All-false: every scannable obligation appears (as NON_COMPLIANT or UNABLE_TO_DETERMINE)
- All-true: every scannable obligation appears (as PARTIAL or COMPLIANT)

Skips non-scannable deontic types: permission, exception, exemption, empowerment,
exception_criterion, classification_rule — these are handled by gap_findings() and
may or may not appear depending on context.
"""
import json
import os
import sys
import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.protocol import BaseArticleModule, ComplianceLevel
from core.context import ProjectContext

OBLIGATIONS_DIR = os.path.join(SCANNER_ROOT, "obligations")

# Non-scannable deontic types — these obligations are informational/conditional
# and may or may not appear in findings depending on context
NON_SCANNABLE_TYPES = frozenset({
    "permission", "exception", "exemption", "empowerment",
    "exception_criterion", "classification_rule", "recommendation",
    "prohibition",  # Art.5 prohibitions have complex mapping (practice→OBL), tested separately
})

ARTICLE_MODULES = [
    (5,  "art05-prohibited-practices",   "art05-prohibited-practices.json"),
    (6,  "art06-risk-classification",    "art06-risk-classification.json"),
    (9,  "art09-risk-management",        "art09-risk-management.json"),
    (10, "art10-data-governance",        "art10-data-governance.json"),
    (11, "art11-technical-documentation","art11-technical-documentation.json"),
    (12, "art12-record-keeping",         "art12-record-keeping.json"),
    (13, "art13-transparency",           "art13-transparency.json"),
    (14, "art14-human-oversight",        "art14-human-oversight.json"),
    (15, "art15-accuracy-robustness",    "art15-accuracy-robustness.json"),
    (50, "art50-transparency-obligations","art50-transparency-obligations.json"),
]


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


def _load_scannable_obligation_ids(json_file: str) -> list[str]:
    """Load obligation IDs that should appear in scan findings.

    Excludes:
    - Non-scannable deontic types (permissions, exceptions, etc.)
    - Obligations with scope_limitation (conditional, e.g. biometric-only)
    """
    path = os.path.join(OBLIGATIONS_DIR, json_file)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    ids = []
    for obl in data.get("obligations", []):
        if obl.get("deontic_type") in NON_SCANNABLE_TYPES:
            continue
        if obl.get("scope_limitation") is not None:
            continue
        ids.append(obl["id"])
    return ids


def _all_false_answers():
    """Compliance answers where everything is false/missing."""
    return {
        "_scope": {"is_ai_system": True, "is_open_source": False,
                    "is_military_defense": False, "is_research_only": False},
        "art5": {
            "is_realtime_processing": True,
            "processing_mode_evidence": "test",
            "prohibited_practices": [
                {"practice": "biometric_surveillance", "detected": True,
                 "evidence": "test", "evidence_paths": ["test.py"], "confidence": "high"},
                {"practice": "social_scoring", "detected": True,
                 "evidence": "test", "evidence_paths": ["test.py"], "confidence": "high"},
                {"practice": "subliminal_manipulation", "detected": True,
                 "evidence": "test", "evidence_paths": ["test.py"], "confidence": "high"},
                {"practice": "prohibited_emotion_recognition", "detected": True,
                 "evidence": "test", "evidence_paths": ["test.py"], "confidence": "high"},
                {"practice": "vulnerability_exploitation", "detected": True,
                 "evidence": "test", "evidence_paths": ["test.py"], "confidence": "high"},
                {"practice": "criminal_profiling", "detected": True,
                 "evidence": "test", "evidence_paths": ["test.py"], "confidence": "high"},
                {"practice": "prohibited_real_time_biometrics", "detected": True,
                 "evidence": "test", "evidence_paths": ["test.py"], "confidence": "high"},
            ],
        },
        "art6": {"annex_iii_categories": ["biometric_identification"],
                 "annex_i_product_type": "medical_device",
                 "is_high_risk": True, "reasoning": "test"},
        "art9": {"has_risk_docs": False, "risk_doc_paths": [],
                 "has_testing_infrastructure": False, "testing_evidence": [],
                 "has_risk_code_patterns": False, "risk_code_evidence": [],
                 "has_defined_metrics": False, "metrics_evidence": []},
        "art10": {"has_data_governance_doc": False, "data_doc_paths": [],
                  "has_bias_mitigation": False, "bias_evidence": [],
                  "has_data_lineage": False},
        "art11": {"has_technical_docs": False, "doc_paths": [],
                  "documented_aspects": []},
        "art12": {"has_logging": False, "logging_description": "",
                  "logging_evidence": [], "has_retention_config": False,
                  "retention_days": None, "retention_evidence": ""},
        "art13": {"has_explainability": False, "explainability_evidence": [],
                  "has_transparency_info": False, "transparency_paths": []},
        "art14": {"has_human_oversight": False, "oversight_evidence": [],
                  "has_override_mechanism": False, "override_evidence": []},
        "art15": {"has_accuracy_testing": False, "accuracy_evidence": [],
                  "has_robustness_testing": False, "robustness_evidence": [],
                  "has_fallback_behavior": False},
        "art50": {"is_chatbot_or_interactive_ai": True,
                  "is_generating_synthetic_content": True,
                  "has_ai_disclosure_to_users": False, "disclosure_evidence": [],
                  "has_content_watermarking": False,
                  "is_emotion_recognition_system": True,
                  "is_biometric_categorization_system": True,
                  "has_emotion_biometric_disclosure": False,
                  "emotion_biometric_evidence": [],
                  "is_deep_fake_system": True,
                  "has_deep_fake_disclosure": False,
                  "deep_fake_evidence": []},
    }


def _all_true_answers():
    """Compliance answers where everything is true/present."""
    return {
        "_scope": {"is_ai_system": True, "is_open_source": False,
                    "is_military_defense": False, "is_research_only": False},
        "art5": {
            "has_subliminal_manipulation": False,
            "has_exploitation_of_vulnerabilities": False,
            "has_social_scoring": False,
            "has_predictive_policing": False,
            "has_facial_recognition_scraping": False,
            "has_emotion_recognition_workplace": False,
            "has_biometric_categorization": False,
            "has_real_time_biometric_id": False,
        },
        "art6": {"annex_iii_categories": ["biometric_identification"],
                 "annex_i_product_type": "medical_device",
                 "is_high_risk": True, "reasoning": "test"},
        "art9": {"has_risk_docs": True, "risk_doc_paths": ["docs/risk.md"],
                 "has_testing_infrastructure": True, "testing_evidence": ["tests/"],
                 "has_risk_code_patterns": True, "risk_code_evidence": ["risk.py"],
                 "has_defined_metrics": True, "metrics_evidence": ["accuracy=0.95"]},
        "art10": {"has_data_governance_doc": True, "data_doc_paths": ["docs/data.md"],
                  "has_bias_mitigation": True, "bias_evidence": ["bias.py"],
                  "has_data_lineage": True},
        "art11": {"has_technical_docs": True, "doc_paths": ["README.md", "docs/arch.md"],
                  "documented_aspects": ["system_design", "model_architecture",
                                         "performance_metrics", "api_usage", "deployment"]},
        "art12": {"has_logging": True, "logging_description": "structlog",
                  "logging_evidence": ["logger.py"], "has_retention_config": True,
                  "retention_days": 365, "retention_evidence": "config/log.yaml"},
        "art13": {"has_explainability": True, "explainability_evidence": ["shap.py"],
                  "has_transparency_info": True, "transparency_paths": ["docs/transparency.md"]},
        "art14": {"has_human_oversight": True, "oversight_evidence": ["review.py"],
                  "has_override_mechanism": True, "override_evidence": ["override.py"]},
        "art15": {"has_accuracy_testing": True, "accuracy_evidence": ["test_acc.py"],
                  "has_robustness_testing": True, "robustness_evidence": ["test_robust.py"],
                  "has_fallback_behavior": True},
        "art50": {"is_chatbot_or_interactive_ai": True,
                  "is_generating_synthetic_content": True,
                  "has_ai_disclosure_to_users": True,
                  "disclosure_evidence": ["disclosure.tsx"],
                  "has_content_watermarking": True,
                  "is_emotion_recognition_system": True,
                  "is_biometric_categorization_system": True,
                  "has_emotion_biometric_disclosure": True,
                  "emotion_biometric_evidence": ["notice.py"],
                  "is_deep_fake_system": True,
                  "has_deep_fake_disclosure": True,
                  "deep_fake_evidence": ["deepfake_notice.py"]},
    }


def _make_ctx(answers: dict) -> ProjectContext:
    return ProjectContext(
        primary_language="python",
        risk_classification="likely high-risk",
        risk_classification_confidence="high",
        compliance_answers=answers,
    )


def _scan(module_dir: str, ctx: ProjectContext, tmp_path) -> list:
    """Scan and return list of ALL obligation_ids found in findings (including informational/gap)."""
    mod = _load_module(module_dir)
    BaseArticleModule.set_context(ctx)
    BaseArticleModule.set_config(None)
    result = mod.scan(str(tmp_path))
    BaseArticleModule.set_context(None)
    return [f.obligation_id for f in result.findings]


# ── Parametrized: all-false scenario ──

@pytest.mark.parametrize("art_num,module_dir,json_file", ARTICLE_MODULES,
                         ids=[f"art{a[0]}" for a in ARTICLE_MODULES])
def test_all_false_covers_scannable_obligations(art_num, module_dir, json_file, tmp_path):
    """With all-false answers, every scannable obligation should appear in findings."""
    expected_ids = _load_scannable_obligation_ids(json_file)
    if not expected_ids:
        pytest.skip(f"Art. {art_num}: all obligations are prohibition/exception type — tested via practice mapping tests")

    ctx = _make_ctx(_all_false_answers())
    found_ids = set(_scan(module_dir, ctx, tmp_path))

    for obl_id in expected_ids:
        assert obl_id in found_ids, (
            f"Art. {art_num}: scannable obligation '{obl_id}' NOT found in findings. "
            f"Found: {sorted(found_ids)}"
        )


# ── Parametrized: all-true scenario ──

@pytest.mark.parametrize("art_num,module_dir,json_file", ARTICLE_MODULES,
                         ids=[f"art{a[0]}" for a in ARTICLE_MODULES])
def test_all_true_covers_scannable_obligations(art_num, module_dir, json_file, tmp_path):
    """With all-true answers, every scannable obligation should appear in findings."""
    expected_ids = _load_scannable_obligation_ids(json_file)
    if not expected_ids:
        pytest.skip(f"Art. {art_num}: all obligations are prohibition/exception type — tested via practice mapping tests")

    ctx = _make_ctx(_all_true_answers())
    found_ids = set(_scan(module_dir, ctx, tmp_path))

    for obl_id in expected_ids:
        assert obl_id in found_ids, (
            f"Art. {art_num}: scannable obligation '{obl_id}' NOT found in findings "
            f"with all-true answers. Found: {sorted(found_ids)}"
        )


# ── Art.5 specific: has_* field → obligation_id mapping (unified format) ──

_ART5_FIELD_TO_OBL = {
    "has_subliminal_manipulation": "ART05-PRO-1a",
    "has_exploitation_of_vulnerabilities": "ART05-PRO-1b",
    "has_social_scoring": "ART05-PRO-1c",
    "has_predictive_policing": "ART05-PRO-1d",
    "has_facial_recognition_scraping": "ART05-PRO-1e",
    "has_emotion_recognition_workplace": "ART05-PRO-1f",
    "has_biometric_categorization": "ART05-PRO-1g",
    "has_real_time_biometric_id": "ART05-PRO-1h",
}


@pytest.mark.parametrize("field,expected_obl", list(_ART5_FIELD_TO_OBL.items()))
def test_art5_field_maps_to_obligation(field, expected_obl, tmp_path):
    """Each has_* field set to True (detected) should produce NON_COMPLIANT for its obligation."""
    answers = _all_true_answers()
    # Set one field to True (detected = violation)
    answers["art5"][field] = True
    ctx = _make_ctx(answers)
    mod = _load_module("art05-prohibited-practices")
    BaseArticleModule.set_context(ctx)
    BaseArticleModule.set_config(None)
    result = mod.scan(str(tmp_path))
    BaseArticleModule.set_context(None)
    obl_findings = [f for f in result.findings if f.obligation_id == expected_obl]
    assert len(obl_findings) > 0, f"Expected finding for {expected_obl}"
    assert obl_findings[0].level == ComplianceLevel.NON_COMPLIANT, (
        f"{expected_obl} should be NON_COMPLIANT when '{field}' is True (detected)"
    )


@pytest.mark.parametrize("field,expected_obl", list(_ART5_FIELD_TO_OBL.items()))
def test_art5_detected_false_is_compliant(field, expected_obl, tmp_path):
    """When a has_* field is False (not detected), finding should be COMPLIANT."""
    answers = _all_true_answers()  # all has_* = False (no prohibited practices)
    ctx = _make_ctx(answers)
    mod = _load_module("art05-prohibited-practices")
    BaseArticleModule.set_context(ctx)
    BaseArticleModule.set_config(None)
    result = mod.scan(str(tmp_path))
    BaseArticleModule.set_context(None)
    obl_findings = [f for f in result.findings if f.obligation_id == expected_obl]
    assert len(obl_findings) > 0, f"Expected finding for {expected_obl}"
    assert obl_findings[0].level == ComplianceLevel.COMPLIANT, (
        f"{expected_obl} should be COMPLIANT when '{practice}' not detected"
    )


# ── Verify no NON_COMPLIANT when all-true ──

# Art.6 is a classification article — NON_COMPLIANT is expected behavior (flags for manual review)
_COMPLIANCE_ARTICLES = [(a, m, j) for a, m, j in ARTICLE_MODULES if a != 6]

@pytest.mark.parametrize("art_num,module_dir,json_file", _COMPLIANCE_ARTICLES,
                         ids=[f"art{a[0]}" for a in _COMPLIANCE_ARTICLES])
def test_all_true_no_non_compliant(art_num, module_dir, json_file, tmp_path):
    """With all-true answers, no finding should be NON_COMPLIANT (except informational)."""
    ctx = _make_ctx(_all_true_answers())
    mod = _load_module(module_dir)
    BaseArticleModule.set_context(ctx)
    BaseArticleModule.set_config(None)
    result = mod.scan(str(tmp_path))
    BaseArticleModule.set_context(None)

    non_compliant = [
        f for f in result.findings
        if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
    ]
    assert len(non_compliant) == 0, (
        f"Art. {art_num}: found {len(non_compliant)} NON_COMPLIANT findings with all-true "
        f"answers: {[(f.obligation_id, f.description[:60]) for f in non_compliant]}"
    )
