"""S-B15 (2026-10-07) — a single-article cl_scan honours _scope.risk_classification like cl_scan_all.

cl_scan's gate REQUIRES compliance_answers._scope.risk_classification (the answers template puts it there), but
ProjectContext.from_dict only filled the top-level `risk_classification` field. cl_scan_all copied _scope onto the
context before each module's high-risk-only check; the single-article path (cl_scan(articles="12")) did not, so for a
minimal-risk project the 28 high-risk-only articles were NOT_APPLICABLE in cl_scan_all but fully scanned in cl_scan.
The context now takes the _scope values when the top-level ones are absent (top-level / .compliancelintrc overrides
still win).
"""

import json
import os
import sys
import types
import importlib.util

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

_server_spec = importlib.util.spec_from_file_location("server", os.path.join(SCANNER_ROOT, "server.py"))
_server_mod = importlib.util.module_from_spec(_server_spec)
_server_mod.mcp = types.SimpleNamespace(tool=lambda: (lambda f: f))
try:
    _server_spec.loader.exec_module(_server_mod)
except Exception:
    pass
_scan_single_article = _server_mod._scan_single_article

from core.context import ProjectContext  # noqa: E402


@pytest.fixture
def project_dir(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')")
    return str(tmp_path)


def _ctx(scope: dict, **top) -> ProjectContext:
    return ProjectContext.from_dict({
        **top,
        "compliance_answers": {
            "_scope": scope,
            "art12": {"has_logging": True, "logging_description": "structured logs", "logging_evidence": [],
                      "has_retention_config": True, "retention_days": 365, "retention_evidence": ""},
        },
    })


def test_from_dict_takes_risk_classification_from_scope():
    ctx = _ctx({"risk_classification": "minimal-risk", "risk_classification_confidence": "high",
                "risk_reasoning": "chat assistant, no Annex III use"})
    assert ctx.risk_classification == "minimal-risk"
    assert ctx.risk_classification_confidence == "high"
    assert ctx.risk_reasoning == "chat assistant, no Annex III use"


def test_from_dict_top_level_risk_wins_over_scope():
    ctx = _ctx({"risk_classification": "minimal-risk", "risk_classification_confidence": "high"},
               risk_classification="high-risk", risk_classification_confidence="medium")
    assert ctx.risk_classification == "high-risk"
    assert ctx.risk_classification_confidence == "medium"


def test_from_dict_without_risk_anywhere_stays_empty():
    ctx = _ctx({"is_open_source": False})
    assert ctx.risk_classification == ""


def test_single_article_scan_skips_high_risk_only_article_for_minimal_risk_scope(project_dir):
    ctx = _ctx({"risk_classification": "minimal-risk", "risk_classification_confidence": "high"})
    result = json.loads(_scan_single_article(12, project_dir, context=ctx))
    assert result["overall_level"] == "not_applicable", result.get("overall_level")


def test_single_article_scan_still_scans_for_high_risk_scope(project_dir):
    ctx = _ctx({"risk_classification": "high-risk", "risk_classification_confidence": "high"})
    result = json.loads(_scan_single_article(12, project_dir, context=ctx))
    assert result["overall_level"] != "not_applicable"
