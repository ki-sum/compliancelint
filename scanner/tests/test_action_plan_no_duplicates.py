"""cl_action_plan lists each Art. 4 / 5 / 6 duty once (2026-10-26).

The series-2 to-do list showed pairs of actions that ask for the same thing: Art. 4 "take measures" next to "verify
the measures", Art. 5 "proactive review" next to "document the assessment", Art. 6 "formal classification" next to
"confirm non-high-risk" and "create classification documentation". Each pair is one action now. The texts passed an
independent legal check against the consolidated text on 2026-10-26.
"""
from datetime import date

from core.protocol import BaseArticleModule
from conftest import _ctx_with

_ART5_ALL_FALSE = {
    "has_subliminal_manipulation": False, "has_exploitation_of_vulnerabilities": False,
    "has_social_scoring": False, "has_predictive_policing": False,
    "has_facial_recognition_scraping": False, "has_emotion_recognition_workplace": False,
    "has_biometric_categorization": False, "has_real_time_biometric_id": False,
    "has_ncii_generation": False, "has_csam_generation": False,
}


def _plan(module, tmp_path, key, answers):
    BaseArticleModule.set_context(_ctx_with(key, answers))
    return module.action_plan(module.scan(str(tmp_path)))


def _art5_plan(art05_module, tmp_path, monkeypatch, **answers):
    monkeypatch.setitem(type(art05_module).scan.__globals__, "_today", lambda: date(2027, 1, 1))
    return _plan(art05_module, tmp_path, "art5", {**_ART5_ALL_FALSE, **answers})


class TestArt4:
    def test_no_measures_gives_one_action(self, art04_module, tmp_path):
        plan = _plan(art04_module, tmp_path, "art4", {"has_ai_literacy_measures": False})
        assert [a.action for a in plan.actions] == [
            "Take measures to support the development of AI literacy of staff and other persons dealing with the "
            "operation and use of AI systems on your behalf"
        ]
        # the one action still names every Art. 4(1) factor the dropped "verify" action named
        d = plan.actions[0].details
        for factor in ("technical knowledge, experience, education and training", "context in which the AI systems",
                       "persons or groups of persons on whom the AI systems are to be used"):
            assert factor in d

    def test_measures_found_gives_the_review_only(self, art04_module, tmp_path):
        plan = _plan(art04_module, tmp_path, "art4", {"has_ai_literacy_measures": True,
                                                       "literacy_description": "AI usage policy"})
        assert [a.action for a in plan.actions] == [
            "Verify AI literacy measures take the required factors into account"]

    def test_unknown_gives_the_review_only(self, art04_module, tmp_path):
        plan = _plan(art04_module, tmp_path, "art4", {"has_ai_literacy_measures": None})
        assert [a.action for a in plan.actions] == [
            "Verify AI literacy measures take the required factors into account"]


class TestArt5:
    def test_nothing_flagged_gives_one_review_and_record_action(self, art05_module, tmp_path, monkeypatch):
        plan = _art5_plan(art05_module, tmp_path, monkeypatch)
        assert len(plan.actions) == 1
        a = plan.actions[0]
        assert (a.priority, a.article) == ("HIGH", "Art. 5 (all)")
        assert a.action == "Review the system against each Art. 5 prohibition and record the assessment"
        # only the points with an exception or limitation are named for it; no overstated "essential" claim
        assert "for points (bb), (d), (f), (g) and (h), which contain an exception or limitation" in a.details
        assert "Art. 5 does not require this record" in a.details
        assert "essential" not in a.details

    def test_flagged_keeps_one_record_action_beside_the_practice(self, art05_module, tmp_path, monkeypatch):
        plan = _art5_plan(art05_module, tmp_path, monkeypatch, has_social_scoring=True)
        assert [a.article for a in plan.actions] == ["Art. 5 (ART05-PRO-1c)", "Art. 5 (all)"]
        assert plan.actions[0].priority == "CRITICAL"
        assert plan.actions[1].action == "Record the Art. 5 assessment"
        assert "Art. 5 does not require this record" in plan.actions[1].details


class TestArt6:
    def test_no_indicator_gives_one_classification_action(self, art06_module, tmp_path):
        plan = _plan(art06_module, tmp_path, "art6", {"annex_iii_categories": [], "annex_i_product_type": None,
                                                       "is_high_risk": False, "reasoning": "support chatbot"})
        assert [a.action for a in plan.actions] == ["Complete formal Art. 6 risk classification"]
        d = plan.actions[0].details
        assert "No high-risk indicators were detected by AI analysis; this does not establish that the system is "                "not high-risk." in d
        # the Art. 6(4) duties stay in the plan when the scanner finds no Annex III category
        assert "Art. 6(4) requires you to document that assessment before the system is placed on the market" in d
        assert "register under Art. 49(2)" in d

    def test_no_action_cites_art_6_3_for_the_documentation_duty(self, art06_module, tmp_path):
        plan = _plan(art06_module, tmp_path, "art6", {"annex_iii_categories": ["employment"],
                                                       "annex_i_product_type": None, "is_high_risk": None,
                                                       "reasoning": ""})
        titles = [a.action for a in plan.actions]
        assert "Create and maintain classification documentation" not in titles
        assert "Confirm non-high-risk classification with manual review" not in titles
        assert titles.count("Complete formal Art. 6 risk classification") == 1

    def test_exception_action_states_art_6_4_not_a_notification(self, art06_module, tmp_path):
        plan = _plan(art06_module, tmp_path, "art6", {"annex_iii_categories": ["employment"],
                                                       "annex_i_product_type": None, "is_high_risk": None,
                                                       "reasoning": ""})
        exc = [a for a in plan.actions if a.action == "Evaluate Art. 6(3) exception applicability"]
        assert len(exc) == 1
        assert exc[0].article == "Art. 6(3)-(4)"
        d = exc[0].details
        assert "notify" not in d.lower()
        assert "Art. 49(2)" in d and "profiling of natural persons is always high-risk" in d
        assert "the system is intended to (a) perform a narrow procedural task" in d
        assert "national competent authorities" in d
