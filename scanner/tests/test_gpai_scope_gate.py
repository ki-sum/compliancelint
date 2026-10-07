"""GPAI scope gate — Art. 51-55 do not apply to a project that is not a general-purpose AI model provider.

Acceptance run A2 (2026-10-07, founder: fix before release): for a credit-scoring system whose answers said
`_scope.is_gpai_provider = false` and `art51.is_gpai_model = false`, cl_scan_all reported ART51-CLS-1 NON_COMPLIANT
("Art. 51(1) requires GPAI model providers to classify…") and Art 52 / 53 non_compliant, while Art 54 / 55 came out
not_applicable and the Art 51 module itself computed "NOT_GPAI_MODEL (Art. 51 does not apply)".

_scope_gate now returns NOT_APPLICABLE for Art. 51-55 when either answer says the project is not a GPAI model provider.
"""
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.context import ProjectContext  # noqa: E402
from core.protocol import BaseArticleModule, ComplianceLevel  # noqa: E402

GPAI_ARTICLES = [
    "art51-gpai-classification",
    "art52-classification-notification",
    "art53-obligations-gpai-providers",
    "art54-gpai-authorised-representatives",
    "art55-gpai-systemic-risk",
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


def _scan(article_dir: str, scope: dict, art51: dict, tmp_path):
    ctx = ProjectContext(
        primary_language="python",
        risk_classification="high-risk",
        risk_classification_confidence="high",
        compliance_answers={"_scope": {"is_ai_system": True, "risk_classification": "high-risk", **scope}, "art51": art51},
    )
    mod = _load_module(article_dir)
    BaseArticleModule.set_context(ctx)
    BaseArticleModule.set_config(None)
    try:
        return mod.scan(str(tmp_path))
    finally:
        BaseArticleModule.set_context(None)


@pytest.mark.parametrize("article_dir", GPAI_ARTICLES)
def test_not_gpai_provider_scope_makes_chapter_v_not_applicable(article_dir, tmp_path):
    result = _scan(article_dir, {"is_gpai_provider": False}, {"is_gpai_model": False}, tmp_path)
    assert result.overall_level == ComplianceLevel.NOT_APPLICABLE
    assert all(f.level == ComplianceLevel.NOT_APPLICABLE for f in result.findings)
    assert "Art. 3(63)" in result.findings[0].description


@pytest.mark.parametrize("article_dir", GPAI_ARTICLES)
def test_art51_not_gpai_model_answer_alone_is_enough(article_dir, tmp_path):
    result = _scan(article_dir, {}, {"is_gpai_model": False}, tmp_path)
    assert result.overall_level == ComplianceLevel.NOT_APPLICABLE


def test_gpai_provider_still_scanned(tmp_path):
    result = _scan("art51-gpai-classification", {"is_gpai_provider": True}, {"is_gpai_model": True}, tmp_path)
    assert result.overall_level != ComplianceLevel.NOT_APPLICABLE


def test_unknown_gpai_status_still_scanned(tmp_path):
    result = _scan("art53-obligations-gpai-providers", {}, {}, tmp_path)
    assert result.overall_level != ComplianceLevel.NOT_APPLICABLE


def test_other_articles_unaffected(tmp_path):
    result = _scan("art09-risk-management", {"is_gpai_provider": False}, {"is_gpai_model": False}, tmp_path)
    assert result.overall_level != ComplianceLevel.NOT_APPLICABLE
