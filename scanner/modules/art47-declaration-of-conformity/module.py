"""
Article 47: EU Declaration of Conformity — Module implementation using unified protocol.

Art. 47 requires providers of high-risk AI systems to draw up an EU declaration
of conformity (DoC) that meets specific format, content, and retention requirements:
  - Written, machine-readable, and signed DoC for each high-risk AI system
  - DoC must contain Annex V information and state Section 2 compliance
  - DoC must be kept at the disposal of authorities for 10 years
  - DoC must be kept up-to-date

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art47"). No regex or keyword scanning is performed.

Obligation mapping:
  ART47-OBL-1   → has_doc_declaration (DoC exists, machine-readable, retained)
  ART47-OBL-2   → has_annex_v_content (DoC has Annex V info and translations)
  ART47-OBL-4   → always UTD (manual: whether DoC is kept up-to-date)
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


class Art47Module(BaseArticleModule):
    """Article 47: EU Declaration of Conformity compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=47,
            article_title="EU Declaration of Conformity",
        )

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for EU Declaration of Conformity compliance using AI-provided answers.

        Reads compliance_answers["art47"] from the AI context. Maps each field
        to obligation findings without any regex or file scanning.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for each declaration of conformity obligation.
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

        answers = ctx.get_article_answers("art47")

        has_doc_declaration = answers.get("has_doc_declaration")
        has_annex_v_content = answers.get("has_annex_v_content")

        # ── ART47-OBL-1: EU Declaration of Conformity document ──
        # Provider must draw up a written, machine-readable, signed DoC
        # and retain it for 10 years
        findings.append(self._finding_from_answer(
            obligation_id="ART47-OBL-1",
            answer=has_doc_declaration,
            true_description=(
                "EU Declaration of Conformity document found. "
                "Verify it is machine-readable or electronically signed, "
                "and that retention policy ensures availability for 10 years "
                "after market placement per Art. 47(1)."
            ),
            false_description=(
                "No EU Declaration of Conformity document found. "
                "Art. 47(1) requires providers to draw up a written, machine-readable "
                "or electronically signed DoC for each high-risk AI system, "
                "retained for 10 years after market placement."
            ),
            none_description=(
                "AI could not determine whether an EU Declaration of Conformity exists. "
                "Art. 47(1) requires a written, machine-readable DoC for each high-risk AI system."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART47-OBL-2: Annex V content and translation ──
        # DoC must state Section 2 compliance, contain Annex V info, and be translated
        findings.append(self._finding_from_answer(
            obligation_id="ART47-OBL-2",
            answer=has_annex_v_content,
            true_description=(
                "DoC appears to contain Annex V elements. "
                "Verify it states compliance with Section 2 requirements "
                "and is translated into languages understood by relevant national authorities."
            ),
            false_description=(
                "DoC does not contain required Annex V information. "
                "Art. 47(2) requires the DoC to state Section 2 compliance, "
                "contain all Annex V information, and be translated into "
                "languages understood by relevant national competent authorities."
            ),
            none_description=(
                "AI could not determine whether the DoC contains Annex V information. "
                "Art. 47(2) requires Annex V content and appropriate translations."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART47-OBL-4: DoC kept up-to-date ──
        # Manual obligation: AI cannot determine if DoC reflects current system state
        findings.append(Finding(
            obligation_id="ART47-OBL-4",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Whether the EU Declaration of Conformity is kept up-to-date requires "
                "human review. Art. 47(4) requires the provider to keep the DoC "
                "up-to-date as appropriate. AI cannot determine from code whether "
                "the DoC reflects the current system state — confirm the DoC date "
                "matches the latest system modification."
            ),
            remediation=(
                "Establish a process to review and update the EU Declaration of Conformity "
                "whenever the AI system undergoes changes that affect Section 2 compliance. "
                "Include DoC review in your change management procedures."
            ),
            gap_type=GapType.PROCESS,
        ))

        # Build details dict
        details = {
            "has_doc_declaration": has_doc_declaration,
            "has_annex_v_content": has_annex_v_content,
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
            article_number=47,
            article_title="EU Declaration of Conformity",
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
            article_number=47,
            article_title="EU Declaration of Conformity",
            one_sentence=(
                "High-risk AI system providers must draw up and maintain an EU Declaration "
                "of Conformity containing Annex V information."
            ),
            official_summary=(
                "Art. 47 requires providers of high-risk AI systems to create a written, "
                "machine-readable EU declaration of conformity (DoC) for each system. "
                "The DoC must state that the system meets Section 2 requirements, contain "
                "all Annex V information, and be translated into languages understood by "
                "relevant national authorities. The DoC must be retained for 10 years "
                "after market placement and kept up-to-date."
            ),
            related_articles={
                "Art. 6": "High-risk classification determining which systems need a DoC",
                "Art. 43": "Conformity assessment procedures preceding the DoC",
                "Art. 48": "CE marking affixed after DoC is drawn up",
                "Art. 49": "EU database registration after DoC",
                "Annex V": "Required content elements of the DoC",
            },
            recital=(
                "Recital 127: The EU declaration of conformity should provide information "
                "on the identity of the provider and the AI system, and confirm that the "
                "relevant requirements have been met."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of DoC document existence",
                    "Detection of Annex V content elements in DoC",
                ],
                "requires_human_judgment": [
                    "Whether DoC contains all required Annex V elements",
                    "Whether DoC is properly signed (machine-readable, physical, or electronic)",
                    "Whether DoC is translated into appropriate languages",
                    "Whether DoC reflects current system state (up-to-date)",
                    "Whether retention policy ensures 10-year availability",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) written EU Declaration "
                "of Conformity document per Annex V, (2) machine-readable or electronically "
                "signed format, (3) 10-year retention policy, (4) process for keeping DoC "
                "up-to-date. Based on: EU AI Act Annex V, ISO/IEC 17050-1:2004."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for Art. 47 (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_doc_declaration") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 47(1)",
                action="Create EU Declaration of Conformity document",
                details=(
                    "Art. 47(1) requires a written, machine-readable or electronically signed "
                    "EU Declaration of Conformity for each high-risk AI system. The DoC must "
                    "be kept at the disposal of national competent authorities for 10 years "
                    "after the system has been placed on the market or put into service.\n"
                    "\n"
                    "  Template elements (per Annex V):\n"
                    "    1. Name and type of the AI system\n"
                    "    2. Name and address of the provider\n"
                    "    3. Statement that the DoC is issued under the provider's sole responsibility\n"
                    "    4. Statement that the AI system meets Section 2 requirements\n"
                    "    5. References to relevant harmonised standards or common specifications\n"
                    "    6. Name and identification number of the notified body (if applicable)\n"
                    "    7. Place and date of issue, signature"
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_annex_v_content") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 47(2)",
                action="Ensure DoC contains all Annex V elements and translations",
                details=(
                    "Art. 47(2) requires the DoC to contain all information set out in Annex V "
                    "and to be translated into languages understood by the national competent "
                    "authorities of Member States where the system is placed on the market."
                ),
                effort="2-4 hours",
                action_type="human_judgment_required",
            ))

        # Always add manual obligation items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 47(4)",
            action="Establish process for keeping DoC up-to-date",
            details=(
                "Art. 47(4) requires the provider to keep the DoC up-to-date as appropriate. "
                "Include DoC review in your change management procedures so that any system "
                "modification triggers a review of whether the DoC needs updating."
            ),
            effort="1-2 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=47,
            article_title="EU Declaration of Conformity",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "The EU Declaration of Conformity is a largely document-oriented obligation "
                "that cannot be fully verified from code. Human expert review is essential "
                "to verify Annex V completeness and legal adequacy. Based on ComplianceLint "
                "compliance checklist. Official CEN-CENELEC standards (expected Q4 2026) may "
                "modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art47Module:
    return Art47Module()
