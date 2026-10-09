"""Scope gate — Art. 2(12) open-source exclusion and the Chapter V (Art. 51-55) gates.

Legal review of the scope reasons (2026-10-08):
- Art. 2(12): the Regulation does not apply to AI systems released under free and open-source licences unless they are
  placed on the market or put into service as high-risk AI systems or as an AI system that falls under Art. 5 or 50.
  It does not keep Art. 4, 5 or 50 for an excluded system; if the system falls under Art. 5 or 50 (or is high-risk),
  the exclusion does not apply at all. Chapter V concerns general-purpose AI MODELS and is assessed by its own gates.
- Chapter V: "not a general-purpose AI model" (art51.is_gpai_model = false) gates the chapter; "not a GPAI provider"
  (_scope.is_gpai_provider = false) gates the provider duties only. Art. 54 binds the authorised representative for
  another (third-country) provider's model (founder 2026-10-09): "not a GPAI model" hides it unless the answers say
  this organisation IS such a representative; "not a GPAI provider" hides it only when they say it is not one
  (_scope.is_authorised_representative) — the same rule as the dashboard's applicability engine.
"""
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.context import ProjectContext  # noqa: E402
from core.protocol import BaseArticleModule, ComplianceLevel  # noqa: E402

NA = ComplianceLevel.NOT_APPLICABLE
OSS_REASON = (
    "this AI system is released under a free and open-source licence and, according to the profile, is not placed "
    "on the market or put into service as a high-risk AI system and does not fall under Article 5 or 50; Article "
    "2(12) therefore excludes the AI system from the Regulation"
)
DIRS = {
    4: "art04-ai-literacy",
    5: "art05-prohibited-practices",
    9: "art09-risk-management",
    50: "art50-transparency-obligations",
    51: "art51-gpai-classification",
    52: "art52-classification-notification",
    53: "art53-obligations-gpai-providers",
    54: "art54-gpai-authorised-representatives",
    55: "art55-gpai-systemic-risk",
}


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


def _scan(art: int, answers: dict, tmp_path, risk: str = "minimal-risk"):
    ctx = ProjectContext(
        primary_language="python",
        risk_classification=risk,
        risk_classification_confidence="high",
        compliance_answers={"_scope": {"is_ai_system": True, **answers.pop("_scope", {})}, **answers},
    )
    mod = _load_module(DIRS[art])
    BaseArticleModule.set_context(ctx)
    BaseArticleModule.set_config(None)
    try:
        return mod.scan(str(tmp_path))
    finally:
        BaseArticleModule.set_context(None)


def _oss(**extra):
    return {"_scope": {"is_open_source": True, "open_source_license": "MIT"}, **extra}


# ── Art. 2(12) ──

@pytest.mark.parametrize("art", [4, 5, 9, 50])
def test_open_source_excludes_the_ai_system_including_art_4_5_50(art, tmp_path):
    result = _scan(art, _oss(), tmp_path)
    assert result.overall_level == NA
    assert "[Art. 2(12)]" in result.findings[0].description
    assert OSS_REASON in result.findings[0].description
    assert "Title III" not in result.findings[0].description


def test_open_source_does_not_decide_chapter_v(tmp_path):
    # GPAI status unanswered: the GPAI-model articles are assessed by their own gates, not excluded by Art. 2(12).
    result = _scan(53, _oss(), tmp_path)
    assert result.overall_level != NA


@pytest.mark.parametrize("risk", ["high-risk", "likely high-risk", "prohibited", "limited-risk"])
def test_open_source_with_a_contradicting_risk_class_is_not_excluded(risk, tmp_path):
    # Art. 4 applies to every AI system in scope — it must be scanned.
    assert _scan(4, _oss(), tmp_path, risk=risk).overall_level != NA, risk
    # Art. 9 may still be not applicable for a limited-risk system (high-risk-only gate), but never via Art. 2(12).
    result = _scan(9, _oss(), tmp_path, risk=risk)
    assert result.overall_level != NA or "[Art. 2(12)]" not in result.findings[0].description, risk
    if "high" in risk:
        assert result.overall_level != NA, risk


@pytest.mark.parametrize("answers", [
    {"art5": {"has_social_scoring": True}},
    {"art50": {"is_generating_synthetic_content": True}},
    {"art50": {"is_chatbot_or_interactive_ai": True}},
    {"art50": {"is_deep_fake_system": True}},
    {"art6": {"is_high_risk": True}},
])
def test_open_source_with_an_art5_art50_or_high_risk_answer_is_not_excluded(answers, tmp_path):
    for art in (4, 5, 50):
        result = _scan(art, _oss(**{k: dict(v) for k, v in answers.items()}), tmp_path)
        assert result.overall_level != NA or "[Art. 2(12)]" not in result.findings[0].description, (art, answers)


# Second legal review (2026-10-09, A6 / C2): Annex III membership or an Annex I product type alone does not establish
# high-risk status (Art. 6(1) has further conditions; Art. 6(3) can take an Annex III system out of high-risk) — only an
# Art. 6 high-risk determination, an Art. 5 practice or an Art. 50 case contradicts the open-source attestation.
@pytest.mark.parametrize("answers", [
    {"art6": {"annex_iii_categories": ["4(a)"]}},
    {"art6": {"annex_i_product_type": "Medical device"}},
])
def test_open_source_attestation_stands_against_raw_annex_answers(answers, tmp_path):
    result = _scan(4, _oss(**{k: dict(v) for k, v in answers.items()}), tmp_path)
    assert result.overall_level == NA
    assert "[Art. 2(12)]" in result.findings[0].description


# ── Chapter V ──

@pytest.mark.parametrize("art", [51, 52, 53, 54, 55])
def test_not_a_gpai_model_gates_the_whole_chapter(art, tmp_path):
    result = _scan(art, {"art51": {"is_gpai_model": False}}, tmp_path)
    assert result.overall_level == NA
    d = result.findings[0].description
    if art == 54:
        assert "the model assessed in this project is not a general-purpose AI model within Article 3(63)" in d
        assert "under Article 54" in d
    else:
        assert "not a general-purpose AI model within Article 3(63)" in d


@pytest.mark.parametrize("art", [51, 52, 53, 55])
def test_not_a_gpai_provider_gates_the_provider_articles(art, tmp_path):
    result = _scan(art, {"_scope": {"is_gpai_provider": False}}, tmp_path)
    assert result.overall_level == NA
    assert "not a provider within Article 3(3) of a general-purpose AI model within Article 3(63)" in result.findings[0].description


def test_not_a_gpai_provider_keeps_art54_while_the_representative_question_is_unanswered(tmp_path):
    result = _scan(54, {"_scope": {"is_gpai_provider": False}}, tmp_path)
    assert result.overall_level != NA


def test_not_a_gpai_provider_keeps_art54_for_an_authorised_representative(tmp_path):
    result = _scan(54, {"_scope": {"is_gpai_provider": False, "is_authorised_representative": True}}, tmp_path)
    assert result.overall_level != NA


def test_neither_provider_nor_representative_gates_art54(tmp_path):
    result = _scan(54, {"_scope": {"is_gpai_provider": False, "is_authorised_representative": False}}, tmp_path)
    assert result.overall_level == NA
    assert "[Art. 54]" in result.findings[0].description
    assert "not the authorised representative of a provider established in a third country" in result.findings[0].description


def test_not_a_gpai_model_keeps_art54_for_an_authorised_representative(tmp_path):
    result = _scan(54, {"_scope": {"is_authorised_representative": True}, "art51": {"is_gpai_model": False}}, tmp_path)
    assert result.overall_level != NA


def test_not_a_gpai_model_art54_reason_names_the_representative_question(tmp_path):
    result = _scan(54, {"art51": {"is_gpai_model": False}}, tmp_path)
    assert result.overall_level == NA
    assert "do not identify this organisation as the authorised representative" in result.findings[0].description
