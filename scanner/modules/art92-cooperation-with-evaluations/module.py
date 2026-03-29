"""
Article 92: Power to conduct evaluations — Module implementation.

Art. 92 covers the Commission's power to conduct evaluations of
general-purpose AI models, including requesting information:
  - Art. 92(5): Provider SHALL supply the information requested

This module reads AI-provided compliance_answers["art92"] and maps each answer
to a Finding. No regex, keyword, or AST scanning is performed — detection is
entirely the AI's responsibility.

Obligation mapping:
  ART92-OBL-5  → has_evaluation_cooperation_readiness (provider obligation, partial, conditional on is_gpai_provider)

Boundary cases:
  - OBL-5 has context_skip_field "is_gpai_provider". When is_gpai_provider=false,
    obligation is NOT_APPLICABLE. When true, check readiness.
  - This is a partially automatable obligation: we can check for documentation
    readiness and evaluation response procedures, but actual compliance requires
    human judgment on whether information would be supplied when requested.
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


class Art92Module(BaseArticleModule):
    """Article 92: Power to conduct evaluations."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=92,
            article_title="Power to conduct evaluations",
        )

    # ── Scanning ──

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for Art. 92 compliance using AI-provided answers.

        Reads compliance_answers["art92"] from the AI context. Maps each field
        to obligation findings:
          - has_evaluation_cooperation_readiness → ART92-OBL-5

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for Art. 92 evaluation cooperation.
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

        answers = ctx.get_article_answers("art92")

        has_evaluation_cooperation_readiness = answers.get("has_evaluation_cooperation_readiness")
        cooperation_evidence = answers.get("cooperation_evidence", "")

        # ── ART92-OBL-5: Supply requested information during evaluations ──
        # Art. 92(5): Provider of GPAI model SHALL supply information
        # requested during Commission evaluations.
        # Conditional on is_gpai_provider (handled by obligation engine).
        findings.append(self._finding_from_answer(
            obligation_id="ART92-OBL-5",
            answer=has_evaluation_cooperation_readiness,
            true_description=(
                "Evidence of evaluation cooperation readiness found. "
                "The provider appears prepared to supply information "
                "requested during Commission evaluations per Art. 92(5). "
                "Verify that GPAI model documentation is maintained and "
                "evaluation response procedures are in place."
                f"{(' Evidence: ' + cooperation_evidence) if cooperation_evidence else ''}"
            ),
            false_description=(
                "No evidence of evaluation cooperation readiness found. "
                "Art. 92(5) requires providers of general-purpose AI models "
                "to supply information requested during Commission evaluations. "
                "Ensure GPAI model documentation is complete and evaluation "
                "cooperation procedures exist."
            ),
            none_description=(
                "AI could not determine whether evaluation cooperation readiness "
                "is in place. Art. 92(5) requires GPAI model providers to "
                "supply requested information during Commission evaluations. "
                "This requires human review of documentation completeness and "
                "organizational response procedures."
            ),
            gap_type=GapType.PROCESS,
        ))

        details = {
            "has_evaluation_cooperation_readiness": has_evaluation_cooperation_readiness,
            "cooperation_evidence": cooperation_evidence,
            "note": (
                "Art. 92 covers the Commission's power to conduct evaluations "
                "of general-purpose AI models. The key provider obligation "
                "(Art. 92(5)) is to supply the requested information during "
                "evaluations. Readiness depends on having complete GPAI model "
                "documentation and evaluation response procedures."
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
            article_number=92,
            article_title="Power to conduct evaluations",
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
            article_number=92,
            article_title="Power to conduct evaluations",
            one_sentence=(
                "Article 92 requires GPAI model providers to supply information "
                "requested by the Commission during evaluations of their models."
            ),
            official_summary=(
                "Art. 92 establishes the Commission's power to conduct evaluations "
                "of general-purpose AI models. Art. 92(5) requires the provider "
                "(or its representative) to supply the information requested during "
                "such evaluations. This is a procedural obligation that depends on "
                "having complete GPAI model documentation and organizational readiness "
                "to cooperate with Commission evaluation activities."
            ),
            related_articles={
                "Art. 53": "GPAI provider obligations (technical documentation)",
                "Art. 55": "GPAI systemic risk obligations (additional documentation)",
                "Art. 91": "Power to request documentation and information",
                "Art. 101": "AI Office supervisory powers",
            },
            recital=(
                "Recital 113: The AI Office should be able to carry out all "
                "necessary actions to monitor the effective implementation and "
                "compliance with the obligations of providers of general-purpose "
                "AI models, including evaluations."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of GPAI model documentation completeness",
                    "Detection of evaluation cooperation procedures",
                ],
                "requires_human_judgment": [
                    "Whether all requested information can be supplied during evaluations",
                    "Whether cooperation procedures are adequate",
                    "Whether documentation is complete for Commission evaluations",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 provides: (1) check for "
                "GPAI model documentation completeness, (2) check for evaluation "
                "cooperation procedures. Note: actual compliance requires human "
                "judgment on organizational readiness to cooperate with Commission "
                "evaluation activities."
            ),
            enforcement_date="2025-08-02",
            waiting_for="CEN-CENELEC harmonized standard for GPAI obligations (expected 2027)",
        )

    # ── Action Plan ──

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_evaluation_cooperation_readiness") is not True:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 92(5)",
                action="Establish evaluation cooperation readiness for Commission evaluations",
                details=(
                    "Art. 92(5) requires GPAI model providers to supply information "
                    "requested during Commission evaluations. Ensure:\n"
                    "\n"
                    "  1. GPAI model documentation (Art. 53/55) is complete and up-to-date\n"
                    "  2. An internal procedure exists for cooperating with Commission evaluations\n"
                    "  3. A designated contact person or representative is identified\n"
                    "  4. Documentation and model access are organized for evaluation readiness\n"
                    "  5. Source code access procedures are documented (if applicable)"
                ),
                effort="4-8 hours (initial setup), ongoing maintenance",
                action_type="human_judgment_required",
            ))

        # Always: documentation maintenance
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 92(5)",
            action="Maintain GPAI model documentation for evaluation readiness",
            details=(
                "Keep GPAI model documentation (Art. 53 technical docs, Art. 55 "
                "systemic risk docs if applicable) current and organized. The "
                "Commission may conduct evaluations at any time under Art. 92, "
                "and providers must be ready to supply requested information."
            ),
            effort="Ongoing — periodic review and updates",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=92,
            article_title="Power to conduct evaluations",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 92 evaluation cooperation is primarily an organizational/legal matter. "
                "Automated scanning can only check for documentation readiness indicators. "
                "Based on ComplianceLint compliance checklist; official CEN-CENELEC "
                "standards (expected 2027) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art92Module:
    return Art92Module()
