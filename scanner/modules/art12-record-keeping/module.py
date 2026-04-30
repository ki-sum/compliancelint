"""
Article 12: Record-keeping — Module implementation using unified protocol.

This module reads AI-provided compliance_answers["art12"] and maps each answer
to a Finding. No regex, keyword, or detector.py scanning is performed —
detection is entirely the AI's responsibility.

Obligation mapping:
  ART12-OBL-1   → has_logging
  ART12-OBL-2a  → has_retention_config + retention_days (>= 180 day minimum)
  ART12-OBL-2b  → has_logging (post-market monitoring aspect)
  ART12-OBL-2c  → UNABLE_TO_DETERMINE always (deployer monitoring requires human review)
"""

import os
import sys
from datetime import datetime, timezone

# Add core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.protocol import (
    BaseArticleModule, ScanResult, Explanation, ActionPlan, ActionItem,
    Finding, ComplianceLevel, Confidence, GapType,
)
from core.obligation_engine import ObligationEngine

RETENTION_MINIMUM_DAYS = 180


class Art12Module(BaseArticleModule):
    """Article 12: Record-keeping compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=12,
            article_title="Record-keeping",
        )

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for record-keeping compliance using AI-provided answers.

        Reads compliance_answers["art12"] from the AI context. Maps each field
        to obligation findings without any regex or file scanning.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for each record-keeping obligation.
        """
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

        answers = ctx.get_article_answers("art12")

        has_logging = answers.get("has_logging")                  # bool | None
        logging_description = answers.get("logging_description", "")
        logging_evidence = answers.get("logging_evidence", [])
        # Accept both "has_retention_config" and "has_retention_policy" (AI may use either)
        has_retention_config = answers.get("has_retention_config")  # bool | None
        if has_retention_config is None:
            has_retention_config = answers.get("has_retention_policy")
        retention_days = answers.get("retention_days")             # int | None
        retention_evidence = answers.get("retention_evidence", "")

        # ── ART12-OBL-1: Logging system ──
        findings.append(self._finding_from_answer(
            obligation_id="ART12-OBL-1",
            answer=has_logging,
            true_description=(
                f"Logging system detected: {logging_description or 'see evidence'}."
            ),
            false_description=(
                "No logging system detected. Art. 12(1) requires automatic recording of events."
            ),
            none_description=(
                "AI could not determine whether a logging system is present. "
                "Manual review of logging infrastructure required."
            ),
            evidence=logging_evidence,
            gap_type=GapType.CODE,
            file_path=logging_evidence[0].split(":")[0] if logging_evidence else "project-wide",
        ))

        # ── ART12-OBL-2a: Risk event logging (Art. 12(2)(a)) ──
        # Art. 12(2)(a) requires logging events that identify risk situations
        findings.append(self._finding_from_answer(
            obligation_id="ART12-OBL-2a",
            answer=has_logging,
            true_description=(
                f"Logging infrastructure present ({logging_description or 'see evidence'}). "
                "Verify logs capture events relevant for identifying risk situations "
                "per Art. 12(2)(a) and substantial modifications per Art. 79(1)."
            ),
            false_description=(
                "No logging infrastructure detected. Art. 12(2)(a) requires logging "
                "events relevant for identifying situations that may result in the "
                "system presenting a risk or undergoing substantial modification."
            ),
            none_description=(
                "AI could not determine whether risk event logging is in place. "
                "Art. 12(2)(a) requires logging risk-relevant events."
            ),
            evidence=logging_evidence,
            gap_type=GapType.CODE,
        ))

        # ── ART19-OBL-1b: Log retention (Art. 19(1) second clause) ──
        findings.append(self._make_retention_finding(
            has_retention_config=has_retention_config,
            retention_days=retention_days,
            retention_evidence=retention_evidence,
        ))

        # ── ART12-OBL-2b: Post-market monitoring (logging aspect) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART12-OBL-2b",
            answer=has_logging,
            true_description=(
                f"Logging infrastructure present ({logging_description or 'see evidence'}) "
                "and can support post-market monitoring per Art. 12(2)(b). "
                "Verify logs capture sufficient data for Art. 72 monitoring plan."
            ),
            false_description=(
                "No logging infrastructure detected. Art. 12(2)(b) requires logs to "
                "facilitate post-market monitoring (Art. 72)."
            ),
            none_description=(
                "AI could not determine whether logging supports post-market monitoring. "
                "Manual review of monitoring infrastructure required."
            ),
            evidence=logging_evidence,
            gap_type=GapType.CODE,
        ))

        # ── ART12-OBL-2c: Deployer operational monitoring ──
        # This always requires human review — AI cannot determine deployer access
        findings.append(Finding(
            obligation_id="ART12-OBL-2c",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Deployer operational monitoring requires human review. "
                "Art. 12(2)(c) requires logs to support deployer operational monitoring "
                "(Art. 26(5)). AI cannot determine from code whether deployers can "
                "access operational logs — confirm health endpoints, log export, or "
                "monitoring dashboards are available to deployers."
            ),
            remediation=(
                "Add health/status endpoints (/health, /status, /metrics), "
                "log export capability, or a monitoring dashboard accessible to deployers."
            ),
            gap_type=GapType.PROCESS,
        ))

        # Build details dict
        details = {
            "has_logging": has_logging,
            "logging_description": logging_description,
            "has_retention_config": has_retention_config,
            "retention_days": retention_days,
            "retention_minimum_days": RETENTION_MINIMUM_DAYS,
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
            article_number=12,
            article_title="Record-keeping",
            project_path=project_path,
            scan_date=datetime.now(timezone.utc).isoformat(),
            files_scanned=file_count,
            language_detected=language,
            overall_level=self._compute_overall_level(findings),
            overall_confidence=Confidence.MEDIUM,
            findings=findings,
            details=details,
        )

    # ── Private helpers ──

    def _make_retention_finding(
        self,
        has_retention_config,
        retention_days,
        retention_evidence: str,
    ) -> Finding:
        """Build the ART19-OBL-1b retention finding from AI answers.

        Rules:
          - has_retention_config=True, retention_days >= 180  → PARTIAL (compliant threshold)
          - has_retention_config=True, retention_days < 180   → NON_COMPLIANT
          - has_retention_config=True, retention_days=None    → PARTIAL (period unknown)
          - has_retention_config=False                        → NON_COMPLIANT
          - has_retention_config=None                         → UNABLE_TO_DETERMINE
        """
        if has_retention_config is None:
            return Finding(
                obligation_id="ART19-OBL-1b",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "AI could not determine whether a log retention policy is configured. "
                    f"Art. 19(1) requires a minimum of {RETENTION_MINIMUM_DAYS} days (6 months). "
                    f"{('Evidence: ' + retention_evidence) if retention_evidence else ''}"
                ),
                gap_type=GapType.CODE,
            )

        if has_retention_config is False:
            return Finding(
                obligation_id="ART19-OBL-1b",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NON_COMPLIANT,
                confidence=Confidence.MEDIUM,
                description=(
                    f"No retention policy configured. "
                    f"Art. 19(1) requires a minimum of {RETENTION_MINIMUM_DAYS} days (6 months)."
                ),
                remediation=(
                    f"Configure log retention for at least {RETENTION_MINIMUM_DAYS} days. "
                    "Options: logrotate (rotate 180), Docker json-file max-file:180, "
                    "AWS CloudWatch retention_in_days:180, or equivalent."
                ),
                gap_type=GapType.CODE,
            )

        # has_retention_config is True
        if retention_days is None:
            return Finding(
                obligation_id="ART19-OBL-1b",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.PARTIAL,
                confidence=Confidence.LOW,
                description=(
                    "Retention configuration found but period could not be determined. "
                    f"Art. 19(1) requires a minimum of {RETENTION_MINIMUM_DAYS} days (6 months). "
                    f"{('Evidence: ' + retention_evidence) if retention_evidence else ''}"
                ),
                remediation=(
                    f"Verify the configured retention period meets the {RETENTION_MINIMUM_DAYS}-day minimum."
                ),
                gap_type=GapType.CODE,
            )

        if retention_days >= RETENTION_MINIMUM_DAYS:
            return Finding(
                obligation_id="ART19-OBL-1b",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.PARTIAL,
                confidence=Confidence.MEDIUM,
                description=(
                    f"Retention configured: {retention_days} days "
                    f"(>= {RETENTION_MINIMUM_DAYS}-day minimum per Art. 19(1)). "
                    f"{('Evidence: ' + retention_evidence) if retention_evidence else ''}"
                ),
                gap_type=GapType.CODE,
            )
        else:
            return Finding(
                obligation_id="ART19-OBL-1b",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NON_COMPLIANT,
                confidence=Confidence.MEDIUM,
                description=(
                    f"Retention of {retention_days} days is below the "
                    f"{RETENTION_MINIMUM_DAYS}-day minimum required by Art. 19(1). "
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
            article_number=12,
            article_title="Record-keeping",
            one_sentence="High-risk AI systems must automatically log events throughout their lifetime.",
            official_summary=(
                "Art. 12 requires providers of high-risk AI systems to build in automatic "
                "event logging. Logs must capture data relevant to: (a) identifying risk "
                "situations, (b) post-market monitoring, and (c) deployer operational "
                "monitoring. For biometric ID systems, additional minimum logging is required."
            ),
            related_articles={
                "Art. 19": "Log retention: minimum 6 months",
                "Art. 72": "Post-market monitoring (logs must support this)",
                "Art. 26(5)": "Deployer must be able to monitor via logs",
                "Art. 14(5)": "Human verification of biometric results must be logged",
                "Art. 79(1)": "Definition of when a system 'presents a risk'",
            },
            recital=(
                "Recital 71: Logging is required to 'enable traceability, verify compliance, "
                "and facilitate post-market monitoring.'"
            ),
            automation_summary={
                "fully_automatable": [
                    "Logging framework detection",
                    "Endpoint logging coverage",
                    "Session timestamp logging (biometric systems)",
                    "Database reference logging (biometric systems)",
                    "Human verifier ID logging (biometric systems)",
                ],
                "partially_automatable": [
                    "Risk event logging completeness",
                    "Post-market monitoring data sufficiency",
                    "Deployer monitoring capability",
                    "Retention period appropriateness",
                ],
                "requires_human_judgment": [],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) structured logging framework, "
                "(2) >= 90% endpoint coverage, (3) minimum fields: timestamp, event_type, "
                "correlation_id, (4) 6-month retention minimum, (5) tamper protection "
                "(SHOULD for general, MUST for biometric systems). "
                "Based on: ISO/IEC DIS 24970:2025, ISO 42001, ISO 27001 A.12.4."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_logging") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 12(1)",
                action="Install a structured logging framework",
                details=(
                    "Art. 12(1) requires 'automatic recording of events.' Install structlog, loguru, or stdlib logging with JSON formatter.\n"
                    "\n"
                    "  Quick-start fix:\n"
                    "\n"
                    "    pip install structlog\n"
                    "\n"
                    "    # logging_config.py — add to your project root\n"
                    "    import structlog\n"
                    "    import logging\n"
                    "\n"
                    "    structlog.configure(\n"
                    "        processors=[\n"
                    "            structlog.stdlib.add_log_level,\n"
                    "            structlog.processors.TimeStamper(fmt=\"iso\"),\n"
                    "            structlog.processors.JSONRenderer(),\n"
                    "        ],\n"
                    "        wrapper_class=structlog.stdlib.BoundLogger,\n"
                    "        logger_factory=structlog.stdlib.LoggerFactory(),\n"
                    "    )\n"
                    "    logger = structlog.get_logger()"
                ),
                effort="1-2 hours",
            ))

        if details.get("has_retention_config") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 19(1)",
                action=f"Configure log retention policy (>= {RETENTION_MINIMUM_DAYS} days / 6 months)",
                details=(
                    f"Art. 19(1) explicitly requires minimum {RETENTION_MINIMUM_DAYS}-day log retention.\n"
                    "\n"
                    "  Option A: logrotate (Linux)\n"
                    "\n"
                    "    # /etc/logrotate.d/ai-system\n"
                    "    /var/log/ai-system/*.log {\n"
                    "        daily\n"
                    f"        rotate {RETENTION_MINIMUM_DAYS}       # 6 months minimum (Art. 19)\n"
                    "        compress\n"
                    "        notifempty\n"
                    "    }\n"
                    "\n"
                    "  Option B: Docker Compose\n"
                    "\n"
                    "    logging:\n"
                    "      driver: \"json-file\"\n"
                    "      options:\n"
                    "        max-size: \"100m\"\n"
                    f"        max-file: \"{RETENTION_MINIMUM_DAYS}\"   # ~6 months of daily logs\n"
                    "\n"
                    "  Option C: Cloud (AWS CloudWatch)\n"
                    "\n"
                    f"    retention_in_days: {RETENTION_MINIMUM_DAYS}  # 6 months minimum"
                ),
                effort="1 hour",
            ))
        elif (
            details.get("has_retention_config") is True
            and details.get("retention_days") is not None
            and details["retention_days"] < RETENTION_MINIMUM_DAYS
        ):
            current_days = details["retention_days"]
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 19(1)",
                action=f"Increase log retention from {current_days} to >= {RETENTION_MINIMUM_DAYS} days",
                details=(
                    f"Current retention of {current_days} days is below the "
                    f"{RETENTION_MINIMUM_DAYS}-day minimum required by Art. 19(1). "
                    f"Update your retention configuration to at least {RETENTION_MINIMUM_DAYS} days."
                ),
                effort="30 minutes",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 12(2)(a)",
            action="Define risk events specific to your AI system",
            details="What events, for YOUR specific system, indicate it is 'presenting a risk' (Art. 79(1))? Document in a risk event catalogue.",
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="LOW",
            article="Art. 12(2)(c)",
            action="Verify deployer can access operational logs",
            details="If deployed by a third party, Art. 12(2)(c) requires logs to support their monitoring.",
            effort="1 hour",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=12,
            article_title="Record-keeping",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer="Based on ComplianceLint compliance checklist. Official CEN-CENELEC standards (expected Q4 2026) may modify these requirements.",
        )


# Module entry point — used by auto-discovery
def create_module() -> Art12Module:
    return Art12Module()
