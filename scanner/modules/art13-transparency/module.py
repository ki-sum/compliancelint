"""
Article 13: Transparency and Provision of Information to Deployers.

Art. 13 requires high-risk AI systems to be transparently designed and
accompanied by instructions for use containing specific information
for deployers (identity, purpose, accuracy, risks, oversight, etc.).

Obligation mapping:
  ART13-OBL-1  -> has_explainability (system transparency)
  ART13-OBL-2  -> has_transparency_info (instructions for use)
  ART13-OBL-3  -> has_transparency_info (Art.13(3)(a)-(f) content - manual)
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


class Art13Module(BaseArticleModule):
    """Article 13: Transparency and Provision of Information to Deployers."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=13,
            article_title="Transparency and Provision of Information to Deployers",
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

        answers = ctx.get_article_answers("art13")

        has_explainability = answers.get("has_explainability")
        if has_explainability is None:
            has_explainability = answers.get("has_interpretability")  # alias
        explainability_evidence = answers.get("explainability_evidence") or []
        has_transparency_info = answers.get("has_transparency_info")
        if has_transparency_info is None:
            has_transparency_info = answers.get("has_instructions_for_use")  # alias
        transparency_paths = answers.get("transparency_paths") or []

        expl_evidence = explainability_evidence or None
        trans_evidence = transparency_paths or None

        # -- ART13-OBL-1: System transparency --
        findings.append(self._finding_from_answer(
            obligation_id="ART13-OBL-1",
            answer=has_explainability,
            true_description=(
                f"Explainability/transparency evidence found: {', '.join(explainability_evidence)}."
                if explainability_evidence
                else "Explainability/transparency evidence found."
            ),
            false_description=(
                "No explainability or transparency mechanisms detected. Art. 13(1) requires "
                "systems to be designed for sufficient transparency to enable deployers "
                "to interpret outputs and use them appropriately."
            ),
            none_description=(
                "AI could not determine whether explainability mechanisms exist."
            ),
            evidence=expl_evidence,
            gap_type=GapType.CODE,
        ))

        # -- ART13-OBL-2: Instructions for use --
        findings.append(self._finding_from_answer(
            obligation_id="ART13-OBL-2",
            answer=has_transparency_info,
            true_description=(
                f"Deployer-facing documentation found: {', '.join(transparency_paths)}."
                if transparency_paths
                else "Deployer-facing documentation found."
            ),
            false_description=(
                "No instructions for use or deployer documentation detected. Art. 13(2) "
                "requires instructions that include concise, complete, correct and clear "
                "information that is relevant, accessible and comprehensible to deployers."
            ),
            none_description=(
                "AI could not determine whether instructions for use exist."
            ),
            evidence=trans_evidence,
            gap_type=GapType.PROCESS,
        ))

        # -- ART13-OBL-3: Art.13(3)(a)-(f) content (always manual) --
        findings.append(Finding(
            obligation_id="ART13-OBL-3",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Art. 13(3) content checklist requires human review. Instructions for use "
                "must contain at least: (a) provider identity/contact, (b) capabilities/limitations "
                "(intended purpose, accuracy, risks, explainability, group performance, input specs, "
                "output interpretation), (c) pre-determined changes, (d) human oversight measures, "
                "(e) resources/lifetime/maintenance, (f) log collection mechanisms."
            ),
            gap_type=GapType.PROCESS,
        ))

        details = {
            "has_explainability": has_explainability,
            "explainability_evidence": explainability_evidence,
            "has_transparency_info": has_transparency_info,
            "transparency_paths": transparency_paths,
        }

        # -- Obligation Engine --
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
            article_number=13,
            article_title="Transparency and Provision of Information to Deployers",
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
            article_number=13,
            article_title="Transparency and Provision of Information to Deployers",
            one_sentence=(
                "High-risk AI systems must be transparent and accompanied by "
                "instructions for use containing specific information for deployers."
            ),
            official_summary=(
                "Art. 13 requires systems to be designed for sufficient transparency "
                "to enable deployers to interpret outputs. Instructions for use must "
                "contain provider identity, intended purpose, accuracy metrics, known risks, "
                "explainability capabilities, human oversight measures, and log mechanisms."
            ),
            related_articles={
                "Art. 9(2)": "Risk identification (referenced in Art. 13(3)(b)(iii))",
                "Art. 12": "Log mechanisms (referenced in Art. 13(3)(f))",
                "Art. 14": "Human oversight measures (referenced in Art. 13(3)(d))",
                "Art. 15": "Accuracy and robustness metrics (referenced in Art. 13(3)(b)(ii))",
            },
            recital=(
                "Recital 72: Transparency is necessary for deployers to fulfil their "
                "obligations and for users to understand the system's functioning."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of explainability tooling (SHAP, LIME, etc.)",
                    "Detection of deployer-facing documentation",
                    "Detection of provider identity in documentation",
                ],
                "requires_human_judgment": [
                    "Whether transparency is 'sufficient' for the use case",
                    "Art. 13(3) content completeness (12 required elements)",
                    "Information quality (concise, complete, correct, clear)",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) explainability mechanism, "
                "(2) deployer-facing documentation, (3) Art. 13(3)(a)-(f) content coverage. "
                "Based on: ISO/IEC 42001:2023."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_explainability") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 13(1)",
                action="Add explainability/transparency mechanisms",
                details=(
                    "Art. 13(1) requires systems to be transparent enough for deployers "
                    "to interpret outputs. Consider: SHAP, LIME, feature importance, "
                    "attention visualization, or confidence scores."
                ),
                effort="4-16 hours",
            ))

        if details.get("has_transparency_info") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 13(2)-(3)",
                action="Create instructions for use (deployer documentation)",
                details=(
                    "Art. 13(2) requires instructions with concise, complete, correct "
                    "and clear information. Art. 13(3) specifies at least: (a) provider identity, "
                    "(b) capabilities/limitations, (c) changes, (d) oversight measures, "
                    "(e) resources/maintenance, (f) log mechanisms."
                ),
                effort="8-24 hours",
                action_type="human_judgment_required",
            ))

        actions.append(ActionItem(
            priority="HIGH",
            article="Art. 13(3)",
            action="Verify Art. 13(3)(a)-(f) content coverage",
            details=(
                "Check instructions contain ALL required elements: provider identity, "
                "intended purpose, accuracy metrics, known risks, explainability info, "
                "group performance, input specs, output interpretation guidance, "
                "pre-determined changes, oversight measures, resources, log mechanisms."
            ),
            effort="4-8 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=13,
            article_title="Transparency and Provision of Information to Deployers",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 13 combines technical transparency with documentation requirements. "
                "Automated scanning detects tooling and documentation presence but cannot "
                "assess comprehensiveness. Human expert review is essential."
            ),
        )


def create_module() -> Art13Module:
    return Art13Module()
