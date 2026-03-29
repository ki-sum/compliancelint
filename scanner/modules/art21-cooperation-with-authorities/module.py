"""
Article 21: Cooperation with competent authorities — Module implementation.

Art. 21 requires providers of high-risk AI systems to cooperate with competent
authorities by providing conformity documentation upon request (Art. 21(1))
and giving access to automatically generated logs (Art. 21(2)).

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art21"). No regex or keyword scanning is performed.

Obligation mapping:
  ART21-OBL-1   → has_conformity_documentation (documentation available for authority)
  ART21-OBL-2   → has_log_export_capability (log access for authority)
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


class Art21Module(BaseArticleModule):
    """Article 21: Cooperation with competent authorities compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=21,
            article_title="Cooperation with competent authorities",
        )

    def scan(self, project_path: str) -> ScanResult:
        project_path = os.path.abspath(project_path)
        ctx = self._effective_ctx(project_path)
        na = self._scope_gate(ctx, project_path)
        if na:
            return na
        # Art. 21 applies only to high-risk AI systems.
        risk = (ctx.risk_classification or "").lower().strip()
        conf = (ctx.risk_classification_confidence or "").lower().strip()
        if risk in self._NOT_HIGH_RISK_VALUES and conf in ("high", "medium"):
            return self._not_applicable_result(
                project_path,
                ctx.primary_language or "unknown",
                "ART21",
                legal_basis="Art. 6",
                reason=(
                    "Art. 21 obligations apply only to providers of high-risk AI systems "
                    "(as classified under Art. 6). This system has been classified as "
                    f"'{ctx.risk_classification}' with {conf} confidence."
                ),
            )

        index = self._build_index(project_path)
        language = self._detect_language(project_path)
        file_count = index.source_file_count
        findings: list[Finding] = self._ctx_warnings(ctx)

        answers = ctx.get_article_answers("art21")

        has_conformity_documentation = answers.get("has_conformity_documentation")
        has_log_export_capability = answers.get("has_log_export_capability")

        # ── ART21-OBL-1: Conformity documentation for authority ──
        findings.append(self._finding_from_answer(
            obligation_id="ART21-OBL-1",
            answer=has_conformity_documentation,
            true_description=(
                "Conformity documentation detected. "
                "Verify it contains all information necessary to demonstrate conformity "
                "with Section 2 requirements and can be provided in an official EU language "
                "upon authority request per Art. 21(1)."
            ),
            false_description=(
                "No conformity documentation detected. "
                "Art. 21(1) requires providers to provide all information and documentation "
                "necessary to demonstrate conformity with Section 2 requirements upon a "
                "reasoned request by a competent authority, in an official EU language."
            ),
            none_description=(
                "AI could not determine whether conformity documentation is available. "
                "Art. 21(1) requires documentation demonstrating conformity with Section 2 "
                "requirements, available upon authority request."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART21-OBL-2: Log access for authority ──
        findings.append(self._finding_from_answer(
            obligation_id="ART21-OBL-2",
            answer=has_log_export_capability,
            true_description=(
                "Log export capability detected. "
                "Verify that automatically generated logs per Art. 12(1) can be provided "
                "to competent authorities upon request per Art. 21(2)."
            ),
            false_description=(
                "No log export capability detected. "
                "Art. 21(2) requires providers to give competent authorities access to "
                "automatically generated logs referred to in Art. 12(1), to the extent "
                "such logs are under their control."
            ),
            none_description=(
                "AI could not determine whether log export capability exists. "
                "Art. 21(2) requires providing authority access to Art. 12(1) logs."
            ),
            gap_type=GapType.CODE,
        ))

        # Build details dict
        details = {
            "has_conformity_documentation": has_conformity_documentation,
            "has_log_export_capability": has_log_export_capability,
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
            article_number=21,
            article_title="Cooperation with competent authorities",
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
            article_number=21,
            article_title="Cooperation with competent authorities",
            one_sentence=(
                "Providers of high-risk AI systems must provide conformity documentation "
                "and log access to competent authorities upon request."
            ),
            official_summary=(
                "Art. 21 requires providers of high-risk AI systems to: (1) upon a reasoned "
                "request by a competent authority, provide all information and documentation "
                "necessary to demonstrate conformity with Section 2 requirements, in an official "
                "EU language (Art. 21(1)); (2) upon a reasoned request, give the competent "
                "authority access to the automatically generated logs referred to in Art. 12(1), "
                "to the extent such logs are under their control (Art. 21(2))."
            ),
            related_articles={
                "Art. 6": "High-risk classification (prerequisite for Art. 21)",
                "Art. 12": "Record-keeping (logs that must be accessible per Art. 21(2))",
                "Art. 16": "Provider obligations (Art. 21 is part of provider duties)",
                "Art. 20": "Corrective actions (related authority interaction)",
                "Art. 64": "Market surveillance authority testing powers",
            },
            recital=(
                "Recital 98: Providers should cooperate with competent authorities and "
                "provide all necessary information and documentation to demonstrate "
                "compliance with the requirements of this Regulation."
            ),
            automation_summary={
                "fully_automatable": [
                    "Log export mechanism detection",
                ],
                "partially_automatable": [
                    "Conformity documentation availability detection",
                ],
                "requires_human_judgment": [
                    "Whether documentation is sufficient to demonstrate conformity",
                    "Whether documentation is available in the required EU language",
                    "Whether all logs under provider control are accessible",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) conformity documentation "
                "package covering all Section 2 requirements, accessible on demand; (2) log export "
                "mechanism for Art. 12(1) automatically generated logs. "
                "Based on: ISO/IEC 42001:2023 (compliance documentation controls)."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for authority cooperation (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_conformity_documentation") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 21(1)",
                action="Create conformity documentation package for authority requests",
                details=(
                    "Art. 21(1) requires providing all information and documentation to "
                    "demonstrate conformity with Section 2 requirements. Create:\n"
                    "  - Conformity evidence document covering Art. 8-15 requirements\n"
                    "  - Technical documentation per Art. 11 and Annex IV\n"
                    "  - Risk management documentation per Art. 9\n"
                    "  - Quality management system documentation per Art. 17\n"
                    "  - Ensure availability in at least one official EU language"
                ),
                effort="16-40 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_log_export_capability") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 21(2)",
                action="Implement log export capability for authority access",
                details=(
                    "Art. 21(2) requires giving authorities access to automatically "
                    "generated logs per Art. 12(1). Implement:\n"
                    "  - Log export API or command-line tool\n"
                    "  - Filtering by date range and event type\n"
                    "  - Standard export format (JSON, CSV)\n"
                    "  - Access control for authorized authority requests"
                ),
                effort="4-8 hours",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 21(1)-(2)",
            action="Verify documentation language availability and log completeness",
            details=(
                "Verify that conformity documentation can be provided in an official EU "
                "language as indicated by the Member State. Verify all automatically "
                "generated logs under your control are accessible for export."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=21,
            article_title="Cooperation with competent authorities",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 21 is a provider obligation for high-risk AI systems. Cooperation with "
                "authorities requires operational readiness for document and log requests. "
                "Based on ComplianceLint compliance checklist. Official CEN-CENELEC standards "
                "(expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art21Module:
    return Art21Module()
