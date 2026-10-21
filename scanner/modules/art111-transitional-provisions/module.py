"""
Article 111: AI systems already placed on the market or put into service
and general-purpose AI models already placed on the market — Module implementation.

Art. 111 covers transitional provisions for existing AI systems and GPAI models:
  ART111-OBL-1 → has_transition_plan (Annex X legacy systems compliance by 31 Dec 2030)
  ART111-OBL-2 → has_significant_change_tracking (high-risk systems placed before the Chapter III
                 application date + public authority compliance by 2 Aug 2030)
  ART111-OBL-3 → has_gpai_compliance_timeline (GPAI models placed before 2 Aug 2025 comply by 2 Aug 2027)
  ART111-OBL-4 → informational only (Art. 111(4), Reg (EU) 2026/1744: generative AI systems placed on
                 the market before 2 Aug 2026 had until 2 Dec 2026 to comply with Art. 50(2); compliance
                 with Art. 50(2) is assessed under ART50-OBL-2)

This module reads AI-provided compliance_answers["art111"] and maps each answer
to a Finding. No regex, keyword, or AST scanning is performed — detection is
entirely the AI's responsibility.

Boundary cases:
  - OBL-1 has context_skip_field "is_annex_x_legacy_system". When false,
    obligation is NOT_APPLICABLE (handled by obligation engine).
  - All obligations are partially automatable — AI can check for documentation
    and timeline tracking, but actual compliance requires human judgment.
"""

import os
import sys
from datetime import datetime, timezone

# Add core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.application_dates import applicable_from, chapter_iii_dates, long_date, milestone_date
from core.harmonised_standards import standard_status
from core.protocol import (
    BaseArticleModule, ScanResult, Explanation, ActionPlan, ActionItem,
    Finding, ComplianceLevel, Confidence, GapType,
)
from core.obligation_engine import ObligationEngine

# Art. 111(2) cut-off: "the date of application of Chapter III referred to in Article 113"
# (Art. 113, third paragraph, point (c), as amended by Reg (EU) 2026/1744).
_CH3 = chapter_iii_dates()
_CUT_OFF = (f"the date Chapter III applies to them ({long_date(_CH3['annex_iii'])} for Annex III "
            f"systems, {long_date(_CH3['annex_i'])} for Annex I systems)")
_ART111_4_DEADLINE = long_date(milestone_date("Art. 111(4)"))


class Art111Module(BaseArticleModule):
    """Article 111: Transitional provisions compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=111,
            article_title="AI systems already placed on the market or put into service and general-purpose AI models already placed on the market",
        )

    # ── Scanning ──

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for Art. 111 compliance using AI-provided answers.

        Reads compliance_answers["art111"] from the AI context. Maps each field
        to obligation findings:
          - has_transition_plan → ART111-OBL-1
          - has_significant_change_tracking → ART111-OBL-2
          - has_gpai_compliance_timeline → ART111-OBL-3

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for Art. 111 transitional provisions.
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

        answers = ctx.get_article_answers("art111")

        has_transition_plan = answers.get("has_transition_plan")
        transition_evidence = answers.get("transition_evidence", "")
        has_significant_change_tracking = answers.get("has_significant_change_tracking")
        change_tracking_evidence = answers.get("change_tracking_evidence", "")
        has_gpai_compliance_timeline = answers.get("has_gpai_compliance_timeline")
        gpai_timeline_evidence = answers.get("gpai_timeline_evidence", "")

        # ── ART111-OBL-1: Annex X legacy system transition plan ──
        # Conditional on is_annex_x_legacy_system (handled by obligation engine gap_findings).
        findings.append(self._finding_from_answer(
            obligation_id="ART111-OBL-1",
            answer=has_transition_plan,
            true_description=(
                "Transition plan for Annex X legacy system compliance found. "
                "Art. 111(1) requires AI systems that are components of Annex X "
                "large-scale IT systems placed on the market before 2 August 2027 "
                "to be brought into compliance by 31 December 2030."
                f"{(' Evidence: ' + transition_evidence) if transition_evidence else ''}"
            ),
            false_description=(
                "No transition plan for Annex X legacy system compliance found. "
                "Art. 111(1) requires AI systems that are components of Annex X "
                "large-scale IT systems placed on the market before 2 August 2027 "
                "to be brought into compliance by 31 December 2030."
            ),
            none_description=(
                "AI could not determine whether a transition plan for Annex X "
                "legacy system compliance exists. Art. 111(1) requires compliance "
                "by 31 December 2030 for Annex X large-scale IT system components."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART111-OBL-2: Significant change tracking + public authority compliance ──
        findings.append(self._finding_from_answer(
            obligation_id="ART111-OBL-2",
            answer=has_significant_change_tracking,
            true_description=(
                "Significant change tracking and/or public authority compliance "
                "planning found. Without prejudice to Art. 5 and excluding systems "
                "referred to in Art. 111(1), Art. 111(2) applies this Regulation to "
                "operators of high-risk AI systems placed on the market or put into "
                f"service before {_CUT_OFF} only if, as from that date, those systems are "
                "subject to significant changes in their designs. In any case, providers "
                "and deployers of high-risk AI systems intended to be used by public "
                "authorities must comply with the applicable requirements and obligations "
                "by 2 August 2030."
                f"{(' Evidence: ' + change_tracking_evidence) if change_tracking_evidence else ''}"
            ),
            false_description=(
                "No significant change tracking or public authority compliance "
                "planning found. Without prejudice to Art. 5 and excluding systems "
                "referred to in Art. 111(1), Art. 111(2) applies this Regulation to "
                "operators of high-risk AI systems placed on the market or put into "
                f"service before {_CUT_OFF} if, as from that date, those systems are "
                "subject to significant changes in their designs; in any case, providers "
                "and deployers of systems intended to be used by public authorities must "
                "comply with the applicable requirements and obligations by 2 August 2030."
            ),
            none_description=(
                "AI could not determine whether significant change tracking or "
                "public authority compliance planning is in place. Without prejudice to "
                "Art. 5 and excluding systems referred to in Art. 111(1), Art. 111(2) "
                "concerns high-risk AI systems placed on the market or put into service "
                "before the date Chapter III applies to them that undergo significant "
                "design changes from that date, and separately requires providers and "
                "deployers of high-risk AI systems intended to be used by public "
                "authorities to comply by 2 August 2030."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART111-OBL-3: GPAI model compliance timeline ──
        findings.append(self._finding_from_answer(
            obligation_id="ART111-OBL-3",
            answer=has_gpai_compliance_timeline,
            true_description=(
                "GPAI model compliance timeline tracking found. Art. 111(3) requires "
                "providers of general-purpose AI models placed on the market before "
                "2 August 2025 to comply by 2 August 2027."
                f"{(' Evidence: ' + gpai_timeline_evidence) if gpai_timeline_evidence else ''}"
            ),
            false_description=(
                "No GPAI model compliance timeline tracking found. Art. 111(3) "
                "requires providers of general-purpose AI models placed on the market "
                "before 2 August 2025 to take necessary steps to comply by 2 August 2027."
            ),
            none_description=(
                "AI could not determine whether GPAI model compliance timeline "
                "tracking is in place. Art. 111(3) requires GPAI model providers "
                "to comply by 2 August 2027 for models placed on market before "
                "2 August 2025."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART111-OBL-4: Art. 50(2) transitional deadline (informational) ──
        # Founder decision 2026-10-03: handled as from 2 December 2026, when the
        # transitional period is spent; Art. 50(2) itself is evaluated by ART50-OBL-2.
        findings.append(Finding(
            obligation_id="ART111-OBL-4",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.NOT_APPLICABLE,
            confidence=Confidence.HIGH,
            description=(
                "Art. 111(4) gives providers of AI systems, including general-purpose AI "
                "systems, generating synthetic audio, image, video or text content that "
                "were placed on the market before 2 August 2026 until "
                f"{_ART111_4_DEADLINE} to comply with Art. 50(2). Compliance with "
                "Art. 50(2) is assessed under ART50-OBL-2."
            ),
            gap_type=GapType.PROCESS,
            is_informational=True,
        ))

        details = {
            "has_transition_plan": has_transition_plan,
            "transition_evidence": transition_evidence,
            "has_significant_change_tracking": has_significant_change_tracking,
            "change_tracking_evidence": change_tracking_evidence,
            "has_gpai_compliance_timeline": has_gpai_compliance_timeline,
            "gpai_timeline_evidence": gpai_timeline_evidence,
            "note": (
                "Art. 111 establishes transitional provisions for existing AI systems "
                "and GPAI models. Different rules apply: Annex X large-scale IT system "
                "components placed on the market or put into service before 2 Aug 2027 "
                "(compliance by 31 Dec 2030, without prejudice to Art. 5); high-risk "
                "systems other than Art. 111(1) systems placed on the market or put into "
                f"service before {_CUT_OFF} (the Regulation applies on significant design "
                "changes from that date, without prejudice to Art. 5); high-risk systems "
                "intended to be used by public authorities (compliance by 2 Aug 2030); "
                "GPAI models placed on the market before 2 Aug 2025 (compliance by "
                "2 Aug 2027); and AI systems generating synthetic audio, image, video or "
                "text content placed on the market before 2 Aug 2026 (Art. 50(2) "
                f"compliance by {_ART111_4_DEADLINE})."
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
            article_number=111,
            article_title="AI systems already placed on the market or put into service and general-purpose AI models already placed on the market",
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
            article_number=111,
            article_title="AI systems already placed on the market or put into service and general-purpose AI models already placed on the market",
            one_sentence=(
                "Article 111 establishes transitional compliance deadlines for "
                "existing AI systems and GPAI models already on the market."
            ),
            official_summary=(
                "Art. 111 provides transitional provisions for existing AI systems and "
                "GPAI models. Annex X large-scale IT system components placed on the "
                "market or put into service before 2 Aug 2027 must be brought into "
                "compliance by 31 Dec 2030, without prejudice to Art. 5. For high-risk AI "
                "systems other than those in Art. 111(1) placed on the market or put into "
                f"service before {_CUT_OFF}, the Regulation applies, without prejudice to "
                "Art. 5, if they undergo significant design changes from that date; "
                "providers and deployers of high-risk systems intended to be used by "
                "public authorities must comply with the applicable requirements and "
                "obligations by 2 Aug 2030 in any case. GPAI models placed on the market "
                "before 2 Aug 2025 must comply by 2 Aug 2027. Under Art. 111(4), AI "
                "systems generating synthetic audio, image, video or text content placed "
                f"on the market before 2 Aug 2026 must comply with Art. 50(2) by "
                f"{_ART111_4_DEADLINE}."
            ),
            related_articles={
                "Art. 5": "Prohibited practices (Art. 111(1) and (2) apply without prejudice to Art. 5)",
                "Art. 50": "Art. 111(4) sets the Art. 50(2) deadline for AI systems generating synthetic audio, image, video or text content placed on the market before 2 Aug 2026",
                "Art. 113": "Entry into force and application dates",
                "Annex X": "List of large-scale IT systems (SIS, VIS, EES, ETIAS, etc.)",
            },
            recital=(
                "Recital 178: It is appropriate to provide for a reasonable period of time "
                "during which AI systems already placed on the market can be brought into "
                "compliance with the requirements of this Regulation."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of compliance transition planning documentation",
                    "Detection of significant change tracking procedures",
                    "Detection of GPAI compliance timeline tracking",
                ],
                "requires_human_judgment": [
                    "Whether the system is a component of an Annex X large-scale IT system",
                    "Whether design changes qualify as 'significant' under Art. 111(2)",
                    "Whether the system is intended for use by public authorities",
                    "Whether the GPAI model was placed on market before 2 Aug 2025",
                    "Whether a generative AI system was placed on the market before 2 Aug 2026 (Art. 111(4))",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 checks: (1) transition plan "
                "for Annex X legacy systems, (2) significant change tracking for "
                "pre-existing high-risk systems, (3) GPAI compliance timeline tracking. "
                "Note: actual compliance requires human judgment on system classification "
                "and deployment dates."
            ),
            enforcement_date=applicable_from(111),
            waiting_for=standard_status(111),
        )

    # ── Action Plan ──

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_transition_plan") is not True:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 111(1)",
                action="Create transition plan for Annex X legacy system compliance",
                details=(
                    "Art. 111(1) requires AI systems that are components of Annex X "
                    "large-scale IT systems (SIS, VIS, EES, ETIAS, etc.) placed on the "
                    "market before 2 August 2027 to comply by 31 December 2030.\n"
                    "\n"
                    "  1. Determine if your system is a component of an Annex X IT system\n"
                    "  2. Document the system's deployment date\n"
                    "  3. Create a compliance roadmap with milestones leading to 31 Dec 2030\n"
                    "  4. Identify gaps against Section 2 (Art. 8-15) requirements\n"
                    "  5. Track remediation progress"
                ),
                effort="4-8 hours (initial assessment)",
                action_type="human_judgment_required",
            ))

        if details.get("has_significant_change_tracking") is not True:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 111(2)",
                action="Establish significant change tracking for pre-existing high-risk AI systems",
                details=(
                    "Without prejudice to Art. 5 and excluding systems referred to in "
                    "Art. 111(1), Art. 111(2) applies this Regulation to operators of "
                    "high-risk AI systems placed on the market or put into service before "
                    f"{_CUT_OFF} if they undergo significant design changes from that date. "
                    "Providers and deployers of high-risk AI systems intended to be used by "
                    "public authorities must comply with the applicable requirements and "
                    "obligations by 2 Aug 2030 in any case.\n"
                    "\n"
                    "  1. Document when the first unit of the system's type and model was placed "
                    "on the market or put into service (Reg. (EU) 2026/1744, Recital 39)\n"
                    "  2. Record design changes made from the applicable cut-off date\n"
                    "  3. Assess whether each design change is significant for Art. 111(2) purposes\n"
                    "  4. If a significant design change occurs, trigger compliance with all relevant "
                    "provisions applicable to the high-risk AI system, including applicable "
                    "conformity-assessment requirements\n"
                    "  5. If the system is intended to be used by public authorities, ensure compliance "
                    "with the applicable requirements and obligations by 2 Aug 2030 regardless of "
                    "design change."
                ),
                effort="4-8 hours (initial setup), ongoing maintenance",
                action_type="human_judgment_required",
            ))

        if details.get("has_gpai_compliance_timeline") is not True:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 111(3)",
                action="Create GPAI model compliance timeline",
                details=(
                    "Art. 111(3) requires GPAI model providers to comply by 2 Aug 2027 "
                    "for models placed on the market before 2 Aug 2025.\n"
                    "\n"
                    "  1. Determine if your GPAI model was placed on market before 2 Aug 2025\n"
                    "  2. Map required obligations (Art. 53 documentation, Art. 55 if systemic risk)\n"
                    "  3. Create a compliance roadmap with milestones leading to 2 Aug 2027\n"
                    "  4. Begin preparing technical documentation per Annex XI\n"
                    "  5. Track compliance progress"
                ),
                effort="4-8 hours (initial assessment)",
                action_type="human_judgment_required",
            ))

        # Always: ongoing monitoring
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 111",
            action="Monitor transitional compliance deadlines and regulatory guidance",
            details=(
                "Art. 111 transitional provisions have multiple deadlines. "
                "Monitor for regulatory guidance on: (1) definition of 'significant "
                "changes' under Art. 111(2), (2) interpretation of Annex X scope, "
                "(3) any delegated acts or implementing acts affecting transitional periods."
            ),
            effort="Ongoing — periodic review",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=111,
            article_title="AI systems already placed on the market or put into service and general-purpose AI models already placed on the market",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 111 transitional provisions are primarily legal/organizational matters. Automated scanning can "
                "only check for documentation and planning readiness. Based on ComplianceLint compliance checklist."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art111Module:
    return Art111Module()
