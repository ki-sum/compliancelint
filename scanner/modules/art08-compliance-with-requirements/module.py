"""
Article 8: Compliance with the requirements — Module implementation using unified protocol.

Art. 8 requires high-risk AI systems to comply with the requirements in Section 2
(Art. 9-15), taking into account their intended purpose and the state of the art.
The risk management system (Art. 9) shall be considered when ensuring compliance.

Obligation mapping:
  ART08-OBL-1   → has_section_2_compliance (overall Section 2 compliance)
  ART08-OBL-2   → has_annex_i_compliance (conditional: only for Annex I products)
                   context_skip_field: is_annex_i_product
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


class Art08Module(BaseArticleModule):
    """Article 8: Compliance with the requirements compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=8,
            article_title="Compliance with the requirements",
        )

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for Art. 8 compliance using AI-provided answers.

        Reads compliance_answers["art8"] from the AI context. Maps each field
        to obligation findings without any regex or file scanning.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for each Art. 8 obligation.
        """
        project_path = os.path.abspath(project_path)
        ctx = self._effective_ctx(project_path)
        na = self._scope_gate(ctx, project_path)
        if na:
            return na
        na = self._high_risk_only_check(ctx, project_path)
        if na:
            return na

        index = self._build_index(project_path)
        language = self._detect_language(project_path)
        file_count = index.source_file_count
        findings: list[Finding] = self._ctx_warnings(ctx)

        answers = ctx.get_article_answers("art8")

        has_section_2_compliance = answers.get("has_section_2_compliance")
        section_2_evidence = answers.get("section_2_evidence") or []
        is_annex_i_product = answers.get("is_annex_i_product")
        has_annex_i_compliance = answers.get("has_annex_i_compliance")

        # ── ART08-OBL-1: Section 2 compliance (Art. 9-15) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART08-OBL-1",
            answer=has_section_2_compliance,
            true_description=(
                "System demonstrates compliance efforts with Section 2 requirements "
                "(Art. 9-15). Verify compliance is maintained considering intended "
                "purpose and state of the art, with risk management (Art. 9) taken "
                "into account."
            ),
            false_description=(
                "No evidence of compliance with Section 2 requirements (Art. 9-15). "
                "Art. 8(1) requires high-risk AI systems to comply with these "
                "requirements, taking into account intended purpose and the generally "
                "acknowledged state of the art."
            ),
            none_description=(
                "AI could not determine overall compliance with Section 2 requirements "
                "(Art. 9-15). Run individual article scans (Art. 9-15) for detailed "
                "assessment."
            ),
            evidence=section_2_evidence or None,
            gap_type=GapType.PROCESS,
        ))

        # ── ART08-OBL-2: Annex I product compliance (conditional) ──
        # Only create a direct finding when is_annex_i_product is not False.
        # When False, the ObligationEngine gap_findings will auto-mark NOT_APPLICABLE
        # via context_skip_field.
        if is_annex_i_product is not False:
            findings.append(self._finding_from_answer(
                obligation_id="ART08-OBL-2",
                answer=has_annex_i_compliance,
                true_description=(
                    "Product compliance documentation found for applicable Union "
                    "harmonisation legislation (Annex I Section A). Verify AI Act "
                    "testing and reporting are integrated with existing sectoral "
                    "documentation per Art. 8(2)."
                ),
                false_description=(
                    "No evidence of compliance with applicable Union harmonisation "
                    "legislation. Art. 8(2) requires providers of products containing "
                    "AI systems to ensure full compliance with all applicable "
                    "requirements under Annex I legislation."
                ),
                none_description=(
                    "AI could not determine whether the product complies with applicable "
                    "Union harmonisation legislation (Annex I Section A). Manual review "
                    "of sectoral compliance documentation required."
                ),
                gap_type=GapType.PROCESS,
            ))

        details = {
            "has_section_2_compliance": has_section_2_compliance,
            "section_2_evidence": section_2_evidence,
            "is_annex_i_product": is_annex_i_product,
            "has_annex_i_compliance": has_annex_i_compliance,
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
            article_number=8,
            article_title="Compliance with the requirements",
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
            article_number=8,
            article_title="Compliance with the requirements",
            one_sentence=(
                "High-risk AI systems must comply with all Section 2 requirements "
                "(Art. 9-15), considering intended purpose and state of the art."
            ),
            official_summary=(
                "Art. 8 establishes that high-risk AI systems shall comply with "
                "the requirements in Section 2 (risk management, data governance, "
                "technical documentation, record-keeping, transparency, human oversight, "
                "accuracy/robustness). Compliance must take into account the intended "
                "purpose and the generally acknowledged state of the art. The risk "
                "management system (Art. 9) must be considered when ensuring compliance. "
                "For products subject to both the AI Act and Annex I Union harmonisation "
                "legislation, providers may integrate AI Act documentation into existing "
                "sectoral documentation."
            ),
            related_articles={
                "Art. 9": "Risk management system",
                "Art. 10": "Data and data governance",
                "Art. 11": "Technical documentation",
                "Art. 12": "Record-keeping",
                "Art. 13": "Transparency and provision of information to deployers",
                "Art. 14": "Human oversight",
                "Art. 15": "Accuracy, robustness and cybersecurity",
                "Art. 16": "Obligations of providers (assigns Art. 8 compliance to providers)",
                "Annex I Section A": "Union harmonisation legislation for product integration",
            },
            recital=(
                "Recital 43: The requirements should apply to high-risk AI systems "
                "as regards the qualities of data sets used, technical documentation "
                "and record-keeping, transparency and the provision of information to "
                "deployers, human oversight measures, and robustness, accuracy and "
                "cybersecurity."
            ),
            automation_summary={
                "fully_automatable": [
                    "Cross-reference check against Art. 9-15 scan results",
                ],
                "partially_automatable": [
                    "Detection of Annex I product compliance documentation",
                    "Detection of integrated testing/reporting procedures",
                ],
                "requires_human_judgment": [
                    "Whether compliance considers intended purpose",
                    "Whether state of the art is adequately reflected",
                    "Whether risk management is properly integrated",
                    "Annex I sectoral legislation applicability",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) evidence of "
                "compliance with all Section 2 articles (Art. 9-15), (2) risk "
                "management system integration, (3) for Annex I products: sectoral "
                "compliance documentation. Based on: EU AI Act Art. 8(1)-(2)."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_section_2_compliance") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 8(1)",
                action="Ensure compliance with Section 2 requirements (Art. 9-15)",
                details=(
                    "Art. 8(1) requires high-risk AI systems to comply with all "
                    "Section 2 requirements. Run individual scans for Art. 9 (risk "
                    "management), Art. 10 (data governance), Art. 11 (technical "
                    "documentation), Art. 12 (record-keeping), Art. 13 (transparency), "
                    "Art. 14 (human oversight), and Art. 15 (accuracy/robustness) to "
                    "identify specific gaps."
                ),
                effort="Varies by article",
            ))

        if details.get("is_annex_i_product") is True and details.get("has_annex_i_compliance") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 8(2)",
                action="Ensure compliance with applicable Annex I harmonisation legislation",
                details=(
                    "Art. 8(2) requires products containing AI systems to comply "
                    "with both the AI Act and applicable Union harmonisation legislation "
                    "(Annex I Section A). Consider integrating AI Act documentation "
                    "into existing sectoral compliance procedures."
                ),
                effort="8-40 hours",
                action_type="human_judgment_required",
            ))

        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 8(1)",
            action="Verify compliance considers intended purpose and state of the art",
            details=(
                "Art. 8(1) requires compliance to take into account the system's "
                "intended purpose and the generally acknowledged state of the art. "
                "Document how your compliance approach reflects these considerations."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=8,
            article_title="Compliance with the requirements",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 8 is a meta-requirement that aggregates compliance across "
                "Art. 9-15. Run individual article scans for detailed gap analysis. "
                "Based on ComplianceLint compliance checklist. Official CEN-CENELEC "
                "standards (expected Q4 2026) may modify requirements."
            ),
        )


def create_module() -> Art08Module:
    return Art08Module()
