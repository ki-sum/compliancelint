"""
Article 53: Obligations for Providers of General-Purpose AI Models — Module implementation.

Art. 53 covers the core obligations for GPAI model providers:
  - Art. 53(1)(a): Technical documentation (Annex XI minimum)
  - Art. 53(1)(b): Downstream provider documentation (Annex XII minimum)
  - Art. 53(1)(c): Copyright compliance policy
  - Art. 53(1)(d): Public training data summary
  - Art. 53(2): Open-source exception for (1)(a) and (1)(b) (unless systemic risk)
  - Art. 53(3): Authority cooperation (manual, always UTD)

This module reads AI-provided compliance_answers["art53"] and maps each answer
to a Finding. No regex, keyword, or AST scanning is performed — detection is
entirely the AI's responsibility.

Obligation mapping:
  ART53-OBL-1a → has_technical_documentation (_finding_from_answer)
  ART53-OBL-1b → has_downstream_documentation (_finding_from_answer)
  ART53-OBL-1c → has_copyright_policy (_finding_from_answer)
  ART53-OBL-1d → has_training_data_summary (_finding_from_answer)
  ART53-EXC-2  → is_open_source_gpai (exception, custom Finding — informational)
  ART53-OBL-3  → UNABLE_TO_DETERMINE always (manual, authority cooperation)

Boundary cases:
  - OBL-1a and OBL-1b are exempt for open-source GPAI without systemic risk
    (Art. 53(2)). When is_open_source_gpai=True and has_systemic_risk!=True,
    these become NOT_APPLICABLE. The module handles this conditional logic.
  - EXC-2 is an exception type — uses custom Finding() to note whether the
    open-source exception applies.
  - OBL-3 is manual (authority cooperation) — always UTD.
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


class Art53Module(BaseArticleModule):
    """Article 53: Obligations for Providers of General-Purpose AI Models."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=53,
            article_title="Obligations for Providers of General-Purpose AI Models",
        )

    # ── Scanning ──

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for Art. 53 GPAI provider obligations using AI-provided answers.

        Reads compliance_answers["art53"] from the AI context. Maps each field
        to obligation findings:
          - has_technical_documentation → ART53-OBL-1a
          - has_downstream_documentation → ART53-OBL-1b
          - has_copyright_policy → ART53-OBL-1c
          - has_training_data_summary → ART53-OBL-1d
          - is_open_source_gpai → ART53-EXC-2 (exception)
          - ART53-OBL-3 → always UTD (authority cooperation)

        OBL-1a and OBL-1b are exempt for open-source GPAI without systemic risk.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for Art. 53 GPAI provider obligations.
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

        answers = ctx.get_article_answers("art53")

        has_technical_documentation = answers.get("has_technical_documentation")
        documentation_evidence = answers.get("documentation_evidence", [])
        has_downstream_documentation = answers.get("has_downstream_documentation")
        downstream_doc_evidence = answers.get("downstream_doc_evidence", [])
        has_copyright_policy = answers.get("has_copyright_policy")
        copyright_policy_evidence = answers.get("copyright_policy_evidence", [])
        has_training_data_summary = answers.get("has_training_data_summary")
        training_data_summary_public = answers.get("training_data_summary_public")
        training_data_evidence = answers.get("training_data_evidence", [])
        is_open_source_gpai = answers.get("is_open_source_gpai")
        has_systemic_risk = answers.get("has_systemic_risk")

        # Determine if open-source exception applies (Art. 53(2)):
        # Exception exempts OBL-1a and OBL-1b ONLY when:
        # 1. Model is open-source GPAI (free licence, params/weights public)
        # 2. Model does NOT have systemic risk
        open_source_exception_applies = (
            is_open_source_gpai is True and has_systemic_risk is not True
        )

        # ── ART53-OBL-1a: Technical documentation (Annex XI) ──
        if open_source_exception_applies:
            findings.append(Finding(
                obligation_id="ART53-OBL-1a",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.MEDIUM,
                description=(
                    "Open-source GPAI model without systemic risk — "
                    "Art. 53(1)(a) technical documentation obligation is exempted "
                    "per Art. 53(2) open-source exception."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            findings.append(self._finding_from_answer(
                obligation_id="ART53-OBL-1a",
                answer=has_technical_documentation,
                true_description=(
                    "Technical documentation found for the GPAI model. "
                    "Verify it includes training process, testing process, "
                    "evaluation results, and meets the minimum requirements "
                    "set out in Annex XI."
                ),
                false_description=(
                    "No technical documentation found for the GPAI model. "
                    "Art. 53(1)(a) requires providers to draw up and keep "
                    "up-to-date technical documentation including training, "
                    "testing, and evaluation information per Annex XI."
                ),
                none_description=(
                    "AI could not determine whether technical documentation exists. "
                    "Art. 53(1)(a) requires comprehensive model documentation "
                    "per Annex XI for the AI Office and national authorities."
                ),
                evidence=documentation_evidence if isinstance(documentation_evidence, list) else [],
                gap_type=GapType.PROCESS,
            ))

        # ── ART53-OBL-1b: Downstream provider documentation (Annex XII) ──
        if open_source_exception_applies:
            findings.append(Finding(
                obligation_id="ART53-OBL-1b",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.MEDIUM,
                description=(
                    "Open-source GPAI model without systemic risk — "
                    "Art. 53(1)(b) downstream documentation obligation is exempted "
                    "per Art. 53(2) open-source exception."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            findings.append(self._finding_from_answer(
                obligation_id="ART53-OBL-1b",
                answer=has_downstream_documentation,
                true_description=(
                    "Downstream provider documentation found. "
                    "Verify it enables downstream AI system providers to understand "
                    "capabilities and limitations, and meets Annex XII minimum elements."
                ),
                false_description=(
                    "No downstream provider documentation found. "
                    "Art. 53(1)(b) requires GPAI providers to make available "
                    "documentation enabling downstream AI system providers to "
                    "understand model capabilities and limitations per Annex XII."
                ),
                none_description=(
                    "AI could not determine whether downstream documentation exists. "
                    "Art. 53(1)(b) requires documentation for downstream providers "
                    "per Annex XII minimum elements."
                ),
                evidence=downstream_doc_evidence if isinstance(downstream_doc_evidence, list) else [],
                gap_type=GapType.PROCESS,
            ))

        # ── ART53-OBL-1c: Copyright compliance policy ──
        # Note: NOT exempted by the open-source exception
        findings.append(self._finding_from_answer(
            obligation_id="ART53-OBL-1c",
            answer=has_copyright_policy,
            true_description=(
                "Copyright compliance policy found. "
                "Verify the policy covers identification and compliance with "
                "reservation of rights (opt-out) per Directive 2019/790 Art. 4(3), "
                "including use of state-of-the-art technologies for compliance."
            ),
            false_description=(
                "No copyright compliance policy found. "
                "Art. 53(1)(c) requires GPAI providers to put in place a policy "
                "to comply with Union copyright law, in particular identifying and "
                "complying with reservation of rights per Directive 2019/790 Art. 4(3)."
            ),
            none_description=(
                "AI could not determine whether a copyright compliance policy exists. "
                "Art. 53(1)(c) requires a policy for Union copyright law compliance, "
                "including reservation of rights identification."
            ),
            evidence=copyright_policy_evidence if isinstance(copyright_policy_evidence, list) else [],
            gap_type=GapType.PROCESS,
        ))

        # ── ART53-OBL-1d: Public training data summary ──
        # Note: NOT exempted by the open-source exception
        findings.append(self._finding_from_answer(
            obligation_id="ART53-OBL-1d",
            answer=has_training_data_summary,
            true_description=(
                "Training data summary found. "
                "Verify the summary is sufficiently detailed and publicly available "
                "as required by Art. 53(1)(d), according to the AI Office template."
            ),
            false_description=(
                "No training data summary found. "
                "Art. 53(1)(d) requires GPAI providers to draw up and make publicly "
                "available a sufficiently detailed summary about training content, "
                "according to the AI Office template."
            ),
            none_description=(
                "AI could not determine whether a training data summary exists. "
                "Art. 53(1)(d) requires a public, sufficiently detailed summary "
                "about training content per the AI Office template."
            ),
            evidence=training_data_evidence if isinstance(training_data_evidence, list) else [],
            gap_type=GapType.PROCESS,
        ))

        # ── ART53-EXC-2: Open-source exception (Art. 53(2)) ──
        # Exception type — custom Finding, informational.
        # Notes whether the open-source exception applies to OBL-1a and OBL-1b.
        if is_open_source_gpai is True:
            if has_systemic_risk is True:
                findings.append(Finding(
                    obligation_id="ART53-EXC-2",
                    file_path="project-wide",
                    line_number=None,
                    level=ComplianceLevel.NON_COMPLIANT,
                    confidence=Confidence.MEDIUM,
                    description=(
                        "Open-source GPAI model WITH systemic risk — "
                        "the Art. 53(2) open-source exception does not apply. "
                        "All Art. 53(1) obligations remain in force despite the "
                        "open-source licence."
                    ),
                    gap_type=GapType.PROCESS,
                ))
            else:
                findings.append(Finding(
                    obligation_id="ART53-EXC-2",
                    file_path="project-wide",
                    line_number=None,
                    level=ComplianceLevel.COMPLIANT,
                    confidence=Confidence.MEDIUM,
                    description=(
                        "Open-source GPAI model without systemic risk — "
                        "Art. 53(2) exception applies. Art. 53(1)(a) and (1)(b) "
                        "obligations are exempted. Art. 53(1)(c) copyright policy "
                        "and Art. 53(1)(d) training data summary still apply."
                    ),
                    gap_type=GapType.PROCESS,
                ))
        elif is_open_source_gpai is False:
            findings.append(Finding(
                obligation_id="ART53-EXC-2",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.MEDIUM,
                description=(
                    "Model is not open-source GPAI — Art. 53(2) exception "
                    "does not apply. All Art. 53(1) obligations are in force."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            findings.append(Finding(
                obligation_id="ART53-EXC-2",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "Cannot determine whether the open-source GPAI exception "
                    "(Art. 53(2)) applies. Requires assessment of licence type, "
                    "parameter/weight public availability, and systemic risk status."
                ),
                gap_type=GapType.PROCESS,
            ))

        # ── ART53-OBL-3: Authority cooperation ──
        # Manual obligation — always UTD. AI cannot determine organizational processes.
        findings.append(Finding(
            obligation_id="ART53-OBL-3",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Authority cooperation requires human review. "
                "Art. 53(3) requires GPAI model providers to cooperate with "
                "the Commission and national competent authorities. This is an "
                "organizational process requirement that cannot be verified "
                "from source code."
            ),
            remediation=(
                "Establish a contact point and procedures for cooperation "
                "with the AI Office and national competent authorities. "
                "Document the liaison process and responsible personnel."
            ),
            gap_type=GapType.PROCESS,
        ))

        details = {
            "has_technical_documentation": has_technical_documentation,
            "has_downstream_documentation": has_downstream_documentation,
            "has_copyright_policy": has_copyright_policy,
            "has_training_data_summary": has_training_data_summary,
            "training_data_summary_public": training_data_summary_public,
            "is_open_source_gpai": is_open_source_gpai,
            "has_systemic_risk": has_systemic_risk,
            "open_source_exception_applies": open_source_exception_applies,
            "note": (
                "Art. 53 sets core obligations for GPAI model providers. "
                "Open-source GPAI models without systemic risk are exempt from "
                "technical documentation (1)(a) and downstream documentation (1)(b), "
                "but must still comply with copyright policy (1)(c) and "
                "training data summary (1)(d)."
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
            article_number=53,
            article_title="Obligations for Providers of General-Purpose AI Models",
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
            article_number=53,
            article_title="Obligations for Providers of General-Purpose AI Models",
            one_sentence=(
                "Article 53 requires GPAI model providers to maintain technical "
                "documentation, provide downstream documentation, have a copyright "
                "policy, and publish a training data summary."
            ),
            official_summary=(
                "Art. 53 establishes four core obligations for providers of "
                "general-purpose AI models: (a) draw up and maintain technical "
                "documentation per Annex XI; (b) provide documentation to downstream "
                "AI system providers per Annex XII; (c) put in place a copyright "
                "compliance policy including reservation of rights (opt-out) per "
                "Directive 2019/790; (d) make publicly available a sufficiently "
                "detailed training data summary per the AI Office template. "
                "Art. 53(2) exempts open-source GPAI models (without systemic risk) "
                "from obligations (a) and (b). Art. 53(3) requires cooperation with "
                "the Commission and national authorities."
            ),
            related_articles={
                "Art. 3(63)": "Definition of general-purpose AI model",
                "Art. 51": "Classification of GPAI models with systemic risk",
                "Art. 53(2)": "Open-source exception (exempts 1(a) and 1(b))",
                "Art. 55": "Additional obligations for systemic risk GPAI models",
                "Art. 56": "Codes of practice for GPAI obligations",
                "Annex XI": "Technical documentation requirements for GPAI models",
                "Annex XII": "Information for downstream providers of GPAI models",
                "Directive 2019/790": "Copyright in the Digital Single Market (Art. 4(3) reservation of rights)",
            },
            recital=(
                "Recital 107: General-purpose AI models, in particular large "
                "generative AI models, capable of generating text, images, and "
                "other content, present unique innovation opportunities but also "
                "challenges to artists, authors, and other creators and the way "
                "their creative content is created, distributed, used, and consumed."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of technical documentation (model cards, Annex XI elements)",
                    "Detection of downstream provider documentation (API docs, Annex XII elements)",
                    "Detection of copyright policy documentation",
                    "Detection of training data summaries (data cards, data sheets)",
                    "Detection of open-source licence and model weight availability",
                ],
                "requires_human_judgment": [
                    "Whether documentation meets Annex XI/XII minimum requirements",
                    "Whether copyright policy is adequate and actually implemented",
                    "Whether training data summary is 'sufficiently detailed'",
                    "Whether open-source exception criteria are fully met",
                    "Authority cooperation process verification",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 provides: (1) technical documentation "
                "existence check per Annex XI elements, (2) downstream documentation "
                "check per Annex XII elements, (3) copyright policy detection, "
                "(4) training data summary public availability check, (5) open-source "
                "exception assessment. Note: content quality assessment of documentation "
                "always requires human judgment."
            ),
            enforcement_date="2025-08-02",
            waiting_for="CEN-CENELEC harmonized standard for GPAI (expected 2027)",
        )

    # ── Action Plan ──

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_technical_documentation") is False and not details.get("open_source_exception_applies"):
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 53(1)(a)",
                action="Create technical documentation per Annex XI",
                details=(
                    "Art. 53(1)(a) requires comprehensive technical documentation "
                    "including: model description, training process, testing process, "
                    "evaluation results, and all Annex XI minimum elements. "
                    "Create a model card or technical report covering these areas."
                ),
                effort="8-16 hours (depending on model complexity)",
            ))

        if details.get("has_downstream_documentation") is False and not details.get("open_source_exception_applies"):
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 53(1)(b)",
                action="Create downstream provider documentation per Annex XII",
                details=(
                    "Art. 53(1)(b) requires documentation for downstream AI system "
                    "providers to understand capabilities and limitations. "
                    "Create API documentation, integration guides, and capability/ "
                    "limitation descriptions per Annex XII elements."
                ),
                effort="4-8 hours",
            ))

        if details.get("has_copyright_policy") is not True:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 53(1)(c)",
                action="Establish copyright compliance policy",
                details=(
                    "Art. 53(1)(c) requires a copyright compliance policy covering "
                    "Union copyright law, including identification and compliance with "
                    "reservation of rights (opt-out) per Directive 2019/790 Art. 4(3). "
                    "Document the policy and implement opt-out mechanisms."
                ),
                effort="4-8 hours (legal review recommended)",
                action_type="human_judgment_required",
            ))

        if details.get("has_training_data_summary") is not True:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 53(1)(d)",
                action="Create and publish training data summary",
                details=(
                    "Art. 53(1)(d) requires a sufficiently detailed, publicly "
                    "available summary of training content per the AI Office template. "
                    "Document data sources, types, volumes, and any notable characteristics."
                ),
                effort="4-8 hours",
            ))

        # Always: authority cooperation
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 53(3)",
            action="Establish authority cooperation procedures",
            details=(
                "Art. 53(3) requires cooperation with the Commission and "
                "national competent authorities. Designate a contact point "
                "and document liaison procedures."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=53,
            article_title="Obligations for Providers of General-Purpose AI Models",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "GPAI provider obligations require documentation quality assessment "
                "that exceeds automated scanning capabilities. Based on ComplianceLint "
                "compliance checklist; official CEN-CENELEC standards (expected 2027) "
                "and the EU AI Office Code of Practice may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art53Module:
    return Art53Module()
