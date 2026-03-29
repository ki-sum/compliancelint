"""Archetype-based integration tests for ComplianceLint scanner.

Each archetype is a JSON fixture representing a specific project type
(open-source biometric lib, commercial chatbot, military system, etc.)
with pre-filled compliance_answers and expected scan results.

This tests the scanner's LOGIC — scope gates, obligation mapping, and
finding generation — without needing real projects or AI analysis.
"""
import json
import os
import sys
import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.protocol import BaseArticleModule, ComplianceLevel
from core.context import ProjectContext

ARCHETYPES_DIR = os.path.join(os.path.dirname(__file__), "archetypes")

# Map article keys to module directory names
ARTICLE_MODULE_MAP = {
    "art5":  "art05-prohibited-practices",
    "art6":  "art06-risk-classification",
    "art9":  "art09-risk-management",
    "art10": "art10-data-governance",
    "art11": "art11-technical-documentation",
    "art12": "art12-record-keeping",
    "art13": "art13-transparency",
    "art14": "art14-human-oversight",
    "art15": "art15-accuracy-robustness",
    "art50": "art50-transparency-obligations",
}


def _load_module(article_dir_name: str):
    """Load a scanner module by directory name."""
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


def _load_archetypes():
    """Load all archetype JSON fixtures."""
    archetypes = []
    for fname in sorted(os.listdir(ARCHETYPES_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(ARCHETYPES_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["_filename"] = fname
        archetypes.append(data)
    return archetypes


ARCHETYPES = _load_archetypes()


def _make_context(project_context: dict) -> ProjectContext:
    """Create a ProjectContext from archetype project_context dict."""
    return ProjectContext(
        primary_language=project_context.get("primary_language", "python"),
        risk_classification=project_context.get("risk_classification", "unclear"),
        risk_classification_confidence=project_context.get("risk_classification_confidence", "low"),
        risk_reasoning=project_context.get("risk_reasoning", ""),
        compliance_answers=project_context.get("compliance_answers", {}),
    )


def _scan_article(article_key: str, ctx: ProjectContext, tmp_path) -> dict:
    """Scan a single article with the given context, return result dict."""
    module_dir = ARTICLE_MODULE_MAP[article_key]
    mod = _load_module(module_dir)
    BaseArticleModule.set_context(ctx)
    BaseArticleModule.set_config(None)
    try:
        result = mod.scan(str(tmp_path))
        return result.to_dict()
    finally:
        BaseArticleModule.set_context(None)


# ── Parametrized test: one test per archetype × article ──

def _archetype_article_params():
    """Generate (archetype, article_key, expected) tuples for parametrize."""
    params = []
    for arch in ARCHETYPES:
        for article_key, expected in arch.get("expected", {}).items():
            test_id = f"{arch['_filename'].replace('.json', '')}--{article_key}"
            params.append(pytest.param(arch, article_key, expected, id=test_id))
    return params


@pytest.mark.parametrize("archetype,article_key,expected", _archetype_article_params())
def test_archetype_article(archetype, article_key, expected, tmp_path):
    """Test that scanning an archetype produces the expected overall level."""
    ctx = _make_context(archetype["project_context"])
    result = _scan_article(article_key, ctx, tmp_path)

    expected_overall = expected["overall"]
    actual_overall = result["overall_level"]

    assert actual_overall == expected_overall, (
        f"[{archetype['name']}] {article_key}: "
        f"expected '{expected_overall}', got '{actual_overall}'"
    )

    # If reason_contains is specified, check that at least one finding contains it
    if "reason_contains" in expected:
        reason_text = expected["reason_contains"]
        all_descriptions = " ".join(
            f.get("description", "") for f in result.get("findings", [])
        )
        assert reason_text in all_descriptions, (
            f"[{archetype['name']}] {article_key}: "
            f"expected finding containing '{reason_text}' but not found in descriptions"
        )

    # If must_have_obligations is specified, verify those obligation IDs appear
    if "must_have_obligations" in expected:
        found_ids = {f["obligation_id"] for f in result.get("findings", [])}
        for obl_id in expected["must_have_obligations"]:
            assert obl_id in found_ids, (
                f"[{archetype['name']}] {article_key}: "
                f"expected obligation '{obl_id}' in findings but not found. "
                f"Found: {sorted(found_ids)}"
            )


# ── Summary test: verify all archetypes loaded ──

def test_archetypes_loaded():
    """Verify that we have the expected number of archetype fixtures."""
    assert len(ARCHETYPES) >= 12, (
        f"Expected at least 12 archetypes, found {len(ARCHETYPES)}"
    )


def test_all_archetypes_have_required_keys():
    """Verify archetype fixture schema."""
    for arch in ARCHETYPES:
        assert "name" in arch, f"{arch.get('_filename')}: missing 'name'"
        assert "project_context" in arch, f"{arch.get('_filename')}: missing 'project_context'"
        assert "expected" in arch, f"{arch.get('_filename')}: missing 'expected'"
        assert "compliance_answers" in arch["project_context"], (
            f"{arch.get('_filename')}: missing 'compliance_answers'"
        )
