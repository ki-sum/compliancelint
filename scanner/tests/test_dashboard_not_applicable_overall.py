"""An article whose findings the dashboard's applicability profile makes not applicable is not applicable as a whole
(found on the production site, 2026-10-22).

cl_scan_all set each finding the dashboard excludes to not_applicable, but the article's overall level was computed
before that: Art. 111 read "unable_to_determine" with all four findings not applicable. cl_scan for one article did
not apply the dashboard's obligation list at all, so the same findings stayed "unable_to_determine" there.
"""
import json
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402

SCOPE = {
    "is_ai_system": True, "territorial_scope_applies": True, "is_open_source": False, "is_military_defense": False,
    "is_research_only": False, "is_biometric_system": False, "is_financial_institution": False, "is_distributor": False,
    "is_importer": False, "is_gpai_provider": False, "is_authorised_representative": False,
    "risk_classification": "limited-risk", "risk_classification_confidence": "high",
    "risk_reasoning": "A customer-support chatbot.", "open_source_license": "",
}
ART111 = {
    "has_transition_plan": None, "has_significant_change_tracking": None, "has_gpai_compliance_timeline": None,
    "transition_evidence": "", "change_tracking_evidence": "", "gpai_timeline_evidence": "",
}
SETTINGS = {
    "roles": ["provider", "deployer"],
    "riskClassification": "limited-risk",
    "is_provider": True,
    "is_deployer": True,
    "applicable_articles": ["art111"],
    # The wizard answered "not an Annex X component", no high-risk legacy system, no general-purpose AI model.
    "applicable_obligations": ["ART111-OBL-4"],
    "questionnaire": None,
    "enforcement_mode": "lenient",
    "tier_at_scan": "business",
}


def _project(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text("print('hi')")
    (tmp_path / ".compliancelintrc").write_text(json.dumps({"saas_api_key": "test-key", "repo_name": "t"}))
    monkeypatch.setattr(server, "_fetch_saas_scan_settings", lambda *a, **k: dict(SETTINGS))
    monkeypatch.setattr(server, "_fetch_effective_status_from_saas", lambda *a, **k: {})
    for name in ("core.classification_client", "scanner.core.classification_client"):
        mod = sys.modules.get(name)
        if mod is not None:
            monkeypatch.setattr(mod, "fetch_classifications", lambda *a, **k: None)
    return str(tmp_path)


def _context():
    return json.dumps({"stack": ["python"], "compliance_answers": {"_scope": SCOPE, "art111": ART111}})


def _first_json(raw):
    return json.JSONDecoder().raw_decode(raw)[0]


def test_scan_all_article_overall_follows_the_dashboard(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    out = _first_json(server.cl_scan_all(project, project_context=_context()))
    art = out["results"]["article_111"]
    assert {f["level"] for f in art["top_findings"]} == {"not_applicable"}
    assert art["overall"] == "not_applicable"


def test_single_article_scan_applies_the_dashboard_list(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    out = _first_json(server.cl_scan(project, project_context=_context(), articles="111"))
    levels = {f["obligation_id"]: f["level"] for f in out["findings"]}
    for oid in ("ART111-OBL-1", "ART111-OBL-2", "ART111-OBL-3"):
        assert levels[oid] == "not_applicable", oid
    assert out["overall_level"] == "not_applicable"
