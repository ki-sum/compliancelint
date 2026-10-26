"""Article 50(2): the marking answer covers every technical method, and "no" says what was not identified (series-2
recording, 2026-10-25, QA #36; legal review o3 Y of 2026-10-25).

`has_content_watermarking` had no description. The assistant answered "no" because the generated text carried no
watermark, although the generated images kept C2PA Content Credentials and a SynthID watermark and the published pages
carried an IPTC marker: the finding read "no content marking was found" while its own evidence listed those measures.
The field now says that any identified mechanism — metadata, watermark or another method, for some outputs only as
well — is a "yes", that a "yes" means evidence for review and not compliance, and that unmarked outputs are listed in
marking_evidence. The "no" finding names what was not identified and asks for a review of the evidence.
"""
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)
sys.path.insert(0, os.path.dirname(__file__))

from test_acceptance_r2_legal_scope import _load_module  # noqa: E402
from test_art50_evidence_fields import _analyze, _art50_findings  # noqa: E402
from core.context import ProjectContext  # noqa: E402
from core.protocol import BaseArticleModule  # noqa: E402

FIELD_DESCRIPTION = (
    "true if at least one of the system's synthetic audio, image, video or text outputs has an identified mechanism "
    "intended to mark it in a machine-readable format and enable detection as artificially generated or manipulated, "
    "including embedded metadata, watermarking or another technical method. This includes cases where only some output "
    "types or output paths are marked. true indicates evidence requiring human review, not compliance with Article "
    "50(2). false if no such mechanism is identified for any relevant synthetic output; null if the available project "
    "evidence is insufficient to determine this. In marking_evidence, identify each mechanism and its code or "
    "configuration location where available, and explicitly identify any synthetic output types or paths for which "
    "marking or detectability is absent or cannot be verified."
)

FALSE_DESCRIPTION = (
    "System generates synthetic content, but no machine-readable marking mechanism enabling detection as artificially "
    "generated or manipulated was identified for its synthetic outputs. Article 50(2) requires such marking, subject "
    "to its applicable exceptions and technical-feasibility qualifications. Review the evidence and confirm whether "
    "marking is implemented elsewhere."
)


def _answers(marking, evidence):
    return {
        "is_chatbot_or_interactive_ai": True, "is_generating_synthetic_content": True,
        "has_ai_disclosure_to_users": True, "has_content_watermarking": marking,
        "is_emotion_recognition_system": False, "is_biometric_categorization_system": False,
        "has_emotion_biometric_disclosure": None, "is_deep_fake_system": False, "has_deep_fake_disclosure": None,
        "publishes_public_interest_text": False,
        "disclosure_evidence": [], "marking_evidence": evidence,
        "deep_fake_evidence": [], "public_interest_text_evidence": [], "emotion_biometric_evidence": [],
    }


def test_the_marking_answer_is_described(tmp_path):
    descs = _analyze(tmp_path)["compliance_answers_field_descriptions"]["art50"]
    assert descs["has_content_watermarking"] == FIELD_DESCRIPTION


def test_a_no_names_what_was_not_identified_and_keeps_the_evidence(tmp_path):
    item = "src/publishing.py: no marking of generated text found"
    finding = _art50_findings(tmp_path, _answers(False, [item]))["ART50-OBL-2"]
    assert finding["level"] == "non_compliant"
    assert finding["description"].startswith(FALSE_DESCRIPTION)
    assert item in finding["description"]
    assert "no content marking was found" not in finding["description"]


def test_the_action_for_missing_marking_has_the_reviewed_text(tmp_path):
    # The action text of review Y was replaced by review Z (2026-10-26, test_art50_action_texts.py).
    from test_art50_action_texts import C
    mod = _load_module("art50-transparency-obligations")
    ctx = ProjectContext(
        primary_language="python", risk_classification="limited-risk", risk_classification_confidence="high",
        compliance_answers={"_scope": {"is_ai_system": True, "risk_classification": "limited-risk"},
                            "art50": _answers(False, [])},
    )
    BaseArticleModule.set_context(ctx)
    BaseArticleModule.set_config(None)
    try:
        actions = mod.action_plan(mod.scan(str(tmp_path))).actions
    finally:
        BaseArticleModule.set_context(None)
    marking = [a for a in actions if a.article == "Art. 50(2)" and a.priority == "CRITICAL"]
    assert len(marking) == 1
    assert (marking[0].action, marking[0].details) == C
    assert "no content marking found" not in marking[0].details
