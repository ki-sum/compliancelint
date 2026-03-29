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
    "art4":  "art04-ai-literacy",
    "art5":  "art05-prohibited-practices",
    "art6":  "art06-risk-classification",
    "art8":  "art08-compliance-with-requirements",
    "art9":  "art09-risk-management",
    "art10": "art10-data-governance",
    "art11": "art11-technical-documentation",
    "art12": "art12-record-keeping",
    "art13": "art13-transparency",
    "art14": "art14-human-oversight",
    "art15": "art15-accuracy-robustness",
    "art17": "art17-quality-management",
    "art26": "art26-deployer-obligations",
    "art27": "art27-fundamental-rights-impact",
    "art72": "art72-post-market-monitoring",
    "art73": "art73-serious-incident-reporting",
    "art86": "art86-right-to-explanation",
    "art43": "art43-conformity-assessment",
    "art47": "art47-declaration-of-conformity",
    "art49": "art49-registration",
    "art50": "art50-transparency-obligations",
    "art51": "art51-gpai-classification",
    "art53": "art53-obligations-gpai-providers",
    "art54": "art54-gpai-authorised-representatives",
    "art55": "art55-gpai-systemic-risk",
    "art16": "art16-provider-obligations",
    "art18": "art18-documentation-keeping",
    "art19": "art19-automatically-generated-logs",
    "art20": "art20-corrective-actions",
    "art21": "art21-cooperation-with-authorities",
    "art22": "art22-authorised-representatives",
    "art23": "art23-obligations-of-importers",
    "art24": "art24-obligations-of-distributors",
    "art25": "art25-value-chain-responsibilities",
    "art8":  "art08-compliance-with-requirements",
    "art52": "art52-classification-notification",
    "art41": "art41-common-specifications",
    "art60": "art60-real-world-testing",
    "art61": "art61-informed-consent-testing",
    "art71": "art71-eu-database",
    "art80": "art80-non-high-risk-misclassification",
    "art82": "art82-compliant-ai-presenting-risk",
    "art91": "art91-documentation-duty",
    "art92": "art92-cooperation-with-evaluations",
    "art111": "art111-transitional-provisions",
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
