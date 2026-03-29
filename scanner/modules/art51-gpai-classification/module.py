"""
Article 51: Classification of General-Purpose AI Models with Systemic Risk — Module implementation.

Art. 51 classifies GPAI models as having systemic risk based on:
  - Art. 51(1): High impact capabilities or Commission designation
  - Art. 51(2): Training compute > 10^25 FLOPs presumption
  - Art. 51(3): Commission empowerment to update thresholds (not a provider obligation)

This module reads AI-provided compliance_answers["art51"] and maps each answer
to a Finding. No regex, keyword, or AST scanning is performed — detection is
entirely the AI's responsibility.

Obligation mapping:
  ART51-CLS-1  → has_systemic_risk_assessment (classification rule: high impact / Commission)
  ART51-CLS-2  → training_compute_exceeds_threshold (10^25 FLOPs presumption)
  ART51-EMP-3  → UNABLE_TO_DETERMINE always (Commission empowerment, not provider obligation)

Boundary cases:
  - CLS-1 and CLS-2 are classification_rule obligations. CLS-1 uses _finding_from_answer()
    framed as "has the provider assessed systemic risk" (documentation of assessment).
    CLS-2 uses custom Finding() because it requires numerical comparison (> 10^25 FLOPs).
  - EMP-3 is a Commission empowerment with automation_level: "manual" — always UTD.
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


class Art51Module(BaseArticleModule):
    """Article 51: Classification of General-Purpose AI Models with Systemic Risk."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=51,
            article_title="Classification of General-Purpose AI Models with Systemic Risk",
        )

    # ── Scanning ──

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for GPAI systemic risk classification using AI-provided answers.

        Reads compliance_answers["art51"] from the AI context. Maps each field
        to obligation findings:
          - has_systemic_risk_assessment → ART51-CLS-1
          - training_compute_exceeds_threshold → ART51-CLS-2
          - ART51-EMP-3 → always UTD (Commission empowerment)

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for GPAI systemic risk classification.
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

        answers = ctx.get_article_answers("art51")

        is_gpai_model = answers.get("is_gpai_model")
        has_high_impact_capabilities = answers.get("has_high_impact_capabilities")
        training_compute_exceeds_threshold = answers.get("training_compute_exceeds_threshold")
        training_compute_flops = answers.get("training_compute_flops")
        has_commission_designation = answers.get("has_commission_designation")
        has_systemic_risk_assessment = answers.get("has_systemic_risk_assessment")
        reasoning = answers.get("reasoning", "")

        # ── ART51-CLS-1: Systemic risk classification assessment ──
        # Art. 51(1): GPAI model SHALL be classified as systemic risk if it has
        # high impact capabilities or Commission designation.
        # Framed as: has the provider assessed systemic risk classification?
        findings.append(self._finding_from_answer(
            obligation_id="ART51-CLS-1",
            answer=has_systemic_risk_assessment,
            true_description=(
                "Systemic risk classification assessment found. "
                "Verify the assessment covers all Art. 51(1) criteria: "
                "(a) high impact capabilities evaluated via appropriate technical "
                "tools, methodologies, indicators and benchmarks; and "
                "(b) any Commission designation per Annex XIII criteria."
            ),
            false_description=(
                "No systemic risk classification assessment found. "
                "Art. 51(1) requires GPAI model providers to classify their "
                "models for systemic risk based on high impact capabilities "
                "or Commission decision."
            ),
            none_description=(
                "AI could not determine whether a systemic risk classification "
                "assessment exists. Art. 51(1) requires assessment of whether "
                "the GPAI model has high impact capabilities or has been "
                "designated by the Commission."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART51-CLS-2: Training compute threshold presumption ──
        # Art. 51(2): GPAI model SHALL be presumed high impact when
        # training compute > 10^25 FLOPs.
        # Custom Finding() because this requires numerical comparison.
        if training_compute_exceeds_threshold is True:
            findings.append(Finding(
                obligation_id="ART51-CLS-2",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NON_COMPLIANT,
                confidence=Confidence.LOW,
                description=(
                    f"Training compute exceeds 10^25 FLOPs threshold"
                    f"{(' (' + str(training_compute_flops) + ')') if training_compute_flops else ''}. "
                    "Per Art. 51(2), this model is PRESUMED to have high impact capabilities "
                    "and is classified as a GPAI model with systemic risk. "
                    f"{reasoning} "
                    "This classification triggers additional obligations under Art. 55."
                ),
                remediation=(
                    "If the model's training compute exceeds 10^25 FLOPs, it is presumed "
                    "systemic risk. Comply with Art. 55 obligations (model evaluation, "
                    "adversarial testing, incident reporting, cybersecurity). "
                    "Contact the AI Office to notify of the classification."
                ),
                gap_type=GapType.PROCESS,
            ))
        elif training_compute_exceeds_threshold is False:
            findings.append(Finding(
                obligation_id="ART51-CLS-2",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    f"Training compute reported below 10^25 FLOPs threshold"
                    f"{(' (' + str(training_compute_flops) + ')') if training_compute_flops else ''}. "
                    "The Art. 51(2) presumption does not apply, but the model may still "
                    "be classified as systemic risk under Art. 51(1)(a) based on high "
                    "impact capabilities, or Art. 51(1)(b) via Commission decision."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            findings.append(Finding(
                obligation_id="ART51-CLS-2",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "Training compute could not be determined. Art. 51(2) presumes "
                    "high impact capabilities when cumulative training compute exceeds "
                    "10^25 FLOPs. Review model documentation for training compute figures."
                ),
                gap_type=GapType.PROCESS,
            ))

        # ── ART51-EMP-3: Commission threshold update power ��─
        # Art. 51(3): Commission empowerment to update thresholds via delegated acts.
        # Not a provider obligation — always UTD, informational only.
        findings.append(Finding(
            obligation_id="ART51-EMP-3",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Commission empowerment to update the 10^25 FLOPs threshold "
                "via delegated acts (Art. 97). Not a provider obligation. "
                "Monitor for Commission delegated acts that may amend the "
                "thresholds in Art. 51(1) and (2) as technology evolves."
            ),
            gap_type=GapType.PROCESS,
        ))

        # Determine classification result for details
        if training_compute_exceeds_threshold is True:
            classification_result = (
                "PRESUMED_SYSTEMIC_RISK (training compute exceeds 10^25 FLOPs threshold)"
            )
        elif has_high_impact_capabilities is True:
            classification_result = (
                "POTENTIALLY_SYSTEMIC_RISK (high impact capabilities reported)"
            )
        elif has_commission_designation is True:
            classification_result = (
                "COMMISSION_DESIGNATED (designated via Art. 51(1)(b))"
            )
        elif is_gpai_model is False:
            classification_result = (
                "NOT_GPAI_MODEL (Art. 51 does not apply)"
            )
        else:
            classification_result = (
                "UNDETERMINED (insufficient information for classification)"
            )

        details = {
            "is_gpai_model": is_gpai_model,
            "has_high_impact_capabilities": has_high_impact_capabilities,
            "training_compute_exceeds_threshold": training_compute_exceeds_threshold,
            "training_compute_flops": training_compute_flops,
            "has_commission_designation": has_commission_designation,
            "has_systemic_risk_assessment": has_systemic_risk_assessment,
            "reasoning": reasoning,
            "classification_result": classification_result,
            "note": (
                "Art. 51 classification determines whether a GPAI model has systemic risk. "
                "The 10^25 FLOPs threshold creates a presumption but is not the only path — "
                "models with high impact capabilities or Commission designation also qualify. "
                "Final classification always requires expert review."
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
            article_number=51,
            article_title="Classification of General-Purpose AI Models with Systemic Risk",
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
            article_number=51,
            article_title="Classification of General-Purpose AI Models with Systemic Risk",
            one_sentence=(
                "Article 51 defines when a general-purpose AI model is classified "
                "as having systemic risk — based on high impact capabilities or "
                "training compute exceeding 10^25 FLOPs."
            ),
            official_summary=(
                "Art. 51 establishes classification rules for GPAI models with "
                "systemic risk. A GPAI model is classified as systemic risk if: "
                "(a) it has high impact capabilities evaluated via appropriate "
                "technical tools, methodologies, indicators and benchmarks; or "
                "(b) the Commission designates it based on Annex XIII criteria. "
                "Art. 51(2) creates a presumption: models trained with compute "
                "exceeding 10^25 FLOPs are presumed to have high impact capabilities. "
                "Art. 51(3) empowers the Commission to update the threshold via "
                "delegated acts as technology evolves."
            ),
            related_articles={
                "Art. 3(63)": "Definition of general-purpose AI model",
                "Art. 3(65)": "Definition of systemic risk",
                "Art. 52": "Obligations for providers of GPAI models",
                "Art. 55": "Additional obligations for systemic risk GPAI models",
                "Art. 89": "Scientific panel for qualified alerts",
                "Art. 97": "Delegated acts procedure for threshold amendments",
                "Annex XIII": "Criteria for designation of systemic risk GPAI models",
            },
            recital=(
                "Recital 110: General-purpose AI models could pose systemic risks "
                "which include actual or reasonably foreseeable negative effects in "
                "relation to major accidents, disruptions of critical sectors, "
                "serious consequences to public health and safety, or actual or "
                "reasonably foreseeable negative effects on democratic processes, "
                "public and economic security."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of training compute documentation (FLOPs figures)",
                    "Detection of model capability benchmarks and evaluations",
                ],
                "requires_human_judgment": [
                    "Whether the model truly has 'high impact capabilities'",
                    "Evaluation of benchmarks against systemic risk criteria",
                    "Verification of training compute figures",
                    "Assessment of Commission designation applicability",
                    "Monitoring for Commission delegated acts updating thresholds",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 provides: (1) a systemic risk "
                "classification decision tree (compute threshold check -> capability "
                "assessment -> Commission designation check), (2) training compute "
                "documentation detection, (3) capability benchmark evaluation guidance. "
                "Note: automated scanning can only flag potential indicators — the final "
                "classification always requires expert evaluation of model capabilities "
                "against Annex XIII criteria."
            ),
            enforcement_date="2025-08-02",
            waiting_for="CEN-CENELEC harmonized standard for GPAI classification (expected 2027)",
        )

    # ── Action Plan ──

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details
        classification = details.get("classification_result", "")

        # Always: assess systemic risk classification
        actions.append(ActionItem(
            priority="CRITICAL",
            article="Art. 51(1)",
            action="Complete GPAI model systemic risk classification assessment",
            details=(
                "Evaluate whether your GPAI model has systemic risk under Art. 51(1): "
                "(1) Does it have high impact capabilities (evaluated via appropriate "
                "technical tools, methodologies, indicators, and benchmarks)? "
                "(2) Has the Commission designated it based on Annex XIII criteria? "
                "Document the assessment reasoning and conclusion."
            ),
            effort="4-8 hours (may require technical evaluation and legal counsel)",
            action_type="human_judgment_required",
        ))

        # If compute exceeds threshold
        if details.get("training_compute_exceeds_threshold") is True:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 51(2)",
                action="Address 10^25 FLOPs presumption of systemic risk",
                details=(
                    "Training compute exceeds the 10^25 FLOPs threshold. "
                    "Per Art. 51(2), the model is PRESUMED to have high impact "
                    "capabilities. This triggers Art. 55 obligations: model evaluation, "
                    "adversarial testing, serious incident tracking and reporting, "
                    "and adequate cybersecurity protection. "
                    "Notify the AI Office of the classification."
                ),
                effort="Significant — plan for comprehensive Art. 55 compliance work",
                action_type="human_judgment_required",
            ))

        # If classified as potentially systemic risk
        if "SYSTEMIC_RISK" in classification or "DESIGNATED" in classification:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 55",
                action="Plan Art. 55 compliance for systemic risk GPAI model",
                details=(
                    "If classified as systemic risk, the model must comply with "
                    "Art. 55 additional obligations: (a) perform model evaluation "
                    "including adversarial testing, (b) assess and mitigate systemic "
                    "risks, (c) track and report serious incidents, (d) ensure "
                    "adequate cybersecurity protection. "
                    "Start with model evaluation and adversarial testing."
                ),
                effort="Significant — ongoing compliance requirement",
                action_type="human_judgment_required",
            ))

        # If not a GPAI model
        if details.get("is_gpai_model") is False:
            actions.append(ActionItem(
                priority="LOW",
                article="Art. 51",
                action="Confirm non-GPAI classification",
                details=(
                    "The system does not appear to be a general-purpose AI model. "
                    "Art. 51 classification requirements do not apply. "
                    "Document this determination for compliance records."
                ),
                effort="30 minutes",
                action_type="human_judgment_required",
            ))

        # Always: monitor Commission delegated acts
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 51(3)",
            action="Monitor Commission delegated acts for threshold updates",
            details=(
                "The Commission may adopt delegated acts to amend the 10^25 FLOPs "
                "threshold and update benchmarks/indicators. Monitor for changes "
                "that may affect your model's classification status."
            ),
            effort="Ongoing — periodic review",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=51,
            article_title="Classification of General-Purpose AI Models with Systemic Risk",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "GPAI systemic risk classification is primarily a human judgment "
                "based on model capabilities, training compute, and Commission "
                "designation. Automated scanning can only flag potential indicators. "
                "Based on ComplianceLint compliance checklist; official CEN-CENELEC "
                "standards (expected 2027) may modify these criteria."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art51Module:
    return Art51Module()
