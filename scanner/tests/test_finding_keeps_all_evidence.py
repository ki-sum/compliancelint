"""A finding quotes every evidence item of its answer (series-2 recording, 2026-10-25, QA #37 and #36).

_finding_from_answer joined only the first three items into the description: the assistant listed eight
marking_evidence items for Art. 50(2) and the eighth — the open text point with its owner and review dates — was cut
from the dashboard's evidence summary and from the Compliance Pack. And an answer "no" dropped its evidence entirely,
so what the assistant had recorded (the image marking, the page marker) disappeared behind "no content marking was
found". Now every item is kept, for a "no" as well.
"""
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)
sys.path.insert(0, os.path.dirname(__file__))

from test_art50_evidence_fields import _art50_findings  # noqa: E402

ITEMS = [
    "OPEN POINT (Art. 50(2), text): no watermark yet; owner Alex Weber; review 23 January 2027",
    "src/chatbot.py: images saved unchanged, C2PA and SynthID kept",
    "src/provenance.py: provenance check before posting",
    "src/web.py: POST /api/provenance/check",
    "src/publishing.py: ai-generated meta tag and IPTC trainedAlgorithmicMedia",
    "src/fingerprint.py: sentence fingerprints",
    "tests/test_fingerprint.py: ten tests",
    "docs/ai-content-marking.md: technical assessment",
]


def _answers(marking):
    return {
        "is_chatbot_or_interactive_ai": True, "is_generating_synthetic_content": True,
        "has_ai_disclosure_to_users": True, "has_content_watermarking": marking,
        "is_emotion_recognition_system": False, "is_biometric_categorization_system": False,
        "has_emotion_biometric_disclosure": None, "is_deep_fake_system": False, "has_deep_fake_disclosure": None,
        "publishes_public_interest_text": False,
        "disclosure_evidence": ["static/widget.html: notice"], "marking_evidence": list(ITEMS),
        "deep_fake_evidence": [], "public_interest_text_evidence": [], "emotion_biometric_evidence": [],
    }


def test_every_evidence_item_is_in_the_description(tmp_path):
    desc = _art50_findings(tmp_path, _answers(True))["ART50-OBL-2"]["description"]
    for item in ITEMS:
        assert item in desc, item


def test_an_answer_no_keeps_its_evidence(tmp_path):
    finding = _art50_findings(tmp_path, _answers(False))["ART50-OBL-2"]
    assert finding["level"] == "non_compliant"
    for item in ITEMS:
        assert item in finding["description"], item
