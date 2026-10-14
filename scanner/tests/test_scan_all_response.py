"""cl_scan_all response: readable by the AI client in one piece, and its numbers say what they count (1.2.2).

Found while recording a real Claude Code scan (2026-10-10):

- The response was 324,637 characters; 253,852 of them (78 %) were `related_recitals_by_article` — the verbatim text
  of every Recital related to every scanned article. Claude Code keeps a tool result in the conversation only up to
  50,000 characters (25,000 tokens); a larger one is written to a file and the assistant gets the file path instead,
  so the assistant never saw the scan summary directly. A tool can declare a higher limit for itself
  (`_meta["anthropic/maxResultSizeChars"]`, ceiling 500,000).
- The assistant reported "15 articles non-compliant" while the dashboard showed "Non-Compliant 2 of 145 findings" for
  the same scan. Both are right, and nothing in the response said why: the response carries the AI's assessment per
  article, while cl_sync records an obligation that needs human judgment as "needs review" until a person confirms it
  (Human Gates) — the AI's verdict on it is a hypothesis.
"""
import asyncio
import glob
import json
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402
from core.context import _build_answers_template  # noqa: E402

# Claude Code's default threshold for keeping a tool result in the conversation, and its hard ceiling for a tool that
# declares its own limit.
CLAUDE_CODE_DEFAULT_CHARS = 50_000
CLAUDE_CODE_CEILING_CHARS = 500_000
LEVELS = ("non_compliant", "partial", "unable_to_determine", "not_applicable", "compliant")


def _context(**scope):
    answers = _build_answers_template()
    answers["_scope"].update({"is_ai_system": True, "risk_classification": "high-risk", "risk_classification_confidence": "high"})
    answers["_scope"].update(scope)
    # Answers that make modules emit verdicts on obligations of every kind (automated, hybrid, manual).
    for article, fields in answers.items():
        if article == "_scope" or not isinstance(fields, dict):
            continue
        for key, value in fields.items():
            if value is None and key.startswith(("has_", "is_")):
                fields[key] = False
    return json.dumps({"framework": "python", "compliance_answers": answers})


def _scan(tmp_path):
    raw = server.cl_scan_all(str(tmp_path), project_context=_context())
    report, _ = json.JSONDecoder().raw_decode(raw.lstrip())
    assert report["report_type"] == "compliance_scan_summary", report
    return raw, report


def _saved_findings_one_per_obligation(tmp_path):
    """The saved scan state, one finding per obligation id: the one saved under the obligation's own article wins
    (what the dashboard stores)."""
    chosen = {}
    for path in sorted(glob.glob(os.path.join(str(tmp_path), ".compliancelint", "local", "articles", "*.json"))):
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
        article = int(os.path.basename(path)[3:].split(".")[0].rstrip("abcdefghijklmnopqrstuvwxyz"))
        for oid, v in (saved.get("findings") or {}).items():
            if v.get("baselineState") == "absent":
                continue
            own = oid.upper().startswith(f"ART{article:02d}-") or oid.upper().startswith(f"ART{article}-")
            if oid not in chosen or (own and not chosen[oid][0]):
                chosen[oid] = (own, dict(v, obligation_id=oid))
    return {oid: f for oid, (_, f) in chosen.items()}


def _declared_limit(tool_name="cl_scan_all"):
    tools = asyncio.run(server.mcp.list_tools())
    tool = next(t for t in tools if t.name == tool_name)
    return (tool.meta or {}).get("anthropic/maxResultSizeChars")


# ── size ──


def test_response_carries_recital_numbers_not_recital_text(tmp_path):
    raw, report = _scan(tmp_path)

    assert "related_recitals_by_article" not in report
    numbers = report["related_recital_numbers_by_article"]
    # Art. 5 (prohibited practices) has related Recitals; each entry is a Recital number.
    assert numbers["5"], numbers.keys()
    assert all(isinstance(n, int) for nums in numbers.values() for n in nums)
    assert "source_quote" not in raw
    # The assistant is told where the text is.
    assert "cl_explain" in report["related_recitals_note"]


def test_recital_numbers_match_the_recitals_the_single_article_tools_return(tmp_path):
    from core.obligation_lookup import recitals_for_article

    _, report = _scan(tmp_path)
    for article, numbers in report["related_recital_numbers_by_article"].items():
        assert numbers == [r["number"] for r in recitals_for_article(int(article))], article


@pytest.mark.parametrize("tool_name", ["cl_analyze_project", "cl_scan_all", "cl_action_plan"])
def test_large_response_tools_declare_a_result_limit_claude_code_accepts(tool_name):
    """The three tools whose response is larger than 50,000 characters on a real project (measured 2026-10-11:
    analyze 56,286, scan-all about 60,000, action plan about 65,000)."""
    limit = _declared_limit(tool_name)
    assert isinstance(limit, int), f"{tool_name} must declare _meta['anthropic/maxResultSizeChars']"
    assert CLAUDE_CODE_DEFAULT_CHARS < limit <= CLAUDE_CODE_CEILING_CHARS


def test_full_scan_response_fits_the_declared_limit_with_room_to_spare(tmp_path):
    raw, report = _scan(tmp_path)
    assert report["total_modules"] >= 45
    # A full scan with a verdict on every obligation: half the declared limit at most.
    assert len(raw) <= _declared_limit() // 2, len(raw)


def test_analyze_response_fits_the_declared_limit_with_room_to_spare(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")
    raw = server.cl_analyze_project(str(tmp_path))
    assert "compliance_answers_template" in raw
    assert len(raw) <= _declared_limit("cl_analyze_project") // 2, len(raw)


# ── action plan ──


def test_action_plan_for_all_articles_carries_recital_numbers_not_recital_text(tmp_path):
    """Same weight as in cl_scan_all: 254,222 of 328,871 characters were Recital text (measured 2026-10-11)."""
    from core.obligation_lookup import recitals_for_article

    _scan(tmp_path)
    raw = server.cl_action_plan(str(tmp_path))
    plan, _ = json.JSONDecoder().raw_decode(raw.lstrip())
    assert plan["total_actions"] > 0, plan.keys()

    assert "related_recitals_by_article" not in plan
    numbers = plan["related_recital_numbers_by_article"]
    assert numbers["5"] == [r["number"] for r in recitals_for_article(5)]
    assert all(isinstance(n, int) for nums in numbers.values() for n in nums)
    assert "cl_explain" in plan["related_recitals_note"]
    # The disclaimer points at the field that is there.
    assert "related_recitals_by_article" not in plan["disclaimer"]
    assert "related_recital_numbers_by_article" in plan["disclaimer"]
    assert len(raw) <= _declared_limit("cl_action_plan") // 2, len(raw)


def test_action_plan_for_one_article_keeps_the_recital_text(tmp_path):
    _scan(tmp_path)
    raw = server.cl_action_plan(str(tmp_path), article=5)
    plan, _ = json.JSONDecoder().raw_decode(raw.lstrip())

    recitals = plan["related_recitals_by_article"]["5"]
    assert len(recitals) >= 1
    assert all(len(r["source_quote"]) > 100 for r in recitals)
    assert "related_recital_numbers_by_article" not in plan
    assert "related_recitals_by_article" in plan["disclaimer"]


# ── what the numbers count ──


def _counts(levels):
    return {level: sum(1 for lv in levels if lv == level) for level in LEVELS}


def test_totals_count_articles_and_findings_separately_and_say_so(tmp_path):
    _, report = _scan(tmp_path)
    totals = report["totals"]

    articles = totals["articles_by_ai_assessment"]
    assert articles == {"unit": "articles", "total": report["total_modules"], **_counts([r["overall"] for r in report["results"].values()])}

    findings = totals["findings_by_ai_assessment"]
    assert findings["unit"] == "findings (one per obligation)"
    # One per obligation (2026-10-14): an obligation that two modules report (Art. 12 reports ART19-OBL-1b / -2)
    # counts once, as on the dashboard; the per-article finding_count still counts it in each article.
    oracle = _saved_findings_one_per_obligation(tmp_path)
    assert findings["total"] == len(oracle)
    assert findings["total"] < sum(r["finding_count"] for r in report["results"].values()), "scenario has no mirrored obligation"
    assert sum(findings[level] for level in LEVELS) == findings["total"]


def test_totals_show_what_the_dashboard_will_record(tmp_path):
    """Oracle: the saved scan state, run through the same post-process cl_sync applies before uploading."""
    _, report = _scan(tmp_path)

    expected = {"non_compliant": 0, "needs_review": 0, "not_applicable": 0, "compliant": 0}
    # One finding per obligation, the one of the obligation's own article (2026-10-14, as the dashboard stores it).
    findings = list(_saved_findings_one_per_obligation(tmp_path).values())
    ai_non_compliant = sum(1 for f in findings if f.get("level") == "non_compliant")
    for f in server._apply_approach_b_post_process(findings):
        level = f.get("level")
        expected[level if level in ("non_compliant", "not_applicable", "compliant") else "needs_review"] += 1

    recorded = report["totals"]["findings_as_recorded_on_dashboard"]
    assert {k: recorded[k] for k in expected} == expected
    assert recorded["unit"] == "findings (one per obligation)"
    assert recorded["total"] == sum(expected.values()) == report["totals"]["findings_by_ai_assessment"]["total"]
    # The scenario exercises the difference: the AI called obligations non-compliant that the dashboard will hold
    # as "needs review" until a person confirms them.
    assert 0 < recorded["non_compliant"] < ai_non_compliant, (recorded, ai_non_compliant)

    explanation = report["totals"]["explanation"]
    for phrase in ("articles", "findings", "Human Gates", "needs review"):
        assert phrase in explanation, phrase


def test_scan_totals_helper_keeps_automated_verdicts_and_holds_human_judgment_ones():
    per_article = {
        # ART72-OBL-1: detected from the code — the AI's verdict is recorded as it is.
        72: [{"obligation_id": "ART72-OBL-1", "level": "non_compliant", "description": "No post-market monitoring system."}],
        # ART82-OBL-2: needs human judgment — recorded as "needs review".
        82: [{"obligation_id": "ART82-OBL-2", "level": "non_compliant", "description": "No corrective action procedure found."}],
        4: [{"obligation_id": "ART04-OBL-1", "level": "not_applicable", "description": "x"}],
    }
    overall = {72: "non_compliant", 82: "non_compliant", 4: "not_applicable"}

    totals = server._scan_totals(overall, per_article)

    assert totals["articles_by_ai_assessment"]["non_compliant"] == 2
    assert totals["findings_by_ai_assessment"]["non_compliant"] == 2
    assert totals["findings_as_recorded_on_dashboard"] == {
        "unit": "findings (one per obligation)",
        "total": 3,
        "non_compliant": 1,
        "needs_review": 1,
        "not_applicable": 1,
        "compliant": 0,
    }
    # The caller's findings are not rewritten by the count.
    assert per_article[82][0]["level"] == "non_compliant"
    assert per_article[82][0]["description"] == "No corrective action procedure found."


def test_scan_totals_count_an_obligation_reported_by_two_modules_once():
    """The Art. 12 module also reports ART19-OBL-1b / -2 (log keeping). The dashboard stores one finding per obligation,
    the one from the obligation's own article; the scan totals counted both
    and said 177 where the dashboard recorded 175 (demo recording, 2026-10-14)."""
    per_article = {
        12: [
            {"obligation_id": "ART12-OBL-1", "level": "unable_to_determine", "description": "x"},
            # mirrored from Art. 19 — reported by the Art. 12 module with a different verdict
            {"obligation_id": "ART19-OBL-1b", "level": "non_compliant", "description": "x"},
            {"obligation_id": "ART19-OBL-2", "level": "not_applicable", "description": "x"},
        ],
        19: [
            {"obligation_id": "ART19-OBL-1b", "level": "not_applicable", "description": "x"},
            {"obligation_id": "ART19-OBL-2", "level": "not_applicable", "description": "x"},
        ],
    }
    overall = {12: "non_compliant", 19: "not_applicable"}

    totals = server._scan_totals(overall, per_article)

    # three obligations; ART19-OBL-1b counts with the Art. 19 module's verdict
    assert totals["findings_by_ai_assessment"]["total"] == 3
    assert totals["findings_by_ai_assessment"]["non_compliant"] == 0
    assert totals["findings_by_ai_assessment"]["not_applicable"] == 2
    assert totals["findings_as_recorded_on_dashboard"]["total"] == 3
    assert totals["findings_as_recorded_on_dashboard"]["not_applicable"] == 2
    assert totals["findings_as_recorded_on_dashboard"]["needs_review"] == 1
    # articles are still counted per module
    assert totals["articles_by_ai_assessment"]["total"] == 2


def test_scan_totals_keep_a_mirrored_obligation_whose_own_module_did_not_report_it():
    per_article = {12: [{"obligation_id": "ART26-OBL-6", "level": "unable_to_determine", "description": "x"}]}
    totals = server._scan_totals({12: "unable_to_determine"}, per_article)
    assert totals["findings_by_ai_assessment"]["total"] == 1
    assert totals["findings_as_recorded_on_dashboard"]["needs_review"] == 1
