"""A scan of some articles keeps the saved answers of the others (series-3 recording, 2026-10-28).

The assistant rescanned Articles 9 and 13 with a project context that held only those two articles' answers (and
_scope). _save_last_context wrote that context over .compliancelint/local/last_context.json, so the saved answers of
the 43 other articles were gone although their results in .compliancelint/local/articles/ were unchanged.
cl_action_plan reads the saved context: on the same project its plan fell from 85 to 44 actions. The saved context
now stays consistent with the per-article results on disk: an article scanned in this call takes the new answers,
an article not scanned keeps its saved answers.
"""
import json
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402
from core.context import _build_answers_template  # noqa: E402
from core.protocol import BaseArticleModule  # noqa: E402


def _answers() -> dict:
    answers = _build_answers_template()
    answers["_scope"].update({"is_ai_system": True, "risk_classification": "high-risk",
                              "risk_classification_confidence": "high"})
    return answers


def _scan(path, answers: dict, articles: str) -> dict:
    raw = server.cl_scan(str(path), project_context=json.dumps({"framework": "python", "compliance_answers": answers}),
                         articles=articles)
    result, _ = json.JSONDecoder().raw_decode(raw.lstrip())  # the tool may append a plain-text footer
    assert "error" not in result, result
    return result


def _saved(path) -> dict:
    return json.loads((path / ".compliancelint" / "local" / "last_context.json").read_text(encoding="utf-8"))


def _only(answers: dict, *keys: str) -> dict:
    return {k: v for k, v in answers.items() if k in ("_scope",) + keys}


def test_scan_of_other_articles_keeps_the_saved_answers(tmp_path):
    full = _answers()
    full["art12"]["has_logging"] = True
    _scan(tmp_path, full, "12")

    partial = _only(_answers(), "art9")
    _scan(tmp_path, partial, "9")

    saved = _saved(tmp_path)["compliance_answers"]
    assert saved["art12"]["has_logging"] is True
    assert "art9" in saved
    assert saved["_scope"]["risk_classification"] == "high-risk"


def test_rescanned_article_takes_the_new_answers(tmp_path):
    first = _answers()
    first["art12"]["has_logging"] = True
    _scan(tmp_path, first, "12")

    second = _only(_answers(), "art12")
    second["art12"]["has_logging"] = False
    _scan(tmp_path, second, "12")

    assert _saved(tmp_path)["compliance_answers"]["art12"]["has_logging"] is False


def test_several_articles_in_one_call_take_their_new_answers(tmp_path):
    first = _answers()
    first["art12"]["has_logging"] = True
    _scan(tmp_path, first, "12")

    second = _only(_answers(), "art9", "art13")
    _scan(tmp_path, second, "9,13")

    saved = _saved(tmp_path)["compliance_answers"]
    assert saved["art12"]["has_logging"] is True
    assert saved["art9"] == second["art9"]
    assert saved["art13"] == second["art13"]


def _art5_answered() -> dict:
    """Every Art. 5 practice answered "no" with evidence, as the assistant answered for the demo project."""
    answers = _answers()
    for key in list(answers["art5"]):
        answers["art5"][key] = False if key.startswith("has_") else "Not present in src/."
    return answers


def test_action_plan_of_an_unscanned_article_is_unchanged_after_a_partial_scan(tmp_path):
    _scan(tmp_path, _art5_answered(), "5")
    BaseArticleModule.set_context(None)
    before = json.loads(server.cl_action_plan(str(tmp_path), article=5))
    assert "error" not in before, before

    _scan(tmp_path, _only(_answers(), "art9"), "9")
    BaseArticleModule.set_context(None)  # a new MCP process: cl_action_plan reads the saved context
    after = json.loads(server.cl_action_plan(str(tmp_path), article=5))

    assert after["actions"] == before["actions"]


def test_action_plan_differs_when_the_answers_are_missing(tmp_path):
    """Guard for the test above: the Art. 5 plan does depend on the saved answers, so an unchanged plan there
    shows the answers were kept, not that the plan ignores them."""
    (tmp_path / "answered").mkdir()
    (tmp_path / "unanswered").mkdir()
    _scan(tmp_path / "answered", _art5_answered(), "5")
    BaseArticleModule.set_context(None)
    answered = json.loads(server.cl_action_plan(str(tmp_path / "answered"), article=5))

    _scan(tmp_path / "unanswered", _answers(), "5")
    BaseArticleModule.set_context(None)
    unanswered = json.loads(server.cl_action_plan(str(tmp_path / "unanswered"), article=5))

    assert answered["actions"] != unanswered["actions"]
