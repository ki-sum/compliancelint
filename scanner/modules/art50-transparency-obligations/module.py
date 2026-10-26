"""
Article 50: Transparency Obligations for Certain AI Systems — Module implementation.

Art. 50 is the BROADEST obligation in the EU AI Act — it applies to almost all
AI systems, not just high-risk ones.  Any system that interacts with persons,
generates synthetic content, or processes biometrics must comply.

Covers four main paragraphs:
  50(1)  Human interaction disclosure (chatbots, virtual assistants, etc.)
  50(2)  Synthetic content marking (images, audio, video, text)
  50(3)  Emotion recognition / biometric categorization disclosure
  50(4)  Deep fake disclosure
"""

import os
import sys
from datetime import datetime, timezone

# Add core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.application_dates import applicable_from
from core.harmonised_standards import standard_status
from core.protocol import (
    BaseArticleModule, ScanResult, Explanation, ActionPlan, ActionItem,
    Finding, ComplianceLevel, Confidence, GapType,
)
from core.obligation_engine import ObligationEngine


class Art50Module(BaseArticleModule):
    """Article 50: Transparency Obligations for Certain AI Systems."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=50,
            article_title="Transparency Obligations for Certain AI Systems",
        )

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for Art. 50 transparency obligations using AI-provided answers."""
        project_path = os.path.abspath(project_path)
        ctx = self._effective_ctx(project_path)  # AI-First: raises if ctx is None
        na = self._scope_gate(ctx, project_path)
        if na:
            return na

        index = self._build_index(project_path)
        language = self._detect_language(project_path)
        file_count = index.source_file_count
        findings: list[Finding] = self._ctx_warnings(ctx)
        answers = ctx.get_article_answers("art50")

        is_chatbot = answers.get("is_chatbot_or_interactive_ai")
        is_generating_synthetic = answers.get("is_generating_synthetic_content")
        has_ai_disclosure = answers.get("has_ai_disclosure_to_users")
        disclosure_evidence = answers.get("disclosure_evidence", [])
        has_content_watermarking = answers.get("has_content_watermarking")
        is_emotion_system = answers.get("is_emotion_recognition_system")
        is_biometric_system = answers.get("is_biometric_categorization_system")
        has_emotion_biometric_disclosure = answers.get("has_emotion_biometric_disclosure")
        emotion_biometric_evidence = answers.get("emotion_biometric_evidence", [])
        is_deep_fake_system = answers.get("is_deep_fake_system")
        publishes_public_interest_text = answers.get("publishes_public_interest_text")
        has_deep_fake_disclosure = answers.get("has_deep_fake_disclosure")
        deep_fake_evidence = answers.get("deep_fake_evidence", [])
        # one list per duty (legal review 2026-10-21): 50(2) marking, 50(4) public-interest text
        marking_evidence = answers.get("marking_evidence", [])
        public_interest_text_evidence = answers.get("public_interest_text_evidence", [])

        # ── ART50-OBL-1: Human interaction disclosure ──
        # Conditioned on whether the system is a chatbot / interactive AI
        if is_chatbot is True:
            if has_ai_disclosure is None:
                # Chatbot confirmed but disclosure status unknown →
                # lean NON_COMPLIANT (obligation clearly applies, evidence missing)
                findings.append(Finding(
                    obligation_id="ART50-OBL-1",
                    file_path="project-wide",
                    line_number=None,
                    level=ComplianceLevel.NON_COMPLIANT,
                    confidence=Confidence.LOW,
                    description=(
                        "System is confirmed as a chatbot/interactive AI, but AI could not "
                        "determine whether disclosure is shown to users. Art. 50(1) requires "
                        "informing users they are interacting with an AI system. The obligation "
                        "clearly applies — if disclosure exists (e.g., in the UI but not in "
                        "source code), provide evidence to override this finding."
                    ),
                    gap_type=GapType.CODE,
                ))
            else:
                findings.append(self._finding_from_answer(
                    obligation_id="ART50-OBL-1",
                    answer=has_ai_disclosure,
                    true_description="AI disclosure to users found.",
                    false_description=(
                        "System is a chatbot/interactive AI but no AI disclosure to users "
                        "was found. Art. 50(1) requires informing users they are interacting "
                        "with an AI system, at the latest at the time of the first interaction or exposure "
                        "(Art. 50(5))."
                    ),
                    evidence=disclosure_evidence,
                    gap_type=GapType.CODE,
                ))
        elif is_chatbot is False:
            findings.append(Finding(
                obligation_id="ART50-OBL-1",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.MEDIUM,
                description=(
                    "Not applicable: system does not appear to be a chatbot or interactive "
                    "AI. Art. 50(1) applies only to systems designed to interact with natural "
                    "persons. Re-scan if you add conversational AI features."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            # is_chatbot is None — AI could not determine
            findings.append(Finding(
                obligation_id="ART50-OBL-1",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "AI could not determine whether this system is a chatbot or interactive "
                    "AI. Art. 50(1) requires disclosure to users when interacting with AI. "
                    "If this system has conversational or interactive AI features, "
                    "verify that disclosure is implemented."
                ),
                gap_type=GapType.PROCESS,
            ))

        # ── ART50-OBL-2: Synthetic content marking ──
        # Art. 50(2): outputs must be marked in machine-readable format
        if is_generating_synthetic is True:
            findings.append(self._finding_from_answer(
                obligation_id="ART50-OBL-2",
                answer=has_content_watermarking,
                # o3 Z (2026-10-26): "true" is evidence for review, not compliance.
                true_description=(
                    "A marking mechanism was identified for at least one synthetic output type. This is evidence for "
                    "review, not proof of Article 50(2) compliance. Human review must confirm machine-readable marking "
                    "and a usable detection method for each in-scope output type, and assess any outputs listed as "
                    "unmarked in marking_evidence."
                ),
                # Wording of the legal review o3 Y (2026-10-25, QA #36): "no" means no mechanism was identified,
                # not that the evidence proves an infringement.
                false_description=(
                    "System generates synthetic content, but no machine-readable marking mechanism enabling "
                    "detection as artificially generated or manipulated was identified for its synthetic outputs. "
                    "Article 50(2) requires such marking, subject to its applicable exceptions and "
                    "technical-feasibility qualifications. Review the evidence and confirm whether marking is "
                    "implemented elsewhere."
                ),
                evidence=marking_evidence,
                gap_type=GapType.CODE,
            ))
        elif is_generating_synthetic is False:
            findings.append(Finding(
                obligation_id="ART50-OBL-2",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.MEDIUM,
                description=(
                    "Not applicable: system does not appear to generate synthetic content. "
                    "Art. 50(2) applies only to systems generating AI images, audio, video, "
                    "or text. Re-scan if you add generative AI features."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            findings.append(Finding(
                obligation_id="ART50-OBL-2",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "AI could not determine whether this system generates synthetic content. "
                    "Art. 50(2) requires machine-readable marking of AI-generated content. "
                    "If this system generates images, audio, video, or text using AI, "
                    "verify content marking is implemented."
                ),
                gap_type=GapType.PROCESS,
            ))

        # ── ART50-OBL-3: Emotion recognition / biometric categorization disclosure ──
        # Art. 50(3): deployers must inform exposed persons
        has_emotion_or_biometric = (is_emotion_system is True or is_biometric_system is True)
        if has_emotion_or_biometric:
            findings.append(self._finding_from_answer(
                obligation_id="ART50-OBL-3",
                answer=has_emotion_biometric_disclosure,
                true_description=(
                    "Emotion/biometric recognition disclosure found. Art. 50(3) requires "
                    "informing exposed persons — verify disclosure reaches ALL affected persons."
                ),
                false_description=(
                    "System performs emotion recognition and/or biometric categorization but "
                    "no disclosure to exposed persons was found. Art. 50(3) requires deployers "
                    "to inform all natural persons exposed to the system, and to process "
                    "personal data in accordance with GDPR."
                ),
                evidence=emotion_biometric_evidence,
                gap_type=GapType.CODE,
            ))
        elif is_emotion_system is False and is_biometric_system is False:
            findings.append(Finding(
                obligation_id="ART50-OBL-3",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.MEDIUM,
                description=(
                    "Not applicable: system does not perform emotion recognition or biometric "
                    "categorization. Art. 50(3) does not apply."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            # None — AI could not determine
            findings.append(Finding(
                obligation_id="ART50-OBL-3",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "AI could not determine whether this system performs emotion recognition "
                    "or biometric categorization. Art. 50(3) requires informing exposed persons "
                    "if such processing occurs. Verify whether the system analyzes emotions, "
                    "age, gender, or other biometric categories."
                ),
                gap_type=GapType.PROCESS,
            ))

        # ── ART50-OBL-4: Deep fake disclosure ──
        # Art. 50(4): deployers must disclose AI-generated/manipulated content
        if is_deep_fake_system is True:
            findings.append(self._finding_from_answer(
                obligation_id="ART50-OBL-4",
                answer=has_deep_fake_disclosure,
                true_description=(
                    "Deep fake disclosure mechanism found. Art. 50(4) requires disclosing "
                    "that content has been artificially generated or manipulated."
                ),
                false_description=(
                    "System generates or manipulates deep fake content but no disclosure "
                    "mechanism was found. Art. 50(4) requires deployers to disclose that "
                    "content has been artificially generated or manipulated."
                ),
                evidence=deep_fake_evidence,
                gap_type=GapType.CODE,
            ))
        elif is_deep_fake_system is False:
            findings.append(Finding(
                obligation_id="ART50-OBL-4",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.MEDIUM,
                description=(
                    "Not applicable: system does not generate or manipulate deep fake content. "
                    "The first subparagraph of Art. 50(4) (deep fakes) does not apply."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            findings.append(Finding(
                obligation_id="ART50-OBL-4",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "AI could not determine whether this system generates or manipulates "
                    "deep fake content. Art. 50(4) requires disclosure of AI-generated or "
                    "manipulated content resembling real persons."
                ),
                gap_type=GapType.PROCESS,
            ))

        details = {
            "is_chatbot_or_interactive_ai": is_chatbot,
            "is_generating_synthetic_content": is_generating_synthetic,
            "has_ai_disclosure_to_users": has_ai_disclosure,
            "disclosure_evidence": disclosure_evidence,
            "marking_evidence": marking_evidence,
            "public_interest_text_evidence": public_interest_text_evidence,
            "has_content_watermarking": has_content_watermarking,
            "is_emotion_recognition_system": is_emotion_system,
            "is_biometric_categorization_system": is_biometric_system,
            "has_emotion_biometric_disclosure": has_emotion_biometric_disclosure,
            "is_deep_fake_system": is_deep_fake_system,
            "has_deep_fake_disclosure": has_deep_fake_disclosure,
            "publishes_public_interest_text": publishes_public_interest_text,
        }

        # ── Obligation Engine: enrich findings + identify gaps ──
        # Art. 50(4) second subparagraph (text published to inform the public on matters of public interest) — settled
        # by its own answer; true / unanswered stays with the obligation engine (acceptance round 2, 2026-10-09).
        if publishes_public_interest_text is False:
            findings = self._set_not_applicable(
                findings, ("ART50-OBL-4b",),
                "Not applicable: the answers state that the system does not generate or manipulate text published "
                "with the purpose of informing the public on matters of public interest (Art. 50(4), second "
                "subparagraph).",
            )

        obligations = self._load_obligations()
        if obligations:
            engine = ObligationEngine(obligations)
            findings = [engine.enrich_finding(f) for f in findings]
            gap_findings = engine.gap_findings(findings, ctx.compliance_answers if ctx else None)
            findings.extend(gap_findings)
            # Art. 50(5) governs "the information referred to in paragraphs 1 to 4": not applicable when none of
            # them applies (acceptance round 2, 2026-10-09).
            paras = ("ART50-OBL-1", "ART50-OBL-2", "ART50-OBL-3", "ART50-OBL-4", "ART50-OBL-4b")
            levels = {f.obligation_id: f.level for f in findings if getattr(f, "obligation_id", None) in paras}
            if len(levels) == len(paras) and all(lv == ComplianceLevel.NOT_APPLICABLE for lv in levels.values()):
                findings = self._set_not_applicable(
                    findings, ("ART50-OBL-5",),
                    "Not applicable: Article 50(5) governs how the information referred to in paragraphs 1 to 4 is "
                    "provided; none of paragraphs 1 to 4 applies to this system.",
                )
            details["obligation_coverage"] = {
                "total_obligations": len(engine.obligations),
                "covered_by_scan": len(engine.obligations) - len(gap_findings),
                "coverage_gaps": len([g for g in gap_findings if g.level != ComplianceLevel.NOT_APPLICABLE]),
                "gap_obligation_ids": [f.obligation_id for f in gap_findings],
            }

        findings = self._cap_findings(findings)

        return ScanResult(
            article_number=50,
            article_title="Transparency Obligations for Certain AI Systems",
            project_path=project_path,
            scan_date=datetime.now(timezone.utc).isoformat(),
            files_scanned=file_count,
            language_detected=language,
            overall_level=self._compute_overall_level(findings),
            overall_confidence=Confidence.MEDIUM,
            findings=findings,
            details=details,
        )

    def explain(self) -> Explanation:
        return Explanation(
            article_number=50,
            article_title="Transparency Obligations for Certain AI Systems",
            one_sentence=(
                "AI systems interacting with people must disclose they are AI; "
                "AI-generated content must be machine-readably marked; emotion recognition "
                "and deep fakes require specific disclosure."
            ),
            official_summary=(
                "Art. 50 imposes transparency obligations on a BROAD range of AI systems "
                "(not just high-risk). Four main requirements: "
                "(1) AI systems interacting with persons must disclose that fact; "
                "(2) AI-generated synthetic content (images, audio, video, text) must be "
                "marked as artificially generated in machine-readable format; "
                "(3) Emotion recognition and biometric categorization systems must inform "
                "exposed persons; "
                "(4) Deep fakes must be disclosed as AI-generated/manipulated. "
                "Exceptions exist for artistic/satirical/fictional content and cases "
                "where AI interaction is obvious from context."
            ),
            related_articles={
                "Art. 4(60)": "Definition of 'deep fake'",
                "Art. 6": "Classification of high-risk AI systems (Art. 50 applies beyond high-risk)",
                "Art. 52": "Previous numbering (pre-final text) of transparency obligations",
                "Art. 86": "Right to explanation of individual decision-making",
                "Annex III, 1(a)": "Biometric identification systems (intersection with Art. 50(3))",
                "GDPR Art. 13-14": "Data subject information rights (required by Art. 50(3))",
            },
            recital=(
                "Recitals 132-134: Transparency obligations are designed to ensure "
                "natural persons can make informed decisions when interacting with AI. "
                "For synthetic content, machine-readable marking is essential to enable "
                "detection and verification of AI-generated material. C2PA and similar "
                "standards are referenced as suitable technical solutions."
            ),
            automation_summary={
                "fully_automatable": [
                    "Chatbot / conversational AI pattern detection",
                    "AI disclosure text detection in code and templates",
                    "Content generation library/API detection",
                    "C2PA / IPTC / watermarking metadata detection",
                    "Emotion recognition library import detection",
                    "Biometric categorization pattern detection",
                    "Deep fake code pattern detection",
                ],
                "partially_automatable": [
                    "Verifying disclosure is shown at point of interaction (not just in docs)",
                    "Verifying content marking covers ALL generated output",
                    "Assessing whether AI interaction is 'obvious from context' (Art. 50(1) exception)",
                    "Verifying emotion/biometric notification reaches all exposed persons",
                ],
                "requires_human_judgment": [
                    "Determining if context makes AI nature 'obvious' (Art. 50(1) exception)",
                    "Assessing if content qualifies for artistic/satirical/fictional exception (Art. 50(4))",
                    "Evaluating adequacy of disclosure language",
                    "GDPR compliance assessment for biometric/emotion data processing",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.2 requires: "
                "(1) Clear AI interaction disclosure for chatbots/assistants, shown at point of contact; "
                "(2) C2PA content credentials for AI-generated media (images, audio, video); "
                "(3) Machine-readable AI-generation markers for text content; "
                "(4) GDPR-compliant notification for emotion recognition/biometric categorization; "
                "(5) Mandatory deep fake disclosure with C2PA manifest. "
                "Based on: C2PA v2.1, IPTC Photo Metadata Standard 2024.1, "
                "ISO/IEC 12792:2024, NIST AI 100-4."
            ),
            enforcement_date=applicable_from(50),
            waiting_for=standard_status(50),
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        # Texts, priorities and routes of the legal review o3 Z (2026-10-26). An action names its obligation; `where`
        # is the route o3 gave it (cl_action_plan keeps it when the dashboard profile applies).

        # ── Art. 50(1) ──
        if details.get("is_chatbot_or_interactive_ai") and not details.get("has_ai_disclosure_to_users"):
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 50(1)",
                action="Inform users that they are interacting with an AI system",
                details=(
                    "For AI systems intended to interact directly with natural persons, Art. 50(1) requires providers "
                    "to ensure people are informed that they are interacting with AI, unless this is obvious in "
                    "context or a statutory exception applies. Give a clear, distinguishable and accessible notice at "
                    "the start of the first interaction (Art. 50(5)), for example when the chat opens: \u201cYou are "
                    "chatting with an AI assistant.\u201d Do not rely solely on terms of service. Record any exception "
                    "relied on."
                ),
                effort="1-2 hours",
                obligation_id="ART50-OBL-1",
                where="project",
            ))
        elif details.get("is_chatbot_or_interactive_ai") and details.get("has_ai_disclosure_to_users"):
            actions.append(ActionItem(
                priority="MEDIUM",
                article="Art. 50(1)",
                action="Verify that the AI disclosure is shown at the first interaction",
                details=(
                    "An AI-interaction notice was identified, but its presentation has not been verified. Check each "
                    "relevant user journey to confirm that people receive a clear, distinguishable and accessible "
                    "notice at the start of their first direct interaction (Art. 50(5)). A notice found only in terms "
                    "of service is insufficient. Document any applicable exception."
                ),
                effort="30 minutes",
                action_type="human_judgment_required",
                obligation_id="ART50-OBL-1",
                where="human_gates",
            ))

        # ── Art. 50(2) — "true" means a mechanism was identified for at least one output type (o3 Y) ──
        if details.get("is_generating_synthetic_content") and details.get("has_content_watermarking") is True:
            actions.append(ActionItem(
                priority="MEDIUM",
                article="Art. 50(2)",
                action="Confirm that marking covers every in-scope synthetic output type",
                details=(
                    "A marking mechanism was identified for at least one output type; this does not establish "
                    "compliance. Check each in-scope synthetic audio, image, video and text output and delivery path "
                    "for machine-readable marking and a usable detection method. Test whether marks survive the "
                    "project's normal processing, where technically feasible. Record unmarked output types, valid "
                    "exceptions and technical limits in marking_evidence. A person confirms the assessment in Human "
                    "Gates."
                ),
                effort="2-4 hours",
                action_type="human_judgment_required",
                obligation_id="ART50-OBL-2",
                where="project",
            ))
        elif details.get("is_generating_synthetic_content"):
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 50(2)",
                action="Mark in-scope AI-generated outputs in a machine-readable format",
                details=(
                    "No marking mechanism was identified for the system's potentially in-scope synthetic outputs. "
                    "Determine which output types Article 50(2) covers; for each covered audio, image, video or text "
                    "output, implement machine-readable marking and a corresponding means of detecting AI generation "
                    "or manipulation. Possible techniques include verifiable provenance metadata (such as C2PA "
                    "Content Credentials), watermarks, or suitable combinations with detection-supporting "
                    "fingerprinting or logging. Preserve existing marks where practicable. Record unmarked output "
                    "types, applicable exceptions and technical limitations; no technique alone guarantees compliance."
                ),
                effort="4-8 hours",
                obligation_id="ART50-OBL-2",
                where="project",
            ))

        # ── Art. 50(3) ──
        art50_3_tail = (
            " of its operation, unless the statutory law-enforcement exception applies. Provide clear, distinguishable "
            "and accessible information by first exposure (Art. 50(5)). Separately check applicable data-protection "
            "law (GDPR, Regulation (EU) 2018/1725 or Directive (EU) 2016/680), including any GDPR Arts. 13\u201314 "
            "notices or Art. 35 impact assessment. Assess any Article 5 prohibition independently."
        )
        if details.get("is_emotion_recognition_system") and not details.get("has_emotion_biometric_disclosure"):
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 50(3)",
                action="Inform exposed persons of the emotion recognition system",
                details=("Art. 50(3) requires deployers to inform natural persons exposed to an emotion recognition "
                         "system" + art50_3_tail),
                effort="4-8 hours",
                obligation_id="ART50-OBL-3",
                where="project",
            ))
        if details.get("is_biometric_categorization_system") and not details.get("has_emotion_biometric_disclosure"):
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 50(3)",
                action="Inform exposed persons of the biometric categorisation system",
                details=("Art. 50(3) requires deployers to inform natural persons exposed to a biometric "
                         "categorisation system" + art50_3_tail),
                effort="4-8 hours",
                obligation_id="ART50-OBL-3",
                where="project",
            ))

        # ── Art. 50(4), first subparagraph: deep fakes ──
        if details.get("is_deep_fake_system") and not details.get("has_deep_fake_disclosure"):
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 50(4)",
                action="Disclose that deep fake image, audio or video content is AI-generated or manipulated",
                details=(
                    "Where AI-generated or manipulated image, audio or video meets the Art. 3(60) definition of a "
                    "deep fake, Art. 50(4) requires deployers to disclose its AI origin clearly, distinguishably and "
                    "accessibly by first exposure (Art. 50(5)), for example with a visible or audible label. For an "
                    "evidently artistic, creative, satirical, fictional or analogous work, disclosure may be "
                    "appropriately non-disruptive but is still required. This is separate from Art. 50(2) "
                    "machine-readable marking. In Human Gates, confirm deep-fake status and any exception, and verify "
                    "or arrange the actual disclosure."
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
                obligation_id="ART50-OBL-4",
                where="human_gates",
            ))

        # ── Art. 50(4), second subparagraph: text on matters of public interest (answer yes or unknown) ──
        if details.get("is_generating_synthetic_content") and details.get("publishes_public_interest_text") is not False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 50(4)",
                action="Decide how AI-generated text published on matters of public interest is disclosed",
                details=(
                    "Check whether AI-generated or manipulated text is published to inform the public on matters of "
                    "public interest. If so, Art. 50(4) requires deployers to disclose its AI origin clearly, "
                    "distinguishably and accessibly by first exposure, unless the text received substantive human "
                    "review or editorial control and a natural or legal person holds editorial responsibility, or a "
                    "statutory law-enforcement exception applies. Mere proofreading is insufficient. Record evidence "
                    "of the exception or the actual disclosure in Human Gates."
                ),
                effort="1-2 hours",
                action_type="human_judgment_required",
                obligation_id="ART50-OBL-4b",
                where="human_gates",
            ))

        # ── Always ──
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 50 (general)",
            action="Document Art. 50 applicability assessment",
            details=(
                "Maintain an internal transparency register recording applicable Art. 50 paragraphs, "
                "provider/deployer roles, implemented measures, supporting evidence, reasons for exceptions or "
                "non-applicability, and review dates. Check other applicable transparency duties separately (Art. "
                "50(6)). This register is recommended compliance evidence, not a separately prescribed Art. 50 "
                "document."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
            where="human_gates",
        ))

        return ActionPlan(
            article_number=50,
            article_title="Transparency Obligations for Certain AI Systems",
            project_path=scan_result.project_path,
            actions=actions,
            # o3 Z (2026-10-26): Art. 50 applies only to the system types it names, and the AI Act prescribes no
            # marking technology; the two sentences that said otherwise are gone.
            disclaimer="Based on ComplianceLint compliance checklist.",
        )


# Module entry point — used by auto-discovery
def create_module() -> Art50Module:
    return Art50Module()
