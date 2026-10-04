"""
Article 27: Fundamental Rights Impact Assessment — Module implementation.

Art. 27 requires certain deployers of high-risk AI systems to perform a
Fundamental Rights Impact Assessment (FRIA) before first use. This applies to
public law bodies, private entities providing public services, and deployers of
Annex III point 5(b) and (c) systems.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art27"). No regex or keyword scanning is performed.

Obligation mapping:
  ART27-OBL-1   → has_fria_documentation (FRIA with all six elements)
  ART27-OBL-2   → has_fria_versioning (FRIA before first use + updated on change)
  ART27-OBL-3   → handled by gap_findings (manual — authority notification)
  ART27-PERM-4  → no finding: Art. 27(4) as amended by Reg (EU) 2026/1744 is a deployer
                  permission (cross-reference or include parts of an existing DPIA);
                  gap_findings() skips permissions

OBL-1/2/3 have context_skip_field "is_public_law_or_annex_iii_5bc". When it is
False, the obligation is NOT_APPLICABLE. When not provided, it is CONDITIONAL (UTD).

NOTE — "handled by gap_findings" means:
  ObligationEngine.gap_findings() auto-generates the finding for any obligation
  in the JSON that this scan() has NOT explicitly emitted a Finding for.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.application_dates import applicable_from
from core.protocol import (
    BaseArticleModule, ScanResult, Explanation, ActionPlan, ActionItem,
    Finding, ComplianceLevel, Confidence, GapType,
)
from core.obligation_engine import ObligationEngine


class Art27Module(BaseArticleModule):
    """Article 27: Fundamental Rights Impact Assessment."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=27,
            article_title="Fundamental Rights Impact Assessment",
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

        answers = ctx.get_article_answers("art27")

        has_fria_documentation = answers.get("has_fria_documentation")
        has_fria_versioning = answers.get("has_fria_versioning")

        # ── ART27-OBL-1: FRIA with all six required elements ──
        findings.append(self._finding_from_answer(
            obligation_id="ART27-OBL-1",
            answer=has_fria_documentation,
            true_description=(
                "Fundamental Rights Impact Assessment (FRIA) documentation found. "
                "Verify it covers all six required elements: (a) description of processes, "
                "(b) period/frequency, (c) categories of affected persons, (d) specific risks, "
                "(e) human oversight measures, (f) risk materialisation measures."
            ),
            false_description=(
                "No Fundamental Rights Impact Assessment (FRIA) documentation found. "
                "Art. 27(1) requires deployers to perform an assessment covering six elements: "
                "processes, period/frequency, affected categories, specific risks, oversight "
                "measures, and risk materialisation measures."
            ),
            none_description=(
                "AI could not determine whether a FRIA exists. "
                "Art. 27(1) requires a Fundamental Rights Impact Assessment for qualifying deployers."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART27-OBL-2: FRIA before first use + updated on change ──
        findings.append(self._finding_from_answer(
            obligation_id="ART27-OBL-2",
            answer=has_fria_versioning,
            true_description=(
                "FRIA versioning/dating found. Verify the assessment was performed before "
                "first use and is updated when relevant elements change."
            ),
            false_description=(
                "No FRIA versioning or dating found. Art. 27(2) requires the FRIA to be "
                "performed before first use and updated when relevant elements have changed."
            ),
            none_description=(
                "AI could not determine whether the FRIA has proper versioning. "
                "Art. 27(2) requires the assessment before first use and updates on change."
            ),
            gap_type=GapType.PROCESS,
        ))

        # OBL-3 (authority notification) is manual — gap_findings() will auto-generate
        # CONDITIONAL/NOT_APPLICABLE/UTD findings. ART27-PERM-4 is a permission: no finding.

        # Build details dict
        details = {
            "has_fria_documentation": has_fria_documentation,
            "has_fria_versioning": has_fria_versioning,
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
            article_number=27,
            article_title="Fundamental Rights Impact Assessment",
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
            article_number=27,
            article_title="Fundamental Rights Impact Assessment",
            one_sentence=(
                "Certain deployers of high-risk AI systems must perform a Fundamental Rights "
                "Impact Assessment before first use and keep it updated."
            ),
            official_summary=(
                "Art. 27 requires, before deployment, a FRIA for high-risk AI systems referred "
                "to in Art. 6(2) by deployers that are bodies governed by public law or private "
                "entities providing public services, except for systems intended for the area "
                "listed in Annex III point 2, and by deployers of systems referred to in Annex "
                "III points 5(b) and (c). The FRIA must cover the six elements in Art. 27(1). "
                "The obligation applies to first use; previous assessments may be relied on in "
                "similar cases and must be updated when relevant elements change. After the "
                "assessment, the deployer must notify the market surveillance authority of the "
                "results, subject to the possible Art. 46(1) exemption. Where a DPIA under GDPR "
                "Art. 35 or Directive (EU) 2016/680 Art. 27 already meets an Art. 27 "
                "obligation, the deployer may cross-reference the relevant DPIA sections or "
                "include relevant parts in the FRIA."
            ),
            related_articles={
                "Art. 6": "High-risk classification (prerequisite for Art. 27)",
                "Art. 9": "Risk management system (related risk documentation)",
                "Art. 26": "Deployer obligations (broader deployer duties)",
                "Art. 35 GDPR": "Data Protection Impact Assessment (DPIA) whose relevant sections the FRIA may cross-reference or include (Art. 27(4))",
                "Annex III 5(b)(c)": "High-risk categories triggering FRIA requirement",
            },
            recital=(
                "Recital 96: The fundamental rights impact assessment identifies specific risks "
                "to the rights of individuals or groups likely to be affected and measures to "
                "be taken if those risks materialise; the AI Office should develop a "
                "questionnaire template to facilitate compliance."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "FRIA documentation existence detection",
                    "FRIA versioning and dating detection",
                ],
                "requires_human_judgment": [
                    "Whether FRIA content is substantively adequate",
                    "Whether all six required elements are covered",
                    "Whether the FRIA was completed for first use and updated where required",
                    "Whether the market surveillance authority was notified or an Art. 46(1) exemption applies",
                    "Whether DPIA sections cross-referenced or included in the FRIA meet the corresponding Art. 27 obligations",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.2 requires evidence of a FRIA covering "
                "the Art. 27(1) elements and completed for first use, evidence of notification "
                "where Art. 27(3) requires it, and, where DPIA material is reused under Art. "
                "27(4), mapping showing which DPIA sections meet the corresponding Art. 27 "
                "obligations. Based on: ISO/IEC 42001:2023, ISO/IEC 23894:2023."
            ),
            enforcement_date=applicable_from(27),
            waiting_for="CEN-CENELEC harmonized standard for fundamental rights impact assessment (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_fria_documentation") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 27(1)",
                action="Create a Fundamental Rights Impact Assessment (FRIA)",
                details=(
                    "Art. 27(1) requires a FRIA covering six elements:\n"
                    "  (a) Description of deployer's processes using the AI system\n"
                    "  (b) Period and frequency of intended use\n"
                    "  (c) Categories of natural persons and groups likely to be affected\n"
                    "  (d) Specific risks of harm likely to affect identified categories\n"
                    "  (e) Description of human oversight measures\n"
                    "  (f) Measures to be taken when risks materialise\n\n"
                    "Create a structured document (e.g., docs/fria.md) addressing each element."
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_fria_versioning") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 27(2)",
                action="Add versioning and dating to the FRIA",
                details=(
                    "Art. 27(2) requires the FRIA to be performed before first use and "
                    "updated when relevant elements change. Add version numbers, dates, "
                    "and a change log to the FRIA document."
                ),
                effort="1-2 hours",
                action_type="human_judgment_required",
            ))

        # Always add human judgment items for manual obligations
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 27(3)",
            action="Notify market surveillance authority of FRIA results",
            details=(
                "Art. 27(3) requires deployers to notify the relevant market surveillance "
                "authority of the results of the FRIA. Identify the appropriate authority "
                "and submit the assessment results."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="LOW",
            article="Art. 27(4)",
            action="Consider reusing an existing DPIA in the FRIA",
            details=(
                "Under Art. 27(4), as amended by Regulation (EU) 2026/1744, if a Data Protection "
                "Impact Assessment (DPIA) under GDPR Art. 35 or Art. 27 of Directive (EU) 2016/680 "
                "already meets any of the Art. 27 obligations, you may include cross-references to "
                "the relevant sections of that DPIA or include relevant parts of it in the FRIA. "
                "The FRIA itself is still required (Art. 27(1))."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=27,
            article_title="Fundamental Rights Impact Assessment",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 27 is a deployer-addressed article. The FRIA is a substantive document "
                "requiring human judgment about fundamental rights impacts. Automated scanning "
                "can only detect the presence of documentation, not its adequacy. "
                "Based on ComplianceLint compliance checklist. Official CEN-CENELEC standards "
                "(expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art27Module:
    return Art27Module()
