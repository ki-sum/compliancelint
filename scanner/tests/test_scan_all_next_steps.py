"""cl_scan_all's next steps do not ask for a changes summary that nothing uses (series-3 recording, 2026-10-28).

The changes-summary upload was removed from cl_sync on 2026-04-16 (it always sends null), but cl_scan_all's
next_steps still told the assistant to write .compliancelint/local/changes_summary.txt "so that cl_sync can include
it in the dashboard upload". In the recording the assistant wrote the file and told the user it was included in the
upload, and later that the upload carried an old summary; neither was true.
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
ART50 = {
    "is_chatbot_or_interactive_ai": True, "is_generating_synthetic_content": False, "has_ai_disclosure_to_users": True,
    "disclosure_evidence": ["static/widget.html: notice before the first message"],
    "is_emotion_recognition_system": False, "is_biometric_categorization_system": False,
    "is_deep_fake_system": False, "publishes_public_interest_text": False,
}


def _scan_all(tmp_path, monkeypatch) -> dict:
    (tmp_path / "app.py").write_text("print('hi')")
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
    raw = server.cl_scan_all(str(tmp_path), project_context=json.dumps(
        {"stack": ["python"], "compliance_answers": {"_scope": SCOPE, "art50": ART50}}))
    return json.JSONDecoder().raw_decode(raw)[0]


def test_next_steps_do_not_ask_for_a_changes_summary(tmp_path, monkeypatch):
    out = _scan_all(tmp_path, monkeypatch)
    steps = out["next_steps"]
    assert "changes_summary" not in steps
    assert "cl_sync can include" not in steps


def test_next_steps_still_guide_the_fix_loop(tmp_path, monkeypatch):
    """Guard: the rest of the instructions stays (review, ask, fix and re-scan, human judgment)."""
    steps = _scan_all(tmp_path, monkeypatch)["next_steps"]
    for phrase in ("REVIEW the findings above", "re-scan to verify the fix worked", "cl_update_finding"):
        assert phrase in steps, phrase
