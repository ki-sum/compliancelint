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

        annex_i_product_type = answers.get("annex_i_product_type")       # None | str
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
                    "Manual classification required. If this AI system is a safety "
                    "component of (or is itself) a product covered by EU harmonisation "
                    "legislation, it is HIGH-RISK under Art. 6(1)."
                ),
                remediation=(
                    "Determine whether this AI system is a safety component of a product "
                    "under Annex I legislation. If yes, it must comply with Chapter 2 "
                    "requirements (Arts. 8-15) and undergo third-party conformity assessment."
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
                    "Check whether the Art. 6(3) exception applies. If no exception, the system "
                    "is HIGH-RISK and must comply with Chapter 2 (Arts. 8-15)."
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
                "Art. 6 establishes the rules for classifying AI systems as high-risk. "
                "There are two paths: (1) Art. 6(1) — the system is itself or is a safety "
                "component of a product covered by EU harmonisation legislation listed in "
                "Annex I (medical devices, machinery, toys, etc.), requiring third-party "
                "conformity assessment; (2) Art. 6(2) — the system falls under one of eight "
                "use-case categories in Annex III (biometrics, critical infrastructure, "
                "education, employment, essential services, law enforcement, migration, "
                "administration of justice). Art. 6(3) provides an exception: an Annex III "
                "system is NOT high-risk if it does not pose significant risk and only "
                "performs narrow procedural tasks, improves prior human work, detects "
                "patterns without replacing judgment, or performs preparatory tasks."
            ),
            related_articles={
                "Annex I": "List of EU harmonisation legislation (product safety)",
                "Annex III": "List of high-risk AI use-case categories",
                "Art. 7": "Amendments to Annex III (Commission can update the list)",
                "Art. 8-15": "Requirements for high-risk AI systems (Chapter 2)",
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
                "ComplianceLint Compliance Checklist v0.1 provides: (1) a three-step classification "
                "decision tree (Annex I check -> Annex III check -> Art. 6(3) exception), "
                "(2) keyword and library detection patterns for all 8 Annex III categories, "
                "(3) Annex I product category indicators, (4) Art. 6(3) exception criteria "
                "checklist. Note: automated scanning can only flag potential matches — "
                "the final classification always requires human judgment on intended purpose."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for Art. 6 classification (expected Q4 2026)",
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
                "(1) Is this a safety component or product under Annex I? "
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
                    "Determine if this AI system is a safety component of (or is itself) a product "
                    "covered by this legislation. If yes, third-party conformity assessment is required."
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
                action="Plan Chapter 2 compliance if confirmed high-risk",
                details=(
                    "If the system is confirmed high-risk, it must comply with all Chapter 2 "
                    "requirements: Art. 8 (compliance), Art. 9 (risk management), Art. 10 "
                    "(data governance), Art. 11 (technical documentation), Art. 12 (record-keeping), "
                    "Art. 13 (transparency), Art. 14 (human oversight), Art. 15 (accuracy/robustness). "
                    "Start with risk management (Art. 9) and record-keeping (Art. 12)."
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
                "Based on ComplianceLint compliance checklist; official CEN-CENELEC standards (expected Q4 2026) "
                "may modify these criteria."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art06Module:
    return Art06Module()
