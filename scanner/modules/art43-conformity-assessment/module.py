"""
Article 43: Conformity Assessment — Module implementation using unified protocol.

Art. 43 requires providers of high-risk AI systems to undergo conformity assessment
procedures. The specific procedure depends on the system's classification:
  - Annex III point 1 (biometric ID): Annex VI or VII (with notified body)
  - Annex III points 2-8: Annex VI internal control only
  - Annex I product systems: sectoral conformity assessment
  - Substantial modifications: new conformity assessment required

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art43"). No regex or keyword scanning is performed.

Obligation mapping:
  ART43-OBL-1   → handled by gap_findings (conditional: is_annex_iii_point_1, manual)
  ART43-OBL-2   → has_internal_control_assessment (Annex VI self-assessment)
  ART43-OBL-3   → handled by gap_findings (conditional: is_annex_i_product, manual)
  ART43-OBL-4   → has_change_management_procedures (reassessment on modification)

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


class Art43Module(BaseArticleModule):
    """Article 43: Conformity Assessment compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=43,
            article_title="Conformity Assessment",
        )

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for conformity assessment compliance using AI-provided answers.

        Reads compliance_answers["art43"] from the AI context. Maps each field
        to obligation findings without any regex or file scanning.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for each conformity assessment obligation.
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

        answers = ctx.get_article_answers("art43")

        has_internal_control_assessment = answers.get("has_internal_control_assessment")
        has_change_management_procedures = answers.get("has_change_management_procedures")

        # ── ART43-OBL-2: Internal control assessment (Annex VI) ──
        # Annex III points 2-8 systems must follow internal control per Annex VI
        findings.append(self._finding_from_answer(
            obligation_id="ART43-OBL-2",
            answer=has_internal_control_assessment,
            true_description=(
                "Internal control assessment documentation found. "
                "Verify it covers all Annex VI requirements including quality management "
                "system and technical documentation review."
            ),
            false_description=(
                "No internal control assessment documentation found. "
                "Art. 43(2) requires providers of Annex III points 2-8 high-risk AI systems "
                "to follow the Annex VI internal control conformity assessment procedure."
            ),
            none_description=(
                "AI could not determine whether internal control assessment has been performed. "
                "Art. 43(2) requires Annex VI conformity assessment for Annex III points 2-8 systems."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART43-OBL-4: Reassessment on substantial modification ──
        # New conformity assessment required when system undergoes substantial modification
        findings.append(self._finding_from_answer(
            obligation_id="ART43-OBL-4",
            answer=has_change_management_procedures,
            true_description=(
                "Change management procedures detected for tracking substantial modifications. "
                "Verify procedures include criteria for triggering new conformity assessment."
            ),
            false_description=(
                "No change management procedures found for tracking substantial modifications. "
                "Art. 43(4) requires a new conformity assessment on substantial modification, "
                "regardless of whether the system is further distributed or continues in use."
            ),
            none_description=(
                "AI could not determine whether change management procedures exist. "
                "Art. 43(4) requires new conformity assessment on substantial modification."
            ),
            gap_type=GapType.PROCESS,
        ))

        # OBL-1 (conditional: is_annex_iii_point_1, manual) and
        # OBL-3 (conditional: is_annex_i_product, manual) are handled by gap_findings

        # Build details dict
        details = {
            "has_internal_control_assessment": has_internal_control_assessment,
            "has_change_management_procedures": has_change_management_procedures,
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
            article_number=43,
            article_title="Conformity Assessment",
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
            article_number=43,
            article_title="Conformity Assessment",
            one_sentence=(
                "High-risk AI system providers must undergo conformity assessment "
                "before placing their system on the market."
            ),
            official_summary=(
                "Art. 43 sets out conformity assessment procedures for high-risk AI systems. "
                "For Annex III point 1 (biometric identification) systems, providers choose between "
                "Annex VI internal control or Annex VII assessment with a notified body. "
                "For Annex III points 2-8 systems, providers follow Annex VI internal control only. "
                "For Annex I product systems, providers follow the relevant sectoral conformity "
                "assessment procedure. All systems require new conformity assessment upon "
                "substantial modification."
            ),
            related_articles={
                "Art. 6": "High-risk classification determining which assessment applies",
                "Art. 40": "Harmonised standards for demonstrating compliance",
                "Art. 41": "Common specifications as alternative to harmonised standards",
                "Art. 42": "Presumption of conformity with harmonised standards",
                "Art. 44": "Certificates issued by notified bodies",
                "Art. 49": "EU database registration after conformity assessment",
            },
            recital=(
                "Recital 126: The conformity assessment procedures should be proportionate "
                "and build on existing conformity assessment schemes."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Internal control assessment documentation detection",
                    "Change management procedures detection",
                ],
                "requires_human_judgment": [
                    "Which conformity assessment procedure is appropriate",
                    "Whether Annex VI or VII procedure was properly followed",
                    "Whether a modification constitutes a 'substantial modification'",
                    "Whether sectoral conformity assessment is complete",
                    "Whether notified body involvement is required",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) conformity assessment "
                "documentation per the applicable procedure (Annex VI or VII), (2) change "
                "management procedures for tracking substantial modifications and triggering "
                "reassessment. Based on: ISO/IEC 42001:2023, ISO/IEC 17065:2012."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for Art. 43 (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_internal_control_assessment") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 43(2)",
                action="Perform Annex VI internal control conformity assessment",
                details=(
                    "Art. 43(2) requires providers of Annex III points 2-8 high-risk AI systems "
                    "to follow the Annex VI internal control procedure. This includes reviewing "
                    "the quality management system and technical documentation to verify "
                    "compliance with Section 2 requirements."
                ),
                effort="40-80 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_change_management_procedures") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 43(4)",
                action="Establish change management procedures for substantial modifications",
                details=(
                    "Art. 43(4) requires a new conformity assessment upon substantial modification. "
                    "Implement change management procedures that: (1) define criteria for what "
                    "constitutes a substantial modification, (2) track all system changes, "
                    "(3) trigger reassessment when thresholds are met."
                ),
                effort="8-16 hours",
            ))

        # Always add human judgment items for conditional/manual obligations
        actions.append(ActionItem(
            priority="HIGH",
            article="Art. 43(1)",
            action="Determine applicable conformity assessment procedure",
            details=(
                "If your system falls under Annex III point 1 (biometric identification), "
                "choose between Annex VI (internal control) or Annex VII (notified body). "
                "If your system is an Annex I product, follow the relevant sectoral procedure. "
                "Document the chosen procedure and rationale."
            ),
            effort="4-8 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=43,
            article_title="Conformity Assessment",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Conformity assessment is a largely process-oriented obligation that cannot be "
                "fully verified from code. Human expert review and potentially notified body "
                "involvement are essential. Based on ComplianceLint compliance checklist. "
                "Official CEN-CENELEC standards (expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art43Module:
    return Art43Module()
