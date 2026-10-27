"""Log retention of "at least six months" (Art. 19(1) for providers, Art. 26(6) for deployers), counted in days.

Found 2026-10-27 (series-3 demo take, independent legal check): the Art. 12, 19 and 26 modules took six months as
180 days, so a log kept for 180 days was rated as meeting the minimum and the guidance told users to keep 180 days.
Six calendar months span 181 to 184 days (e.g. 1 September to 1 March = 181, 1 July to 1 January = 184), so 180 days
always falls short. A period counted in days meets "at least six months" for every log, whatever the day it was
written, only from 184 days.
"""
import re

import pytest

from core.protocol import BaseArticleModule, ComplianceLevel
from conftest import _ctx_with


def _art12(days):
    return _ctx_with("art12", {
        "has_logging": True, "logging_description": "structlog JSON", "logging_evidence": [],
        "has_retention_config": True, "retention_days": days, "retention_evidence": f"{days} days in config",
    })


def _art19(days):
    return _ctx_with("art19", {
        "has_log_retention": True, "log_retention_evidence": "", "has_retention_config": True,
        "retention_days": days, "retention_evidence": f"{days} days in config",
    })


def _art26(days):
    return _ctx_with("art26", {
        "has_deployment_documentation": True, "has_human_oversight_assignment": True,
        "has_operational_monitoring": True, "has_log_retention": True, "retention_days": days,
        "retention_evidence": f"{days} days in config", "has_affected_persons_notification": True,
    })


CASES = [
    ("art12_module", _art12, "ART19-OBL-1b"),
    ("art19_module", _art19, "ART19-OBL-1b"),
    ("art26_module", _art26, "ART26-OBL-6"),
]


def _scan(request, fixture, ctx, tmp_path):
    module = request.getfixturevalue(fixture)
    BaseArticleModule.set_context(ctx)
    try:
        result = module.scan(str(tmp_path))
        return module, result
    finally:
        BaseArticleModule.set_context(None)


def _level(result, obligation_id):
    found = [f for f in result.findings if f.obligation_id == obligation_id]
    assert found, f"no finding for {obligation_id}"
    return found[0].level


@pytest.mark.parametrize("fixture,ctx_for,obligation_id", CASES)
@pytest.mark.parametrize("days", [180, 181, 183])
def test_a_period_shorter_than_every_six_months_is_non_compliant(request, tmp_path, fixture, ctx_for,
                                                                 obligation_id, days):
    _, result = _scan(request, fixture, ctx_for(days), tmp_path)
    assert _level(result, obligation_id) == ComplianceLevel.NON_COMPLIANT


@pytest.mark.parametrize("fixture,ctx_for,obligation_id", CASES)
@pytest.mark.parametrize("days", [184, 365])
def test_184_days_or_more_meets_the_minimum(request, tmp_path, fixture, ctx_for, obligation_id, days):
    _, result = _scan(request, fixture, ctx_for(days), tmp_path)
    # PARTIAL is the best level these findings reach: the period must also be appropriate to the intended purpose,
    # which a person judges.
    assert _level(result, obligation_id) == ComplianceLevel.PARTIAL


def _texts(module, result):
    """Every text the user reads for this module: findings and the action plan."""
    out = []
    for f in result.findings:
        out += [f.description or "", getattr(f, "remediation", None) or ""]
    plan = module.action_plan(result)
    for a in plan.actions:
        out += [a.action or "", a.details or ""]
    return out


SIX_MONTHS_AS_180 = re.compile(r"180[- ]?days?|\b180\b.{0,20}(6|six)[- ]months?|(6|six)[- ]months?.{0,20}\b180\b",
                               re.IGNORECASE)


@pytest.mark.parametrize("fixture,ctx_for,obligation_id", CASES)
@pytest.mark.parametrize("days", [None, 30, 180])
def test_no_text_gives_180_days_as_the_minimum(request, tmp_path, fixture, ctx_for, obligation_id, days):
    module, result = _scan(request, fixture, ctx_for(days), tmp_path)
    for text in _texts(module, result):
        # the user's own number may be quoted back ("Retention configured: 180 days"), never as the minimum
        assert not SIX_MONTHS_AS_180.search(text.replace(f"{days} days", "")) if days == 180 else \
            not SIX_MONTHS_AS_180.search(text), text


@pytest.mark.parametrize("fixture,ctx_for,obligation_id", CASES)
def test_a_short_period_is_told_the_minimum_as_six_months_and_184_days(request, tmp_path, fixture, ctx_for,
                                                                       obligation_id):
    module, result = _scan(request, fixture, ctx_for(180), tmp_path)
    finding = [f for f in result.findings if f.obligation_id == obligation_id][0]
    assert "six months" in finding.description
    assert "184 days" in finding.description


def test_the_art12_action_plan_examples_meet_six_months(request, tmp_path):
    ctx = _ctx_with("art12", {
        "has_logging": True, "logging_description": "x", "logging_evidence": [],
        "has_retention_config": False, "retention_days": None, "retention_evidence": "",
    })
    module, result = _scan(request, "art12_module", ctx, tmp_path)
    details = "\n".join(a.details or "" for a in module.action_plan(result).actions)
    assert "rotate 184" in details
    # CloudWatch accepts fixed values only (..., 150, 180, 365, ...): the first one of six months or more is 365
    assert "--retention-in-days 365" in details
    # Docker's json-file driver rotates by size, not by date, so a file count is no retention period
    assert "max-file" not in details


@pytest.mark.parametrize("fixture,ctx_for,obligation_id,holder", [
    ("art12_module", _art12, "ART19-OBL-1b", "provider"),
    ("art19_module", _art19, "ART19-OBL-1b", "provider"),
    ("art26_module", _art26, "ART26-OBL-6", "deployer"),
])
def test_the_minimum_keeps_the_law_s_limits(request, tmp_path, fixture, ctx_for, obligation_id, holder):
    """Independent legal check 2026-10-27: the duty covers logs under the holder's control, and Union or national
    law, in particular on the protection of personal data, may provide otherwise."""
    _, result = _scan(request, fixture, ctx_for(30), tmp_path)
    text = [f for f in result.findings if f.obligation_id == obligation_id][0].description
    assert f"to the extent they are under the {holder}'s control" in text
    assert "in particular in Union law on the protection of personal data" in text


@pytest.mark.parametrize("fixture,ctx_for,obligation_id", CASES)
def test_181_to_183_days_says_why_it_falls_short(request, tmp_path, fixture, ctx_for, obligation_id):
    _, result = _scan(request, fixture, ctx_for(182), tmp_path)
    text = [f for f in result.findings if f.obligation_id == obligation_id][0].description
    assert "182 days does not keep every log for six months" in text
    assert "six calendar months last 181 to 184 days" in text


@pytest.mark.parametrize("fixture,ctx_for,obligation_id", CASES)
def test_a_period_within_the_minimum_leaves_the_judgement_to_a_person(request, tmp_path, fixture, ctx_for,
                                                                     obligation_id):
    _, result = _scan(request, fixture, ctx_for(365), tmp_path)
    text = [f for f in result.findings if f.obligation_id == obligation_id][0].description
    assert "a person still needs to confirm that the period is appropriate to the intended purpose" in text


# Founder 2026-10-27: where a number of days is shown, it reads "184 days (at least six months)".
MINIMUM_SHOWN = "184 days (at least six months)"


@pytest.mark.parametrize("fixture,ctx_for,obligation_id", CASES)
@pytest.mark.parametrize("days", [None, 30, 182])
def test_every_day_count_of_the_minimum_reads_184_days_at_least_six_months(request, tmp_path, fixture, ctx_for,
                                                                            obligation_id, days):
    module, result = _scan(request, fixture, ctx_for(days), tmp_path)
    texts = _texts(module, result)
    shown = [t for t in texts if "184" in t]
    assert shown, "no text gives the minimum in days"
    for text in shown:
        for m in re.finditer(r"184 days", text):
            assert text[m.start():].startswith(MINIMUM_SHOWN) or "181 to 184 days" in text[max(0, m.start() - 7):m.end()], text
