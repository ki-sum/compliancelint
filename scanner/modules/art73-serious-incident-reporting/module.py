"""
Article 73: Reporting of Serious Incidents — Module implementation.

Art. 73 requires providers of high-risk AI systems to report serious incidents
to market surveillance authorities, with differentiated timelines based on
severity, and to perform investigations with corrective action.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art73"). No regex or keyword scanning is performed.

Obligation mapping:
  ART73-OBL-1   → has_incident_reporting_procedure (reporting framework)
  ART73-OBL-2   → has_reporting_timelines (15-day general deadline)
  ART73-OBL-3   → has_expedited_reporting_procedure (2-day widespread infringement)
  ART73-OBL-4   → has_expedited_reporting_procedure (10-day death — same field as OBL-3)
  ART73-PER-1   → handled by gap_findings (permission, manual)
  ART73-OBL-5   → has_investigation_procedure (investigation + corrective action)
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


class Art73Module(BaseArticleModule):
    """Article 73: Reporting of Serious Incidents compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=73,
            article_title="Reporting of Serious Incidents",
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

        answers = ctx.get_article_answers("art73")

        has_incident_reporting_procedure = answers.get("has_incident_reporting_procedure")
        has_reporting_timelines = answers.get("has_reporting_timelines")
        has_expedited_reporting_procedure = answers.get("has_expedited_reporting_procedure")
        has_investigation_procedure = answers.get("has_investigation_procedure")

        # ── ART73-OBL-1: Serious incident reporting procedure ──
        findings.append(self._finding_from_answer(
            obligation_id="ART73-OBL-1",
            answer=has_incident_reporting_procedure,
            true_description=(
                "Incident reporting procedure detected. "
                "Verify it covers reporting serious incidents to market surveillance "
                "authorities of the Member States where the incident occurred per Art. 73(1)."
            ),
            false_description=(
                "No incident reporting procedure detected. "
                "Art. 73(1) requires providers to report any serious incident to the market "
                "surveillance authorities of the Member States where the incident occurred."
            ),
            none_description=(
                "AI could not determine whether an incident reporting procedure exists. "
                "Art. 73(1) requires reporting serious incidents to market surveillance authorities."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART73-OBL-2: Reporting within 15 days ──
        findings.append(self._finding_from_answer(
            obligation_id="ART73-OBL-2",
            answer=has_reporting_timelines,
            true_description=(
                "Reporting timelines documented. "
                "Verify the procedure ensures reporting immediately and not later than "
                "15 days after the provider becomes aware of the serious incident per Art. 73(2)."
            ),
            false_description=(
                "No reporting timelines documented. "
                "Art. 73(2) requires reporting immediately and not later than 15 days "
                "after the provider becomes aware of the serious incident."
            ),
            none_description=(
                "AI could not determine whether reporting timelines are documented. "
                "Art. 73(2) requires reporting within 15 days of awareness."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART73-OBL-3: Widespread infringement — 2-day deadline ──
        findings.append(self._finding_from_answer(
            obligation_id="ART73-OBL-3",
            answer=has_expedited_reporting_procedure,
            true_description=(
                "Expedited reporting procedure detected. "
                "Verify it includes a 2-day deadline for widespread infringement "
                "per Art. 73(3)."
            ),
            false_description=(
                "No expedited reporting procedure detected. "
                "Art. 73(3) requires reporting widespread infringement immediately "
                "and not later than 2 days after the provider becomes aware."
            ),
            none_description=(
                "AI could not determine whether an expedited reporting procedure exists. "
                "Art. 73(3) requires a 2-day deadline for widespread infringement."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART73-OBL-4: Death — 10-day deadline ──
        # Uses same field as OBL-3: expedited reporting covers both severity tiers
        findings.append(self._finding_from_answer(
            obligation_id="ART73-OBL-4",
            answer=has_expedited_reporting_procedure,
            true_description=(
                "Expedited reporting procedure detected. "
                "Verify it includes a 10-day deadline for incidents involving death "
                "per Art. 73(4)."
            ),
            false_description=(
                "No expedited reporting procedure for fatal incidents detected. "
                "Art. 73(4) requires reporting incidents involving death immediately "
                "and not later than 10 days after the provider becomes aware."
            ),
            none_description=(
                "AI could not determine whether an expedited reporting procedure "
                "for fatal incidents exists. Art. 73(4) requires a 10-day deadline."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ART73-PER-1 is a permission (MAY) with automation_level "manual".
        # gap_findings() will auto-generate UTD findings for it.

        # ── ART73-OBL-5: Investigation and corrective action ──
        findings.append(self._finding_from_answer(
            obligation_id="ART73-OBL-5",
            answer=has_investigation_procedure,
            true_description=(
                "Incident investigation procedure detected. "
                "Verify it includes risk assessment and corrective action "
                "performed without delay per Art. 73(6)."
            ),
            false_description=(
                "No incident investigation procedure detected. "
                "Art. 73(6) requires providers to perform necessary investigations "
                "without delay, including risk assessment and corrective action."
            ),
            none_description=(
                "AI could not determine whether an incident investigation procedure exists. "
                "Art. 73(6) requires investigation with risk assessment and corrective action."
            ),
            gap_type=GapType.PROCESS,
        ))

        # Build details dict
        details = {
            "has_incident_reporting_procedure": has_incident_reporting_procedure,
            "has_reporting_timelines": has_reporting_timelines,
            "has_expedited_reporting_procedure": has_expedited_reporting_procedure,
            "has_investigation_procedure": has_investigation_procedure,
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
            article_number=73,
            article_title="Reporting of Serious Incidents",
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
            article_number=73,
            article_title="Reporting of Serious Incidents",
            one_sentence=(
                "Providers of high-risk AI systems must report serious incidents to market "
                "surveillance authorities with differentiated timelines based on severity."
            ),
            official_summary=(
                "Art. 73 requires providers of high-risk AI systems to report serious "
                "incidents to market surveillance authorities of the Member States where "
                "the incident occurred. Reporting must be immediate and within 15 days "
                "(Art. 73(2)), with expedited deadlines for widespread infringement (2 days, "
                "Art. 73(3)) and incidents involving death (10 days, Art. 73(4)). Providers "
                "may submit an initial incomplete report followed by a complete report "
                "(Art. 73(5)). After a serious incident, providers must perform necessary "
                "investigations without delay, including risk assessment and corrective "
                "action (Art. 73(6))."
            ),
            related_articles={
                "Art. 6": "High-risk classification (prerequisite for Art. 73)",
                "Art. 9": "Risk management system (complementary risk processes)",
                "Art. 72": "Post-market monitoring (may trigger incident reporting)",
                "Art. 79": "Definition of when a system presents a risk",
                "Art. 26": "Deployer obligations (deployers also have reporting duties)",
            },
            recital=(
                "Recitals 134-136: Serious incidents require immediate reporting to "
                "ensure timely regulatory response and protect public safety."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Incident reporting procedure detection",
                    "Reporting timeline documentation detection",
                    "Expedited reporting procedure detection",
                    "Investigation procedure detection",
                ],
                "requires_human_judgment": [
                    "Whether incidents are correctly classified as serious",
                    "Whether reporting deadlines are met in practice",
                    "Whether an incident constitutes a widespread infringement",
                    "Whether the causal link between AI system and death is established",
                    "Whether investigations are sufficiently thorough",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) documented incident "
                "reporting procedure with authority contacts, (2) reporting timelines with "
                "15-day general deadline, (3) expedited procedures for widespread infringement "
                "(2 days) and death (10 days), (4) investigation methodology with risk "
                "assessment and corrective action. "
                "Based on: ISO/IEC 42001:2023, ISO 9001:2015 (nonconformity and corrective action)."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for AI incident reporting (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_incident_reporting_procedure") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 73(1)",
                action="Create a serious incident reporting procedure",
                details=(
                    "Art. 73(1) requires reporting serious incidents to market surveillance "
                    "authorities. Create documentation covering:\n"
                    "  - Definition of serious incident per the AI Act\n"
                    "  - Incident detection and classification procedures\n"
                    "  - Authority contact information per Member State\n"
                    "  - Reporting templates and required information\n"
                    "  - Escalation chain and responsible persons\n\n"
                    "Consider using docs/incident-reporting.md as the primary document."
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_reporting_timelines") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 73(2)",
                action="Document reporting timelines with 15-day deadline",
                details=(
                    "Art. 73(2) requires reporting immediately and not later than 15 days "
                    "after becoming aware of a serious incident. Document:\n"
                    "  - Timeline-based escalation tiers\n"
                    "  - SLA definitions for reporting deadlines\n"
                    "  - Automated alerting for approaching deadlines"
                ),
                effort="2-4 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_expedited_reporting_procedure") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 73(3)-(4)",
                action="Create expedited reporting procedures for severe incidents",
                details=(
                    "Art. 73(3) requires a 2-day deadline for widespread infringement. "
                    "Art. 73(4) requires a 10-day deadline for incidents involving death. "
                    "Create tiered escalation procedures covering:\n"
                    "  - Criteria for classifying widespread infringement\n"
                    "  - Criteria for fatal incident escalation\n"
                    "  - Expedited reporting workflow for each tier\n"
                    "  - On-call rotation with authority for expedited reporting"
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_investigation_procedure") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 73(6)",
                action="Create incident investigation and corrective action procedures",
                details=(
                    "Art. 73(6) requires performing necessary investigations without delay "
                    "after a serious incident. Create documentation covering:\n"
                    "  - Investigation methodology and root cause analysis\n"
                    "  - Risk assessment of the incident and its potential recurrence\n"
                    "  - Corrective action plan with timelines\n"
                    "  - Verification that corrective actions are effective\n"
                    "  - Documentation and lessons learned"
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 73(1)",
            action="Verify incident classification criteria align with AI Act definitions",
            details=(
                "Art. 73 requires classifying incidents as 'serious'. Verify your criteria "
                "align with the AI Act definition and that staff can distinguish between "
                "general incidents, widespread infringements, and fatal incidents."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=73,
            article_title="Reporting of Serious Incidents",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 73 is a provider obligation for high-risk AI systems. Incident reporting "
                "requires operational readiness and authority relationships beyond documentation. "
                "Based on ComplianceLint compliance checklist. Official CEN-CENELEC standards "
                "(expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art73Module:
    return Art73Module()
