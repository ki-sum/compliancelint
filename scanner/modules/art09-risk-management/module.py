"""
Article 9: Risk Management System — Module implementation using unified protocol.

Art. 9 requires high-risk AI systems to have a continuous risk management system
that identifies, analyzes, evaluates, and mitigates risks throughout the lifecycle.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art9"). No regex or keyword scanning is performed here.

Obligation mapping:
  ART09-OBL-1   → has_risk_docs (RMS established/documented)
  ART09-OBL-2   → has_risk_docs (continuous iterative process)
  ART09-OBL-2a  → has_risk_docs (identify/analyze risks)
  ART09-OBL-2b  → has_risk_docs (intended use + misuse evaluation)
  ART09-OBL-2c  → UNABLE_TO_DETERMINE always (post-market monitoring feedback)
  ART09-OBL-2d  → has_risk_code_patterns (adopt risk measures)
  ART09-OBL-3   → handled by gap_findings (scope-definition clause, manual)
  ART09-OBL-4   → UNABLE_TO_DETERMINE always (combined effects — manual)
  ART09-OBL-5   → UNABLE_TO_DETERMINE always (residual risk acceptable — manual)
  ART09-OBL-5a  → has_risk_code_patterns (eliminate risks by design)
  ART09-OBL-5b  → has_risk_code_patterns (implement mitigations)
  ART09-OBL-5c  → UNABLE_TO_DETERMINE always (deployer info/training — manual)
  ART09-OBL-5d  → UNABLE_TO_DETERMINE always (deployer context — manual)
  ART09-OBL-6   → has_testing_infrastructure (testing for risk measures)
  ART09-OBL-8a  → has_testing_infrastructure (testing throughout dev)
  ART09-OBL-8b  → has_defined_metrics (metrics + probabilistic thresholds)
  ART09-OBL-9   → conditional (affects_children) — handled by gap_findings
  ART09-PERM-7  → permission — handled by gap_findings (skipped, no finding)
  ART09-PERM-10 → permission — handled by gap_findings (skipped, no finding)

NOTE — "handled by gap_findings" means:
  ObligationEngine.gap_findings() auto-generates the finding for any obligation
  in the JSON that this scan() has NOT explicitly emitted a Finding for.

  Rules (see obligation_engine.py gap_findings() docstring for full detail):
  - obligation (manual, no scope_limitation) → UNABLE_TO_DETERMINE [COVERAGE GAP]
  - obligation with scope_limitation → CONDITIONAL or NOT_APPLICABLE (context-driven)
  - permission / exception / empowerment (no scope_limitation) → SKIPPED entirely
  - permission / exception WITH scope_limitation → CONDITIONAL (not skipped!)

  Consequence for maintenance:
  Do NOT add a findings.append() here for new obligations added to the JSON.
  gap_findings() will handle them automatically. Only add explicit scan() code
  when you need to map a compliance_answers field to that obligation's level
  (i.e., you want something better than UNABLE_TO_DETERMINE).
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


class Art09Module(BaseArticleModule):
    """Article 9: Risk Management System compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=9,
            article_title="Risk Management System",
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

        answers = ctx.get_article_answers("art9")

        has_risk_docs = answers.get("has_risk_docs")
        risk_doc_paths = answers.get("risk_doc_paths") or []
        has_risk_code = answers.get("has_risk_code_patterns")
        if has_risk_code is None:
            has_risk_code = answers.get("has_risk_code")  # alias
        risk_code_evidence = answers.get("risk_code_evidence") or []
        has_testing = answers.get("has_testing_infrastructure")
        if has_testing is None:
            has_testing = answers.get("has_testing")  # alias
        testing_evidence = answers.get("testing_evidence") or []
        has_defined_metrics = answers.get("has_defined_metrics")
        if has_defined_metrics is None:
            has_defined_metrics = answers.get("has_metrics")  # alias
        metrics_evidence = answers.get("metrics_evidence") or []

        doc_evidence = risk_doc_paths or None
        code_evidence = risk_code_evidence or None
        test_evidence = testing_evidence or None

        # ── ART09-OBL-1: RMS established, implemented, documented, maintained ──
        findings.append(self._finding_from_answer(
            obligation_id="ART09-OBL-1",
            answer=has_risk_docs,
            true_description=(
                f"Risk management documentation found: {', '.join(risk_doc_paths)}."
                if risk_doc_paths
                else "Risk management documentation found."
            ),
            false_description=(
                "No risk management documentation found. Art. 9(1) requires "
                "a risk management system that is established, implemented, "
                "documented, and maintained."
            ),
            none_description=(
                "AI could not determine whether risk management documentation exists."
            ),
            evidence=doc_evidence,
            gap_type=GapType.PROCESS,
        ))

        # ── ART09-OBL-2: Continuous iterative process ──
        findings.append(self._finding_from_answer(
            obligation_id="ART09-OBL-2",
            answer=has_risk_docs,
            true_description=(
                "Risk documentation found. Verify it represents a continuous "
                "iterative process with regular systematic review per Art. 9(2)."
            ),
            false_description=(
                "No risk documentation found. Art. 9(2) requires a continuous "
                "iterative risk management process throughout the entire lifecycle."
            ),
            none_description=(
                "AI could not determine whether a continuous risk management process exists."
            ),
            evidence=doc_evidence,
            gap_type=GapType.PROCESS,
        ))

        # ── ART09-OBL-2a: Identify/analyze known + foreseeable risks ──
        findings.append(self._finding_from_answer(
            obligation_id="ART09-OBL-2a",
            answer=has_risk_docs,
            true_description=(
                "Risk documentation found. Verify it identifies and analyzes "
                "known and foreseeable risks to health, safety, and fundamental "
                "rights per Art. 9(2)(a)."
            ),
            false_description=(
                "No risk identification documentation found. Art. 9(2)(a) requires "
                "identification and analysis of known and foreseeable risks."
            ),
            none_description=(
                "AI could not determine whether risk identification has been performed."
            ),
            evidence=doc_evidence,
            gap_type=GapType.PROCESS,
        ))

        # ── ART09-OBL-2b: Evaluate risks from intended use + misuse ──
        findings.append(self._finding_from_answer(
            obligation_id="ART09-OBL-2b",
            answer=has_risk_docs,
            true_description=(
                "Risk documentation found. Verify it evaluates risks from "
                "intended use AND reasonably foreseeable misuse per Art. 9(2)(b)."
            ),
            false_description=(
                "No risk evaluation documentation found. Art. 9(2)(b) requires "
                "risk evaluation for intended use and foreseeable misuse."
            ),
            none_description=(
                "AI could not determine whether misuse risk evaluation exists."
            ),
            evidence=doc_evidence,
            gap_type=GapType.PROCESS,
        ))

        # ── ART09-OBL-2c: Post-market monitoring feedback (always manual) ──
        findings.append(Finding(
            obligation_id="ART09-OBL-2c",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Post-market monitoring feedback into risk management requires human review. "
                "Art. 9(2)(c) requires evaluation of risks based on post-market monitoring "
                "data (Art. 72). Cannot be assessed from code alone."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART09-OBL-2d: Adopt risk management measures ──
        findings.append(self._finding_from_answer(
            obligation_id="ART09-OBL-2d",
            answer=has_risk_code,
            true_description=(
                f"Risk management code patterns found: {', '.join(risk_code_evidence)}."
                if risk_code_evidence
                else "Risk management code patterns found."
            ),
            false_description=(
                "No risk management code patterns detected (guardrails, safety checks, "
                "input validation). Art. 9(2)(d) requires adoption of appropriate "
                "risk management measures."
            ),
            none_description=(
                "AI could not determine whether risk management measures are implemented in code."
            ),
            evidence=code_evidence,
            gap_type=GapType.CODE,
        ))

        # ── ART09-OBL-4: Combined effects consideration (always manual) ──
        findings.append(Finding(
            obligation_id="ART09-OBL-4",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Combined effects analysis requires human review. Art. 9(4) requires "
                "due consideration of effects from combined application of all Section "
                "requirements. Cannot be assessed from code alone."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART09-OBL-5: Residual risk acceptable (always manual) ──
        findings.append(Finding(
            obligation_id="ART09-OBL-5",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Residual risk acceptability requires human judgment. Art. 9(5) requires "
                "that residual risk per hazard and overall residual risk be judged acceptable."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART09-OBL-5a: Eliminate/reduce risks through design ──
        findings.append(self._finding_from_answer(
            obligation_id="ART09-OBL-5a",
            answer=has_risk_code,
            true_description=(
                "Safety-by-design patterns found in code. Art. 9(5)(a) requires "
                "elimination or reduction of risks through adequate design."
            ),
            false_description=(
                "No safety-by-design patterns detected. Art. 9(5)(a) requires "
                "elimination or reduction of risks through adequate design and development."
            ),
            none_description=(
                "AI could not determine whether risks are addressed through design."
            ),
            evidence=code_evidence,
            gap_type=GapType.CODE,
        ))

        # ── ART09-OBL-5b: Implement mitigation measures ──
        findings.append(self._finding_from_answer(
            obligation_id="ART09-OBL-5b",
            answer=has_risk_code,
            true_description=(
                "Risk mitigation code patterns found. Art. 9(5)(b) requires "
                "mitigation and control measures for non-eliminable risks."
            ),
            false_description=(
                "No mitigation code patterns detected. Art. 9(5)(b) requires "
                "implementation of adequate mitigation and control measures."
            ),
            none_description=(
                "AI could not determine whether mitigation measures are implemented."
            ),
            evidence=code_evidence,
            gap_type=GapType.CODE,
        ))

        # ── ART09-OBL-5c: Provide info + training to deployers (always manual) ──
        findings.append(Finding(
            obligation_id="ART09-OBL-5c",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Deployer information and training requires human review. Art. 9(5)(c) "
                "requires provision of information per Art. 13 and training to deployers."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART09-OBL-5d: Deployer context consideration (always manual) ──
        findings.append(Finding(
            obligation_id="ART09-OBL-5d",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Deployer context consideration requires human review. Art. 9(5) requires "
                "due consideration of deployer's technical knowledge, experience, education, "
                "and the presumable context of use."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART09-OBL-6: Testing for risk management ──
        findings.append(self._finding_from_answer(
            obligation_id="ART09-OBL-6",
            answer=has_testing,
            true_description=(
                f"Testing infrastructure found: {', '.join(testing_evidence)}."
                if testing_evidence
                else "Testing infrastructure found."
            ),
            false_description=(
                "No testing infrastructure detected. Art. 9(6) requires testing "
                "to identify appropriate risk management measures and ensure "
                "consistent performance."
            ),
            none_description=(
                "AI could not determine whether testing infrastructure exists."
            ),
            evidence=test_evidence,
            gap_type=GapType.CODE,
        ))

        # ── ART09-OBL-8a: Testing throughout development ──
        findings.append(self._finding_from_answer(
            obligation_id="ART09-OBL-8a",
            answer=has_testing,
            true_description=(
                "Testing infrastructure found. Art. 9(8) requires testing throughout "
                "development and prior to market placement."
            ),
            false_description=(
                "No testing infrastructure detected. Art. 9(8) requires testing "
                "throughout the development process and prior to market placement."
            ),
            none_description=(
                "AI could not determine whether testing is performed throughout development."
            ),
            evidence=test_evidence,
            gap_type=GapType.CODE,
        ))

        # ── ART09-OBL-8b: Defined metrics + probabilistic thresholds ──
        findings.append(self._finding_from_answer(
            obligation_id="ART09-OBL-8b",
            answer=has_defined_metrics,
            true_description=(
                f"Defined metrics found: {', '.join(metrics_evidence)}."
                if metrics_evidence
                else "Defined metrics and thresholds found."
            ),
            false_description=(
                "No defined metrics or probabilistic thresholds detected. Art. 9(8) "
                "requires testing against prior defined metrics and probabilistic "
                "thresholds appropriate to the intended purpose."
            ),
            none_description=(
                "AI could not determine whether prior defined metrics and "
                "probabilistic thresholds are used."
            ),
            evidence=metrics_evidence or None,
            gap_type=GapType.CODE,
        ))

        # Build details dict
        details = {
            "has_risk_docs": has_risk_docs,
            "risk_doc_paths": risk_doc_paths,
            "has_risk_code_patterns": has_risk_code,
            "risk_code_evidence": risk_code_evidence,
            "has_testing_infrastructure": has_testing,
            "testing_evidence": testing_evidence,
            "has_defined_metrics": has_defined_metrics,
            "metrics_evidence": metrics_evidence,
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
            article_number=9,
            article_title="Risk Management System",
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
            article_number=9,
            article_title="Risk Management System",
            one_sentence=(
                "High-risk AI systems must have a continuous risk management system "
                "that identifies, analyzes, and mitigates risks throughout the entire lifecycle."
            ),
            official_summary=(
                "Art. 9 requires providers of high-risk AI systems to establish, implement, "
                "document, and maintain a risk management system as a continuous iterative "
                "process. It must identify known and foreseeable risks to health, safety, and "
                "fundamental rights; evaluate risks from intended use and foreseeable misuse; "
                "adopt measures that eliminate risks by design, implement mitigations, and "
                "communicate residual risks. Testing must use prior defined metrics and "
                "probabilistic thresholds. Systems affecting children require specific assessment."
            ),
            related_articles={
                "Art. 13": "Transparency and provision of information to deployers",
                "Art. 15": "Accuracy, robustness, and cybersecurity (testing requirements)",
                "Art. 60": "Testing in real-world conditions",
                "Art. 72": "Post-market monitoring (feeds back into risk management)",
            },
            recital=(
                "Recitals 65-67: Risk management is the foundation of the high-risk AI "
                "framework. Measures must follow the hierarchy: eliminate, then reduce, "
                "then mitigate, then communicate."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of risk management documentation",
                    "Detection of risk mitigation code patterns",
                    "Detection of testing infrastructure",
                    "Detection of defined metrics and thresholds",
                ],
                "requires_human_judgment": [
                    "Risk identification completeness",
                    "Misuse scenario adequacy",
                    "Post-market monitoring feedback",
                    "Combined effects analysis",
                    "Residual risk acceptability",
                    "Deployer information and training sufficiency",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) documented risk "
                "management system maintained throughout lifecycle, (2) risk register with "
                "identified risks, (3) documented intended use and foreseeable misuse, "
                "(4) risk mitigation measures in code, (5) testing with quantitative metrics "
                "and probabilistic thresholds, (6) child-specific risk assessment (if applicable). "
                "Based on: ISO 14971, ISO/IEC 23894:2023, NIST AI RMF."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_risk_docs") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 9(1)-(2)",
                action="Create risk management plan and risk register",
                details=(
                    "Art. 9(1) requires an established, documented, and maintained risk "
                    "management system. Create: (1) risk_assessment.md following ISO 14971 "
                    "or NIST AI RMF, (2) risk_register.csv with risk ID, category, likelihood, "
                    "severity, mitigation strategy."
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_risk_code_patterns") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 9(2)(d), 9(5)(a)(b)",
                action="Implement code-level risk mitigations",
                details=(
                    "No risk mitigation patterns found. Art. 9(2)(d) requires adopting "
                    "risk management measures. Implement input validation, output guardrails, "
                    "safety checks, or content filters as appropriate."
                ),
                effort="4-16 hours",
            ))

        if details.get("has_testing_infrastructure") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 9(6), 9(8)",
                action="Create testing and evaluation infrastructure",
                details=(
                    "Art. 9(6) requires testing for risk management. Art. 9(8) requires "
                    "testing against defined metrics and probabilistic thresholds. Create "
                    "test suites, evaluation scripts, and defined pass/fail thresholds."
                ),
                effort="8-16 hours",
            ))

        if details.get("has_defined_metrics") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 9(8)",
                action="Define quantitative metrics and probabilistic thresholds",
                details=(
                    "Art. 9(8) explicitly requires 'prior defined metrics and probabilistic "
                    "thresholds.' Define measurable metrics (accuracy, precision, recall, F1, "
                    "AUC) with specific threshold values before testing."
                ),
                effort="4-8 hours",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 9(9)",
            action="Assess whether child-specific risk evaluation is required",
            details=(
                "Art. 9(9) requires consideration of adverse impact on persons under 18 "
                "and other vulnerable groups. Determine if this applies to your system."
            ),
            effort="1-4 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 9(2)(c)",
            action="Establish post-market monitoring feedback into risk management",
            details=(
                "Art. 9(2)(c) requires evaluation of risks based on post-market monitoring "
                "data (Art. 72). Define how deployment data feeds back into the risk register."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=9,
            article_title="Risk Management System",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 9 is primarily a documentation and process requirement. Automated "
                "scanning can detect presence of artifacts but cannot assess quality. "
                "Human expert review is essential."
            ),
        )


def create_module() -> Art09Module:
    return Art09Module()
