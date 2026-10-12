"""A conditional obligation whose condition is unanswered must stay undetermined.

The answers template lists every field with the value null, so "the field is present" does not mean "the condition
was answered". The obligation engine treated a present-but-null condition field as a definitive answer that does
not trigger the skip and reported "[APPLICABLE] ... (field=None)". Three states:

    condition answered so that the obligation does not apply  -> NOT_APPLICABLE
    condition answered so that it applies                     -> applicable, to be verified
    condition unanswered (null, or the field is absent)       -> conditional: nothing is concluded
"""
import json
import os

import pytest

from core.obligation_engine import ObligationEngine
from core.protocol import ComplianceLevel

OBLIGATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "obligations")


def _engine(prefix: str) -> ObligationEngine:
    name = next(f for f in os.listdir(OBLIGATIONS_DIR) if f.startswith(prefix) and f.endswith(".json"))
    with open(os.path.join(OBLIGATIONS_DIR, name), encoding="utf-8") as f:
        return ObligationEngine(json.load(f))


def _gap(prefix: str, article_key: str, obligation_id: str, answers):
    findings = _engine(prefix).gap_findings([], {article_key: answers} if answers is not None else {})
    matching = [f for f in findings if f.obligation_id == obligation_id]
    assert len(matching) == 1, f"{obligation_id}: {len(matching)} findings"
    return matching[0]


CASES = [
    # (obligation file prefix, answers key, obligation id, condition field, value that makes it not applicable)
    ("art49-", "art49", "ART49-OBL-2", "claims_art6_3_exception", False),
    ("art52-", "art52", "ART52-OBL-1", "is_gpai_with_systemic_risk", False),
    ("art48-", "art48", "ART48-OBL-4a", "has_notified_body_assessment", False),
]


@pytest.mark.parametrize("prefix,key,oid,field,skip_value", CASES)
def test_condition_unanswered_null_is_conditional_not_applicable(prefix, key, oid, field, skip_value):
    finding = _gap(prefix, key, oid, {field: None})
    assert finding.level == ComplianceLevel.UNABLE_TO_DETERMINE
    assert finding.description.startswith("[CONDITIONAL]"), finding.description
    assert "=None" not in finding.description


@pytest.mark.parametrize("prefix,key,oid,field,skip_value", CASES)
def test_condition_field_absent_is_conditional(prefix, key, oid, field, skip_value):
    finding = _gap(prefix, key, oid, None)
    assert finding.description.startswith("[CONDITIONAL]"), finding.description


@pytest.mark.parametrize("prefix,key,oid,field,skip_value", CASES)
def test_condition_answered_not_met_is_not_applicable(prefix, key, oid, field, skip_value):
    finding = _gap(prefix, key, oid, {field: skip_value})
    assert finding.level == ComplianceLevel.NOT_APPLICABLE


@pytest.mark.parametrize("prefix,key,oid,field,skip_value", CASES)
def test_condition_answered_met_is_applicable(prefix, key, oid, field, skip_value):
    finding = _gap(prefix, key, oid, {field: not skip_value})
    assert finding.level == ComplianceLevel.UNABLE_TO_DETERMINE
    assert finding.description.startswith("[APPLICABLE]"), finding.description
