"""
Article 6: Classification Rules for High-Risk AI Systems — Module implementation.

This is the FIRST tool customers need: "Is my AI system high-risk?"

Art. 6 defines two paths to high-risk:
  - Art. 6(1): Safety component of Annex I product, or is itself such a product
  - Art. 6(2): Falls under Annex III use-case categories
  - Art. 6(3): Exception — Annex III system that doesn't pose significant risk

This module reads AI-provided compliance_answers["art6"] and maps each answer
to a Finding. No regex, keyword, or AST scanning is performed — detection is
entirely the AI's responsibility.
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


class Art06Module(BaseArticleModule):
    """Article 6: Classification Rules for High-Risk AI Systems."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=6,
            article_title="Classification Rules for High-Risk AI Systems",
        )

    # ── Scanning ──

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for high-risk classification indicators using AI-provided answers.

        Reads compliance_answers["art6"] from the AI context. Maps each field
        to one or more obligation findings:
          - annex_i_product_type → ART06-CLS-1
          - annex_iii_categories → ART06-CLS-2
          - both empty/None     → ART06-SCAN (NOT_APPLICABLE)

        NON_COMPLIANT here means "potential high-risk, needs human classification"
        — it is a FLAG, not a confirmed violation.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for high-risk classification.
        """
        project_path = os.path.abspath(project_path)
        ctx = self._effective_ctx(project_path)
        na = self._scope_gate(ctx, project_path)
        if na:
            return na
        index = self._build_index(project_path)
        language = self._detect_language(project_path)
        file_count = index.source_file_count
        findings: list[Finding] = self._ctx_warnings(ctx)

        answers = ctx.get_article_answers("art6")

        annex_i_product_type = answers.get("annex_i_product_type") or None  # empty text = no product
        annex_iii_categories = answers.get("annex_iii_categories", [])   # list[str]
        is_high_risk = answers.get("is_high_risk")                       # bool | None
        reasoning = answers.get("reasoning", "")

        # ── ART06-CLS-1: Annex I product type ──
        if annex_i_product_type is not None:
            findings.append(Finding(
                obligation_id="ART06-CLS-1",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NON_COMPLIANT,
                confidence=Confidence.LOW,
                description=(
                    f"Potential Annex I product detected: {annex_i_product_type}. "
                    "Manual classification required. Under Art. 6(1) this AI system is "
                    "HIGH-RISK only where both conditions are met: (a) it is intended to be "
                    "used as a safety component of a product, or is itself a product, covered "
                    "by the Union harmonisation legislation listed in Annex I, and (b) that "
                    "product is required to undergo a third-party conformity assessment under "
                    "that legislation."
                ),
                remediation=(
                    "Determine whether both Art. 6(1) conditions are met, taking the definition "
                    "of safety component in Art. 3(14) and Art. 6(1a)-(1c) into account. An AI "
                    "system solely used for the non-safety related aspects listed in Art. 6(1a) "
                    "is not a safety component, subject to Art. 6(1b), and a third-party "
                    "conformity assessment required solely because of risks other than risks to "
                    "health and safety does not meet point (b) (Art. 6(1c)). If the system is "
                    "high-risk and is related to a product covered by Section A of Annex I, the "
                    "requirements of Chapter III, Section 2 apply, subject to Art. 2(13). If it "
                    "is related to a product covered by Section B of Annex I, apply the "
                    "limitation in Art. 2(2); Arts. 8-15 do not apply by virtue of this "
                    "Regulation."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            findings.append(Finding(
                obligation_id="ART06-CLS-1",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "AI found no Annex I product indicators, but manual review recommended. "
                    "Confirm the system is not a safety component of any product listed in Annex I."
                ),
                gap_type=GapType.PROCESS,
            ))

        # ── ART06-CLS-2: Annex III categories ──
        if annex_iii_categories:
            categories_str = ", ".join(annex_iii_categories)
            findings.append(Finding(
                obligation_id="ART06-CLS-2",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NON_COMPLIANT,
                confidence=Confidence.LOW,
                description=(
                    f"Annex III categories detected: {categories_str}. "
                    f"{reasoning} "
                    "This may classify the system as HIGH-RISK under Art. 6(2). "
                    "Manual classification required."
                ),
                remediation=(
                    f"Review whether this system actually falls under Annex III ({categories_str}). "
                    "Check whether the Art. 6(3) exception applies (an Annex III system that "
                    "performs profiling of natural persons is always high-risk). If no exception "
                    "applies, the system is HIGH-RISK and must comply with the requirements of "
                    "Chapter III, Section 2 (Arts. 8-15)."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            findings.append(Finding(
                obligation_id="ART06-CLS-2",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "No Annex III patterns detected. Manual classification required. "
                    "AI scanning may miss high-risk use cases not evident in code structure."
                ),
                gap_type=GapType.PROCESS,
            ))

        # ── ART06-SCAN: Overall — no indicators at all ──
        if not annex_iii_categories and annex_i_product_type is None:
            findings.append(Finding(
                obligation_id="ART06-SCAN",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.LOW,
                description=(
                    "No high-risk indicators detected by AI analysis. "
                    "Manual classification still required — AI scanning cannot detect all "
                    "high-risk use cases. Review intended purpose against all Annex III categories."
                ),
                remediation=(
                    "Complete a manual Art. 6 classification using the decision tree in the "
                    "compliance checklist. Document the classification reasoning regardless of outcome."
                ),
                gap_type=GapType.PROCESS,
            ))

        # ── ART06-OBL-4: Provider documentation obligation ──
        # Art. 6(4): Provider who considers Annex III system is NOT high-risk
        # must document the assessment before placing on market.
        # Uses _finding_from_answer() like all other modules.
        has_risk_classification_doc = answers.get("has_risk_classification_doc")
        findings.append(self._finding_from_answer(
            obligation_id="ART06-OBL-4",
            answer=has_risk_classification_doc,
            true_description="Risk classification assessment documentation found.",
            false_description=(
                "No risk classification assessment documentation found. "
                "Art. 6(4) requires providers to document their assessment "
                "before placing the system on the market."
            ),
        ))

        # Determine classification result string for details
        if annex_i_product_type and annex_iii_categories:
            classification_result = "LIKELY_HIGH_RISK (AI detected both Annex I and Annex III indicators)"
        elif annex_i_product_type:
            classification_result = f"POTENTIALLY_HIGH_RISK (Annex I product indicator: {annex_i_product_type})"
        elif annex_iii_categories:
            classification_result = f"POTENTIALLY_HIGH_RISK (Annex III categories: {', '.join(annex_iii_categories)})"
        else:
            classification_result = "NO_INDICATORS_FOUND (likely not high-risk, but manual review recommended)"

        details = {
            "annex_iii_categories": annex_iii_categories,
            "annex_i_product_type": annex_i_product_type,
            "is_high_risk": is_high_risk,
            "reasoning": reasoning,
            "classification_result": classification_result,
            "note": (
                "Art. 6 classification is heuristic — AI detected these signals from project "
                "structure and dependencies. The final classification is always a human judgment "
                "based on the system's intended purpose, not its technical implementation."
            ),
        }

        # ── Obligation Engine: enrich findings + identify gaps ──
        # Acceptance round 2 (2026-10-09): Art. 6(4) applies to "a provider who considers that an AI system
        # referred to in Annex III is not high-risk". ART06-CLS-1 has no such gate: is_annex_i_product answers the
        # Section A question only, which rules out neither a Section B product nor the safety-component side of
        # Art. 6(1)(a) (o3 Prompt G item C2).
        flat = self._answers_flat(ctx)
        if flat.get("claims_art6_3_exception") is False:
            findings = self._set_not_applicable(
                findings, ("ART06-OBL-4",),
                "Not applicable: Article 6(4) applies to a provider who considers that an AI system referred to in "
                "Annex III is not high-risk; the answers state that the Article 6(3) derogation is not relied on.",
            )

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
            article_number=6,
            article_title="Classification Rules for High-Risk AI Systems",
            project_path=project_path,
            scan_date=datetime.now(timezone.utc).isoformat(),
            files_scanned=file_count,
            language_detected=language,
            overall_level=self._compute_overall_level(findings),
            overall_confidence=Confidence.LOW,
            findings=findings,
            details=details,
        )

    # ── Explain ──

    def explain(self) -> Explanation:
        return Explanation(
            article_number=6,
            article_title="Classification Rules for High-Risk AI Systems",
            one_sentence=(
                "Article 6 defines when an AI system is classified as 'high-risk' — "
                "either as a safety component of regulated products (Annex I) or by "
                "falling under specific use-case categories (Annex III)."
            ),
            official_summary=(
                "Art. 6 establishes the rules for classifying AI systems as high-risk. There "
                "are two paths: (1) Art. 6(1) — the system is itself or is a safety component "
                "of a product covered by Union harmonisation legislation listed in Annex I and "
                "that product is required to undergo a third-party conformity assessment; the "
                "meaning of safety component is set by Art. 3(14), as qualified by Art. "
                "6(1a)-(1b), and Art. 6(1c) excludes third-party assessment required solely "
                "because of risks other than health and safety; (2) Art. 6(2) — the system "
                "falls under a use case listed in Annex III. Under Art. 6(3), an Annex III "
                "system is not high-risk where it does not pose a significant risk of harm to "
                "health, safety or fundamental rights and one of points (a)-(d) applies; "
                "notwithstanding that exception, an Annex III system that performs profiling of "
                "natural persons is always high-risk."
            ),
            related_articles={
                "Annex I": "List of EU harmonisation legislation (product safety)",
                "Annex III": "List of high-risk AI use-case categories",
                "Art. 7": "Amendments to Annex III (Commission can update the list)",
                "Art. 8-15": "Requirements for high-risk AI systems (Chapter III, Section 2)",
                "Art. 43": "Conformity assessment procedures",
                "Art. 52": "Transparency obligations for certain AI systems",
            },
            recital=(
                "Recitals 46-56: The classification as high-risk should be based on the "
                "intended purpose of the AI system and the severity of potential harm. "
                "The list in Annex III should be limited to AI systems that pose significant "
                "risk. The exception in Art. 6(3) prevents over-regulation of systems that "
                "perform only supportive or preparatory roles."
            ),
            automation_summary={
                "fully_automatable": [
                    "Detection of known high-risk libraries (face_recognition, deepface, etc.)",
                    "Detection of domain keywords in source code",
                    "Detection of Annex I product references in documentation",
                ],
                "partially_automatable": [
                    "Annex III category matching (keywords may have multiple meanings)",
                    "Art. 6(3) exception assessment (some criteria can be inferred)",
                ],
                "requires_human_judgment": [
                    "Final high-risk classification decision",
                    "Art. 6(3) exception determination and documentation",
                    "Annex I safety component assessment",
                    "Intended purpose analysis (same code can serve regulated or unregulated purposes)",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.2 provides: (1) a three-step classification "
                "decision tree (Annex I check -> Annex III check -> Art. 6(3) exception), "
                "(2) keyword and library detection patterns for all 8 Annex III categories, "
                "(3) Annex I product category indicators, (4) Art. 6(3) exception criteria "
                "checklist. Note: automated scanning can only flag potential matches — "
                "the final classification always requires human judgment on intended purpose."
            ),
            enforcement_date=applicable_from(6),
            waiting_for=standard_status(6),
        )

    # ── Action Plan ──

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details
        classification = details.get("classification_result", "")

        # Always: document classification
        actions.append(ActionItem(
            priority="CRITICAL",
            article="Art. 6",
            action="Complete formal Art. 6 risk classification",
            details=(
                "Walk through the Art. 6 classification decision tree: "
                "(1) Is this a safety component of a product, or itself a product, covered by "
                "Annex I legislation, AND is that product required to undergo a third-party "
                "conformity assessment (taking Art. 6(1a)-(1c) into account)? "
                "(2) Does it fall under an Annex III category? "
                "(3) Does the Art. 6(3) exception apply? "
                "Document the reasoning and conclusion."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        # If Annex I indicators found
        if details.get("annex_i_product_type"):
            product_type = details["annex_i_product_type"]
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 6(1)",
                action="Verify Annex I product classification",
                details=(
                    f"Potential Annex I product indicator detected: {product_type}. "
                    "Determine whether this AI system is a safety component of (or is itself) a product "
                    "covered by this legislation AND whether that product is required to undergo a "
                    "third-party conformity assessment under it; Art. 6(1) requires both. Apply "
                    "Art. 6(1a)-(1c): systems solely used for non-safety related aspects are not "
                    "safety components unless their failure or malfunctioning would endanger health "
                    "and safety, and an assessment required solely for risks other than health and "
                    "safety does not count."
                ),
                effort="4-8 hours (may require legal counsel)",
                action_type="human_judgment_required",
            ))

        # If Annex III categories found
        annex_iii_categories = details.get("annex_iii_categories", [])
        if annex_iii_categories:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 6(2)",
                action=f"Evaluate Annex III classification for: {', '.join(annex_iii_categories)}",
                details=(
                    f"The AI detected patterns matching these Annex III categories: "
                    f"{', '.join(annex_iii_categories)}. Verify whether the system's intended "
                    f"purpose actually falls under these categories. If the signals were "
                    f"false positives, document why."
                ),
                effort="2-4 hours",
                action_type="human_judgment_required",
            ))

            # Art. 6(3) exception evaluation
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 6(3)",
                action="Evaluate Art. 6(3) exception applicability",
                details=(
                    "If the system IS under Annex III, check whether it qualifies for the "
                    "Art. 6(3) exception. The system must NOT pose significant risk AND must "
                    "meet at least one criterion: (a) narrow procedural task, (b) improves "
                    "prior human activity, (c) detects patterns without replacing judgment, "
                    "(d) performs preparatory task. If claiming the exception, you MUST document "
                    "the reasoning and notify the relevant national authority before market placement."
                ),
                effort="2-4 hours (may require legal counsel)",
                action_type="human_judgment_required",
            ))

        # If classified as potentially high-risk
        if "HIGH_RISK" in classification:
            actions.append(ActionItem(
                priority="HIGH",
                article="Arts. 8-15",
                action="Plan Chapter III, Section 2 compliance if confirmed high-risk",
                details=(
                    "For a high-risk AI system to which the Section B rule in Art. 2(2) does "
                    "not apply, the requirements of Chapter III, Section 2 are Arts. 8 "
                    "(compliance), 9 (risk management), 10 (data governance), 11 (technical "
                    "documentation), 12 (record-keeping), 13 (transparency), 14 (human "
                    "oversight) and 15 (accuracy, robustness and cybersecurity). For a "
                    "high-risk AI system under Art. 6(1) related to a product covered by "
                    "Section A of Annex I, specific requirements in Arts. 9-15 may be limited "
                    "only where and to the extent permitted by Art. 2(13). For an AI system "
                    "classified as high-risk under Art. 6(1) and related to a product covered "
                    "by Section B of Annex I, Art. 2(2) provides that only Art. 6(1), Art. 60a "
                    "and Arts. 102-112 apply directly; Arts. 57-59 apply only insofar as the AI "
                    "Act high-risk requirements have been integrated into the relevant Union "
                    "harmonisation legislation. For systems to which Chapter III, Section 2 "
                    "applies, start with risk management (Art. 9) and record-keeping (Art. 12)."
                ),
                effort="Significant — plan for 3-6 months of compliance work",
                action_type="human_judgment_required",
            ))

            actions.append(ActionItem(
                priority="MEDIUM",
                article="Art. 43",
                action="Identify applicable conformity assessment procedure",
                details=(
                    "High-risk systems require conformity assessment before market placement. "
                    "Art. 6(1) systems follow the assessment procedure of the relevant Annex I "
                    "legislation. Art. 6(2) systems follow Art. 43 procedures (self-assessment "
                    "or third-party, depending on the category)."
                ),
                effort="2-4 hours research + legal counsel recommended",
                action_type="human_judgment_required",
            ))

        # If no indicators found
        if not annex_iii_categories and not details.get("annex_i_product_type"):
            actions.append(ActionItem(
                priority="MEDIUM",
                article="Art. 6",
                action="Confirm non-high-risk classification with manual review",
                details=(
                    "No high-risk indicators were detected by AI analysis, but this "
                    "does not guarantee the system is not high-risk. Review the intended purpose "
                    "against all Annex III categories manually. Consider whether the system could "
                    "be used in a high-risk context even if not designed for one."
                ),
                effort="1-2 hours",
                action_type="human_judgment_required",
            ))

        # Always: documentation
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 6(3)",
            action="Create and maintain classification documentation",
            details=(
                "Regardless of outcome, document the Art. 6 classification analysis. "
                "Include: intended purpose description, Annex I/III assessment, Art. 6(3) "
                "exception analysis (if applicable), conclusion, date, and reviewer. "
                "This documentation may be required by national supervisory authorities."
            ),
            effort="1-2 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=6,
            article_title="Classification Rules for High-Risk AI Systems",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Automated scanning can only detect potential indicators — it cannot make "
                "the final classification decision. The intended purpose of the AI system, "
                "not its technical implementation, determines the classification. Legal "
                "counsel familiar with the EU AI Act is recommended for final classification. "
                "Based on ComplianceLint compliance checklist; the Commission guidelines under "
                "Art. 6(5) specify the practical implementation of these criteria."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art06Module:
    return Art06Module()
