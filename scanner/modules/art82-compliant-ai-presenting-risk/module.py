"""
Article 82: Compliant AI systems which present a risk — Module implementation.

Art. 82 addresses the situation where a market surveillance authority finds that
an AI system, although compliant with the Regulation, nevertheless presents a
risk to health, safety, fundamental rights, or other aspects of public interest
protection. The provider must ensure corrective action is taken for all affected
systems on the Union market within the timeline prescribed by the authority.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art82"). No regex or keyword scanning is performed.

Obligation mapping:
  ART82-OBL-2   → has_corrective_action_procedure (corrective action for all affected systems)
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


class Art82Module(BaseArticleModule):
    """Article 82: Compliant AI systems which present a risk compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=82,
            article_title="Compliant AI systems which present a risk",
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

        answers = ctx.get_article_answers("art82")

        has_corrective_action_procedure = answers.get("has_corrective_action_procedure")

        # ── ART82-OBL-2: Corrective action for all affected systems ──
        findings.append(self._finding_from_answer(
            obligation_id="ART82-OBL-2",
            answer=has_corrective_action_procedure,
            true_description=(
                "Corrective action procedure detected. "
                "Verify it covers ALL AI systems concerned that have been made "
                "available on the Union market and that corrective action can be "
                "taken within the timeline prescribed by the market surveillance "
                "authority per Art. 82(2)."
            ),
            false_description=(
                "No corrective action procedure detected. "
                "Art. 82(2) requires the provider or other relevant operator to "
                "ensure that corrective action is taken in respect of all the AI "
                "systems concerned that it has made available on the Union market "
                "within the timeline prescribed by the market surveillance authority."
            ),
            none_description=(
                "AI could not determine whether a corrective action procedure exists. "
                "Art. 82(2) requires corrective action for all affected AI systems on "
                "the Union market within the authority-prescribed timeline."
            ),
            gap_type=GapType.PROCESS,
        ))

        # Build details dict
        details = {
            "has_corrective_action_procedure": has_corrective_action_procedure,
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
            article_number=82,
            article_title="Compliant AI systems which present a risk",
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
            article_number=82,
            article_title="Compliant AI systems which present a risk",
            one_sentence=(
                "When a market surveillance authority finds that a compliant AI system "
                "nevertheless presents a risk, the provider must take corrective action "
                "for all affected systems on the Union market within the prescribed timeline."
            ),
            official_summary=(
                "Art. 82 establishes the procedure when a market surveillance authority "
                "determines that an AI system, despite being compliant with this Regulation, "
                "presents a risk to the health or safety of persons, to compliance with "
                "obligations under Union or national law intended to protect fundamental "
                "rights, or to other aspects of public interest protection. The provider "
                "or other relevant operator must ensure corrective action is taken for ALL "
                "AI systems concerned on the Union market within the timeline prescribed "
                "by the authority (Art. 82(2)). The authority must inform the Commission "
                "and other Member States of findings and corrective measures (Art. 82(3))."
            ),
            related_articles={
                "Art. 79": "Non-compliant AI systems (general non-compliance procedure)",
                "Art. 80": "Non-high-risk misclassification procedure",
                "Art. 20": "Corrective actions and duty of information",
                "Art. 16": "Provider obligations for high-risk AI systems",
            },
            recital="",
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Corrective action procedure documentation detection",
                ],
                "requires_human_judgment": [
                    "Whether the AI system actually presents a risk despite compliance",
                    "Whether corrective action scope covers all affected systems",
                    "Whether corrective action timeline meets authority requirements",
                    "Market surveillance authority communication and coordination",
                    "Assessment of risk to health, safety, fundamental rights, or public interest",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: documented corrective "
                "action procedure that enables the provider to take corrective action in "
                "respect of all affected AI systems on the Union market within the timeline "
                "prescribed by the market surveillance authority."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_corrective_action_procedure") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 82(2)",
                action="Create corrective action procedure for compliant-but-risky systems",
                details=(
                    "Art. 82(2) requires corrective action for all affected AI systems "
                    "on the Union market. Create documentation covering:\n"
                    "  - Procedure for identifying all affected systems on the Union market\n"
                    "  - Process for implementing corrective measures (withdraw, recall, disable, modify)\n"
                    "  - Timeline management to meet market surveillance authority deadlines\n"
                    "  - Communication plan with market surveillance authorities\n"
                    "  - System inventory and deployment tracking\n\n"
                    "Consider using docs/corrective-action-procedure.md as the primary document."
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 82(1)-(3)",
            action="Review risk assessment for compliant AI systems",
            details=(
                "Even compliant AI systems may present risks. Establish a process for "
                "ongoing risk assessment that considers health, safety, fundamental rights, "
                "and public interest impacts. Engage legal counsel to prepare for potential "
                "market surveillance authority evaluations."
            ),
            effort="4-8 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=82,
            article_title="Compliant AI systems which present a risk",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 82 applies when market surveillance authorities evaluate compliant "
                "AI systems that nevertheless present a risk. Proactive risk assessment "
                "and corrective action planning helps ensure timely response. Based on "
                "ComplianceLint compliance checklist. Official CEN-CENELEC standards "
                "(expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art82Module:
    return Art82Module()
