"""
Article 55: Obligations of Providers of General-Purpose AI Models with Systemic Risk.

Art. 55 imposes additional obligations on providers of GPAI models classified as
having systemic risk (per Art. 51). These obligations apply IN ADDITION to Art. 53
obligations and include model evaluation, systemic risk assessment, incident tracking,
and cybersecurity protection.

This module reads AI-provided compliance_answers["art55"] and maps each answer
to a Finding. No regex, keyword, or AST scanning is performed — detection is
entirely the AI's responsibility.

Obligation mapping:
  ART55-OBL-1a → has_model_evaluation + has_adversarial_testing (_finding_from_answer)
  ART55-OBL-1b → UNABLE_TO_DETERMINE always (manual, systemic risk assessment)
  ART55-OBL-1c → has_incident_tracking (_finding_from_answer)
  ART55-OBL-1d → has_cybersecurity_protection (_finding_from_answer)

Boundary cases:
  - All obligations only apply to GPAI models with systemic risk (has_systemic_risk=True).
    When False → NOT_APPLICABLE for the entire article.
  - OBL-1b is manual (requires legal/domain judgment on systemic risks) — always UTD.
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


class Art55Module(BaseArticleModule):
    """Article 55: Obligations of Providers of General-Purpose AI Models with Systemic Risk."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=55,
            article_title="Obligations of Providers of General-Purpose AI Models with Systemic Risk",
        )

    # ── Scanning ──

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for Art. 55 systemic risk GPAI obligations.

        Reads compliance_answers["art55"] from the AI context. Maps each field
        to obligation findings:
          - has_model_evaluation + has_adversarial_testing → ART55-OBL-1a
          - ART55-OBL-1b → always UTD (systemic risk assessment — manual)
          - has_incident_tracking → ART55-OBL-1c
          - has_cybersecurity_protection → ART55-OBL-1d

        All obligations only apply when has_systemic_risk=True.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for Art. 55 systemic risk obligations.
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

        answers = ctx.get_article_answers("art55")

        has_systemic_risk = answers.get("has_systemic_risk")
        has_model_evaluation = answers.get("has_model_evaluation")
        has_adversarial_testing = answers.get("has_adversarial_testing")
        evaluation_evidence = answers.get("evaluation_evidence", [])
        has_incident_tracking = answers.get("has_incident_tracking")
        incident_evidence = answers.get("incident_evidence", [])
        has_cybersecurity_protection = answers.get("has_cybersecurity_protection")
        cybersecurity_evidence = answers.get("cybersecurity_evidence", [])

        # Scope gate: Art. 55 only applies to GPAI with systemic risk
        if has_systemic_risk is False:
            for obl_id in ["ART55-OBL-1a", "ART55-OBL-1b", "ART55-OBL-1c", "ART55-OBL-1d"]:
                findings.append(Finding(
                    obligation_id=obl_id,
                    file_path="project-wide",
                    line_number=None,
                    level=ComplianceLevel.NOT_APPLICABLE,
                    confidence=Confidence.MEDIUM,
                    description=(
                        "GPAI model does not have systemic risk — "
                        "Art. 55 obligations only apply to GPAI models "
                        "classified as having systemic risk per Art. 51."
                    ),
                    gap_type=GapType.PROCESS,
                ))

            details = {
                "has_systemic_risk": has_systemic_risk,
                "note": "Art. 55 not applicable — model does not have systemic risk.",
            }

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
                article_number=55,
                article_title="Obligations of Providers of General-Purpose AI Models with Systemic Risk",
                project_path=project_path,
                scan_date=datetime.now(timezone.utc).isoformat(),
                files_scanned=file_count,
                language_detected=language,
                overall_level=self._compute_overall_level(findings),
                overall_confidence=Confidence.LOW,
                findings=findings,
                details=details,
            )

        # ── ART55-OBL-1a: Model evaluation and adversarial testing ──
        # Combines has_model_evaluation and has_adversarial_testing.
        # Both must be True for PARTIAL; either False → NON_COMPLIANT.
        if has_model_evaluation is not None and has_adversarial_testing is not None:
            combined = has_model_evaluation and has_adversarial_testing
        elif has_model_evaluation is None and has_adversarial_testing is None:
            combined = None
        else:
            # One is known, one is None — if the known one is False, combined is False
            # Otherwise we can't determine (one True + one None = None)
            if has_model_evaluation is False or has_adversarial_testing is False:
                combined = False
            else:
                combined = None

        findings.append(self._finding_from_answer(
            obligation_id="ART55-OBL-1a",
            answer=combined,
            true_description=(
                "Model evaluation and adversarial testing documentation found. "
                "Verify evaluation uses standardised protocols reflecting the state of the art "
                "and that adversarial testing targets systemic risk identification and mitigation."
            ),
            false_description=(
                "Model evaluation or adversarial testing not found. "
                "Art. 55(1)(a) requires performing model evaluation per standardised protocols "
                "and conducting documented adversarial testing to identify and mitigate systemic risks."
            ),
            none_description=(
                "Cannot determine whether model evaluation and adversarial testing are performed. "
                "Art. 55(1)(a) requires standardised evaluation and documented adversarial testing."
            ),
            evidence=evaluation_evidence if isinstance(evaluation_evidence, list) else [],
            gap_type=GapType.TECHNICAL,
        ))

        # ── ART55-OBL-1b: Systemic risk assessment ──
        # Manual obligation — always UTD. Requires domain/legal judgment.
        findings.append(Finding(
            obligation_id="ART55-OBL-1b",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Systemic risk assessment requires human review. "
                "Art. 55(1)(b) requires assessing and mitigating possible systemic risks "
                "at Union level, including their sources, that may stem from the development, "
                "placing on the market, or use of the GPAI model."
            ),
            remediation=(
                "Conduct a formal systemic risk assessment covering: potential for "
                "large-scale harm, risks from development/deployment/use, risk sources, "
                "and mitigation measures. Document the assessment and its conclusions."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART55-OBL-1c: Incident tracking and reporting ──
        findings.append(self._finding_from_answer(
            obligation_id="ART55-OBL-1c",
            answer=has_incident_tracking,
            true_description=(
                "Incident tracking system found. Verify it covers serious incidents, "
                "includes corrective measures, and enables reporting to the AI Office "
                "and national competent authorities without undue delay."
            ),
            false_description=(
                "No incident tracking system found. Art. 55(1)(c) requires tracking, "
                "documenting, and reporting serious incidents and corrective measures "
                "to the AI Office without undue delay."
            ),
            none_description=(
                "Cannot determine whether incident tracking is in place. "
                "Art. 55(1)(c) requires incident tracking, documentation, and reporting "
                "to the AI Office."
            ),
            evidence=incident_evidence if isinstance(incident_evidence, list) else [],
            gap_type=GapType.PROCESS,
        ))

        # ── ART55-OBL-1d: Cybersecurity protection ──
        findings.append(self._finding_from_answer(
            obligation_id="ART55-OBL-1d",
            answer=has_cybersecurity_protection,
            true_description=(
                "Cybersecurity protection measures found. Verify they provide adequate "
                "protection for both the GPAI model and the physical infrastructure."
            ),
            false_description=(
                "No cybersecurity protection measures found. Art. 55(1)(d) requires "
                "ensuring an adequate level of cybersecurity protection for the GPAI model "
                "with systemic risk and the physical infrastructure of the model."
            ),
            none_description=(
                "Cannot determine whether cybersecurity protection is adequate. "
                "Art. 55(1)(d) requires adequate cybersecurity for model and infrastructure."
            ),
            evidence=cybersecurity_evidence if isinstance(cybersecurity_evidence, list) else [],
            gap_type=GapType.CODE,
        ))

        details = {
            "has_systemic_risk": has_systemic_risk,
            "has_model_evaluation": has_model_evaluation,
            "has_adversarial_testing": has_adversarial_testing,
            "has_incident_tracking": has_incident_tracking,
            "has_cybersecurity_protection": has_cybersecurity_protection,
            "note": (
                "Art. 55 imposes additional obligations on GPAI model providers "
                "with systemic risk, in addition to Art. 53 general GPAI obligations."
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
            article_number=55,
            article_title="Obligations of Providers of General-Purpose AI Models with Systemic Risk",
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
            article_number=55,
            article_title="Obligations of Providers of General-Purpose AI Models with Systemic Risk",
            one_sentence=(
                "Article 55 requires providers of GPAI models with systemic risk to perform "
                "model evaluation, assess systemic risks, track incidents, and ensure cybersecurity."
            ),
            official_summary=(
                "Art. 55 imposes additional obligations on providers of general-purpose AI models "
                "classified as having systemic risk (per Art. 51). In addition to Art. 53 "
                "obligations, providers must: (a) perform model evaluation using standardised "
                "protocols including adversarial testing to identify and mitigate systemic risks; "
                "(b) assess and mitigate possible systemic risks at Union level; (c) track, "
                "document, and report serious incidents and corrective measures to the AI Office "
                "without undue delay; (d) ensure adequate cybersecurity protection for the model "
                "and its physical infrastructure."
            ),
            related_articles={
                "Art. 51": "Classification of GPAI models with systemic risk",
                "Art. 53": "General obligations for all GPAI model providers",
                "Art. 54": "Authorised representatives for third-country providers",
                "Art. 55(2)": "Code of practice compliance as presumption of conformity",
            },
            recital=(
                "Recital 110: Providers of general-purpose AI models with systemic risk should "
                "be subject to additional obligations, including performing model evaluation, "
                "assessing and mitigating systemic risks, and ensuring adequate cybersecurity."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of model evaluation scripts and benchmark results",
                    "Detection of adversarial testing documentation",
                    "Detection of incident tracking systems or procedures",
                    "Detection of cybersecurity policies and access controls",
                ],
                "requires_human_judgment": [
                    "Whether model evaluation uses appropriate standardised protocols",
                    "Whether systemic risks at Union level are adequately assessed",
                    "Whether incident reporting procedures meet 'without undue delay' requirement",
                    "Whether cybersecurity level is 'adequate' for the systemic risk",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 provides: (1) model evaluation and "
                "adversarial testing detection, (2) incident tracking system detection, "
                "(3) cybersecurity protection detection. Note: systemic risk assessment (Art. 55(1)(b)) "
                "always requires human judgment and cannot be automated."
            ),
            enforcement_date="2025-08-02",
            waiting_for="CEN-CENELEC harmonized standard for GPAI systemic risk (expected 2027)",
        )

    # ── Action Plan ──

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_systemic_risk") is False:
            return ActionPlan(
                article_number=55,
                article_title="Obligations of Providers of General-Purpose AI Models with Systemic Risk",
                project_path=scan_result.project_path,
                actions=[],
                disclaimer=(
                    "Art. 55 does not apply — model not classified as having systemic risk."
                ),
            )

        if details.get("has_model_evaluation") is not True:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 55(1)(a)",
                action="Perform standardised model evaluation with adversarial testing",
                details=(
                    "Art. 55(1)(a) requires model evaluation per standardised protocols and "
                    "documented adversarial testing to identify and mitigate systemic risks.\n\n"
                    "  Steps:\n"
                    "  1. Select evaluation benchmarks relevant to your model's capabilities\n"
                    "  2. Run benchmarks per standardised protocols (e.g., NIST AI 600-1)\n"
                    "  3. Conduct red-teaming / adversarial testing for systemic risks\n"
                    "  4. Document all results, including identified risks and mitigations"
                ),
                effort="1-4 weeks (depending on model complexity)",
            ))

        if details.get("has_adversarial_testing") is not True and details.get("has_model_evaluation") is True:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 55(1)(a)",
                action="Document adversarial testing results",
                details=(
                    "Model evaluation found but adversarial testing documentation is missing. "
                    "Art. 55(1)(a) specifically requires adversarial testing with documentation."
                ),
                effort="1-2 weeks",
            ))

        # Systemic risk assessment — always human judgment
        actions.append(ActionItem(
            priority="CRITICAL",
            article="Art. 55(1)(b)",
            action="Conduct formal systemic risk assessment at Union level",
            details=(
                "Art. 55(1)(b) requires assessing and mitigating systemic risks at Union level. "
                "This includes identifying risk sources from development, market placement, and use."
            ),
            effort="2-4 weeks (legal and domain expert involvement recommended)",
            action_type="human_judgment_required",
        ))

        if details.get("has_incident_tracking") is not True:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 55(1)(c)",
                action="Establish incident tracking and reporting procedures",
                details=(
                    "Art. 55(1)(c) requires tracking, documenting, and reporting serious "
                    "incidents and corrective measures to the AI Office without undue delay.\n\n"
                    "  Steps:\n"
                    "  1. Set up incident tracking system (e.g., dedicated issue tracker)\n"
                    "  2. Define what constitutes a 'serious incident' for your model\n"
                    "  3. Create reporting templates for AI Office communication\n"
                    "  4. Establish escalation and response procedures"
                ),
                effort="1-2 weeks",
            ))

        if details.get("has_cybersecurity_protection") is not True:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 55(1)(d)",
                action="Ensure adequate cybersecurity protection for model and infrastructure",
                details=(
                    "Art. 55(1)(d) requires adequate cybersecurity for the GPAI model and its "
                    "physical infrastructure.\n\n"
                    "  Steps:\n"
                    "  1. Assess current security posture of model and infrastructure\n"
                    "  2. Implement access controls, encryption, and monitoring\n"
                    "  3. Conduct vulnerability assessments\n"
                    "  4. Document security measures and incident response plan"
                ),
                effort="2-4 weeks",
            ))

        return ActionPlan(
            article_number=55,
            article_title="Obligations of Providers of General-Purpose AI Models with Systemic Risk",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 55 obligations are in addition to Art. 53 general GPAI obligations. "
                "Based on ComplianceLint compliance checklist; official CEN-CENELEC standards "
                "(expected 2027) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art55Module:
    return Art55Module()
