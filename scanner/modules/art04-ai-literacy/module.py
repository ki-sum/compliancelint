"""
Article 4: AI Literacy — Module implementation using unified protocol.

Art. 4 requires providers AND deployers of AI systems to take measures to
ensure a sufficient level of AI literacy of their staff and other persons
dealing with the operation and use of AI systems on their behalf.

This applies to ALL AI systems (not just high-risk).

Obligation mapping:
  ART04-OBL-1  → has_ai_literacy_measures (documentation artifacts detected)
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


class Art04Module(BaseArticleModule):
    """Article 4: AI Literacy compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=4,
            article_title="AI Literacy",
        )

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for AI literacy compliance using AI-provided answers.

        Reads compliance_answers["art4"] from the AI context. Maps each field
        to obligation findings without any regex or file scanning.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for each AI literacy obligation.
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

        answers = ctx.get_article_answers("art4")

        has_ai_literacy_measures = answers.get("has_ai_literacy_measures")
        literacy_description = answers.get("literacy_description", "")
        literacy_evidence = answers.get("literacy_evidence") or []

        # -- ART04-OBL-1: AI literacy measures for staff --
        # Art. 4 requires providers and deployers to ensure a sufficient level
        # of AI literacy. Code scanning can detect documentation artifacts
        # (AI policies, training docs, competency frameworks) but cannot assess
        # whether training is actually adequate or sufficient.
        findings.append(self._finding_from_answer(
            obligation_id="ART04-OBL-1",
            answer=has_ai_literacy_measures,
            true_description=(
                f"AI literacy documentation detected: {literacy_description}."
                if literacy_description
                else "AI literacy documentation or policy artifacts detected."
            ),
            false_description=(
                "No AI literacy documentation detected. Art. 4 requires providers "
                "and deployers to take measures to ensure a sufficient level of AI "
                "literacy of their staff and other persons dealing with the operation "
                "and use of AI systems on their behalf."
            ),
            none_description=(
                "AI could not determine whether AI literacy measures are in place. "
                "Manual review of training programs, AI usage policies, and "
                "competency frameworks required."
            ),
            evidence=literacy_evidence or None,
            gap_type=GapType.PROCESS,
            file_path=literacy_evidence[0] if literacy_evidence else "project-wide",
        ))

        details = {
            "has_ai_literacy_measures": has_ai_literacy_measures,
            "literacy_description": literacy_description,
            "literacy_evidence": literacy_evidence,
        }

        # -- Obligation Engine: enrich findings + identify gaps --
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
            article_number=4,
            article_title="AI Literacy",
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
            article_number=4,
            article_title="AI Literacy",
            one_sentence=(
                "Providers and deployers must ensure their staff have sufficient "
                "AI literacy for operating and using AI systems."
            ),
            official_summary=(
                "Art. 4 requires providers and deployers of AI systems to take "
                "measures to ensure, to their best extent, a sufficient level of "
                "AI literacy of their staff and other persons dealing with the "
                "operation and use of AI systems on their behalf. This must take "
                "into account technical knowledge, experience, education, training, "
                "the context of use, and the persons on whom the AI systems are used."
            ),
            related_articles={
                "Art. 3(1)": "Definition of AI system",
                "Art. 2": "Scope — Art. 4 applies to all AI systems, not just high-risk",
                "Recital 20": "AI literacy measures should be proportionate",
            },
            recital=(
                "Recital 20: Providers and deployers should ensure that their staff "
                "and other persons involved have a sufficient level of AI literacy."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of AI usage policies and training documentation",
                    "Detection of competency frameworks mentioning AI",
                    "Detection of onboarding materials with AI guidance",
                ],
                "requires_human_judgment": [
                    "Whether literacy measures are sufficient and proportionate",
                    "Whether staff have actually been trained",
                    "Whether training quality meets the context requirements",
                    "Whether affected persons have been considered",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) AI usage policy "
                "document, (2) staff training documentation or competency framework, "
                "(3) evidence of context-appropriate training. "
                "Based on: ISO/IEC 42001:2023 Clause 7.2 (Competence), 7.3 (Awareness)."
            ),
            enforcement_date="2025-02-02",
            waiting_for="CEN-CENELEC harmonized standard for AI literacy (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_ai_literacy_measures") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 4",
                action="Create AI literacy program for staff",
                details=(
                    "Art. 4 requires measures to ensure AI literacy. Create:\n"
                    "  (1) AI usage policy document defining acceptable use\n"
                    "  (2) Training program covering AI system operation\n"
                    "  (3) Competency framework for staff roles\n"
                    "  (4) Documentation of training completion\n\n"
                    "Consider: technical knowledge, experience, education, training context, "
                    "and the persons on whom the AI systems are used."
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 4",
            action="Verify AI literacy measures are proportionate to context",
            details=(
                "Art. 4 requires considering technical knowledge, experience, "
                "education and training, and the context in which AI systems are used. "
                "Review whether your training program is appropriate for:\n"
                "  - The complexity of your AI system\n"
                "  - The technical background of your staff\n"
                "  - The persons or groups affected by the AI system"
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=4,
            article_title="AI Literacy",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 4 is primarily an organizational obligation. Automated scanning "
                "detects documentation artifacts (policies, training docs) but cannot "
                "assess whether actual AI literacy measures are sufficient. "
                "Human expert review is essential."
            ),
        )


# Module entry point -- used by auto-discovery
def create_module() -> Art04Module:
    return Art04Module()
