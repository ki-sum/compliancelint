"""
Article 41: Common specifications — Module implementation using unified protocol.

Art. 41 addresses common specifications adopted by the Commission when harmonised
standards do not exist or are insufficient. The key provider obligation is Art. 41(5):
providers who do NOT comply with common specifications must justify that their
alternative technical solutions meet requirements to an equivalent level.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art41"). No regex or keyword scanning is performed.

Obligation mapping:
  ART41-OBL-5   → has_alternative_justification (conditional: follows_common_specifications)

NOTE — When follows_common_specifications=True, OBL-5 is NOT_APPLICABLE (the provider
follows CS, so no justification of alternatives is needed). When False, the provider
must have documented justification. When None → gap_findings handles it as CONDITIONAL.
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


class Art41Module(BaseArticleModule):
    """Article 41: Common specifications compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=41,
            article_title="Common specifications",
        )

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for common specifications compliance using AI-provided answers.

        Reads compliance_answers["art41"] from the AI context. Maps each field
        to obligation findings without any regex or file scanning.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for each common specifications obligation.
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

        answers = ctx.get_article_answers("art41")

        follows_common_specifications = answers.get("follows_common_specifications")
        has_alternative_justification = answers.get("has_alternative_justification")

        # ── ART41-OBL-5: Justify alternative technical solutions ──
        # Only applies when provider does NOT follow common specifications.
        # When follows_common_specifications=True → NOT_APPLICABLE
        # When follows_common_specifications=False → check has_alternative_justification
        # When follows_common_specifications=None → UNABLE_TO_DETERMINE (conditional)
        if follows_common_specifications is True:
            findings.append(Finding(
                obligation_id="ART41-OBL-5",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.HIGH,
                description=(
                    "Provider follows common specifications — no justification of "
                    "alternative technical solutions is required under Art. 41(5)."
                ),
                gap_type=GapType.PROCESS,
            ))
        elif follows_common_specifications is False:
            findings.append(self._finding_from_answer(
                obligation_id="ART41-OBL-5",
                answer=has_alternative_justification,
                true_description=(
                    "Provider does not follow common specifications but has documented "
                    "justification that alternative technical solutions meet requirements "
                    "to an equivalent level, as required by Art. 41(5)."
                ),
                false_description=(
                    "Provider does not follow common specifications and no documented "
                    "justification of alternative technical solutions found. Art. 41(5) "
                    "requires providers to duly justify that their alternative solutions "
                    "meet requirements to a level at least equivalent to common specifications."
                ),
                none_description=(
                    "Provider does not follow common specifications but AI could not "
                    "determine whether justification documentation exists. Art. 41(5) "
                    "requires documented justification of equivalent alternative solutions."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            # follows_common_specifications=None → conditional / UTD
            findings.append(Finding(
                obligation_id="ART41-OBL-5",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "Cannot determine whether the provider follows common specifications. "
                    "If common specifications have been adopted and the provider does not "
                    "comply with them, Art. 41(5) requires documented justification that "
                    "alternative technical solutions meet requirements to an equivalent level."
                ),
                gap_type=GapType.PROCESS,
            ))

        # Build details dict
        details = {
            "follows_common_specifications": follows_common_specifications,
            "has_alternative_justification": has_alternative_justification,
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
            article_number=41,
            article_title="Common specifications",
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
            article_number=41,
            article_title="Common specifications",
            one_sentence=(
                "When harmonised standards do not exist, the Commission may adopt common "
                "specifications, and providers who deviate must justify equivalent compliance."
            ),
            official_summary=(
                "Art. 41 allows the Commission to adopt common specifications for high-risk "
                "AI systems when harmonised standards (Art. 40) do not exist or are insufficient. "
                "Providers who comply with common specifications are presumed to comply with the "
                "corresponding requirements. Providers who do NOT comply with common specifications "
                "must duly justify that their alternative technical solutions meet the requirements "
                "to a level at least equivalent (Art. 41(5))."
            ),
            related_articles={
                "Art. 8": "Compliance with Section 2 requirements (what common specifications cover)",
                "Art. 40": "Harmonised standards (primary route; common specifications are fallback)",
                "Art. 42": "Presumption of conformity with harmonised standards or common specifications",
                "Art. 43": "Conformity assessment procedures",
            },
            recital=(
                "Recital 124: In the absence of harmonised standards, common specifications "
                "should be an exceptional fallback solution to facilitate the provider's "
                "obligation to comply with the requirements of this Regulation."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of standards compliance documentation",
                    "Detection of alternative technical solution justification",
                ],
                "requires_human_judgment": [
                    "Whether common specifications have been adopted for the specific system type",
                    "Whether the provider complies with or deviates from common specifications",
                    "Whether alternative solutions are truly equivalent",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) identification of "
                "applicable common specifications, (2) if deviating from common specifications, "
                "documented justification of equivalent alternative technical solutions. "
                "Based on: EU AI Act Art. 41, Recital 124."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standards for AI Act (expected 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("follows_common_specifications") is None:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 41",
                action="Determine whether common specifications apply to your system",
                details=(
                    "Check whether the European Commission has adopted common specifications "
                    "relevant to your high-risk AI system type. If common specifications exist, "
                    "determine whether your system complies with them or uses alternative solutions."
                ),
                effort="2-4 hours",
                action_type="human_judgment_required",
            ))

        if details.get("follows_common_specifications") is False and details.get("has_alternative_justification") is not True:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 41(5)",
                action="Document justification for alternative technical solutions",
                details=(
                    "Art. 41(5) requires providers who do not comply with common specifications "
                    "to duly justify that their alternative technical solutions meet the Section 2 "
                    "requirements to a level at least equivalent. Create a document that:\n"
                    "  1. Lists the applicable common specifications\n"
                    "  2. Identifies where your system deviates\n"
                    "  3. Describes the alternative technical solutions used\n"
                    "  4. Justifies equivalence for each deviation"
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        if not actions:
            actions.append(ActionItem(
                priority="LOW",
                article="Art. 41",
                action="Monitor for new common specifications",
                details=(
                    "Common specifications may be adopted by the Commission at any time. "
                    "Monitor the Official Journal of the EU for new common specifications "
                    "relevant to your AI system type."
                ),
                effort="Ongoing",
                action_type="human_judgment_required",
            ))

        return ActionPlan(
            article_number=41,
            article_title="Common specifications",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Common specifications compliance is largely process-oriented and context-dependent. "
                "As of the current date, no common specifications have been formally adopted under "
                "Art. 41. Based on ComplianceLint compliance checklist. Official CEN-CENELEC "
                "standards (expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art41Module:
    return Art41Module()
