"""A scan reports the level it saves, after the evidence is counted (series-2 recording, 2026-10-25, QA #38).

A finding with evidence provided (cl_update_finding) is saved as compliant when the next scan finds it partial or
unable to determine (core/state.py), and cl_sync puts that level on the dashboard. cl_scan and cl_scan_all reported
the scan's own level instead: after "rescan and sync" the assistant said "Article 50(1) is partial, with your evidence
attached" while the dashboard showed it compliant. Now every scan response reports the saved level, names the scan's
own level next to it when the two differ, and computes the article's overall level from the saved levels.
"""
import json
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402
from core.state import update_finding  # noqa: E402

SCOPE = {
    "is_ai_system": True, "territorial_scope_applies": True, "is_open_source": False, "is_military_defense": False,
    "is_research_only": False, "is_biometric_system": False, "is_financial_institution": False, "is_distributor": False,
    "is_importer": False, "is_gpai_provider": False, "is_authorised_representative": False,
    "risk_classification": "limited-risk", "risk_classification_confidence": "high",
    "risk_reasoning": "A customer-support chatbot.", "open_source_license": "",
}
# A chatbot with an AI notice: ART50-OBL-1 comes out partial (a person has to confirm it), 50(5)-(7) unable to determine.
ART50 = {
    "is_chatbot_or_interactive_ai": True, "is_generating_synthetic_content": False, "has_ai_disclosure_to_users": True,
    "disclosure_evidence": ["static/widget.html: notice before the first message"],
    "is_emotion_recognition_system": False, "is_biometric_categorization_system": False,
    "is_deep_fake_system": False, "publishes_public_interest_text": False,
}
ATTESTER = {"name": "Alex Weber", "email": "alex@example.com", "role": "developer", "source": "config"}


def _context(*more_articles):
    """Art. 50 answered as above; every other article named left open (its template, all null)."""
    answers = {"_scope": SCOPE, "art50": ART50}
    if more_articles:
        from core.context import _build_answers_template
        template = _build_answers_template()
        answers.update({art: template[art] for art in more_articles})
    return json.dumps({"stack": ["python"], "compliance_answers": answers})


def _first_json(raw):
    return json.JSONDecoder().raw_decode(raw)[0]


def _project(tmp_path):
    (tmp_path / "app.py").write_text("print('hi')")
    return str(tmp_path)


def _overall(findings):
    """As BaseArticleModule._compute_overall_level: informational findings (coverage gaps, meta warnings) do not count."""
    levels = [f["level"] for f in findings if not f.get("is_informational")]
    if not levels:
        return "unable_to_determine"
    active = [lv for lv in levels if lv != "not_applicable"]
    if not active:
        return "not_applicable"
    if all(lv == "compliant" for lv in active):
        return "compliant"
    for worst in ("non_compliant", "partial"):
        if worst in active:
            return worst
    return "unable_to_determine"


def _scan_one(project):
    return _first_json(server.cl_scan(project, project_context=_context(), articles="50"))


class TestSingleArticleScan:
    def test_evidence_provided_is_reported_as_the_saved_level(self, tmp_path):
        project = _project(tmp_path)
        first = {f["obligation_id"]: f for f in _scan_one(project)["findings"]}
        assert first["ART50-OBL-1"]["level"] == "partial"
        update_finding(project, "ART50-OBL-1", "provide_evidence", "repo_file", "static/widget.html", attester=ATTESTER)

        out = _scan_one(project)
        f = {x["obligation_id"]: x for x in out["findings"]}["ART50-OBL-1"]
        assert f["level"] == "compliant"
        assert f["level_in_this_scan"] == "partial"
        assert "evidence" in f["level_note"]
        expected = _overall(out["findings"])
        assert expected == "compliant"
        assert out["overall_level"] == expected
        assert out["compliance_summary"]["overall"] == expected

    def test_without_evidence_the_scan_level_stands(self, tmp_path):
        project = _project(tmp_path)
        _scan_one(project)
        f = {x["obligation_id"]: x for x in _scan_one(project)["findings"]}["ART50-OBL-1"]
        assert f["level"] == "partial"
        assert "level_in_this_scan" not in f


class TestSeveralArticles:
    def test_the_summary_reports_the_saved_level(self, tmp_path):
        project = _project(tmp_path)
        _scan_one(project)
        update_finding(project, "ART50-OBL-1", "provide_evidence", "repo_file", "static/widget.html", attester=ATTESTER)
        out = _first_json(server.cl_scan(project, project_context=_context("art4"), articles="50,4"))
        art50 = out["results"]["article_50"]
        top = {f["obligation_id"]: f for f in art50["top_findings"]}
        assert top.get("ART50-OBL-1", {}).get("level") != "partial"
        assert art50["overall"] != "partial"


class TestScanAll:
    def test_scan_all_reports_the_saved_level(self, tmp_path, monkeypatch):
        project = _project(tmp_path)
        (tmp_path / ".compliancelintrc").write_text(json.dumps({"saas_api_key": "test-key", "repo_name": "t"}))
        settings = {
            "roles": ["provider", "deployer"], "riskClassification": "limited-risk", "is_provider": True,
            "is_deployer": True, "applicable_articles": ["art50"],
            "applicable_obligations": ["ART50-OBL-1", "ART50-OBL-5", "ART50-OBL-6", "ART50-OBL-7", "ART50-OBL-7a"],
            "questionnaire": None, "enforcement_mode": "lenient", "tier_at_scan": "business",
        }
        monkeypatch.setattr(server, "_fetch_saas_scan_settings", lambda *a, **k: dict(settings))
        monkeypatch.setattr(server, "_fetch_effective_status_from_saas", lambda *a, **k: {})
        for name in ("core.classification_client", "scanner.core.classification_client"):
            mod = sys.modules.get(name)
            if mod is not None:
                monkeypatch.setattr(mod, "fetch_classifications", lambda *a, **k: None)
        _first_json(server.cl_scan_all(project, project_context=_context()))
        update_finding(project, "ART50-OBL-1", "provide_evidence", "repo_file", "static/widget.html", attester=ATTESTER)

        out = _first_json(server.cl_scan_all(project, project_context=_context()))
        art50 = out["results"]["article_50"]
        top = {f["obligation_id"]: f for f in art50["top_findings"]}
        assert "ART50-OBL-1" not in top or top["ART50-OBL-1"]["level"] == "compliant"
        assert art50["overall"] != "partial"
        recorded = out["totals"]["findings_as_recorded_on_dashboard"]
        assert recorded["compliant"] >= 1, recorded
