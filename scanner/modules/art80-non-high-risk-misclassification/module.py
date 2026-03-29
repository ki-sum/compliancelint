"""
Article 80: Procedure for dealing with AI systems classified by the provider
as non-high-risk in application of Annex III — Module implementation.

Art. 80 addresses the procedure when a market surveillance authority evaluates
an AI system that the provider classified as non-high-risk under Annex III and
determines the classification was wrong. It requires providers to bring the
system into compliance, take corrective action across all affected systems,
and face fines for deliberate misclassification.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art80"). No regex or keyword scanning is performed.

Obligation mapping:
  ART80-OBL-4   → has_compliance_remediation_plan (bring system into compliance)
  ART80-OBL-5   → has_corrective_action_for_all_systems (corrective action scope)
  ART80-OBL-7   → has_classification_rationale (documented classification rationale)
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.protocol import (
    BaseArticleModule, ScanResult, Explanation, ActionPlan, ActionItem,
    Finding, ComplianceLevel, Confidence, GapType,
)
from core.obligation_engine import ObligationEngine


class Art80Module(BaseArticleModule):
    """Article 80: Non-high-risk misclassification procedure compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=80,
            article_title="Procedure for dealing with AI systems classified by the provider as non-high-risk in application of Annex III",
        )

    def scan(self, project_path: str) -> ScanResult:
        project_path = os.path.abspath(project_path)
        ctx = self._effective_ctx(project_path)
        na = self._scope_gate(ctx, project_path)
        if na:
            return na

        index = self._build_index(project_path)
        language = self._detect_language(project_path)
        file_count = index.source_file_count
        findings: list[Finding] = self._ctx_warnings(ctx)

        answers = ctx.get_article_answers("art80")

        has_compliance_remediation_plan = answers.get("has_compliance_remediation_plan")
        has_corrective_action_for_all_systems = answers.get("has_corrective_action_for_all_systems")
        has_classification_rationale = answers.get("has_classification_rationale")

        # ── ART80-OBL-4: Bring system into compliance ──
        findings.append(self._finding_from_answer(
            obligation_id="ART80-OBL-4",
            answer=has_compliance_remediation_plan,
            true_description=(
                "Compliance remediation plan detected. "
                "Verify it covers bringing the AI system into full compliance with "
                "Chapter III, Section 2 requirements within the period set by the "
                "market surveillance authority per Art. 80(4)."
            ),
            false_description=(
                "No compliance remediation plan detected. "
                "Art. 80(4) requires the provider to ensure all necessary action is "
                "taken to bring the AI system into compliance with the requirements "
                "and obligations of this Regulation. Failure to comply within the "
                "prescribed period results in fines per Art. 99."
            ),
            none_description=(
                "AI could not determine whether a compliance remediation plan exists. "
                "Art. 80(4) requires providers to bring wrongly classified systems "
                "into compliance within the prescribed period."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART80-OBL-5: Corrective action for all affected systems ──
        findings.append(self._finding_from_answer(
            obligation_id="ART80-OBL-5",
            answer=has_corrective_action_for_all_systems,
            true_description=(
                "Corrective action scope documentation detected. "
                "Verify it covers ALL AI systems concerned that have been made "
                "available on the Union market, not just the investigated system, "
                "per Art. 80(5)."
            ),
            false_description=(
                "No corrective action scope documentation detected. "
                "Art. 80(5) requires the provider to ensure that appropriate "
                "corrective action is taken in respect of ALL AI systems concerned "
                "that it has made available on the Union market."
            ),
            none_description=(
                "AI could not determine whether corrective action scope documentation exists. "
                "Art. 80(5) requires corrective action across all affected systems on "
                "the Union market."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART80-OBL-7: Classification rationale (anti-circumvention) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART80-OBL-7",
            answer=has_classification_rationale,
            true_description=(
                "Risk classification rationale documentation detected. "
                "Verify it demonstrates the classification decision was made in "
                "good faith based on Art. 6(3) criteria, not to circumvent "
                "Chapter III, Section 2 requirements per Art. 80(7)."
            ),
            false_description=(
                "No risk classification rationale documentation detected. "
                "Art. 80(7) provides that if the market surveillance authority "
                "establishes the system was misclassified to circumvent Chapter III, "
                "Section 2 requirements, the provider is subject to fines per Art. 99. "
                "Document your classification methodology to demonstrate good faith."
            ),
            none_description=(
                "AI could not determine whether a risk classification rationale exists. "
                "Art. 80(7) imposes fines for deliberate misclassification to circumvent "
                "requirements. Document classification methodology to demonstrate good faith."
            ),
            gap_type=GapType.PROCESS,
        ))

        # Build details dict
        details = {
            "has_compliance_remediation_plan": has_compliance_remediation_plan,
            "has_corrective_action_for_all_systems": has_corrective_action_for_all_systems,
            "has_classification_rationale": has_classification_rationale,
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
            article_number=80,
            article_title="Procedure for dealing with AI systems classified by the provider as non-high-risk in application of Annex III",
            project_path=project_path,
            scan_date=datetime.now(timezone.utc).isoformat(),
            files_scanned=file_count,
            language_detected=language,
            overall_level=self._compute_overall_level(findings),
            overall_confidence=Confidence.LOW,
            findings=findings,
            details=details,
        )

    def explain(self) -> Explanation:
        return Explanation(
            article_number=80,
            article_title="Procedure for dealing with AI systems classified by the provider as non-high-risk in application of Annex III",
            one_sentence=(
                "When a market surveillance authority finds an AI system was wrongly "
                "classified as non-high-risk, the provider must bring it into compliance "
                "and take corrective action across all affected systems."
            ),
            official_summary=(
                "Art. 80 establishes the procedure when a market surveillance authority "
                "evaluates an AI system classified by the provider as non-high-risk under "
                "Annex III and determines the classification was incorrect. The provider must: "
                "(1) bring the system into compliance with Chapter III, Section 2 requirements "
                "within the prescribed period (Art. 80(4)); (2) ensure corrective action is "
                "taken for ALL affected systems on the Union market (Art. 80(5)); (3) face "
                "fines per Art. 99 if the misclassification was deliberate to circumvent "
                "requirements (Art. 80(7))."
            ),
            related_articles={
                "Art. 6": "High-risk classification rules (Annex III categories)",
                "Art. 6(3)": "Provider's obligation to document classification decision",
                "Art. 79": "Non-compliant AI systems (triggers market surveillance action)",
                "Art. 99": "Fines for non-compliance and deliberate misclassification",
            },
            recital="",
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Compliance remediation plan detection",
                    "Corrective action scope documentation detection",
                    "Classification rationale documentation detection",
                ],
                "requires_human_judgment": [
                    "Whether the AI system is actually high-risk under Annex III",
                    "Whether classification was made in good faith or to circumvent",
                    "Whether remediation plan covers all Chapter III, Section 2 requirements",
                    "Whether corrective action scope covers all affected systems",
                    "Market surveillance authority communication and timeline compliance",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) documented compliance "
                "remediation plan for bringing system into conformity with Chapter III, Section 2; "
                "(2) corrective action scope documentation covering all affected systems on the "
                "Union market; (3) documented risk classification rationale demonstrating good "
                "faith classification decision under Art. 6(3)."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_compliance_remediation_plan") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 80(4)",
                action="Create a compliance remediation plan for wrongly classified systems",
                details=(
                    "Art. 80(4) requires all necessary action to bring the system into "
                    "compliance. Create documentation covering:\n"
                    "  - Gap analysis against Chapter III, Section 2 requirements (Art. 8-15)\n"
                    "  - Remediation timeline aligned with market surveillance authority period\n"
                    "  - Resource allocation for compliance activities\n"
                    "  - Milestone tracking for each requirement area\n\n"
                    "Consider using docs/compliance-remediation-plan.md as the primary document."
                ),
                effort="16-40 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_corrective_action_for_all_systems") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 80(5)",
                action="Document corrective action scope for all affected systems",
                details=(
                    "Art. 80(5) requires corrective action for ALL AI systems concerned "
                    "on the Union market, not just the investigated system. Create:\n"
                    "  - Inventory of all AI systems using the same classification logic\n"
                    "  - Assessment of which systems are similarly affected\n"
                    "  - Corrective action plan for each affected system\n"
                    "  - Deployment records and market presence documentation"
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_classification_rationale") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 80(7)",
                action="Document risk classification rationale to demonstrate good faith",
                details=(
                    "Art. 80(7) imposes fines for deliberate misclassification to circumvent "
                    "requirements. Document your classification methodology:\n"
                    "  - Art. 6(3) criteria assessment and decision process\n"
                    "  - Analysis of Annex III categories considered\n"
                    "  - Reasoning for non-high-risk classification\n"
                    "  - Date and responsible persons for the classification decision\n\n"
                    "This documentation serves as evidence of good faith classification."
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 80(1)-(7)",
            action="Review classification methodology against Annex III categories",
            details=(
                "Verify your risk classification process correctly evaluates all Annex III "
                "categories. Consider engaging legal counsel to review classification decisions "
                "for systems that may fall near the high-risk boundary."
            ),
            effort="4-8 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=80,
            article_title="Procedure for dealing with AI systems classified by the provider as non-high-risk in application of Annex III",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 80 applies when market surveillance authorities evaluate systems "
                "classified as non-high-risk. Proactive classification documentation helps "
                "demonstrate good faith. Based on ComplianceLint compliance checklist. "
                "Official CEN-CENELEC standards (expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art80Module:
    return Art80Module()
