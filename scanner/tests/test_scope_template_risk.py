"""The answers template carries the required _scope.risk_classification (acceptance run A1, 2026-10-07).

validation_gate.validate_scope requires _scope.risk_classification and _scope.is_ai_system, but the template that
cl_analyze_project returns built _scope from the boolean fields only — an AI filling the template exactly got the
"_scope.risk_classification is required" error (the subagent acting as the user's AI only avoided it because the tool
description says REQUIRED). The template now has the risk fields, and the field descriptions say what they take.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.context import _FIELD_DESCRIPTIONS, _build_answers_template  # noqa: E402
from core.validation_gate import validate_scope  # noqa: E402


def test_template_scope_has_the_required_risk_fields():
    scope = _build_answers_template()["_scope"]
    for key in ("risk_classification", "risk_classification_confidence", "risk_reasoning"):
        assert key in scope, key
    assert "is_ai_system" in scope


def test_scope_field_descriptions_name_the_values():
    desc = _FIELD_DESCRIPTIONS["_scope"]
    for value in ("prohibited", "high-risk", "limited-risk", "minimal-risk"):
        assert value in desc["risk_classification"], value
    for value in ("high", "medium", "low"):
        assert f"'{value}'" in desc["risk_classification_confidence"], value


def test_a_template_filled_in_place_passes_the_scope_gate():
    scope = dict(_build_answers_template()["_scope"])
    scope["is_ai_system"] = True
    scope["risk_classification"] = "high-risk"
    assert validate_scope(scope) == []
