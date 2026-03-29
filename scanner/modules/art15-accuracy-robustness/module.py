"""
Article 15: Accuracy, Robustness and Cybersecurity.

Art. 15 requires high-risk AI systems to achieve appropriate levels of
accuracy, robustness, and cybersecurity throughout their lifecycle.

Obligation mapping:
  ART15-OBL-1   -> has_accuracy_testing (accuracy + robustness + cybersecurity)
  ART15-EMP-2   -> empowerment (Commission benchmarks) - gap_findings
  ART15-OBL-3   -> has_accuracy_testing (accuracy metrics declared)
  ART15-OBL-4   -> has_robustness_testing (error resilience)
  ART15-OBL-4b  -> conditional (feedback loops - online learning) - gap_findings
  ART15-OBL-5   -> has_fallback_behavior (cybersecurity resilience)
  ART15-OBL-5b  -> has_fallback_behavior (AI-specific vulnerabilities)
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


class Art15Module(BaseArticleModule):
    """Article 15: Accuracy, Robustness and Cybersecurity."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=15,
            article_title="Accuracy, Robustness and Cybersecurity",
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

        answers = ctx.get_article_answers("art15")

        has_accuracy = answers.get("has_accuracy_testing")
        if has_accuracy is None:
            has_accuracy = answers.get("has_accuracy_metrics")  # alias
        accuracy_evidence = answers.get("accuracy_evidence") or []
        has_robustness = answers.get("has_robustness_testing")
        if has_robustness is None:
            has_robustness = answers.get("has_error_handling")  # alias
        robustness_evidence = answers.get("robustness_evidence") or []
        has_fallback = answers.get("has_fallback_behavior")
        if has_fallback is None:
            has_fallback = answers.get("has_cybersecurity")  # alias

        acc_ev = accuracy_evidence or None
        rob_ev = robustness_evidence or None

        # -- ART15-OBL-1: Accuracy, robustness, cybersecurity --
        findings.append(self._finding_from_answer(
            obligation_id="ART15-OBL-1",
            answer=has_accuracy,
            true_description=(
                f"Accuracy testing found: {', '.join(accuracy_evidence)}."
                if accuracy_evidence
                else "Accuracy testing infrastructure found."
            ),
            false_description=(
                "No accuracy testing detected. Art. 15(1) requires appropriate levels "
                "of accuracy, robustness, and cybersecurity throughout the lifecycle."
            ),
            none_description=(
                "AI could not determine whether accuracy testing exists."
            ),
            evidence=acc_ev,
            gap_type=GapType.CODE,
        ))

        # -- ART15-OBL-3: Accuracy metrics declared in instructions --
        findings.append(self._finding_from_answer(
            obligation_id="ART15-OBL-3",
            answer=has_accuracy,
            true_description=(
                "Accuracy metrics found. Verify they are declared in the "
                "accompanying instructions of use per Art. 15(3)."
            ),
            false_description=(
                "No accuracy metrics detected. Art. 15(3) requires accuracy levels "
                "and relevant metrics to be declared in instructions of use."
            ),
            none_description=(
                "AI could not determine whether accuracy metrics are declared."
            ),
            evidence=acc_ev,
            gap_type=GapType.PROCESS,
        ))

        # -- ART15-OBL-4: Error resilience --
        findings.append(self._finding_from_answer(
            obligation_id="ART15-OBL-4",
            answer=has_robustness,
            true_description=(
                f"Robustness/error handling found: {', '.join(robustness_evidence)}."
                if robustness_evidence
                else "Robustness testing infrastructure found."
            ),
            false_description=(
                "No robustness or error handling detected. Art. 15(4) requires "
                "resilience regarding errors, faults or inconsistencies."
            ),
            none_description=(
                "AI could not determine whether robustness measures exist."
            ),
            evidence=rob_ev,
            gap_type=GapType.CODE,
        ))

        # -- ART15-OBL-5: Cybersecurity resilience --
        findings.append(self._finding_from_answer(
            obligation_id="ART15-OBL-5",
            answer=has_fallback,
            true_description=(
                "Cybersecurity measures found. Art. 15(5) requires resilience "
                "against unauthorized third-party attempts to alter use or performance."
            ),
            false_description=(
                "No cybersecurity measures detected. Art. 15(5) requires resilience "
                "against unauthorized alteration of use, outputs or performance."
            ),
            none_description=(
                "AI could not determine whether cybersecurity measures exist."
            ),
            gap_type=GapType.CODE,
        ))

        # -- ART15-OBL-5b: AI-specific vulnerability measures --
        findings.append(self._finding_from_answer(
            obligation_id="ART15-OBL-5b",
            answer=has_fallback,
            true_description=(
                "Security measures found. Verify they address AI-specific vulnerabilities: "
                "data poisoning, model poisoning, adversarial examples, "
                "confidentiality attacks, model flaws per Art. 15(5)."
            ),
            false_description=(
                "No AI-specific security measures detected. Art. 15(5) requires measures "
                "to prevent data poisoning, model poisoning, adversarial examples, "
                "confidentiality attacks, and model flaws."
            ),
            none_description=(
                "AI could not determine whether AI-specific security measures exist."
            ),
            gap_type=GapType.CODE,
        ))

        details = {
            "has_accuracy_testing": has_accuracy,
            "accuracy_evidence": accuracy_evidence,
            "has_robustness_testing": has_robustness,
            "robustness_evidence": robustness_evidence,
            "has_fallback_behavior": has_fallback,
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
            article_number=15,
            article_title="Accuracy, Robustness and Cybersecurity",
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
            article_number=15,
            article_title="Accuracy, Robustness and Cybersecurity",
            one_sentence=(
                "High-risk AI systems must achieve appropriate accuracy, robustness, "
                "and cybersecurity, performing consistently throughout their lifecycle."
            ),
            official_summary=(
                "Art. 15 requires appropriate levels of accuracy, robustness, and "
                "cybersecurity. Accuracy metrics must be declared in instructions of use. "
                "Systems must be resilient to errors and unauthorized alteration, "
                "with specific measures against data poisoning, adversarial attacks, "
                "and model flaws. Feedback loops in online learning systems must be mitigated."
            ),
            related_articles={
                "Art. 9": "Risk management (accuracy/robustness feed into risk assessment)",
                "Art. 13(3)(b)(ii)": "Accuracy metrics must be in instructions of use",
                "Art. 10": "Data governance (data quality affects accuracy)",
            },
            recital=(
                "Recital 74: Accuracy, robustness and cybersecurity are essential "
                "for high-risk AI systems to function reliably."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of accuracy testing infrastructure",
                    "Detection of error handling / fallback patterns",
                    "Detection of cybersecurity measures",
                    "Detection of adversarial defense tooling",
                ],
                "requires_human_judgment": [
                    "Whether accuracy levels are 'appropriate'",
                    "Whether robustness measures are adequate",
                    "Whether AI-specific vulnerabilities are addressed",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) accuracy metrics defined, "
                "(2) robustness testing, (3) error handling / fallback behavior, "
                "(4) cybersecurity measures, (5) AI-specific attack mitigation. "
                "Based on: ISO/IEC 42001:2023, NIST AI RMF."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_accuracy_testing") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 15(1), 15(3)",
                action="Implement accuracy testing and declare metrics",
                details=(
                    "Art. 15(1) requires appropriate accuracy. Art. 15(3) requires "
                    "accuracy metrics declared in instructions of use. "
                    "Define metrics (accuracy, precision, recall, F1, AUC), "
                    "run evaluations, document results."
                ),
                effort="8-16 hours",
            ))

        if details.get("has_robustness_testing") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 15(4)",
                action="Implement robustness and error handling",
                details=(
                    "Art. 15(4) requires resilience to errors, faults and inconsistencies. "
                    "Add: input validation, error handling, graceful degradation, "
                    "integration tests, and backup/fail-safe plans."
                ),
                effort="4-16 hours",
            ))

        if details.get("has_fallback_behavior") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 15(5)",
                action="Implement cybersecurity measures for AI-specific attacks",
                details=(
                    "Art. 15(5) requires resilience against unauthorized alteration. "
                    "Address: data poisoning prevention, adversarial input detection, "
                    "model integrity verification, access control, rate limiting."
                ),
                effort="8-24 hours",
            ))

        return ActionPlan(
            article_number=15,
            article_title="Accuracy, Robustness and Cybersecurity",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 15 combines accuracy testing with cybersecurity requirements. "
                "Automated scanning detects testing infrastructure and security patterns "
                "but cannot assess appropriateness or completeness."
            ),
        )


def create_module() -> Art15Module:
    return Art15Module()
