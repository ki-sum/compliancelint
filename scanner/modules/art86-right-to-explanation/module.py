"""
Article 86: Right to Explanation of Individual Decision-Making — Module implementation.

Art. 86 requires deployers of Annex III high-risk AI systems (excluding point 2) to
provide affected persons with clear and meaningful explanations of the role of the AI
system in decision-making and the main elements of the decision taken.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art86"). No regex or keyword scanning is performed.

Obligation mapping:
  ART86-OBL-1   → has_explanation_mechanism (explainability interface / mechanism)
  ART86-EXC-1   → handled by gap_findings (exception, manual)
  ART86-EXC-2   → handled by gap_findings (savings clause, manual)
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


class Art86Module(BaseArticleModule):
    """Article 86: Right to Explanation of Individual Decision-Making compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=86,
            article_title="Right to Explanation of Individual Decision-Making",
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

        answers = ctx.get_article_answers("art86")

        has_explanation_mechanism = answers.get("has_explanation_mechanism")
        explanation_evidence = answers.get("explanation_evidence", [])

        # ── ART86-OBL-1: Right to explanation mechanism ──
        # Art. 86(1) requires deployers to provide clear and meaningful explanations
        # of the AI system's role and the main elements of the decision taken.
        findings.append(self._finding_from_answer(
            obligation_id="ART86-OBL-1",
            answer=has_explanation_mechanism,
            true_description=(
                "Explanation mechanism detected. "
                "Verify it provides clear and meaningful explanations of the AI system's "
                "role in decision-making and the main elements of the decision taken "
                "per Art. 86(1)."
            ),
            false_description=(
                "No explanation mechanism detected. "
                "Art. 86(1) requires deployers to provide affected persons with clear "
                "and meaningful explanations of the role of the AI system in the "
                "decision-making procedure and the main elements of the decision taken."
            ),
            none_description=(
                "AI could not determine whether an explanation mechanism exists. "
                "Art. 86(1) requires clear and meaningful explanations of AI-assisted "
                "decisions to affected persons."
            ),
            evidence=explanation_evidence,
            gap_type=GapType.PROCESS,
        ))

        # ART86-EXC-1 and ART86-EXC-2 are exception/savings_clause with automation_level "manual".
        # gap_findings() will auto-generate UTD findings for them.

        # Build details dict
        details = {
            "has_explanation_mechanism": has_explanation_mechanism,
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
            article_number=86,
            article_title="Right to Explanation of Individual Decision-Making",
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
            article_number=86,
            article_title="Right to Explanation of Individual Decision-Making",
            one_sentence=(
                "Affected persons have the right to obtain clear and meaningful explanations "
                "of AI-assisted decisions that produce legal or similarly significant effects."
            ),
            official_summary=(
                "Art. 86 requires deployers of Annex III high-risk AI systems (excluding "
                "point 2) to provide affected persons with clear and meaningful explanations "
                "when a decision based on the AI system's output produces legal effects or "
                "similarly significantly affects that person with adverse impact on their "
                "health, safety or fundamental rights. The explanation must cover the role "
                "of the AI system in the decision-making procedure and the main elements "
                "of the decision taken. Exceptions apply where Union or national law provides "
                "for exceptions (Art. 86(2)), and the article does not apply where the right "
                "to explanation is already provided under other Union law (Art. 86(3))."
            ),
            related_articles={
                "Art. 6": "High-risk classification (prerequisite for Art. 86)",
                "Art. 13": "Transparency obligations (complementary explainability requirements)",
                "Art. 14": "Human oversight (human review of AI decisions)",
                "Art. 26": "Deployer obligations (deployers are the addressee of Art. 86)",
                "GDPR Art. 22": "Automated individual decision-making (potential overlap via Art. 86(3))",
            },
            recital=(
                "Recital 171: The right to explanation should help affected persons understand "
                "the role of AI in decisions affecting them and enable them to exercise their "
                "other rights effectively."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Explainability mechanism detection (SHAP, LIME, feature importance)",
                    "Explanation endpoint or interface detection",
                    "Decision audit trail detection",
                ],
                "requires_human_judgment": [
                    "Whether explanations are truly clear and meaningful to affected persons",
                    "Whether Union or national law exceptions apply (Art. 86(2))",
                    "Whether other Union law already provides equivalent right (Art. 86(3))",
                    "Whether the system produces legal effects or similarly significant effects",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) mechanism for generating "
                "explanations of AI-assisted decisions, (2) explanation covers AI system's role "
                "in the decision-making procedure, (3) explanation covers main elements of the "
                "decision taken, (4) explanations are accessible to affected persons. "
                "Based on: ISO/IEC 42001:2023, ISO/IEC TR 24028:2020 (explainability)."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for AI transparency and explainability (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_explanation_mechanism") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 86(1)",
                action="Implement an explanation mechanism for AI-assisted decisions",
                details=(
                    "Art. 86(1) requires deployers to provide clear and meaningful "
                    "explanations to affected persons. Implement:\n"
                    "  - Explainability tooling (SHAP, LIME, or feature importance)\n"
                    "  - User-facing explanation endpoint or interface\n"
                    "  - Decision audit trail capturing AI inputs, outputs, and reasoning\n"
                    "  - Documentation of the AI system's role in decision-making\n\n"
                    "The explanation must cover:\n"
                    "  1. The role of the AI system in the decision-making procedure\n"
                    "  2. The main elements of the decision taken"
                ),
                effort="8-24 hours",
                action_type="human_judgment_required",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="HIGH",
            article="Art. 86(1)",
            action="Verify explanations are clear and meaningful to affected persons",
            details=(
                "Art. 86(1) requires explanations to be 'clear and meaningful'. "
                "This is a qualitative standard that requires human assessment. "
                "Consider user testing with representative affected persons to validate "
                "that explanations are understandable and actionable."
            ),
            effort="4-8 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 86(2)-(3)",
            action="Assess whether legal exceptions or savings clauses apply",
            details=(
                "Art. 86(2) provides exceptions where Union or national law restricts "
                "the right to explanation. Art. 86(3) is a savings clause — Art. 86 does "
                "not apply where other Union law already provides the right to explanation "
                "(e.g., GDPR Art. 22). Obtain legal advice on whether these apply to your system."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=86,
            article_title="Right to Explanation of Individual Decision-Making",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 86 is a deployer obligation for Annex III high-risk AI systems "
                "(excluding point 2). Compliance requires both technical mechanisms and "
                "qualitative assessment of explanation adequacy. "
                "Based on ComplianceLint compliance checklist. Official CEN-CENELEC standards "
                "(expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art86Module:
    return Art86Module()
