"""cl_action_plan works in a new MCP process after a scan (acceptance run A5a, 2026-10-07, founder: fix before release).

The scan answers (project context) lived only in the MCP server's memory, so after Claude Code restarted,
cl_action_plan answered "No project context available. Run a scan first" although the scan results were on disk.
cl_scan / cl_scan_all now keep the context in .compliancelint/local/last_context.json and cl_action_plan reads the
project's own copy (falling back to the in-memory context when there is none).
"""
import json
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402
from core.context import _build_answers_template  # noqa: E402
from core.protocol import BaseArticleModule  # noqa: E402


def _context_json() -> str:
    # The full template (the scan asks for every applicable article first), scope filled, one answer set.
    answers = _build_answers_template()
    answers["_scope"].update({"is_ai_system": True, "risk_classification": "high-risk", "risk_classification_confidence": "high"})
    answers["art12"]["has_logging"] = True
    return json.dumps({"framework": "python", "compliance_answers": answers})


def _new_process():
    """What a restarted MCP server looks like: no context in memory."""
    BaseArticleModule.set_context(None)


def test_action_plan_after_restart_uses_the_saved_context(tmp_path):
    raw = server.cl_scan(str(tmp_path), project_context=_context_json(), articles="12")
    scan, _ = json.JSONDecoder().raw_decode(raw.lstrip())  # the tool may append a plain-text footer
    assert "error" not in scan, scan
    assert (tmp_path / ".compliancelint" / "local" / "last_context.json").is_file()

    _new_process()
    plan = json.loads(server.cl_action_plan(str(tmp_path), article=12))
    assert "error" not in plan, plan
    assert plan["articles_covered"] == ["Art. 12 (Record-keeping)"]


def test_saved_context_keeps_the_answers(tmp_path):
    server.cl_scan(str(tmp_path), project_context=_context_json(), articles="12")
    saved = json.loads((tmp_path / ".compliancelint" / "local" / "last_context.json").read_text(encoding="utf-8"))
    assert saved["compliance_answers"]["art12"]["has_logging"] is True
    assert saved["compliance_answers"]["_scope"]["risk_classification"] == "high-risk"


def test_no_scan_and_nothing_in_memory_still_asks_for_a_scan(tmp_path):
    _new_process()
    plan = json.loads(server.cl_action_plan(str(tmp_path), article=12))
    assert "No project context available" in plan["error"]
