"""
Article 52: Procedure for Classification and Notification of Systemic Risk — Module implementation.

Art. 52 covers the notification procedure when a GPAI model is classified as systemic risk:
  - Art. 52(1): Provider must notify Commission within 2 weeks of meeting threshold
  - Art. 52(2): Provider may present rebuttal arguments (permission, not obligation)
  - Art. 52(5): Reassessment request must contain objective, detailed and new reasons
  - Art. 52(5): Provider may request reassessment at earliest 6 months (permission)
  - Art. 52(6): Commission must publish/maintain systemic risk GPAI list (not provider obligation)

This module reads AI-provided compliance_answers["art52"] and maps each answer
to a Finding. No regex, keyword, or AST scanning is performed — detection is
entirely the AI's responsibility.

Obligation mapping:
  ART52-OBL-1  → has_commission_notification (provider obligation, manual, conditional)
  ART52-PERM-2 → UNABLE_TO_DETERMINE always (permission, not enforceable obligation)
  ART52-OBL-5  → UNABLE_TO_DETERMINE always (manual, reassessment request content)
  ART52-PERM-5 → UNABLE_TO_DETERMINE always (permission, reassessment request right)
  ART52-OBL-6  → UNABLE_TO_DETERMINE always (Commission obligation, not provider)

Boundary cases:
  - OBL-1 is a provider obligation with context_skip_field "is_gpai_with_systemic_risk".
    Uses _finding_from_answer() — has the provider notified the Commission?
  - PERM-2 is a permission (MAY) — not enforceable. Always UTD with informational note.
  - OBL-5 is a manual provider obligation — reassessment request content cannot be
    verified by code. Always UTD.
  - PERM-5 is a permission (MAY) — not enforceable. Always UTD with informational note.
  - OBL-6 is a Commission obligation — always UTD, informational only.
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


class Art52Module(BaseArticleModule):
    """Article 52: Procedure for Classification and Notification of Systemic Risk."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=52,
            article_title="Procedure for Classification and Notification of Systemic Risk",
        )

    # ── Scanning ──

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for Art. 52 compliance using AI-provided answers.

        Reads compliance_answers["art52"] from the AI context. Maps each field
        to obligation findings:
          - has_commission_notification → ART52-OBL-1
          - ART52-PERM-2 → always UTD (permission, not obligation)
          - ART52-OBL-5 → always UTD (manual, reassessment request content)
          - ART52-PERM-5 → always UTD (permission, reassessment request right)
          - ART52-OBL-6 → always UTD (Commission obligation)

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for Art. 52 notification procedure.
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

        answers = ctx.get_article_answers("art52")

        has_commission_notification = answers.get("has_commission_notification")
        notification_evidence = answers.get("notification_evidence", "")

        # ── ART52-OBL-1: Commission notification within 2 weeks ──
        # Art. 52(1): Provider SHALL notify Commission without delay and within
        # 2 weeks after systemic risk threshold is met.
        # Conditional on is_gpai_with_systemic_risk (handled by obligation engine).
        findings.append(self._finding_from_answer(
            obligation_id="ART52-OBL-1",
            answer=has_commission_notification,
            true_description=(
                "Evidence of Commission notification found. "
                "Verify the notification was made within 2 weeks of meeting "
                "the systemic risk threshold per Art. 52(1), and that it "
                "includes all required information."
                f"{(' Evidence: ' + notification_evidence) if notification_evidence else ''}"
            ),
            false_description=(
                "No evidence of Commission notification found. "
                "Art. 52(1) requires providers of GPAI models meeting the "
                "systemic risk threshold (Art. 51(1)(a)) to notify the Commission "
                "without delay and within two weeks."
            ),
            none_description=(
                "AI could not determine whether Commission notification has been made. "
                "Art. 52(1) requires notification within 2 weeks of meeting the "
                "systemic risk threshold. This is an organizational/legal matter "
                "that requires human review."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART52-PERM-2: Rebuttal right (permission) ──
        # Art. 52(2): Provider MAY present rebuttal arguments.
        # Permission, not obligation — always UTD, informational only.
        findings.append(Finding(
            obligation_id="ART52-PERM-2",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Provider may present substantiated arguments that the model "
                "does not present systemic risks despite meeting the threshold. "
                "This is a permission (MAY), not an obligation — exercising this "
                "right is a strategic/legal decision. No compliance action required."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART52-OBL-5: Reassessment request content (manual) ──
        # Art. 52(5): Reassessment request SHALL contain objective, detailed and
        # new reasons. Manual obligation — cannot be verified from code.
        # Always UTD.
        findings.append(Finding(
            obligation_id="ART52-OBL-5",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Reassessment request content requires human review. "
                "Art. 52(5) requires that any request to reassess systemic risk "
                "designation must contain objective, detailed and new reasons "
                "that have arisen since the designation decision. This is an "
                "organizational/legal matter that cannot be verified from code."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART52-PERM-5: Reassessment request right (permission) ──
        # Art. 52(5): Provider MAY request reassessment at earliest 6 months.
        # Permission, not obligation — always UTD, informational only.
        findings.append(Finding(
            obligation_id="ART52-PERM-5",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Provider may request reassessment of systemic risk designation "
                "at the earliest six months after the designation decision. "
                "This is a permission (MAY), not an obligation — exercising this "
                "right is a strategic/legal decision. No compliance action required."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART52-OBL-6: Commission publishes systemic risk list ──
        # Art. 52(6): Commission obligation — not a provider obligation.
        # Always UTD, informational only.
        findings.append(Finding(
            obligation_id="ART52-OBL-6",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Commission obligation to publish and maintain a list of "
                "general-purpose AI models with systemic risk. Not a provider "
                "obligation. Monitor the published list to verify your model's "
                "classification status."
            ),
            gap_type=GapType.PROCESS,
        ))

        details = {
            "has_commission_notification": has_commission_notification,
            "notification_evidence": notification_evidence,
            "note": (
                "Art. 52 covers the notification procedure for GPAI models classified "
                "as having systemic risk under Art. 51. The key provider obligation is "
                "notifying the Commission within 2 weeks. The provider also has a right "
                "(not obligation) to present rebuttal arguments against classification."
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
            article_number=52,
            article_title="Procedure for Classification and Notification of Systemic Risk",
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
            article_number=52,
            article_title="Procedure for Classification and Notification of Systemic Risk",
            one_sentence=(
                "Article 52 requires GPAI model providers to notify the Commission "
                "within two weeks when their model meets the systemic risk threshold."
            ),
            official_summary=(
                "Art. 52 establishes the notification procedure for GPAI models "
                "classified as having systemic risk under Art. 51. Providers must "
                "notify the Commission without delay and within two weeks of meeting "
                "the threshold (Art. 52(1)). Providers may present rebuttal arguments "
                "that the model does not present systemic risks despite meeting the "
                "threshold (Art. 52(2)). The Commission must publish and maintain a "
                "list of systemic risk GPAI models (Art. 52(6))."
            ),
            related_articles={
                "Art. 51": "Classification criteria for systemic risk GPAI models",
                "Art. 51(1)(a)": "Systemic risk threshold (high impact capabilities)",
                "Art. 55": "Additional obligations for systemic risk GPAI models",
                "Art. 89": "Scientific panel for qualified alerts",
                "Annex XIII": "Criteria for designation of systemic risk GPAI models",
            },
            recital=(
                "Recital 110: General-purpose AI models could pose systemic risks "
                "which include actual or reasonably foreseeable negative effects in "
                "relation to major accidents, disruptions of critical sectors, "
                "serious consequences to public health and safety."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of Commission notification documentation",
                ],
                "requires_human_judgment": [
                    "Whether the systemic risk threshold has been met",
                    "Whether Commission notification has been made within 2 weeks",
                    "Whether to exercise the rebuttal right under Art. 52(2)",
                    "Verification of notification content and timing",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 provides: (1) check for evidence "
                "of Commission notification documentation, (2) verify notification timing "
                "(within 2 weeks of threshold), (3) informational note about rebuttal right. "
                "Note: all obligations under Art. 52 require human judgment — automated "
                "scanning can only check for documentation of notification."
            ),
            enforcement_date="2025-08-02",
            waiting_for="CEN-CENELEC harmonized standard for GPAI notification (expected 2027)",
        )

    # ── Action Plan ──

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_commission_notification") is not True:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 52(1)",
                action="Notify the Commission of systemic risk classification",
                details=(
                    "Art. 52(1) requires notification to the Commission without delay "
                    "and within two weeks of meeting the systemic risk threshold. "
                    "Prepare and submit the notification with all required information "
                    "about the model and its capabilities."
                ),
                effort="2-4 hours (legal review recommended)",
                action_type="human_judgment_required",
            ))

        # Always: consider rebuttal right
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 52(2)",
            action="Consider whether to exercise rebuttal right",
            details=(
                "Art. 52(2) allows providers to present substantiated arguments "
                "that the model does not present systemic risks despite meeting "
                "the threshold. Evaluate whether this applies to your model and "
                "prepare arguments if appropriate."
            ),
            effort="4-8 hours (requires technical and legal analysis)",
            action_type="human_judgment_required",
        ))

        # Always: reassessment option
        actions.append(ActionItem(
            priority="LOW",
            article="Art. 52(5)",
            action="Consider reassessment request if circumstances change",
            details=(
                "Art. 52(5) allows providers to request reassessment of systemic "
                "risk designation at the earliest 6 months after designation. Any "
                "request must contain objective, detailed and new reasons that have "
                "arisen since the designation decision."
            ),
            effort="Ongoing — monitor for new reasons to request reassessment",
            action_type="human_judgment_required",
        ))

        # Always: monitor Commission list
        actions.append(ActionItem(
            priority="LOW",
            article="Art. 52(6)",
            action="Monitor Commission's published systemic risk GPAI list",
            details=(
                "The Commission publishes and maintains a list of GPAI models "
                "with systemic risk. Monitor this list to verify your model's "
                "classification status and track changes."
            ),
            effort="Ongoing — periodic review",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=52,
            article_title="Procedure for Classification and Notification of Systemic Risk",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 52 notification is primarily an organizational/legal matter. "
                "Automated scanning can only check for documentation of notification. "
                "Based on ComplianceLint compliance checklist; official CEN-CENELEC "
                "standards (expected 2027) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art52Module:
    return Art52Module()
