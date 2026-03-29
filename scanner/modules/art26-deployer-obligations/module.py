"""
Article 26: Obligations of Deployers of High-Risk AI Systems — Module implementation.

Art. 26 requires deployers of high-risk AI systems to comply with 11 obligations
covering use-per-instructions, human oversight, input data quality, operational
monitoring, log retention, worker notification, public authority registration,
DPIA, biometric authorisation, affected person notification, and authority cooperation.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art26"). No regex or keyword scanning is performed.

Obligation mapping:
  ART26-OBL-1   → has_deployment_documentation (use per instructions)
  ART26-OBL-2   → has_human_oversight_assignment (oversight assigned)
  ART26-OBL-4   → handled by gap_findings (conditional: deployer_controls_input_data)
  ART26-OBL-5   → has_operational_monitoring (monitoring)
  ART26-OBL-6   → has_log_retention + retention_days (>= 180 day minimum)
  ART26-OBL-7   → handled by gap_findings (conditional: is_workplace_deployment, manual)
  ART26-OBL-8   → handled by gap_findings (conditional: is_public_authority, manual)
  ART26-OBL-9   → handled by gap_findings (conditional: requires_dpia, manual)
  ART26-OBL-10  → handled by gap_findings (conditional: is_post_remote_biometric_id, manual)
  ART26-OBL-11  → has_affected_persons_notification (inform affected persons)
  ART26-OBL-12  → handled by gap_findings (manual — authority cooperation)

NOTE — "handled by gap_findings" means:
  ObligationEngine.gap_findings() auto-generates the finding for any obligation
  in the JSON that this scan() has NOT explicitly emitted a Finding for.

  Rules (see obligation_engine.py gap_findings() docstring for full detail):
  - obligation with scope_limitation → CONDITIONAL/APPLICABLE/NOT_APPLICABLE
  - obligation (manual, no scope_limitation) → UNABLE_TO_DETERMINE [COVERAGE GAP]

  Consequence for maintenance:
  Do NOT add a findings.append() here for new obligations added to the JSON.
  gap_findings() will handle them automatically. Only add explicit scan() code
  when you need to map a compliance_answers field to that obligation's level.
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

RETENTION_MINIMUM_DAYS = 180


class Art26Module(BaseArticleModule):
    """Article 26: Obligations of Deployers of High-Risk AI Systems."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=26,
            article_title="Obligations of Deployers of High-Risk AI Systems",
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

        answers = ctx.get_article_answers("art26")

        has_deployment_documentation = answers.get("has_deployment_documentation")
        has_human_oversight_assignment = answers.get("has_human_oversight_assignment")
        has_operational_monitoring = answers.get("has_operational_monitoring")
        has_log_retention = answers.get("has_log_retention")
        retention_days = answers.get("retention_days")
        retention_evidence = answers.get("retention_evidence", "")
        has_affected_persons_notification = answers.get("has_affected_persons_notification")

        # ── ART26-OBL-1: Use per instructions (deployment documentation) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART26-OBL-1",
            answer=has_deployment_documentation,
            true_description=(
                "Deployment documentation found referencing provider instructions for use. "
                "Verify it covers all provider-specified operational parameters."
            ),
            false_description=(
                "No deployment documentation referencing provider instructions found. "
                "Art. 26(1) requires deployers to take measures ensuring use in accordance "
                "with the instructions for use."
            ),
            none_description=(
                "AI could not determine whether deployment documentation exists. "
                "Art. 26(1) requires use in accordance with provider instructions."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART26-OBL-2: Human oversight assignment ──
        findings.append(self._finding_from_answer(
            obligation_id="ART26-OBL-2",
            answer=has_human_oversight_assignment,
            true_description=(
                "Human oversight assignment documentation found. "
                "Verify assigned persons have necessary competence, training, and authority."
            ),
            false_description=(
                "No human oversight assignment found. Art. 26(2) requires deployers to "
                "assign human oversight to natural persons with necessary competence, "
                "training and authority."
            ),
            none_description=(
                "AI could not determine whether human oversight has been assigned. "
                "Art. 26(2) requires assignment to competent natural persons."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART26-OBL-5: Operational monitoring ──
        findings.append(self._finding_from_answer(
            obligation_id="ART26-OBL-5",
            answer=has_operational_monitoring,
            true_description=(
                "Operational monitoring detected. Verify monitoring follows provider "
                "instructions for use and covers risk identification per Art. 79(1)."
            ),
            false_description=(
                "No operational monitoring detected. Art. 26(5) requires deployers to "
                "monitor the operation of the high-risk AI system on the basis of "
                "the instructions for use."
            ),
            none_description=(
                "AI could not determine whether operational monitoring is in place. "
                "Art. 26(5) requires monitoring per instructions for use."
            ),
            gap_type=GapType.CODE,
        ))

        # ── ART26-OBL-6: Log retention (>= 6 months / 180 days) ──
        # Multi-value comparison: needs custom logic (boundary case #5)
        findings.append(self._make_retention_finding(
            has_log_retention=has_log_retention,
            retention_days=retention_days,
            retention_evidence=retention_evidence,
        ))

        # ── ART26-OBL-11: Inform affected persons ──
        findings.append(self._finding_from_answer(
            obligation_id="ART26-OBL-11",
            answer=has_affected_persons_notification,
            true_description=(
                "Affected persons notification mechanism detected. Verify natural persons "
                "are informed they are subject to the high-risk AI system."
            ),
            false_description=(
                "No affected persons notification found. Art. 26(11) requires deployers "
                "to inform natural persons that they are subject to the use of the "
                "high-risk AI system."
            ),
            none_description=(
                "AI could not determine whether affected persons are notified. "
                "Art. 26(11) requires notification to natural persons."
            ),
            gap_type=GapType.PROCESS,
        ))

        # Build details dict
        details = {
            "has_deployment_documentation": has_deployment_documentation,
            "has_human_oversight_assignment": has_human_oversight_assignment,
            "has_operational_monitoring": has_operational_monitoring,
            "has_log_retention": has_log_retention,
            "retention_days": retention_days,
            "retention_minimum_days": RETENTION_MINIMUM_DAYS,
            "has_affected_persons_notification": has_affected_persons_notification,
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
            article_number=26,
            article_title="Obligations of Deployers of High-Risk AI Systems",
            project_path=project_path,
            scan_date=datetime.now(timezone.utc).isoformat(),
            files_scanned=file_count,
            language_detected=language,
            overall_level=self._compute_overall_level(findings),
            overall_confidence=Confidence.LOW,
            findings=findings,
            details=details,
        )

    # ── Private helpers ──

    def _make_retention_finding(
        self,
        has_log_retention,
        retention_days,
        retention_evidence: str,
    ) -> Finding:
        """Build the ART26-OBL-6 retention finding from AI answers.

        Rules (same threshold as Art. 19(1) — 6 months / 180 days):
          - has_log_retention=True, retention_days >= 180  → PARTIAL
          - has_log_retention=True, retention_days < 180   → NON_COMPLIANT
          - has_log_retention=True, retention_days=None    → PARTIAL (period unknown)
          - has_log_retention=False                        → NON_COMPLIANT
          - has_log_retention=None                         → UNABLE_TO_DETERMINE
        """
        if has_log_retention is None:
            return Finding(
                obligation_id="ART26-OBL-6",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "AI could not determine whether log retention is configured. "
                    f"Art. 26(6) requires a minimum of {RETENTION_MINIMUM_DAYS} days (6 months). "
                    f"{('Evidence: ' + retention_evidence) if retention_evidence else ''}"
                ),
                gap_type=GapType.CODE,
            )

        if has_log_retention is False:
            return Finding(
                obligation_id="ART26-OBL-6",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NON_COMPLIANT,
                confidence=Confidence.MEDIUM,
                description=(
                    "No log retention policy configured. "
                    f"Art. 26(6) requires keeping logs for at least {RETENTION_MINIMUM_DAYS} days (6 months)."
                ),
                remediation=(
                    f"Configure log retention for at least {RETENTION_MINIMUM_DAYS} days. "
                    "Options: logrotate, cloud log retention settings, or database archival policy."
                ),
                gap_type=GapType.CODE,
            )

        # has_log_retention is True
        if retention_days is None:
            return Finding(
                obligation_id="ART26-OBL-6",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.PARTIAL,
                confidence=Confidence.LOW,
                description=(
                    "Log retention configuration found but period could not be determined. "
                    f"Art. 26(6) requires a minimum of {RETENTION_MINIMUM_DAYS} days (6 months). "
                    f"{('Evidence: ' + retention_evidence) if retention_evidence else ''}"
                ),
                remediation=(
                    f"Verify the configured retention period meets the {RETENTION_MINIMUM_DAYS}-day minimum."
                ),
                gap_type=GapType.CODE,
            )

        if retention_days >= RETENTION_MINIMUM_DAYS:
            return Finding(
                obligation_id="ART26-OBL-6",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.PARTIAL,
                confidence=Confidence.MEDIUM,
                description=(
                    f"Log retention configured: {retention_days} days "
                    f"(>= {RETENTION_MINIMUM_DAYS}-day minimum per Art. 26(6)). "
                    f"{('Evidence: ' + retention_evidence) if retention_evidence else ''}"
                ),
                gap_type=GapType.CODE,
            )
        else:
            return Finding(
                obligation_id="ART26-OBL-6",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NON_COMPLIANT,
                confidence=Confidence.MEDIUM,
                description=(
                    f"Log retention of {retention_days} days is below the "
                    f"{RETENTION_MINIMUM_DAYS}-day minimum required by Art. 26(6). "
                    f"{('Evidence: ' + retention_evidence) if retention_evidence else ''}"
                ),
                remediation=(
                    f"Increase log retention to at least {RETENTION_MINIMUM_DAYS} days "
                    f"(currently {retention_days} days)."
                ),
                gap_type=GapType.CODE,
            )

    def explain(self) -> Explanation:
        return Explanation(
            article_number=26,
            article_title="Obligations of Deployers of High-Risk AI Systems",
            one_sentence=(
                "Deployers of high-risk AI systems must use them per instructions, assign "
                "human oversight, monitor operations, retain logs, and inform affected persons."
            ),
            official_summary=(
                "Art. 26 sets out obligations for deployers (users) of high-risk AI systems. "
                "Deployers must: (1) use systems per provider instructions, (2) assign human "
                "oversight to competent persons, (4) ensure input data quality where they control it, "
                "(5) monitor system operation, (6) retain auto-generated logs for at least 6 months, "
                "(7) inform workers if used in the workplace, (8) register in EU database if public "
                "authority, (9) conduct DPIA where required, (10) obtain judicial authorisation for "
                "post-remote biometric ID, (11) inform affected natural persons, and (12) cooperate "
                "with competent authorities."
            ),
            related_articles={
                "Art. 13": "Transparency information that deployers must use",
                "Art. 14": "Human oversight requirements (provider side)",
                "Art. 49": "EU database registration (public authority deployers)",
                "Art. 50": "Transparency obligations (affected persons)",
                "Art. 72": "Post-market monitoring (provider informs deployer)",
                "Art. 79(1)": "Definition of when a system 'presents a risk'",
            },
            recital=(
                "Recital 93: Deployers play a critical role in the chain of compliance. "
                "They must ensure the system is used as intended and monitor its operation."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Deployment documentation detection",
                    "Human oversight assignment documentation",
                    "Operational monitoring infrastructure",
                    "Log retention configuration",
                    "Affected persons notification mechanism",
                ],
                "requires_human_judgment": [
                    "Whether system is actually used per instructions",
                    "Whether oversight persons have necessary competence",
                    "Input data representativeness assessment",
                    "Worker notification compliance (labor law)",
                    "EU database registration completion",
                    "DPIA adequacy",
                    "Judicial authorisation for biometric ID",
                    "Authority cooperation procedures",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) deployment documentation "
                "referencing provider instructions, (2) documented human oversight assignment with "
                "competency records, (3) operational monitoring infrastructure, (4) log retention "
                ">= 180 days, (5) notification mechanism for affected persons. "
                "Based on: ISO/IEC 42001:2023, ISO/IEC 23894:2023."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for deployer obligations (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_deployment_documentation") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 26(1)",
                action="Create deployment documentation referencing provider instructions",
                details=(
                    "Art. 26(1) requires deployers to take measures ensuring use in accordance "
                    "with the instructions for use. Create a deployment guide that references "
                    "the provider's instructions and documents how your deployment complies."
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_human_oversight_assignment") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 26(2)",
                action="Assign human oversight to competent persons",
                details=(
                    "Art. 26(2) requires deployers to assign human oversight to natural persons "
                    "with necessary competence, training, and authority. Document the assignment "
                    "and competency requirements."
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_operational_monitoring") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 26(5)",
                action="Set up operational monitoring for the AI system",
                details=(
                    "Art. 26(5) requires monitoring the operation on the basis of the instructions "
                    "for use. Implement health checks, alerting, and monitoring dashboards."
                ),
                effort="4-16 hours",
            ))

        if details.get("has_log_retention") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 26(6)",
                action=f"Configure log retention (>= {RETENTION_MINIMUM_DAYS} days / 6 months)",
                details=(
                    f"Art. 26(6) requires keeping auto-generated logs for at least "
                    f"{RETENTION_MINIMUM_DAYS} days. Configure retention via logrotate, "
                    f"cloud log settings, or database archival."
                ),
                effort="1-2 hours",
            ))
        elif (
            details.get("has_log_retention") is True
            and details.get("retention_days") is not None
            and details["retention_days"] < RETENTION_MINIMUM_DAYS
        ):
            current_days = details["retention_days"]
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 26(6)",
                action=f"Increase log retention from {current_days} to >= {RETENTION_MINIMUM_DAYS} days",
                details=(
                    f"Current retention of {current_days} days is below the "
                    f"{RETENTION_MINIMUM_DAYS}-day minimum required by Art. 26(6)."
                ),
                effort="30 minutes",
            ))

        if details.get("has_affected_persons_notification") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 26(11)",
                action="Implement affected persons notification",
                details=(
                    "Art. 26(11) requires informing natural persons that they are subject "
                    "to the use of a high-risk AI system. Add disclosure notices, consent "
                    "forms, or notification mechanisms."
                ),
                effort="2-4 hours",
            ))

        # Always add human judgment items for conditional/manual obligations
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 26(7)",
            action="Assess worker notification requirements",
            details=(
                "If deploying in a workplace, Art. 26(7) requires informing workers' "
                "representatives and affected workers before deployment."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="LOW",
            article="Art. 26(12)",
            action="Establish authority cooperation procedures",
            details=(
                "Art. 26(12) requires cooperation with competent authorities. "
                "Document a point of contact and cooperation procedures."
            ),
            effort="1-2 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=26,
            article_title="Obligations of Deployers of High-Risk AI Systems",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 26 is a deployer-addressed article. Many obligations are organizational "
                "processes that cannot be fully verified from code. Human expert review is essential. "
                "Based on ComplianceLint compliance checklist. Official CEN-CENELEC standards "
                "(expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art26Module:
    return Art26Module()
