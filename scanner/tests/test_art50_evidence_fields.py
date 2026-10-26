"""Art. 50: one evidence list per duty (legal review of 2026-10-21; found on the production site).

The scanner asked for one `disclosure_evidence` list and used it for 50(1); the AI put the image-marking and the
press-release evidence there too, so the 50(1) finding quoted evidence about 50(2) and 50(4). Now four lists:
`disclosure_evidence` (50(1)), `marking_evidence` (50(2)), `deep_fake_evidence` (50(4) first subparagraph),
`public_interest_text_evidence` (50(4) second subparagraph), each with its own description, and each finding quotes
only its own list. An empty list means only that nothing was found for that duty.
"""
import json
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402

DESCRIPTIONS = {
    "disclosure_evidence": (
        "List of free-text items identifying where natural persons are informed that they are interacting with an AI "
        "system for the purposes of Article 50(1), for example a notice displayed at or before the first interaction. "
        "Empty list if no such evidence is found."
    ),
    # review AA (2026-10-26): gaps, negative findings and the means of detection (test_art50_2_scope_and_detection.py)
    "marking_evidence": None,
    "deep_fake_evidence": (
        "List of free-text items identifying where deployers disclose that image, audio or video content "
        "constituting a deep fake has been artificially generated or manipulated for the purposes of Article 50(4), "
        "first subparagraph. Empty list if no such evidence is found."
    ),
    "public_interest_text_evidence": (
        "List of free-text items identifying either (i) where deployers disclose that AI-generated or manipulated "
        "text published for the purpose of informing the public on matters of public interest has been artificially "
        "generated or manipulated, or (ii) evidence that the exception in Article 50(4), second subparagraph, applies "
        "because the content has undergone human review or editorial control and a natural or legal person holds "
        "editorial responsibility for its publication. Empty list if no such evidence is found."
    ),
}


def _analyze(tmp_path):
    (tmp_path / "app.py").write_text("print('hi')")
    return json.loads(server.cl_analyze_project(str(tmp_path)))


def _reviewed():
    from test_art50_2_scope_and_detection import MARKING_EVIDENCE_DESCRIPTION
    return {**DESCRIPTIONS, "marking_evidence": MARKING_EVIDENCE_DESCRIPTION}


def test_the_template_has_the_four_lists(tmp_path):
    template = _analyze(tmp_path)["compliance_answers_template"]["art50"]
    for name in DESCRIPTIONS:
        assert template[name] == [], name


def test_each_list_has_its_description(tmp_path):
    descs = _analyze(tmp_path)["compliance_answers_field_descriptions"]["art50"]
    for name, text in _reviewed().items():
        assert descs[name] == text, name


def _art50_findings(tmp_path, answers):
    (tmp_path / "app.py").write_text("print('hi')")
    scope = {
        "is_ai_system": True, "territorial_scope_applies": True, "is_open_source": False, "is_military_defense": False,
        "is_research_only": False, "is_biometric_system": False, "is_financial_institution": False,
        "is_distributor": False, "is_importer": False, "is_gpai_provider": False,
        "is_authorised_representative": False, "risk_classification": "limited-risk",
        "risk_classification_confidence": "high", "risk_reasoning": "A chatbot.", "open_source_license": "",
    }
    ctx = json.dumps({"stack": ["python"], "compliance_answers": {"_scope": scope, "art50": answers}})
    out = json.JSONDecoder().raw_decode(server.cl_scan(str(tmp_path), project_context=ctx, articles="50"))[0]
    findings = out.get("findings") or out.get("results", {}).get("article_50", {}).get("findings") or []
    return {f["obligation_id"]: f for f in findings}


def test_each_finding_quotes_its_own_evidence(tmp_path):
    answers = {
        "is_chatbot_or_interactive_ai": True, "is_generating_synthetic_content": True,
        "has_ai_disclosure_to_users": True, "has_content_watermarking": True,
        "is_emotion_recognition_system": False, "is_biometric_categorization_system": False,
        "has_emotion_biometric_disclosure": None, "is_deep_fake_system": False, "has_deep_fake_disclosure": None,
        "publishes_public_interest_text": True,
        "disclosure_evidence": ["src/chatbot.py: AI notice before the first message"],
        "marking_evidence": ["src/chatbot.py: IPTC trainedAlgorithmicMedia in the image XMP"],
        "deep_fake_evidence": [],
        "public_interest_text_evidence": ["src/chatbot.py: label above every press release"],
        "emotion_biometric_evidence": [],
    }
    f = _art50_findings(tmp_path, answers)
    blob1 = json.dumps(f["ART50-OBL-1"])
    blob2 = json.dumps(f["ART50-OBL-2"])
    assert "AI notice before the first message" in blob1 and "trainedAlgorithmicMedia" not in blob1
    assert "trainedAlgorithmicMedia" in blob2 and "AI notice" not in blob2
