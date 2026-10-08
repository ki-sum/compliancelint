"""The paid evidence-completeness check no longer blocks cl_scan_all (acceptance run E, founder 2026-10-08:
do not block the scan, list the missing evidence).

Every paid tier is in "strict" mode (getEnforcementMode). Once a repo had synced (repo_id cached), each cl_scan_all
returned `pending_evidence_needs_sync` — "190 obligations need evidence on file before this scan can run" — and the
suggested cl_sync → cl_scan_all chain returned the same answer again: a paying user could not rescan until every
required obligation had evidence and an answer. It went unnoticed because the dashboard settings were only read when
the MCP server's working directory was the project (fixed the same day).

Now the scan always runs; the obligations still missing evidence / an answer come back in `pending_evidence`.
"""
import json
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402
from core.context import _build_answers_template  # noqa: E402

SETTINGS = {
    "roles": ["provider"],
    "is_provider": True,
    "riskClassification": "high-risk",
    "applicable_articles": None,
    "applicable_obligations": None,
    "questionnaire": {"ART12-OBL-1": {"evidence_min": 1, "completion_required": True}},
    "enforcement_mode": "strict",
    "tier_at_scan": "pro",
}


def _project(tmp):
    os.makedirs(os.path.join(tmp, ".compliancelint", "local"))
    with open(os.path.join(tmp, ".compliancelint", "local", "metadata.json"), "w") as f:
        json.dump({"repo_id": "repo-xyz"}, f)
    with open(os.path.join(tmp, ".compliancelintrc"), "w") as f:
        json.dump({"saas_url": "https://dash.test.local", "saas_api_key": "cl_test_key", "repo_name": "acme/x"}, f)


def _context():
    answers = _build_answers_template()
    answers["_scope"].update({"is_ai_system": True, "risk_classification": "high-risk", "risk_classification_confidence": "high"})
    return json.dumps({"framework": "python", "compliance_answers": answers})


def test_strict_mode_with_missing_evidence_still_scans_and_lists_it(tmp_path, monkeypatch):
    _project(str(tmp_path))
    monkeypatch.setattr(server, "_fetch_saas_scan_settings", lambda config, project_path: json.loads(json.dumps(SETTINGS)))
    result, _ = json.JSONDecoder().raw_decode(server.cl_scan_all(str(tmp_path), project_context=_context()).lstrip())

    assert result.get("status") != "pending_evidence_needs_sync", result
    assert result["report_type"] == "compliance_scan_summary"
    assert (tmp_path / ".compliancelint" / "local" / "articles" / "art12.json").is_file()
    pending = result["pending_evidence"]
    assert [p["obligation_id"] for p in pending["obligations"]] == ["ART12-OBL-1"]
    assert pending["count"] == 1
    assert "scan ran" in pending["note"]


def test_nothing_pending_no_field(tmp_path, monkeypatch):
    _project(str(tmp_path))
    settings = json.loads(json.dumps(SETTINGS))
    settings["questionnaire"] = {}
    monkeypatch.setattr(server, "_fetch_saas_scan_settings", lambda config, project_path: settings)
    result, _ = json.JSONDecoder().raw_decode(server.cl_scan_all(str(tmp_path), project_context=_context()).lstrip())
    assert result["report_type"] == "compliance_scan_summary"
    assert "pending_evidence" not in result
