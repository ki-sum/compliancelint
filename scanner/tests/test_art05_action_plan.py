"""Art 5 action plan must be built from the findings.

Self-audit B1 (2026-10-02): action_plan() read details["detected_practices"], which scan()
never set — so with social scoring or NCII detected it still said "No prohibited practice
signals detected by AI".
"""
from datetime import date

from core.protocol import BaseArticleModule
from conftest import _ctx_with

_ALL_FALSE = {
    "has_subliminal_manipulation": False, "has_exploitation_of_vulnerabilities": False,
    "has_social_scoring": False, "has_predictive_policing": False,
    "has_facial_recognition_scraping": False, "has_emotion_recognition_workplace": False,
    "has_biometric_categorization": False, "has_real_time_biometric_id": False,
    "has_ncii_generation": False, "has_csam_generation": False,
}


def _plan(art05_module, tmp_path, monkeypatch, today: date, **answers):
    monkeypatch.setitem(type(art05_module).scan.__globals__, "_today", lambda: today)
    BaseArticleModule.set_context(_ctx_with("art5", {**_ALL_FALSE, **answers}))
    result = art05_module.scan(str(tmp_path))
    return art05_module.action_plan(result)


def _text(plan) -> str:
    return " ".join(f"{a.priority} {a.article} {a.action} {a.details}" for a in plan.actions)


def test_ncii_detected_after_application_is_critical(art05_module, tmp_path, monkeypatch):
    plan = _plan(art05_module, tmp_path, monkeypatch, date(2027, 1, 1), has_ncii_generation=True,
                 ncii_generation_evidence="'undress' preset in src/editor/presets.py")
    critical = [a for a in plan.actions if a.priority == "CRITICAL"]
    assert len(critical) == 1
    assert "ART05-PRO-1ba" in critical[0].article
    assert "'undress' preset in src/editor/presets.py" in critical[0].details
    assert "No prohibited practice" not in _text(plan)


def test_social_scoring_detected_is_critical(art05_module, tmp_path, monkeypatch):
    plan = _plan(art05_module, tmp_path, monkeypatch, date(2026, 10, 2), has_social_scoring=True)
    assert [a.article for a in plan.actions if a.priority == "CRITICAL"] == ["Art. 5 (ART05-PRO-1c)"]
    assert "No prohibited practice" not in _text(plan)


def test_unknown_answer_asks_for_a_determination(art05_module, tmp_path, monkeypatch):
    plan = _plan(art05_module, tmp_path, monkeypatch, date(2026, 10, 2), has_predictive_policing=None)
    high = [a for a in plan.actions if a.priority == "HIGH" and "ART05-PRO-1d" in a.article]
    assert len(high) == 1
    assert not [a for a in plan.actions if a.priority == "CRITICAL"]


def test_ncii_detected_before_application_is_a_preparation_item(art05_module, tmp_path, monkeypatch):
    plan = _plan(art05_module, tmp_path, monkeypatch, date(2026, 11, 30), has_ncii_generation=True)
    assert not [a for a in plan.actions if a.priority == "CRITICAL"]
    prep = [a for a in plan.actions if "ART05-PRO-1ba" in a.article]
    assert len(prep) == 1 and prep[0].priority == "HIGH"
    assert "2026-12-02" in prep[0].action


def test_nothing_detected_gives_one_review_and_record_action(art05_module, tmp_path, monkeypatch):
    # 2026-10-26: the review and its record are one action (test_action_plan_no_duplicates.py)
    plan = _plan(art05_module, tmp_path, monkeypatch, date(2027, 1, 1))
    assert [(a.priority, a.article, a.action) for a in plan.actions] == [
        ("HIGH", "Art. 5 (all)", "Review the system against each Art. 5 prohibition and record the assessment")]


def test_disclaimer_states_both_application_dates(art05_module, tmp_path, monkeypatch):
    plan = _plan(art05_module, tmp_path, monkeypatch, date(2026, 10, 2))
    assert "2025-02-02" in plan.disclaimer and "2026-12-02" in plan.disclaimer
