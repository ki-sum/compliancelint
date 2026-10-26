"""cl_action_plan follows the dashboard's applicability profile (series-2 recording, 2026-10-25, QA #39).

For a limited-risk chatbot (Profiling Wizard: provider + deployer, not high-risk, not a GPAI provider) the plan listed
78 actions over all 45 article modules — GPAI systemic-risk duties as CRITICAL, high-risk duties as HIGH — because it
never read the applicable set the scan uses, and its actions carry no obligation id, so the dashboard overlay could
not mark them either. A user who asks "what do I have to fix?" got a misleading list.

Now, when the dashboard's scan settings are available: only the applicable articles are planned, an action is kept
only if one of its obligations is applicable, every kept action names its obligations, and each says whether a person
answers it in Human Gates or the project has to change.
"""
import json

import pytest

import server
from test_cl_action_plan_overlay import _real_context


def _settings(articles, obligations, questionnaire=()):
    return {
        "applicable_articles": list(articles),
        "applicable_obligations": list(obligations),
        "questionnaire": {o: {"prompt": "?", "evidence_min": 0} for o in questionnaire},
    }


def _plan(tmp_path, monkeypatch, settings, article=0):
    _real_context()
    monkeypatch.setattr(server, "_fetch_saas_scan_settings", lambda _config, _path: settings)
    monkeypatch.setattr(server, "_fetch_effective_status_from_saas", lambda _p: {})
    return json.loads(server.cl_action_plan(str(tmp_path), article=article))


class TestPlanFollowsTheDashboardProfile:
    def test_only_the_applicable_articles_are_planned(self, tmp_path, monkeypatch):
        applicable = ["ART04-OBL-1", "ART12-OBL-2a", "ART12-OBL-2c"]
        plan = _plan(tmp_path, monkeypatch, _settings(["art4", "art12"], applicable))
        assert plan["actions"], "the applicable articles still have actions"
        assert {c.split(" (")[0] for c in plan["articles_covered"]} == {"Art. 4", "Art. 12"}
        for action in plan["actions"]:
            assert action["obligation_ids"], action
            assert set(action["obligation_ids"]) <= set(applicable), action
        assert not any(a["article"].startswith(("Art. 51", "Art. 52", "Art. 55", "Art. 9")) for a in plan["actions"])
        assert plan["dashboard_applicability"]["applied"] is True

    def test_an_action_on_an_obligation_the_profile_excludes_is_dropped(self, tmp_path, monkeypatch):
        # Under the high-risk test context the Art. 12 plan has "Art. 12(2)(a)" and "Art. 12(2)(c)".
        plan = _plan(tmp_path, monkeypatch, _settings(["art12"], ["ART12-OBL-2a"]), article=12)
        assert [a["article"] for a in plan["actions"]] == ["Art. 12(2)(a)"]
        assert plan["actions"][0]["obligation_ids"] == ["ART12-OBL-2a"]
        excluded = plan["dashboard_applicability"]["actions_not_applicable"]
        assert excluded == {"count": 1, "articles": ["Art. 12(2)(c)"]}
        assert plan["total_actions"] == 1

    def test_each_action_says_whether_a_person_answers_it_in_human_gates(self, tmp_path, monkeypatch):
        plan = _plan(tmp_path, monkeypatch,
                     _settings(["art4", "art12"], ["ART04-OBL-1", "ART12-OBL-2a", "ART12-OBL-2c"],
                               questionnaire=["ART04-OBL-1"]))
        by_article = {a["article"]: a for a in plan["actions"]}
        art4 = [a for ref, a in by_article.items() if ref.startswith("Art. 4")]
        assert art4 and all(a["where"] == "human_gates" for a in art4)
        assert by_article["Art. 12(2)(a)"]["where"] == "project"
        assert plan["by_where"] == {
            where: sum(1 for a in plan["actions"] if a["where"] == where) for where in ("human_gates", "project", "both")
        }


class TestPlanFollowsTheScan:
    """An obligation the dashboard profile lists can still be not applicable in this project's scan: Art. 111(4) (the
    Art. 50(2) transition for systems placed on the market before 2 August 2026) is always not applicable in the scan,
    yet the e1 to-do list of the demo chatbot (2026-10-26) listed "Monitor transitional compliance deadlines and
    regulatory guidance" as a project change. An action whose obligations are all not applicable in the scan is left
    out and counted with the other not-applicable actions."""

    def test_an_action_on_obligations_the_scan_finds_not_applicable_is_dropped(self, tmp_path, monkeypatch):
        plan = _plan(tmp_path, monkeypatch, _settings(["art111"], ["ART111-OBL-4"]), article=111)
        assert not any("Monitor transitional" in a["action"] for a in plan["actions"]), plan["actions"]
        assert "Art. 111" in plan["dashboard_applicability"]["actions_not_applicable"]["articles"]

    def test_an_obligation_open_in_the_scan_keeps_its_action(self, tmp_path, monkeypatch):
        # Under the high-risk test context the Art. 12 findings are open, so both Art. 12 actions stay.
        plan = _plan(tmp_path, monkeypatch, _settings(["art12"], ["ART12-OBL-2a", "ART12-OBL-2c"]), article=12)
        assert [a["article"] for a in plan["actions"]] == ["Art. 12(2)(a)", "Art. 12(2)(c)"]


class TestWhereAnActionIsAnswered:
    """A person answers an obligation in Human Gates when it is in the repo's questionnaire and the scanner cannot
    settle it from the code (automation level partial or manual). Obligations the scanner checks in the code (level
    full: Art. 50(1) notice, 50(2) marking) are in the questionnaire too — they need evidence — but the project
    changes for them; the dashboard's Art. 50 Human Gate asks only 50(4), 50(4) second subparagraph and 50(5)."""

    QUESTIONNAIRE = {"ART50-OBL-1", "ART50-OBL-2", "ART50-OBL-4", "ART50-OBL-4b", "ART50-OBL-5", "ART04-OBL-1"}

    def test_code_checked_obligation_is_a_project_change(self):
        assert server._action_where(["ART50-OBL-1"], self.QUESTIONNAIRE) == "project"
        assert server._action_where(["ART50-OBL-2"], self.QUESTIONNAIRE) == "project"

    def test_judgment_obligations_are_human_gates(self):
        assert server._action_where(["ART50-OBL-4", "ART50-OBL-5"], self.QUESTIONNAIRE) == "human_gates"
        assert server._action_where(["ART04-OBL-1"], self.QUESTIONNAIRE) == "human_gates"

    def test_not_in_the_questionnaire_is_a_project_change(self):
        assert server._action_where(["ART12-OBL-2a"], self.QUESTIONNAIRE) == "project"

    def test_an_action_over_both_kinds_says_both(self):
        assert server._action_where(["ART50-OBL-1", "ART50-OBL-4"], self.QUESTIONNAIRE) == "both"

    def test_no_obligation_is_a_project_change(self):
        assert server._action_where([], self.QUESTIONNAIRE) == "project"


class TestPlanWithoutTheDashboardProfile:
    def test_not_connected_plans_every_article_and_says_so(self, tmp_path, monkeypatch):
        plan = _plan(tmp_path, monkeypatch, None)
        assert len(plan["articles_covered"]) > 10
        applicability = plan["dashboard_applicability"]
        assert applicability["applied"] is False
        assert "Profiling Wizard" in applicability["note"]
        assert all("where" not in a for a in plan["actions"])
