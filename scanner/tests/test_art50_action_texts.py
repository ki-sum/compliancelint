"""Article 50 action-plan texts (series-2 e1 to-do list, 2026-10-26; legal review o3 Z of 2026-10-26).

The e1 preview of `cl_action_plan` for the demo chatbot showed Art. 50 actions with wrong law: "Art. 50(4) requires:
... Implement C2PA manifest", an artistic exception described as "but still indicate AI origin", an "X-AI-Generated
header for text" as Art. 50(2) marking, and an action "Evaluate C2PA integration for future-proofing" that began "Even
if not currently generating synthetic content" for a system that does generate content. The texts are now those of
review Z: one action per duty, each naming its obligation, with the route o3 gave (`where`); a "yes" to the marking
question gets its own action (marking for every in-scope output type), and text published on matters of public
interest gets one too. The future-proofing action is gone.
"""
import json
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)
sys.path.insert(0, os.path.dirname(__file__))

import server  # noqa: E402
from core.context import ProjectContext, _build_answers_template  # noqa: E402
from core.protocol import BaseArticleModule  # noqa: E402
from test_acceptance_r2_legal_scope import _load_module  # noqa: E402
from test_art50_evidence_fields import _art50_findings  # noqa: E402

A = ("Inform users that they are interacting with an AI system",
     "For AI systems intended to interact directly with natural persons, Art. 50(1) requires providers to ensure people "
     "are informed that they are interacting with AI, unless this is obvious in context or a statutory exception "
     "applies. Give a clear, distinguishable and accessible notice at the start of the first interaction (Art. 50(5)), "
     "for example when the chat opens: “You are chatting with an AI assistant.” Do not rely solely on terms of "
     "service. Record any exception relied on.")
B = ("Verify that the AI disclosure is shown at the first interaction",
     "An AI-interaction notice was identified, but its presentation has not been verified. Check each relevant user "
     "journey to confirm that people receive a clear, distinguishable and accessible notice at the start of their "
     "first direct interaction (Art. 50(5)). A notice found only in terms of service is insufficient. Document any "
     "applicable exception.")
C = ("Mark in-scope AI-generated outputs in a machine-readable format",
     "No marking mechanism was identified for the system's potentially in-scope synthetic outputs. Determine which "
     "output types Article 50(2) covers; for each covered audio, image, video or text output, implement "
     "machine-readable marking and a corresponding means of detecting AI generation or manipulation. Possible "
     "techniques include verifiable provenance metadata (such as C2PA Content Credentials), watermarks, or suitable "
     "combinations with detection-supporting fingerprinting or logging. Preserve existing marks where practicable. "
     "Record unmarked output types, applicable exceptions and technical limitations; no technique alone guarantees "
     "compliance.")
D = ("Confirm that marking covers every in-scope synthetic output type",
     "A marking mechanism was identified for at least one output type; this does not establish compliance. Check "
     "each in-scope synthetic audio, image, video and text output and delivery path for machine-readable marking and "
     "a usable detection method. Test whether marks survive the project's normal processing, where technically "
     "feasible. Record unmarked output types, valid exceptions and technical limits in marking_evidence. A person "
     "confirms the assessment in Human Gates.")
D_FINDING = (
    "A marking mechanism was identified for at least one synthetic output type. This is evidence for review, not "
    "proof of Article 50(2) compliance. Human review must confirm machine-readable marking and a usable detection "
    "method for each in-scope output type, and assess any outputs listed as unmarked in marking_evidence.")
E_TAIL = (
    " of its operation, unless the statutory law-enforcement exception applies. Provide clear, distinguishable and "
    "accessible information by first exposure (Art. 50(5)). Separately check applicable data-protection law (GDPR, "
    "Regulation (EU) 2018/1725 or Directive (EU) 2016/680), including any GDPR Arts. 13–14 notices or Art. 35 "
    "impact assessment. Assess any Article 5 prohibition independently.")
E1 = ("Inform exposed persons of the emotion recognition system",
      "Art. 50(3) requires deployers to inform natural persons exposed to an emotion recognition system" + E_TAIL)
E2 = ("Inform exposed persons of the biometric categorisation system",
      "Art. 50(3) requires deployers to inform natural persons exposed to a biometric categorisation system" + E_TAIL)
F = ("Disclose that deep fake image, audio or video content is AI-generated or manipulated",
     "Where AI-generated or manipulated image, audio or video meets the Art. 3(60) definition of a deep fake, Art. "
     "50(4) requires deployers to disclose its AI origin clearly, distinguishably and accessibly by first exposure "
     "(Art. 50(5)), for example with a visible or audible label. For an evidently artistic, creative, satirical, "
     "fictional or analogous work, disclosure may be appropriately non-disruptive but is still required. This is "
     "separate from Art. 50(2) machine-readable marking. In Human Gates, confirm deep-fake status and any exception, "
     "and verify or arrange the actual disclosure.")
G = ("Decide how AI-generated text published on matters of public interest is disclosed",
     "Check whether AI-generated or manipulated text is published to inform the public on matters of public interest. "
     "If so, Art. 50(4) requires deployers to disclose its AI origin clearly, distinguishably and accessibly by first "
     "exposure, unless the text received substantive human review or editorial control and a natural or legal person "
     "holds editorial responsibility, or a statutory law-enforcement exception applies. Mere proofreading is "
     "insufficient. Record evidence of the exception or the actual disclosure in Human Gates.")
H = ("Document Art. 50 applicability assessment",
     "Maintain an internal transparency register recording applicable Art. 50 paragraphs, provider/deployer roles, "
     "implemented measures, supporting evidence, reasons for exceptions or non-applicability, and review dates. Check "
     "other applicable transparency duties separately (Art. 50(6)). This register is recommended compliance evidence, "
     "not a separately prescribed Art. 50 document.")

# The e1 state of the demo chatbot: no notice, images re-encoded (no marking), photorealistic images without a label,
# press releases not answered yet.
E1_STATE = {
    "is_chatbot_or_interactive_ai": True, "is_generating_synthetic_content": True,
    "has_ai_disclosure_to_users": False, "has_content_watermarking": False,
    "is_emotion_recognition_system": False, "is_biometric_categorization_system": False,
    "has_emotion_biometric_disclosure": None, "is_deep_fake_system": True, "has_deep_fake_disclosure": False,
    "publishes_public_interest_text": None,
    "disclosure_evidence": [], "marking_evidence": [], "deep_fake_evidence": [], "public_interest_text_evidence": [],
    "emotion_biometric_evidence": [],
}


def _actions(tmp_path, **changes):
    mod = _load_module("art50-transparency-obligations")
    answers = {**E1_STATE, **changes}
    BaseArticleModule.set_context(ProjectContext(
        primary_language="python", risk_classification="limited-risk", risk_classification_confidence="high",
        compliance_answers={"_scope": {"is_ai_system": True, "risk_classification": "limited-risk"}, "art50": answers},
    ))
    BaseArticleModule.set_config(None)
    try:
        return [a.to_dict() for a in mod.action_plan(mod.scan(str(tmp_path))).actions]
    finally:
        BaseArticleModule.set_context(None)


def _by_title(actions):
    return {a["action"]: a for a in actions}


def _assert_action(actions, text, priority, obligation_id, where):
    a = _by_title(actions).get(text[0])
    assert a is not None, f"missing action {text[0]!r}; have {[x['action'] for x in actions]}"
    assert a["details"] == text[1]
    assert a["priority"] == priority
    assert a.get("obligation_id") == obligation_id
    assert a.get("where") == where


def test_e1_state_actions(tmp_path):
    actions = _actions(tmp_path)
    _assert_action(actions, A, "CRITICAL", "ART50-OBL-1", "project")
    _assert_action(actions, C, "CRITICAL", "ART50-OBL-2", "project")
    _assert_action(actions, F, "CRITICAL", "ART50-OBL-4", "human_gates")
    _assert_action(actions, G, "HIGH", "ART50-OBL-4b", "human_gates")
    _assert_action(actions, H, "MEDIUM", None, "human_gates")
    assert {a["action"] for a in actions} == {A[0], C[0], F[0], G[0], H[0]}


def test_no_wrong_law_and_no_future_proofing_action(tmp_path):
    for changes in ({}, {"has_content_watermarking": True, "has_ai_disclosure_to_users": True},
                    {"is_generating_synthetic_content": False, "is_deep_fake_system": False}):
        text = json.dumps(_actions(tmp_path, **changes))
        assert "future-proofing" not in text
        assert "X-AI-Generated" not in text
        assert "Implement C2PA manifest" not in text
        assert "but still indicate AI origin" not in text


def test_disclosure_found_is_verified_in_human_gates(tmp_path):
    actions = _actions(tmp_path, has_ai_disclosure_to_users=True)
    _assert_action(actions, B, "MEDIUM", "ART50-OBL-1", "human_gates")
    assert A[0] not in _by_title(actions)


def test_marking_found_asks_for_every_output_type(tmp_path):
    actions = _actions(tmp_path, has_content_watermarking=True)
    _assert_action(actions, D, "MEDIUM", "ART50-OBL-2", "project")
    assert C[0] not in _by_title(actions)


def test_marking_unknown_is_treated_as_not_identified(tmp_path):
    _assert_action(_actions(tmp_path, has_content_watermarking=None), C, "CRITICAL", "ART50-OBL-2", "project")


def test_the_marking_yes_finding_is_evidence_for_review(tmp_path):
    finding = _art50_findings(tmp_path, {**E1_STATE, "has_content_watermarking": True,
                                         "marking_evidence": ["src/chatbot.py: C2PA kept"]})["ART50-OBL-2"]
    assert finding["description"].startswith(D_FINDING)
    assert "src/chatbot.py: C2PA kept" in finding["description"]


def test_emotion_recognition_and_biometric_categorisation(tmp_path):
    actions = _actions(tmp_path, is_emotion_recognition_system=True, is_biometric_categorization_system=True,
                       has_emotion_biometric_disclosure=False)
    _assert_action(actions, E1, "CRITICAL", "ART50-OBL-3", "project")
    _assert_action(actions, E2, "CRITICAL", "ART50-OBL-3", "project")


def test_deep_fake_disclosed_has_no_disclosure_action(tmp_path):
    assert F[0] not in _by_title(_actions(tmp_path, has_deep_fake_disclosure=True))


def test_public_interest_text_action_follows_the_answer(tmp_path):
    assert G[0] in _by_title(_actions(tmp_path, publishes_public_interest_text=True))
    assert G[0] in _by_title(_actions(tmp_path, publishes_public_interest_text=None))
    assert G[0] not in _by_title(_actions(tmp_path, publishes_public_interest_text=False))
    assert G[0] not in _by_title(_actions(tmp_path, publishes_public_interest_text=True,
                                          is_generating_synthetic_content=False))


class TestThePlanUsesTheGivenRoute:
    """cl_action_plan keeps the route of an action that names one (o3 Z), and its obligation id; other actions keep
    the route computed from their obligations."""

    QUESTIONNAIRE = ["ART50-OBL-1", "ART50-OBL-2", "ART50-OBL-4", "ART50-OBL-4b", "ART50-OBL-5"]

    def _plan(self, tmp_path, monkeypatch, **changes):
        server._ensure_all_modules_loaded()
        answers = _build_answers_template()
        answers["_scope"].update({"is_ai_system": True, "risk_classification": "limited-risk",
                                  "risk_classification_confidence": "high"})
        answers["art50"] = {**E1_STATE, **changes}
        BaseArticleModule.set_context(ProjectContext(
            primary_language="python", risk_classification="limited-risk", risk_classification_confidence="high",
            compliance_answers=answers))
        oids = ["ART50-OBL-1", "ART50-OBL-2", "ART50-OBL-4", "ART50-OBL-4b", "ART50-OBL-5", "ART50-OBL-6"]
        settings = {"applicable_articles": ["art50"], "applicable_obligations": oids,
                    "questionnaire": {o: {"prompt": "?", "evidence_min": 0} for o in self.QUESTIONNAIRE}}
        monkeypatch.setattr(server, "_fetch_saas_scan_settings", lambda _config, _path: settings)
        monkeypatch.setattr(server, "_fetch_effective_status_from_saas", lambda _p: {})
        plan = json.loads(server.cl_action_plan(str(tmp_path), article=50))
        return {a["action"]: a for a in plan["actions"]}

    def test_routes_and_obligations(self, tmp_path, monkeypatch):
        plan = self._plan(tmp_path, monkeypatch)
        assert (plan[A[0]]["where"], plan[A[0]]["obligation_ids"]) == ("project", ["ART50-OBL-1"])
        assert (plan[C[0]]["where"], plan[C[0]]["obligation_ids"]) == ("project", ["ART50-OBL-2"])
        assert (plan[F[0]]["where"], plan[F[0]]["obligation_ids"]) == ("human_gates", ["ART50-OBL-4"])
        assert (plan[G[0]]["where"], plan[G[0]]["obligation_ids"]) == ("human_gates", ["ART50-OBL-4b"])
        assert plan[H[0]]["where"] == "human_gates"

    def test_a_code_checked_obligation_can_be_routed_to_human_gates(self, tmp_path, monkeypatch):
        plan = self._plan(tmp_path, monkeypatch, has_ai_disclosure_to_users=True)
        assert (plan[B[0]]["where"], plan[B[0]]["obligation_ids"]) == ("human_gates", ["ART50-OBL-1"])


def test_the_plan_disclaimer_states_no_wrong_scope(tmp_path):
    mod = _load_module("art50-transparency-obligations")
    BaseArticleModule.set_context(ProjectContext(
        primary_language="python", risk_classification="limited-risk", risk_classification_confidence="high",
        compliance_answers={"_scope": {"is_ai_system": True, "risk_classification": "limited-risk"}, "art50": E1_STATE},
    ))
    try:
        disclaimer = mod.action_plan(mod.scan(str(tmp_path))).disclaimer
    finally:
        BaseArticleModule.set_context(None)
    assert disclaimer == "Based on ComplianceLint compliance checklist."
