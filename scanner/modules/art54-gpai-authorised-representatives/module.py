"""
Article 54: Authorised Representatives of Providers of General-Purpose AI Models.

Art. 54 requires third-country GPAI providers to appoint an EU-based authorised
representative by written mandate. The representative must perform mandate tasks,
provide mandate copies to the AI Office, and terminate the mandate if the provider
acts contrary to the Regulation.

Open-source GPAI models (without systemic risk) are exempt (Art. 54(6)).

This module reads AI-provided compliance_answers["art54"] and maps each answer
to a Finding. No regex, keyword, or AST scanning is performed — detection is
entirely the AI's responsibility.

Obligation mapping:
  ART54-OBL-1  → has_authorised_representative (_finding_from_answer, conditional)
  ART54-OBL-3  → UNABLE_TO_DETERMINE always (manual, mandate tasks)
  ART54-OBL-5  → UNABLE_TO_DETERMINE always (manual, termination obligation)
  ART54-EXC-6  → is_open_source_gpai (exception, custom Finding — informational)

Boundary cases:
  - All obligations (OBL-1, OBL-3, OBL-5) only apply to third-country providers
    (is_third_country_provider=True). When False → NOT_APPLICABLE.
  - EXC-6 exempts the entire article for open-source GPAI without systemic risk.
  - OBL-3 and OBL-5 are manual (procedural/organizational) — always UTD.
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


class Art54Module(BaseArticleModule):
    """Article 54: Authorised Representatives of Providers of General-Purpose AI Models."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=54,
            article_title="Authorised Representatives of Providers of General-Purpose AI Models",
        )

    # ── Scanning ──

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for Art. 54 authorised representative obligations.

        Reads compliance_answers["art54"] from the AI context. Maps each field
        to obligation findings:
          - has_authorised_representative → ART54-OBL-1 (conditional on is_third_country_provider)
          - ART54-OBL-3 → always UTD (mandate tasks — manual)
          - ART54-OBL-5 → always UTD (termination obligation — manual)
          - is_open_source_gpai → ART54-EXC-6 (exception)

        All obligations except EXC-6 only apply when is_third_country_provider=True.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for Art. 54 authorised representative obligations.
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

        answers = ctx.get_article_answers("art54")

        is_third_country_provider = answers.get("is_third_country_provider")
        has_authorised_representative = answers.get("has_authorised_representative")
        representative_evidence = answers.get("representative_evidence", [])
        has_written_mandate = answers.get("has_written_mandate")
        mandate_evidence = answers.get("mandate_evidence", [])
        is_open_source_gpai = answers.get("is_open_source_gpai")
        has_systemic_risk = answers.get("has_systemic_risk")

        # Determine if open-source exception applies (Art. 54(6)):
        # Entire article exempt for open-source GPAI without systemic risk
        open_source_exception_applies = (
            is_open_source_gpai is True and has_systemic_risk is not True
        )

        # Check if third-country obligations apply
        third_country_applies = is_third_country_provider is True

        # ── ART54-OBL-1: Appoint authorised representative ──
        if open_source_exception_applies:
            findings.append(Finding(
                obligation_id="ART54-OBL-1",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.MEDIUM,
                description=(
                    "Open-source GPAI model without systemic risk — "
                    "Art. 54 obligations are exempted per Art. 54(6) "
                    "open-source exception."
                ),
                gap_type=GapType.PROCESS,
            ))
        elif is_third_country_provider is False:
            findings.append(Finding(
                obligation_id="ART54-OBL-1",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.MEDIUM,
                description=(
                    "Provider is established in the EU — Art. 54(1) authorised "
                    "representative obligation only applies to third-country providers."
                ),
                gap_type=GapType.PROCESS,
            ))
        elif is_third_country_provider is None:
            findings.append(self._finding_from_answer(
                obligation_id="ART54-OBL-1",
                answer=None,
                true_description="",
                false_description="",
                none_description=(
                    "Cannot determine whether the provider is established outside the EU. "
                    "Art. 54(1) requires third-country providers to appoint an EU-based "
                    "authorised representative by written mandate before placing a GPAI "
                    "model on the Union market."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            # Third-country provider — check for authorised representative
            findings.append(self._finding_from_answer(
                obligation_id="ART54-OBL-1",
                answer=has_authorised_representative,
                true_description=(
                    "Authorised representative documentation found for third-country "
                    "GPAI provider. Verify the representative is established in the Union "
                    "and the written mandate covers the tasks specified in Art. 54(3)."
                ),
                false_description=(
                    "No authorised representative found for third-country GPAI provider. "
                    "Art. 54(1) requires providers established outside the EU to appoint "
                    "an authorised representative established in the Union by written mandate "
                    "before placing the model on the Union market."
                ),
                none_description=(
                    "Cannot determine whether an authorised representative has been "
                    "appointed. Art. 54(1) requires third-country providers to appoint "
                    "an EU-based representative by written mandate."
                ),
                evidence=representative_evidence if isinstance(representative_evidence, list) else [],
                gap_type=GapType.PROCESS,
            ))

        # ── ART54-OBL-3: Mandate tasks and AI Office cooperation ──
        # Manual obligation — always UTD. Procedural/organizational.
        if open_source_exception_applies:
            findings.append(Finding(
                obligation_id="ART54-OBL-3",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.MEDIUM,
                description=(
                    "Open-source GPAI model without systemic risk — "
                    "Art. 54 obligations are exempted per Art. 54(6) "
                    "open-source exception."
                ),
                gap_type=GapType.PROCESS,
            ))
        elif is_third_country_provider is False:
            findings.append(Finding(
                obligation_id="ART54-OBL-3",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.MEDIUM,
                description=(
                    "Provider is established in the EU — Art. 54(3) mandate tasks "
                    "obligation only applies when an authorised representative is appointed "
                    "(third-country providers)."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            findings.append(Finding(
                obligation_id="ART54-OBL-3",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "Mandate tasks and AI Office cooperation require human review. "
                    "Art. 54(3) requires the authorised representative to perform "
                    "mandate tasks, provide a mandate copy to the AI Office upon request, "
                    "and the mandate must empower the representative to: (a) verify "
                    "Annex XI documentation is maintained, (b) keep documentation for "
                    "10 years, (c) provide information to AI Office, (d) cooperate "
                    "with competent authorities."
                ),
                remediation=(
                    "Ensure the written mandate explicitly covers all tasks specified "
                    "in Art. 54(3)(a)-(d). Keep a copy available for the AI Office "
                    "in an official EU language."
                ),
                gap_type=GapType.PROCESS,
            ))

        # ── ART54-OBL-5: Mandate termination obligation ──
        # Manual obligation — always UTD. Procedural/organizational.
        if open_source_exception_applies:
            findings.append(Finding(
                obligation_id="ART54-OBL-5",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.MEDIUM,
                description=(
                    "Open-source GPAI model without systemic risk — "
                    "Art. 54 obligations are exempted per Art. 54(6) "
                    "open-source exception."
                ),
                gap_type=GapType.PROCESS,
            ))
        elif is_third_country_provider is False:
            findings.append(Finding(
                obligation_id="ART54-OBL-5",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.MEDIUM,
                description=(
                    "Provider is established in the EU — Art. 54(5) mandate termination "
                    "obligation only applies when an authorised representative is appointed "
                    "(third-country providers)."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            findings.append(Finding(
                obligation_id="ART54-OBL-5",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "Mandate termination procedures require human review. "
                    "Art. 54(5) requires the authorised representative to terminate "
                    "the mandate if the provider acts contrary to its obligations "
                    "under the Regulation, and immediately inform the AI Office "
                    "about the termination and reasons."
                ),
                remediation=(
                    "Establish a procedure for mandate termination in case of "
                    "provider non-compliance. Include AI Office notification "
                    "requirements in the mandate agreement."
                ),
                gap_type=GapType.PROCESS,
            ))

        # ── ART54-EXC-6: Open-source exception ──
        # Exception type — custom Finding, informational.
        if is_open_source_gpai is True:
            if has_systemic_risk is True:
                findings.append(Finding(
                    obligation_id="ART54-EXC-6",
                    file_path="project-wide",
                    line_number=None,
                    level=ComplianceLevel.NON_COMPLIANT,
                    confidence=Confidence.MEDIUM,
                    description=(
                        "Open-source GPAI model WITH systemic risk — "
                        "the Art. 54(6) open-source exception does not apply. "
                        "All Art. 54 obligations remain in force despite the "
                        "open-source licence."
                    ),
                    gap_type=GapType.PROCESS,
                ))
            else:
                findings.append(Finding(
                    obligation_id="ART54-EXC-6",
                    file_path="project-wide",
                    line_number=None,
                    level=ComplianceLevel.COMPLIANT,
                    confidence=Confidence.MEDIUM,
                    description=(
                        "Open-source GPAI model without systemic risk — "
                        "Art. 54(6) exception applies. All Art. 54 obligations "
                        "(authorised representative appointment, mandate tasks, "
                        "termination procedures) are exempted."
                    ),
                    gap_type=GapType.PROCESS,
                ))
        elif is_open_source_gpai is False:
            findings.append(Finding(
                obligation_id="ART54-EXC-6",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.MEDIUM,
                description=(
                    "Model is not open-source GPAI — Art. 54(6) exception "
                    "does not apply. All Art. 54 obligations are in force "
                    "(for third-country providers)."
                ),
                gap_type=GapType.PROCESS,
            ))
        else:
            findings.append(Finding(
                obligation_id="ART54-EXC-6",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "Cannot determine whether the open-source GPAI exception "
                    "(Art. 54(6)) applies. Requires assessment of licence type, "
                    "parameter/weight public availability, and systemic risk status."
                ),
                gap_type=GapType.PROCESS,
            ))

        details = {
            "is_third_country_provider": is_third_country_provider,
            "has_authorised_representative": has_authorised_representative,
            "has_written_mandate": has_written_mandate,
            "is_open_source_gpai": is_open_source_gpai,
            "has_systemic_risk": has_systemic_risk,
            "open_source_exception_applies": open_source_exception_applies,
            "note": (
                "Art. 54 requires third-country GPAI providers to appoint an "
                "EU-based authorised representative. Open-source GPAI models "
                "without systemic risk are exempt (Art. 54(6)). EU-based "
                "providers are not subject to this article."
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
            article_number=54,
            article_title="Authorised Representatives of Providers of General-Purpose AI Models",
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
            article_number=54,
            article_title="Authorised Representatives of Providers of General-Purpose AI Models",
            one_sentence=(
                "Article 54 requires third-country GPAI providers to appoint "
                "an EU-based authorised representative by written mandate."
            ),
            official_summary=(
                "Art. 54 establishes the obligation for providers of general-purpose "
                "AI models established in third countries (outside the EU) to appoint "
                "an authorised representative established in the Union by written mandate "
                "before placing their model on the Union market. The mandate must empower "
                "the representative to: (a) verify Annex XI documentation is maintained, "
                "(b) keep documentation for 10 years after placing on market, (c) provide "
                "information and documentation to the AI Office upon request, (d) cooperate "
                "with competent authorities. The representative may terminate the mandate if "
                "the provider acts contrary to the Regulation. Art. 54(6) exempts open-source "
                "GPAI models (without systemic risk) from these obligations."
            ),
            related_articles={
                "Art. 53": "Core obligations for GPAI model providers",
                "Art. 54(3)": "Mandate scope and tasks for authorised representative",
                "Art. 54(6)": "Open-source exception",
                "Art. 55": "Additional obligations for systemic risk GPAI models",
                "Annex XI": "Technical documentation requirements for GPAI models",
            },
            recital=(
                "Recital 116: Providers of general-purpose AI models established in "
                "third countries should appoint an authorised representative to ensure "
                "compliance with obligations under this Regulation."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of authorised representative documentation",
                    "Detection of written mandate documentation",
                    "Detection of open-source licence and systemic risk status",
                ],
                "requires_human_judgment": [
                    "Whether the provider is established in a third country",
                    "Whether the mandate covers all required tasks (Art. 54(3)(a)-(d))",
                    "Whether the representative is validly established in the EU",
                    "Mandate termination procedures and AI Office notification",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 provides: (1) third-country provider "
                "status assessment, (2) authorised representative documentation check, "
                "(3) open-source exception assessment. Note: mandate validity, representative "
                "establishment status, and procedural obligations always require human judgment."
            ),
            enforcement_date="2025-08-02",
            waiting_for="CEN-CENELEC harmonized standard for GPAI (expected 2027)",
        )

    # ── Action Plan ──

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("open_source_exception_applies"):
            actions.append(ActionItem(
                priority="LOW",
                article="Art. 54(6)",
                action="Verify open-source exception eligibility",
                details=(
                    "Art. 54(6) exempts open-source GPAI models without systemic risk. "
                    "Confirm your licence allows access, usage, modification, and "
                    "distribution, and that model parameters/weights are publicly available."
                ),
                effort="1 hour",
                action_type="human_judgment_required",
            ))
        elif details.get("is_third_country_provider") is True:
            if details.get("has_authorised_representative") is not True:
                actions.append(ActionItem(
                    priority="CRITICAL",
                    article="Art. 54(1)",
                    action="Appoint an EU-based authorised representative",
                    details=(
                        "Art. 54(1) requires third-country providers to appoint an "
                        "authorised representative established in the Union by written "
                        "mandate BEFORE placing the model on the Union market. "
                        "The mandate must cover the tasks in Art. 54(3)(a)-(d)."
                    ),
                    effort="4-8 hours (legal engagement required)",
                    action_type="human_judgment_required",
                ))

            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 54(3)",
                action="Verify mandate covers all required tasks",
                details=(
                    "Art. 54(3) requires the mandate to empower the representative to: "
                    "(a) verify Annex XI documentation is maintained, "
                    "(b) keep documentation for 10 years after market placement, "
                    "(c) provide information to AI Office upon request, "
                    "(d) cooperate with competent authorities."
                ),
                effort="2-4 hours (legal review recommended)",
                action_type="human_judgment_required",
            ))

            actions.append(ActionItem(
                priority="MEDIUM",
                article="Art. 54(5)",
                action="Establish mandate termination procedures",
                details=(
                    "Art. 54(5) requires the representative to terminate the mandate "
                    "if the provider acts contrary to the Regulation, and immediately "
                    "inform the AI Office. Include termination clauses in the mandate."
                ),
                effort="1-2 hours",
                action_type="human_judgment_required",
            ))
        elif details.get("is_third_country_provider") is None:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 54(1)",
                action="Determine whether provider is a third-country entity",
                details=(
                    "Art. 54 only applies to providers established outside the EU. "
                    "Determine your establishment location to assess whether you need "
                    "to appoint an authorised representative."
                ),
                effort="30 minutes",
                action_type="human_judgment_required",
            ))

        return ActionPlan(
            article_number=54,
            article_title="Authorised Representatives of Providers of General-Purpose AI Models",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 54 obligations are primarily legal/organizational and require "
                "human judgment. Based on ComplianceLint compliance checklist; official "
                "CEN-CENELEC standards (expected 2027) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art54Module:
    return Art54Module()
