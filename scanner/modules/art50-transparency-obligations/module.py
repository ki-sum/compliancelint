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
        has_deep_fake_disclosure = answers.get("has_deep_fake_disclosure")
        deep_fake_evidence = answers.get("deep_fake_evidence", [])

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
                        "with an AI system prior to their first interaction."
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
                true_description="Synthetic content marking/watermarking found.",
                false_description=(
                    "System generates synthetic content but no content marking "
                    "was found. Art. 50(2) requires marking output as artificially "
                    "generated in machine-readable format (C2PA recommended)."
                ),
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
                    "Art. 50(4) does not apply."
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
            "has_content_watermarking": has_content_watermarking,
            "is_emotion_recognition_system": is_emotion_system,
            "is_biometric_categorization_system": is_biometric_system,
            "has_emotion_biometric_disclosure": has_emotion_biometric_disclosure,
            "is_deep_fake_system": is_deep_fake_system,
            "has_deep_fake_disclosure": has_deep_fake_disclosure,
        }

        # ── Obligation Engine: enrich findings + identify gaps ──
        obligations = self._load_obligations()
        if obligations:
            engine = ObligationEngine(obligations)
            findings = [engine.enrich_finding(f) for f in findings]
            gap_findings = engine.gap_findings(findings, ctx.compliance_answers if ctx else None)
            findings.extend(gap_findings)
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
                "ComplianceLint Compliance Checklist v0.1 requires: "
                "(1) Clear AI interaction disclosure for chatbots/assistants, shown at point of contact; "
                "(2) C2PA content credentials for AI-generated media (images, audio, video); "
                "(3) Machine-readable AI-generation markers for text content; "
                "(4) GDPR-compliant notification for emotion recognition/biometric categorization; "
                "(5) Mandatory deep fake disclosure with C2PA manifest. "
                "Based on: C2PA v2.1, IPTC Photo Metadata Standard 2024.1, "
                "ISO/IEC 12792:2024, NIST AI 100-4."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for Art. 50 (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        # ── Art. 50(1) actions — uses scan() detail keys directly ──
        if details.get("is_chatbot_or_interactive_ai") and not details.get("has_ai_disclosure_to_users"):
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 50(1)",
                action="Add AI interaction disclosure to chatbot/conversational interface",
                details=(
                    "Art. 50(1) requires informing users they are interacting with AI. "
                    "Add a clear, persistent disclosure at the start of every conversation. "
                    "Example: 'You are interacting with an AI assistant.' Must be shown "
                    "'prior to their first interaction' per Art. 50(1)."
                ),
                effort="1-2 hours",
            ))
        elif details.get("is_chatbot_or_interactive_ai") and details.get("has_ai_disclosure_to_users"):
            actions.append(ActionItem(
                priority="MEDIUM",
                article="Art. 50(1)",
                action="Verify AI disclosure is shown at point of interaction",
                details=(
                    "AI disclosure detected — verify it is displayed to ALL users at "
                    "the START of interaction, not buried in terms of service."
                ),
                effort="30 minutes",
                action_type="human_judgment_required",
            ))

        # ── Art. 50(2) actions ──
        if details.get("is_generating_synthetic_content") and not details.get("has_content_watermarking"):
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 50(2)",
                action="Implement machine-readable marking for AI-generated content",
                details=(
                    "System generates synthetic content but no content marking found. "
                    "Art. 50(2) requires marking output as artificially generated in "
                    "machine-readable format. Recommended: C2PA SDK for media, "
                    "X-AI-Generated header for text, IPTC DigitalSourceType metadata."
                ),
                effort="4-8 hours",
            ))

        # ── Art. 50(3) actions ──
        if details.get("is_emotion_recognition_system") and not details.get("has_emotion_biometric_disclosure"):
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 50(3)",
                action="Implement emotion recognition disclosure and GDPR notice",
                details=(
                    "Emotion recognition detected. Art. 50(3) requires:\n"
                    "1. Inform all exposed persons\n"
                    "2. Explain what personal data is processed\n"
                    "3. Provide GDPR Art. 13/14 compliant privacy notice\n"
                    "4. Consider DPIA under GDPR Art. 35"
                ),
                effort="4-8 hours",
            ))
        if details.get("is_biometric_categorization_system") and not details.get("has_emotion_biometric_disclosure"):
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 50(3)",
                action="Implement biometric categorization disclosure and GDPR notice",
                details=(
                    "Biometric categorization detected. Art. 50(3) requires:\n"
                    "1. Inform all exposed persons\n"
                    "2. Explain what categories are inferred (age, gender, etc.)\n"
                    "3. Provide GDPR Art. 13/14 compliant privacy notice"
                ),
                effort="4-8 hours",
            ))

        # ── Art. 50(4) actions ──
        if details.get("is_deep_fake_system") and not details.get("has_deep_fake_disclosure"):
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 50(4)",
                action="Implement deep fake disclosure mechanism",
                details=(
                    "Deep fake code detected. Art. 50(4) requires:\n"
                    "1. Disclose that content is AI-generated/manipulated\n"
                    "2. Implement C2PA manifest\n"
                    "3. Exception for artistic/satirical content — but still indicate AI origin"
                ),
                effort="4-8 hours",
            ))

        # ── Always-applicable actions ──
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 50 (general)",
            action="Document Art. 50 applicability assessment",
            details=(
                "Create a transparency obligations register documenting:\n"
                "- Which Art. 50 paragraphs apply to your system\n"
                "- What transparency measures are implemented\n"
                "- Justification for any 'not applicable' determinations\n"
                "- Schedule for reviewing transparency measures\n\n"
                "This documentation supports demonstrating compliance to regulators."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="LOW",
            article="Art. 50(2)",
            action="Evaluate C2PA integration for future-proofing",
            details=(
                "Even if not currently generating synthetic content, consider integrating "
                "C2PA content credentials proactively. The standard is gaining EU regulatory "
                "endorsement and will likely become the de facto compliance mechanism.\n\n"
                "C2PA resources:\n"
                "- Specification: https://c2pa.org/specifications/\n"
                "- Python SDK: https://github.com/contentauth/c2pa-python\n"
                "- Rust SDK: https://github.com/contentauth/c2pa-rs"
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=50,
            article_title="Transparency Obligations for Certain AI Systems",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Based on ComplianceLint compliance checklist. Art. 50 applies broadly to almost all "
                "AI systems. Official CEN-CENELEC standards (expected Q4 2026) may modify "
                "these requirements. C2PA is recommended but not yet mandated by harmonized standard."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art50Module:
    return Art50Module()
