"""cl_scan(articles="50") asks only for the requested article's answers (found on the production site, 2026-10-21).

A single-article scan with complete Art. 50 answers came back "needs_analysis_first … still need to check 4 more" and
listed art111, art4, art5 and art6 — the completeness gate of the full scan. The gate now counts only the requested
articles as missing; `articles="all"` keeps the full check (cl_scan_all).
"""
import json
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402

SCOPE = {
    "is_ai_system": True, "territorial_scope_applies": True, "is_open_source": False, "is_military_defense": False,
    "is_research_only": False, "is_biometric_system": False, "is_financial_institution": False,
    "is_distributor": False, "is_importer": False, "is_gpai_provider": False, "is_authorised_representative": False,
    "risk_classification": "limited-risk", "risk_classification_confidence": "high",
    "risk_reasoning": "A customer-support chatbot.", "open_source_license": "",
}
ART50 = {
    "is_chatbot_or_interactive_ai": True, "is_generating_synthetic_content": False, "has_ai_disclosure_to_users": True,
    "has_content_watermarking": None, "is_emotion_recognition_system": False, "is_biometric_categorization_system": False,
    "has_emotion_biometric_disclosure": None, "is_deep_fake_system": False, "has_deep_fake_disclosure": None,
    "publishes_public_interest_text": False, "disclosure_evidence": ["src/chat.py: notice before the first message"],
    "emotion_biometric_evidence": [], "deep_fake_evidence": [],
}


def _ctx(answers):
    return json.dumps({"stack": ["python"], "compliance_answers": {"_scope": SCOPE, **answers}})


def test_single_article_scan_needs_only_its_own_answers(tmp_path):
    (tmp_path / "app.py").write_text("print('hi')")
    out = json.JSONDecoder().raw_decode(server.cl_scan(str(tmp_path), project_context=_ctx({"art50": ART50}),
                                                       articles="50"))[0]
    assert out.get("status") != "needs_analysis_first", out


def test_the_requested_article_still_has_to_be_answered(tmp_path):
    (tmp_path / "app.py").write_text("print('hi')")
    out = json.JSONDecoder().raw_decode(server.cl_scan(str(tmp_path), project_context=_ctx({}), articles="50"))[0]
    assert out.get("status") == "needs_analysis_first"
    assert out["missing_articles"] == ["art50"]
