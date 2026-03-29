"""Art. 12 multilanguage test — same obligation mapping regardless of project language.

The scanner is language-agnostic: the AI provides logging/retention answers
whether the project is Go, Java, Rust, C#, JavaScript, or any other language.
This test verifies that the obligation mapper produces correct findings
regardless of the language hint in ProjectContext.
"""
import pytest
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with, _load_module

LANGUAGES = ["python", "typescript", "java", "go", "rust", "csharp"]


@pytest.fixture
def art12_module():
    return _load_module("art12-record-keeping")


@pytest.mark.parametrize("language", LANGUAGES)
def test_logging_present_any_language(art12_module, tmp_path, language):
    """ART12-OBL-1 is PARTIAL when AI confirms logging, for ANY language."""
    from core.context import ProjectContext
    from core.protocol import BaseArticleModule

    base = _ctx_with("art12", {
        "has_logging": True,
        "logging_description": f"logging framework detected in {language} project",
        "logging_evidence": ["app.log:1"],
        "has_retention_config": True,
        "retention_days": 365,
        "retention_evidence": "retention = 365 days"
    })
    ctx = ProjectContext(**{**base.to_dict(), "primary_language": language})
    BaseArticleModule.set_context(ctx)
    result = art12_module.scan(str(tmp_path))
    obl1 = [f for f in result.findings if f.obligation_id == "ART12-OBL-1"]
    assert any(f.level == ComplianceLevel.PARTIAL for f in obl1), \
        f"Expected PARTIAL for language={language}, got {[f.level for f in obl1]}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_logging_any_language(art12_module, tmp_path, language):
    """ART12-OBL-1 is NON_COMPLIANT when AI confirms no logging, for ANY language."""
    from core.context import ProjectContext
    from core.protocol import BaseArticleModule

    base = _ctx_with("art12", {
        "has_logging": False,
        "logging_description": "",
        "logging_evidence": [],
        "has_retention_config": False,
        "retention_days": None,
        "retention_evidence": ""
    })
    ctx = ProjectContext(**{**base.to_dict(), "primary_language": language})
    BaseArticleModule.set_context(ctx)
    result = art12_module.scan(str(tmp_path))
    obl1 = [f for f in result.findings if f.obligation_id == "ART12-OBL-1"]
    assert any(f.level == ComplianceLevel.NON_COMPLIANT for f in obl1), \
        f"Expected NON_COMPLIANT for language={language}, got {[f.level for f in obl1]}"
