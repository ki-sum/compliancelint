"""
Article 72: Post-Market Monitoring by Providers — Module implementation.

Art. 72 requires providers of high-risk AI systems to establish a post-market
monitoring system that is proportionate to the nature and risks of the AI system.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art72"). No regex or keyword scanning is performed.

Obligation mapping:
  ART72-OBL-1   → has_pmm_system (system established, documented, proportionate)
  ART72-OBL-2   → has_active_data_collection (active collection + compliance evaluation)
  ART72-OBL-3   → has_pmm_plan (plan exists + part of Annex IV technical documentation)
  ART72-PER-1   → handled by gap_findings (permission, conditional: is_annex_i_product)
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


class Art72Module(BaseArticleModule):
    """Article 72: Post-Market Monitoring by Providers."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=72,
            article_title="Post-Market Monitoring by Providers",
        )

    def scan(self, project_path: str) -> ScanResult:
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

        answers = ctx.get_article_answers("art72")

        has_pmm_system = answers.get("has_pmm_system")
        has_active_data_collection = answers.get("has_active_data_collection")
        has_pmm_plan = answers.get("has_pmm_plan")

        # ── ART72-OBL-1: PMM system established, documented, proportionate ──
        findings.append(self._finding_from_answer(
            obligation_id="ART72-OBL-1",
            answer=has_pmm_system,
            true_description=(
                "Post-market monitoring system detected. "
                "Verify it is documented and proportionate to the nature and risks "
                "of the AI system per Art. 72(1)."
            ),
            false_description=(
                "No post-market monitoring system detected. "
                "Art. 72(1) requires providers to establish and document a post-market "
                "monitoring system proportionate to the nature of the AI technology "
                "and the risks of the high-risk AI system."
            ),
            none_description=(
                "AI could not determine whether a post-market monitoring system is in place. "
                "Art. 72(1) requires providers to establish and document such a system."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART72-OBL-2: Active data collection + continuous compliance evaluation ──
        findings.append(self._finding_from_answer(
            obligation_id="ART72-OBL-2",
            answer=has_active_data_collection,
            true_description=(
                "Active data collection and compliance evaluation mechanisms detected. "
                "Verify they systematically collect, document, and analyse relevant data "
                "throughout the system's lifetime per Art. 72(2)."
            ),
            false_description=(
                "No active data collection or compliance evaluation detected. "
                "Art. 72(2) requires the post-market monitoring system to actively and "
                "systematically collect, document, and analyse relevant data to evaluate "
                "continuous compliance throughout the AI system's lifetime."
            ),
            none_description=(
                "AI could not determine whether active data collection and compliance "
                "evaluation mechanisms exist. Art. 72(2) requires systematic data collection "
                "and analysis throughout the system's lifetime."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART72-OBL-3: PMM plan as part of Annex IV technical documentation ──
        findings.append(self._finding_from_answer(
            obligation_id="ART72-OBL-3",
            answer=has_pmm_plan,
            true_description=(
                "Post-market monitoring plan detected. "
                "Verify it is included as part of the technical documentation "
                "referred to in Annex IV per Art. 72(3)."
            ),
            false_description=(
                "No post-market monitoring plan detected. "
                "Art. 72(3) requires the monitoring system to be based on a post-market "
                "monitoring plan that is part of the Annex IV technical documentation."
            ),
            none_description=(
                "AI could not determine whether a post-market monitoring plan exists. "
                "Art. 72(3) requires a plan as part of Annex IV technical documentation."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ART72-PER-1 is a permission (MAY) with context_skip_field "is_annex_i_product".
        # gap_findings() will auto-generate CONDITIONAL/NOT_APPLICABLE/UTD findings.

        # Build details dict
        details = {
            "has_pmm_system": has_pmm_system,
            "has_active_data_collection": has_active_data_collection,
            "has_pmm_plan": has_pmm_plan,
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
            article_number=72,
            article_title="Post-Market Monitoring by Providers",
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
            article_number=72,
            article_title="Post-Market Monitoring by Providers",
            one_sentence=(
                "Providers of high-risk AI systems must establish a post-market monitoring "
                "system proportionate to the nature and risks of the AI system."
            ),
            official_summary=(
                "Art. 72 requires providers of high-risk AI systems to establish and "
                "document a post-market monitoring system that is proportionate to the "
                "nature of the AI technology and the risks of the system. The system must "
                "actively and systematically collect, document, and analyse relevant data "
                "throughout the AI system's lifetime to evaluate continuous compliance "
                "(Art. 72(2)). It must be based on a post-market monitoring plan that is "
                "part of the Annex IV technical documentation (Art. 72(3)). For products "
                "covered by Annex I Union harmonisation legislation, the AI monitoring may "
                "be integrated into existing post-market monitoring systems (Art. 72(4))."
            ),
            related_articles={
                "Art. 6": "High-risk classification (prerequisite for Art. 72)",
                "Art. 9": "Risk management system (complementary risk processes)",
                "Art. 11": "Technical documentation including Annex IV",
                "Art. 12(2)(b)": "Record-keeping must support post-market monitoring",
                "Art. 73": "Serious incident reporting (triggered by monitoring findings)",
                "Annex IV": "Technical documentation requirements including PMM plan",
            },
            recital=(
                "Recital 93: Post-market monitoring is essential for providers to ensure "
                "that AI systems continue to comply with requirements throughout their "
                "lifecycle and to identify potential risks after deployment."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Post-market monitoring system documentation detection",
                    "Active data collection mechanism detection",
                    "Post-market monitoring plan existence detection",
                ],
                "requires_human_judgment": [
                    "Whether the monitoring system is proportionate to specific risks",
                    "Whether data collection is sufficiently comprehensive",
                    "Whether the PMM plan adequately covers Annex IV requirements",
                    "Whether integration with existing monitoring is appropriate (Annex I products)",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) documented post-market "
                "monitoring system proportionate to AI system risks, (2) active data collection "
                "and compliance evaluation throughout system lifetime, (3) post-market monitoring "
                "plan included in Annex IV technical documentation. "
                "Based on: ISO/IEC 42001:2023, ISO 9001:2015 (post-delivery activities)."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for post-market monitoring of AI systems (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_pmm_system") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 72(1)",
                action="Establish and document a post-market monitoring system",
                details=(
                    "Art. 72(1) requires a post-market monitoring system proportionate to "
                    "the nature and risks of your AI system. Create documentation covering:\n"
                    "  - Monitoring objectives and scope\n"
                    "  - Data sources and collection methods\n"
                    "  - Analysis procedures and frequency\n"
                    "  - Escalation and corrective action procedures\n"
                    "  - Roles and responsibilities\n\n"
                    "Consider using docs/post-market-monitoring.md as the primary document."
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_active_data_collection") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 72(2)",
                action="Implement active data collection and compliance evaluation",
                details=(
                    "Art. 72(2) requires actively collecting, documenting, and analysing "
                    "relevant data throughout the system's lifetime. Implement:\n"
                    "  - Performance metrics collection (accuracy, drift, latency)\n"
                    "  - User feedback collection mechanisms\n"
                    "  - Automated compliance evaluation checks\n"
                    "  - Regular analysis and reporting cadence"
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_pmm_plan") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 72(3)",
                action="Create a post-market monitoring plan for Annex IV documentation",
                details=(
                    "Art. 72(3) requires a post-market monitoring plan as part of the "
                    "Annex IV technical documentation. The plan should specify:\n"
                    "  - What data will be collected and how\n"
                    "  - Monitoring frequency and review cadence\n"
                    "  - Thresholds for corrective actions\n"
                    "  - Integration with incident reporting (Art. 73)"
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 72(1)",
            action="Verify monitoring system proportionality to AI system risks",
            details=(
                "Art. 72(1) requires the monitoring system to be proportionate to the "
                "nature and risks of your specific AI system. Review whether monitoring "
                "depth and frequency match your system's risk profile."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=72,
            article_title="Post-Market Monitoring by Providers",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 72 is a provider obligation for high-risk AI systems. Post-market "
                "monitoring requires ongoing operational commitment beyond initial documentation. "
                "Based on ComplianceLint compliance checklist. Official CEN-CENELEC standards "
                "(expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art72Module:
    return Art72Module()
