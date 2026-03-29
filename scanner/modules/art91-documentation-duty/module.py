"""
Article 91: Power to request documentation and information — Module implementation.

Art. 91 covers the Commission's power to request documentation and information
from providers of general-purpose AI models during investigations:
  - Art. 91(5): Provider SHALL supply the information requested by the Commission

This module reads AI-provided compliance_answers["art91"] and maps each answer
to a Finding. No regex, keyword, or AST scanning is performed — detection is
entirely the AI's responsibility.

Obligation mapping:
  ART91-OBL-5  → has_information_supply_readiness (provider obligation, partial, conditional on is_gpai_provider)

Boundary cases:
  - OBL-5 has context_skip_field "is_gpai_provider". When is_gpai_provider=false,
    obligation is NOT_APPLICABLE. When true, check readiness.
  - This is a partially automatable obligation: we can check for documentation
    readiness (Art. 53/55 docs, information request response procedures), but
    actual compliance requires human judgment on whether information would be
    supplied when requested.
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


class Art91Module(BaseArticleModule):
    """Article 91: Power to request documentation and information."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=91,
            article_title="Power to request documentation and information",
        )

    # ── Scanning ──

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for Art. 91 compliance using AI-provided answers.

        Reads compliance_answers["art91"] from the AI context. Maps each field
        to obligation findings:
          - has_information_supply_readiness → ART91-OBL-5

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for Art. 91 documentation duty.
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

        answers = ctx.get_article_answers("art91")

        has_information_supply_readiness = answers.get("has_information_supply_readiness")
        readiness_evidence = answers.get("readiness_evidence", "")

        # ── ART91-OBL-5: Supply requested information ──
        # Art. 91(5): Provider of GPAI model SHALL supply information
        # requested by the Commission during investigations.
        # Conditional on is_gpai_provider (handled by obligation engine).
        findings.append(self._finding_from_answer(
            obligation_id="ART91-OBL-5",
            answer=has_information_supply_readiness,
            true_description=(
                "Evidence of information supply readiness found. "
                "The provider appears prepared to supply documentation and "
                "information to the Commission upon request per Art. 91(5). "
                "Verify that Art. 53/55 documentation is maintained and an "
                "information request response procedure is in place."
                f"{(' Evidence: ' + readiness_evidence) if readiness_evidence else ''}"
            ),
            false_description=(
                "No evidence of information supply readiness found. "
                "Art. 91(5) requires providers of general-purpose AI models "
                "to supply information requested by the Commission during "
                "investigations. Ensure Art. 53/55 documentation is complete "
                "and an information request response procedure exists."
            ),
            none_description=(
                "AI could not determine whether information supply readiness "
                "is in place. Art. 91(5) requires GPAI model providers to "
                "supply requested information to the Commission. This requires "
                "human review of documentation completeness and organizational "
                "response procedures."
            ),
            gap_type=GapType.PROCESS,
        ))

        details = {
            "has_information_supply_readiness": has_information_supply_readiness,
            "readiness_evidence": readiness_evidence,
            "note": (
                "Art. 91 covers the Commission's power to request documentation "
                "and information from GPAI model providers during investigations. "
                "The key provider obligation (Art. 91(5)) is to supply the "
                "requested information. Readiness depends on having complete "
                "Art. 53/55 documentation and response procedures."
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
            article_number=91,
            article_title="Power to request documentation and information",
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
            article_number=91,
            article_title="Power to request documentation and information",
            one_sentence=(
                "Article 91 requires GPAI model providers to supply documentation "
                "and information to the Commission when requested during investigations."
            ),
            official_summary=(
                "Art. 91 establishes the Commission's power to request documentation "
                "and information from providers of general-purpose AI models. "
                "Art. 91(5) requires the provider (or its representative) to supply "
                "the information requested. This is a procedural obligation that "
                "depends on having complete documentation (Art. 53/55) and "
                "organizational readiness to respond to Commission requests."
            ),
            related_articles={
                "Art. 53": "GPAI provider obligations (technical documentation)",
                "Art. 55": "GPAI systemic risk obligations (additional documentation)",
                "Art. 101": "AI Office supervisory powers",
            },
            recital=(
                "Recital 113: The AI Office should be able to carry out all "
                "necessary actions to monitor the effective implementation and "
                "compliance with the obligations of providers of general-purpose "
                "AI models."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of Art. 53/55 documentation completeness",
                    "Detection of information request response procedures",
                ],
                "requires_human_judgment": [
                    "Whether all requested information can be supplied",
                    "Whether response procedures are adequate",
                    "Whether documentation is complete for Commission requests",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 provides: (1) check for "
                "Art. 53/55 documentation completeness, (2) check for information "
                "request response procedures. Note: actual compliance requires "
                "human judgment on organizational readiness to respond to "
                "Commission information requests."
            ),
            enforcement_date="2025-08-02",
            waiting_for="CEN-CENELEC harmonized standard for GPAI obligations (expected 2027)",
        )

    # ── Action Plan ──

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_information_supply_readiness") is not True:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 91(5)",
                action="Establish information supply readiness for Commission requests",
                details=(
                    "Art. 91(5) requires GPAI model providers to supply information "
                    "requested by the Commission during investigations. Ensure:\n"
                    "\n"
                    "  1. Art. 53 technical documentation is complete and up-to-date\n"
                    "  2. Art. 55 documentation (if systemic risk) is maintained\n"
                    "  3. An internal procedure exists for responding to Commission requests\n"
                    "  4. A designated contact person or representative is identified\n"
                    "  5. Documentation is stored in an accessible, organized manner"
                ),
                effort="4-8 hours (initial setup), ongoing maintenance",
                action_type="human_judgment_required",
            ))

        # Always: documentation maintenance
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 91(5)",
            action="Maintain Art. 53/55 documentation for Commission readiness",
            details=(
                "Keep GPAI model documentation (Art. 53 technical docs, Art. 55 "
                "systemic risk docs if applicable) current and organized. The "
                "Commission may request this information at any time during "
                "investigations under Art. 91."
            ),
            effort="Ongoing — periodic review and updates",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=91,
            article_title="Power to request documentation and information",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 91 information supply is primarily an organizational/legal matter. "
                "Automated scanning can only check for documentation readiness indicators. "
                "Based on ComplianceLint compliance checklist; official CEN-CENELEC "
                "standards (expected 2027) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art91Module:
    return Art91Module()
