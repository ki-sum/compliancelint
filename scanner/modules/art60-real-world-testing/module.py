"""
Article 60: Testing of high-risk AI systems in real world conditions — Module implementation.

Art. 60 requires providers conducting real-world testing of Annex III high-risk AI
systems outside regulatory sandboxes to meet specific conditions: testing plan with
authority approval, incident reporting and mitigation, authority notification of
outcomes, and liability for testing damage.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art60"). No regex or keyword scanning is performed.

Obligation mapping:
  ART60-OBL-4   → has_testing_plan (testing plan drawn up, submitted, approved, registered)
  ART60-OBL-7   → has_incident_reporting_for_testing (serious incident reporting + mitigation + recall)
  ART60-OBL-8   → has_authority_notification_procedure (notify suspension/termination/outcomes)
  ART60-OBL-9   → manual always UTD (liability for testing damage)

Scope gate: conducts_real_world_testing — all obligations skip when false.
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


class Art60Module(BaseArticleModule):
    """Article 60: Testing of high-risk AI systems in real world conditions compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=60,
            article_title="Testing of high-risk AI systems in real world conditions",
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

        answers = ctx.get_article_answers("art60")

        has_testing_plan = answers.get("has_testing_plan")
        has_incident_reporting_for_testing = answers.get("has_incident_reporting_for_testing")
        has_authority_notification_procedure = answers.get("has_authority_notification_procedure")

        # ── ART60-OBL-4: Real-world testing plan (Art. 60(4)) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART60-OBL-4",
            answer=has_testing_plan,
            true_description=(
                "Real-world testing plan detected. "
                "Verify it covers: (a) submission to market surveillance authority, "
                "(b) authority approval, (c) EU database registration with unique ID, "
                "(d) provider EU establishment or legal representative, "
                "(e) data transfer safeguards, (f) 6-month duration limit, "
                "(g) vulnerable group protections, (h) deployer instructions per Art. 13, "
                "(i) informed consent per Art. 61, (j) effective oversight by qualified persons, "
                "(k) reversibility of AI decisions."
            ),
            false_description=(
                "No real-world testing plan detected. "
                "Art. 60(4) requires providers to draw up a testing plan and submit it to "
                "the market surveillance authority before conducting testing in real world "
                "conditions. The plan must address all 12 conditions in Art. 60(4)(a)-(l)."
            ),
            none_description=(
                "AI could not determine whether a real-world testing plan exists. "
                "Art. 60(4) requires a comprehensive testing plan submitted to the market "
                "surveillance authority."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART60-OBL-7: Serious incident reporting and mitigation (Art. 60(7)) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART60-OBL-7",
            answer=has_incident_reporting_for_testing,
            true_description=(
                "Incident reporting procedure for real-world testing detected. "
                "Verify it covers: (a) serious incident reporting to market surveillance "
                "authority per Art. 73, (b) immediate mitigation measures or testing suspension, "
                "(c) prompt recall procedure upon testing termination."
            ),
            false_description=(
                "No incident reporting procedure for real-world testing detected. "
                "Art. 60(7) requires: reporting serious incidents to the national market "
                "surveillance authority per Art. 73, adopting immediate mitigation measures "
                "or suspending testing, and establishing a prompt recall procedure."
            ),
            none_description=(
                "AI could not determine whether an incident reporting procedure for "
                "real-world testing exists. Art. 60(7) requires incident reporting, "
                "mitigation, and recall procedures."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART60-OBL-8: Authority notification of suspension/termination/outcomes (Art. 60(8)) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART60-OBL-8",
            answer=has_authority_notification_procedure,
            true_description=(
                "Authority notification procedure detected. "
                "Verify it covers notifying the market surveillance authority of: "
                "(a) testing suspension or termination, and (b) final outcomes of testing."
            ),
            false_description=(
                "No authority notification procedure detected. "
                "Art. 60(8) requires providers to notify the national market surveillance "
                "authority of the suspension or termination of testing and the final outcomes."
            ),
            none_description=(
                "AI could not determine whether an authority notification procedure exists. "
                "Art. 60(8) requires notification of testing suspension/termination and outcomes."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART60-OBL-9: Liability for testing damage (Art. 60(9)) ──
        # Always requires human review — AI cannot determine liability coverage
        findings.append(Finding(
            obligation_id="ART60-OBL-9",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Liability for real-world testing damage requires human review. "
                "Art. 60(9) states the provider shall be liable under applicable Union "
                "and national liability law for any damage caused during real-world testing. "
                "Verify insurance policies, liability coverage, and indemnification agreements."
            ),
            remediation=(
                "Obtain appropriate liability insurance or indemnification coverage for "
                "real-world testing. Consult legal counsel to ensure compliance with "
                "applicable Union and national liability law."
            ),
            gap_type=GapType.PROCESS,
        ))

        # Build details dict
        details = {
            "has_testing_plan": has_testing_plan,
            "has_incident_reporting_for_testing": has_incident_reporting_for_testing,
            "has_authority_notification_procedure": has_authority_notification_procedure,
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
            article_number=60,
            article_title="Testing of high-risk AI systems in real world conditions",
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
            article_number=60,
            article_title="Testing of high-risk AI systems in real world conditions",
            one_sentence=(
                "Providers testing Annex III high-risk AI systems in real world conditions "
                "must follow strict testing plans, incident reporting, and authority notification procedures."
            ),
            official_summary=(
                "Art. 60 governs testing of high-risk AI systems in real world conditions "
                "outside regulatory sandboxes. Providers must: (1) draw up and submit a "
                "real-world testing plan to the market surveillance authority (Art. 60(4)); "
                "(2) meet 12 conditions including authority approval, EU database registration, "
                "informed consent, effective oversight, and reversible decisions (Art. 60(4)(a)-(l)); "
                "(3) report serious incidents and adopt immediate mitigation or suspend testing "
                "(Art. 60(7)); (4) notify the authority of suspension/termination and final "
                "outcomes (Art. 60(8)); (5) be liable for any damage caused during testing "
                "(Art. 60(9))."
            ),
            related_articles={
                "Art. 6": "High-risk classification (prerequisite for Art. 60)",
                "Art. 13": "Transparency — deployer instructions referenced in Art. 60(4)(j)",
                "Art. 57": "AI regulatory sandboxes (Art. 60 is for testing OUTSIDE sandboxes)",
                "Art. 61": "Informed consent of test subjects referenced in Art. 60(4)(k)",
                "Art. 73": "Serious incident reporting referenced in Art. 60(7)",
                "Annex III": "High-risk AI system categories (Art. 60 applies to Annex III systems)",
                "Annex IX": "Real-world testing plan content requirements",
            },
            recital=(
                "Recital 140: Testing in real world conditions outside regulatory sandboxes "
                "should be subject to specific conditions and safeguards to protect the "
                "rights and safety of test subjects."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Testing plan documentation detection",
                    "Incident reporting procedure detection",
                    "Authority notification procedure detection",
                ],
                "requires_human_judgment": [
                    "Whether testing plan meets all 12 conditions of Art. 60(4)",
                    "Whether authority approval has been obtained",
                    "Whether informed consent procedures are adequate per Art. 61",
                    "Whether oversight persons are suitably qualified",
                    "Whether liability coverage is adequate",
                    "Whether data transfer safeguards are appropriate",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) documented real-world "
                "testing plan per Annex IX, (2) authority submission and approval records, "
                "(3) EU database registration with unique ID, (4) incident reporting procedure "
                "per Art. 73, (5) testing suspension/mitigation protocol, (6) recall procedure, "
                "(7) authority notification procedure for outcomes, (8) liability insurance or "
                "indemnification. Based on: EU AI Act Art. 60, Annex IX."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for AI real-world testing (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_testing_plan") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 60(4)",
                action="Create a real-world testing plan per Annex IX",
                details=(
                    "Art. 60(4) requires a comprehensive testing plan before conducting "
                    "real-world testing. The plan must cover all 12 conditions:\n"
                    "  - Testing plan submission to market surveillance authority\n"
                    "  - Authority approval obtained before testing begins\n"
                    "  - EU database registration with unique identification number\n"
                    "  - Provider established in the Union or legal representative appointed\n"
                    "  - Data transfer safeguards for third countries\n"
                    "  - Testing duration limited to 6 months (extendable by 6 months)\n"
                    "  - Vulnerable group protections (age, disability)\n"
                    "  - Deployer instructions per Art. 13\n"
                    "  - Informed consent procedures per Art. 61\n"
                    "  - Effective oversight by qualified persons\n"
                    "  - Reversibility of AI system decisions\n\n"
                    "Use Annex IX as the template for the testing plan content."
                ),
                effort="16-40 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_incident_reporting_for_testing") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 60(7)",
                action="Create incident reporting and mitigation procedure for real-world testing",
                details=(
                    "Art. 60(7) requires:\n"
                    "  - Serious incident reporting to national market surveillance authority per Art. 73\n"
                    "  - Immediate mitigation measures or testing suspension upon serious incident\n"
                    "  - Prompt recall procedure for the AI system upon testing termination\n\n"
                    "Create a dedicated testing incident response plan that covers detection, "
                    "assessment, mitigation, authority notification, and recall procedures."
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_authority_notification_procedure") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 60(8)",
                action="Create authority notification procedure for testing outcomes",
                details=(
                    "Art. 60(8) requires notifying the market surveillance authority of:\n"
                    "  - Testing suspension or termination\n"
                    "  - Final outcomes of real-world testing\n\n"
                    "Establish a procedure for formal notification including contact details, "
                    "templates, and timeline for communication."
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="HIGH",
            article="Art. 60(9)",
            action="Verify liability coverage for real-world testing damage",
            details=(
                "Art. 60(9) states providers shall be liable for any damage caused "
                "during real-world testing. Verify:\n"
                "  - Adequate insurance policies or indemnification agreements\n"
                "  - Coverage aligned with Union and national liability law\n"
                "  - Coverage scope includes all test subjects and affected persons"
            ),
            effort="4-8 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 60(4)",
            action="Verify real-world testing plan meets all 12 conditions",
            details=(
                "Even if a testing plan exists, verify it addresses all conditions "
                "in Art. 60(4)(a)-(l) including informed consent per Art. 61, "
                "vulnerable group protections, and effective oversight provisions."
            ),
            effort="4-8 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=60,
            article_title="Testing of high-risk AI systems in real world conditions",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 60 applies to providers testing Annex III high-risk AI systems in "
                "real world conditions outside regulatory sandboxes. Testing requires prior "
                "authority approval. Based on ComplianceLint compliance checklist. Official "
                "CEN-CENELEC standards (expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art60Module:
    return Art60Module()
