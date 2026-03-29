"""
Article 16: Obligations of providers of high-risk AI systems — Module implementation.

Art. 16 is the umbrella obligation article for providers of high-risk AI systems.
It enumerates 12 sub-obligations (a)-(l), each cross-referencing a specific
requirement article (Art. 8-15, 17-20, 43, 47-49).

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art16"). No regex or keyword scanning is performed here.

Obligation mapping:
  ART16-OBL-1a  → has_section_2_compliance (Section 2 requirements, Art. 8-15)
  ART16-OBL-1b  → has_provider_identification (name/contact on system/docs)
  ART16-OBL-1c  → has_qms (quality management system per Art. 17)
  ART16-OBL-1d  → has_documentation_kept (Art. 18 documentation)
  ART16-OBL-1e  → has_log_retention (Art. 19 logs under provider control)
  ART16-OBL-1f  → has_conformity_assessment (Art. 43 conformity assessment)
  ART16-OBL-1g  → has_eu_declaration (Art. 47 EU declaration of conformity)
  ART16-OBL-1h  → has_ce_marking (Art. 48 CE marking)
  ART16-OBL-1i  → has_registration (Art. 49 EU database registration)
  ART16-OBL-1j  → has_corrective_actions_process (Art. 20 corrective actions)
  ART16-OBL-1k  → has_conformity_evidence (demonstrable conformity on request)
  ART16-OBL-1l  → has_accessibility_compliance (EU accessibility directives)
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


class Art16Module(BaseArticleModule):
    """Article 16: Obligations of providers of high-risk AI systems."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=16,
            article_title="Obligations of providers of high-risk AI systems",
        )

    def scan(self, project_path: str) -> ScanResult:
        """Scan for Art. 16 provider obligation compliance using AI-provided answers.

        Art. 16 applies exclusively to high-risk AI systems. If the AI has
        classified the project as not high-risk with sufficient confidence,
        the scan returns NOT_APPLICABLE.
        """
        project_path = os.path.abspath(project_path)
        ctx = self._effective_ctx(project_path)
        na = self._scope_gate(ctx, project_path)
        if na:
            return na

        # Art. 16 applies only to high-risk AI systems.
        # Inline check since Art. 16 is not in _HIGH_RISK_ONLY_ARTICLES.
        risk = (ctx.risk_classification or "").lower().strip()
        conf = (ctx.risk_classification_confidence or "").lower().strip()
        if risk in self._NOT_HIGH_RISK_VALUES and conf in ("high", "medium"):
            return self._not_applicable_result(
                project_path,
                ctx.primary_language or "unknown",
                "ART16",
                legal_basis="Art. 6",
                reason=(
                    "Art. 16 obligations apply only to providers of high-risk AI systems "
                    "(as classified under Art. 6). This system has been classified as "
                    f"'{ctx.risk_classification}' with {conf} confidence."
                ),
            )

        index = self._build_index(project_path)
        language = self._detect_language(project_path)
        file_count = index.source_file_count
        findings: list[Finding] = self._ctx_warnings(ctx)

        answers = ctx.get_article_answers("art16")

        has_section_2_compliance = answers.get("has_section_2_compliance")
        has_provider_identification = answers.get("has_provider_identification")
        has_qms = answers.get("has_qms")
        has_documentation_kept = answers.get("has_documentation_kept")
        has_log_retention = answers.get("has_log_retention")
        has_conformity_assessment = answers.get("has_conformity_assessment")
        has_eu_declaration = answers.get("has_eu_declaration")
        has_ce_marking = answers.get("has_ce_marking")
        has_registration = answers.get("has_registration")
        has_corrective_actions_process = answers.get("has_corrective_actions_process")
        has_conformity_evidence = answers.get("has_conformity_evidence")
        has_accessibility_compliance = answers.get("has_accessibility_compliance")

        # ── ART16-OBL-1a: Section 2 compliance (Art. 8-15) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART16-OBL-1a",
            answer=has_section_2_compliance,
            true_description=(
                "Section 2 requirements (Art. 8-15) appear to be addressed. "
                "Verify full compliance via individual article scans for Art. 9-15."
            ),
            false_description=(
                "Section 2 requirements (Art. 8-15) are not fully met. "
                "Art. 16(a) requires compliance with risk management, data governance, "
                "technical documentation, record-keeping, transparency, human oversight, "
                "and accuracy/robustness requirements."
            ),
            none_description=(
                "AI could not determine overall Section 2 compliance. "
                "Run individual article scans (Art. 9-15) for detailed assessment."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART16-OBL-1b: Provider identification ──
        findings.append(self._finding_from_answer(
            obligation_id="ART16-OBL-1b",
            answer=has_provider_identification,
            true_description=(
                "Provider identification found on the system, packaging, or documentation. "
                "Verify it includes name, registered trade name or trade mark, and contact address."
            ),
            false_description=(
                "No provider identification found. Art. 16(b) requires the provider's "
                "name, registered trade name or trade mark, and contact address on the "
                "system, its packaging, or accompanying documentation."
            ),
            none_description=(
                "AI could not determine whether provider identification is present. "
                "Check README, package metadata, or product documentation for provider details."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART16-OBL-1c: Quality management system (Art. 17) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART16-OBL-1c",
            answer=has_qms,
            true_description=(
                "Quality management system documentation found. "
                "Verify it complies with Art. 17 requirements."
            ),
            false_description=(
                "No quality management system found. Art. 16(c) requires "
                "a QMS compliant with Art. 17."
            ),
            none_description=(
                "AI could not determine whether a quality management system is in place. "
                "Review project documentation for QMS policies and procedures."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART16-OBL-1d: Documentation kept (Art. 18) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART16-OBL-1d",
            answer=has_documentation_kept,
            true_description=(
                "Technical documentation found. "
                "Verify it meets Art. 18 documentation requirements."
            ),
            false_description=(
                "No technical documentation found as required by Art. 18. "
                "Art. 16(d) requires keeping the documentation referred to in Art. 18."
            ),
            none_description=(
                "AI could not determine whether Art. 18 documentation is maintained."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART16-OBL-1e: Logs kept when under control (Art. 19) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART16-OBL-1e",
            answer=has_log_retention,
            true_description=(
                "Log retention mechanism found. "
                "Verify automatically generated logs are kept per Art. 19 requirements."
            ),
            false_description=(
                "No log retention mechanism found. Art. 16(e) requires keeping "
                "automatically generated logs as referred to in Art. 19, "
                "when under the provider's control."
            ),
            none_description=(
                "AI could not determine whether logs are retained. "
                "Check for log storage, archival, or retention configuration."
            ),
            gap_type=GapType.CODE,
        ))

        # ── ART16-OBL-1f: Conformity assessment (Art. 43) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART16-OBL-1f",
            answer=has_conformity_assessment,
            true_description=(
                "Conformity assessment evidence found. "
                "Verify it follows the procedure in Art. 43 and was completed "
                "prior to market placement."
            ),
            false_description=(
                "No conformity assessment evidence found. Art. 16(f) requires "
                "the system to undergo the relevant conformity assessment per Art. 43 "
                "prior to being placed on the market or put into service."
            ),
            none_description=(
                "AI could not determine whether a conformity assessment has been completed."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART16-OBL-1g: EU declaration of conformity (Art. 47) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART16-OBL-1g",
            answer=has_eu_declaration,
            true_description=(
                "EU declaration of conformity found. "
                "Verify it complies with Art. 47 requirements."
            ),
            false_description=(
                "No EU declaration of conformity found. Art. 16(g) requires "
                "drawing up an EU declaration of conformity in accordance with Art. 47."
            ),
            none_description=(
                "AI could not determine whether an EU declaration of conformity exists."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART16-OBL-1h: CE marking (Art. 48) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART16-OBL-1h",
            answer=has_ce_marking,
            true_description=(
                "CE marking reference found. "
                "Verify it is affixed to the system, packaging, or documentation "
                "per Art. 48 requirements."
            ),
            false_description=(
                "No CE marking found. Art. 16(h) requires affixing the CE marking "
                "to the system or its packaging or documentation per Art. 48."
            ),
            none_description=(
                "AI could not determine whether CE marking is present. "
                "This typically requires physical or product-level verification."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART16-OBL-1i: Registration (Art. 49) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART16-OBL-1i",
            answer=has_registration,
            true_description=(
                "EU database registration evidence found. "
                "Verify registration is complete per Art. 49(1)."
            ),
            false_description=(
                "No EU database registration evidence found. Art. 16(i) requires "
                "compliance with Art. 49(1) registration obligations."
            ),
            none_description=(
                "AI could not determine whether EU database registration is completed."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART16-OBL-1j: Corrective actions (Art. 20) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART16-OBL-1j",
            answer=has_corrective_actions_process,
            true_description=(
                "Corrective action procedures found. "
                "Verify they meet Art. 20 requirements for corrective actions "
                "and information provision."
            ),
            false_description=(
                "No corrective action procedures found. Art. 16(j) requires "
                "taking necessary corrective actions and providing information "
                "as required in Art. 20."
            ),
            none_description=(
                "AI could not determine whether corrective action procedures exist."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART16-OBL-1k: Demonstrable conformity ──
        findings.append(self._finding_from_answer(
            obligation_id="ART16-OBL-1k",
            answer=has_conformity_evidence,
            true_description=(
                "Compliance evidence documentation found. "
                "Verify it is sufficient to demonstrate Section 2 conformity "
                "upon request by a national competent authority."
            ),
            false_description=(
                "No compliance evidence documentation found. Art. 16(k) requires "
                "the ability to demonstrate conformity with Section 2 requirements "
                "upon a reasoned request of a national competent authority."
            ),
            none_description=(
                "AI could not determine whether conformity evidence is available. "
                "Review audit-ready materials and conformity assessment records."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART16-OBL-1l: Accessibility compliance ──
        findings.append(self._finding_from_answer(
            obligation_id="ART16-OBL-1l",
            answer=has_accessibility_compliance,
            true_description=(
                "Accessibility compliance evidence found. "
                "Verify it meets Directives (EU) 2016/2102 and (EU) 2019/882."
            ),
            false_description=(
                "No accessibility compliance evidence found. Art. 16(l) requires "
                "compliance with accessibility requirements in Directives "
                "(EU) 2016/2102 and (EU) 2019/882."
            ),
            none_description=(
                "AI could not determine whether accessibility requirements are met. "
                "Check for WCAG compliance, accessibility testing, or accessibility documentation."
            ),
            gap_type=GapType.CODE,
        ))

        # Build details dict
        details = {
            "has_section_2_compliance": has_section_2_compliance,
            "has_provider_identification": has_provider_identification,
            "has_qms": has_qms,
            "has_documentation_kept": has_documentation_kept,
            "has_log_retention": has_log_retention,
            "has_conformity_assessment": has_conformity_assessment,
            "has_eu_declaration": has_eu_declaration,
            "has_ce_marking": has_ce_marking,
            "has_registration": has_registration,
            "has_corrective_actions_process": has_corrective_actions_process,
            "has_conformity_evidence": has_conformity_evidence,
            "has_accessibility_compliance": has_accessibility_compliance,
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
            article_number=16,
            article_title="Obligations of providers of high-risk AI systems",
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
            article_number=16,
            article_title="Obligations of providers of high-risk AI systems",
            one_sentence=(
                "Providers of high-risk AI systems must ensure compliance with 12 specific "
                "obligations covering technical requirements, documentation, conformity "
                "assessment, and post-market responsibilities."
            ),
            official_summary=(
                "Art. 16 is the umbrella obligation article for providers of high-risk AI "
                "systems. It requires providers to: (a) ensure Section 2 compliance "
                "(Art. 8-15), (b) identify themselves on the system, (c) maintain a QMS "
                "(Art. 17), (d) keep documentation (Art. 18), (e) retain logs (Art. 19), "
                "(f) complete conformity assessment (Art. 43), (g) draw up EU declaration "
                "(Art. 47), (h) affix CE marking (Art. 48), (i) register in EU database "
                "(Art. 49), (j) take corrective actions (Art. 20), (k) demonstrate "
                "conformity on request, and (l) comply with accessibility requirements."
            ),
            related_articles={
                "Art. 8-15": "Section 2 technical requirements for high-risk AI",
                "Art. 17": "Quality management system",
                "Art. 18": "Documentation obligations",
                "Art. 19": "Log retention",
                "Art. 20": "Corrective actions",
                "Art. 43": "Conformity assessment procedures",
                "Art. 47": "EU declaration of conformity",
                "Art. 48": "CE marking",
                "Art. 49": "EU database registration",
            },
            recital=(
                "Recital 73: To ensure legal certainty, it is necessary to clarify that "
                "provider obligations under this Regulation are specific obligations that "
                "complement and do not replace obligations under other Union law."
            ),
            automation_summary={
                "fully_automatable": [
                    "Section 2 compliance aggregation (cross-reference scan results)",
                    "Log retention mechanism detection",
                ],
                "partially_automatable": [
                    "Provider identification in documentation",
                    "QMS documentation detection",
                    "Technical documentation presence",
                    "Conformity assessment records",
                    "EU declaration presence",
                    "Registration evidence",
                    "Corrective action procedures",
                    "Accessibility compliance evidence",
                ],
                "requires_human_judgment": [
                    "CE marking physical verification",
                    "Conformity demonstration adequacy",
                    "Accessibility compliance completeness",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) all Section 2 articles "
                "passing scan, (2) provider identification in documentation, (3) QMS per Art. 17, "
                "(4) technical documentation per Art. 18, (5) log retention per Art. 19, "
                "(6) conformity assessment per Art. 43, (7) EU declaration per Art. 47, "
                "(8) CE marking per Art. 48, (9) EU database registration per Art. 49, "
                "(10) corrective action process per Art. 20, (11) audit-ready evidence, "
                "(12) accessibility compliance. "
                "Based on: ISO/IEC 42001:2023."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_section_2_compliance") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 16(a)",
                action="Address Section 2 (Art. 8-15) compliance gaps",
                details=(
                    "Art. 16(a) requires compliance with all Section 2 requirements. "
                    "Run individual article scans (Art. 9-15) to identify specific gaps "
                    "and remediate each non-compliant area."
                ),
                effort="Variable (depends on gaps)",
            ))

        if details.get("has_provider_identification") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 16(b)",
                action="Add provider identification to system documentation",
                details=(
                    "Art. 16(b) requires the provider's name, registered trade name or "
                    "trade mark, and contact address on the system, packaging, or documentation. "
                    "Add these details to README, package metadata, or product documentation."
                ),
                effort="1 hour",
            ))

        if details.get("has_qms") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 16(c)",
                action="Establish a quality management system per Art. 17",
                details=(
                    "Art. 16(c) requires a QMS compliant with Art. 17. Create a quality "
                    "manual covering all 13 aspects listed in Art. 17(1)(a)-(m)."
                ),
                effort="16-40 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_log_retention") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 16(e)",
                action="Configure log retention per Art. 19",
                details=(
                    "Art. 16(e) requires keeping automatically generated logs when under "
                    "provider control. Configure log retention for at least 6 months (180 days) "
                    "per Art. 19(1)."
                ),
                effort="2-4 hours",
            ))

        if details.get("has_conformity_assessment") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 16(f)",
                action="Complete conformity assessment per Art. 43",
                details=(
                    "Art. 16(f) requires a conformity assessment per Art. 43 before "
                    "market placement. Determine which procedure applies (internal control "
                    "or third-party assessment) and complete it."
                ),
                effort="8-40 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_eu_declaration") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 16(g)",
                action="Draw up EU declaration of conformity per Art. 47",
                details=(
                    "Art. 16(g) requires an EU declaration of conformity per Art. 47. "
                    "Prepare the declaration covering all Annex V content requirements."
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_registration") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 16(i)",
                action="Register in EU database per Art. 49",
                details=(
                    "Art. 16(i) requires registration in the EU database per Art. 49(1). "
                    "Complete registration before placing the system on the market."
                ),
                effort="2-4 hours",
                action_type="human_judgment_required",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 16(h)",
            action="Verify CE marking is properly affixed",
            details=(
                "Art. 16(h) requires CE marking on the system, packaging, or documentation "
                "per Art. 48. This typically requires physical or product-level verification."
            ),
            effort="1-2 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 16(l)",
            action="Verify accessibility compliance",
            details=(
                "Art. 16(l) requires compliance with Directives (EU) 2016/2102 "
                "(public sector accessibility) and (EU) 2019/882 (European Accessibility Act). "
                "Conduct accessibility testing or audit as appropriate."
            ),
            effort="4-16 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=16,
            article_title="Obligations of providers of high-risk AI systems",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 16 is an umbrella article. Many obligations cross-reference other "
                "articles. Run individual article scans for detailed assessment of each "
                "requirement. Official CEN-CENELEC standards (expected Q4 2026) may "
                "modify these requirements."
            ),
        )


def create_module() -> Art16Module:
    return Art16Module()
