"""
Article 22: Authorised representatives of providers of high-risk AI systems — Module implementation.

Art. 22 requires non-EU providers of high-risk AI systems to appoint an
authorised representative in the Union by written mandate, and to enable
that representative to perform mandate tasks.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art22"). No regex or keyword scanning is performed.

Obligation mapping:
  ART22-OBL-1   → has_authorised_representative (non-EU provider appointed EU representative)
  ART22-OBL-2   → has_representative_enablement (provider enables representative to perform tasks)
  ART22-OBL-3   → always UTD (manual — addressee is authorised_representative, not provider)
  ART22-OBL-4   → has_mandate_authority_contact (mandate empowers representative for authority contact)

Conditional logic:
  All provider obligations (OBL-1, OBL-2, OBL-4) only apply to non-EU providers.
  When is_eu_established_provider=True → these obligations are NOT_APPLICABLE.
  OBL-3 is addressed to the authorised_representative — handled as a gap finding by the engine.
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


class Art22Module(BaseArticleModule):
    """Article 22: Authorised representatives compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=22,
            article_title="Authorised representatives of providers of high-risk AI systems",
        )

    def scan(self, project_path: str) -> ScanResult:
        project_path = os.path.abspath(project_path)
        ctx = self._effective_ctx(project_path)
        na = self._scope_gate(ctx, project_path)
        if na:
            return na
        # Art. 22 applies only to high-risk AI systems.
        risk = (ctx.risk_classification or "").lower().strip()
        conf = (ctx.risk_classification_confidence or "").lower().strip()
        if risk in self._NOT_HIGH_RISK_VALUES and conf in ("high", "medium"):
            return self._not_applicable_result(
                project_path,
                ctx.primary_language or "unknown",
                "ART22",
                legal_basis="Art. 6",
                reason=(
                    "Art. 22 obligations apply only to providers of high-risk AI systems "
                    "(as classified under Art. 6). This system has been classified as "
                    f"'{ctx.risk_classification}' with {conf} confidence."
                ),
            )

        index = self._build_index(project_path)
        language = self._detect_language(project_path)
        file_count = index.source_file_count
        findings: list[Finding] = self._ctx_warnings(ctx)

        answers = ctx.get_article_answers("art22")

        is_eu_established = answers.get("is_eu_established_provider")
        has_authorised_representative = answers.get("has_authorised_representative")
        has_representative_enablement = answers.get("has_representative_enablement")
        has_mandate_authority_contact = answers.get("has_mandate_authority_contact")

        # ── Conditional: EU-established providers don't need Art. 22 ──
        # All provider obligations (OBL-1, OBL-2, OBL-4) only apply to non-EU providers.
        # When is_eu_established_provider=True, create NOT_APPLICABLE findings.
        # This is custom Finding() per boundary case #6 (conditional control flow).
        if is_eu_established is True:
            for obl_id in ["ART22-OBL-1", "ART22-OBL-2", "ART22-OBL-4"]:
                findings.append(Finding(
                    obligation_id=obl_id,
                    file_path="project-wide",
                    line_number=None,
                    level=ComplianceLevel.NOT_APPLICABLE,
                    confidence=Confidence.HIGH,
                    description=(
                        "Provider is established in the EU. Art. 22 authorised representative "
                        "obligations only apply to providers established in third countries (non-EU)."
                    ),
                    gap_type=GapType.PROCESS,
                    is_informational=True,
                ))
        else:
            # ── ART22-OBL-1: Appoint authorised representative ──
            findings.append(self._finding_from_answer(
                obligation_id="ART22-OBL-1",
                answer=has_authorised_representative,
                true_description=(
                    "Authorised representative documentation detected. "
                    "Verify the representative is established in the Union and was appointed "
                    "by written mandate prior to making the system available on the Union market "
                    "per Art. 22(1)."
                ),
                false_description=(
                    "No authorised representative documentation detected. "
                    "Art. 22(1) requires providers established in third countries to appoint "
                    "an authorised representative established in the Union by written mandate, "
                    "prior to making high-risk AI systems available on the Union market."
                ),
                none_description=(
                    "AI could not determine whether an authorised representative has been appointed. "
                    "Art. 22(1) requires non-EU providers to appoint an EU-based authorised representative."
                ),
                gap_type=GapType.PROCESS,
            ))

            # ── ART22-OBL-2: Enable representative to perform tasks ──
            findings.append(self._finding_from_answer(
                obligation_id="ART22-OBL-2",
                answer=has_representative_enablement,
                true_description=(
                    "Representative enablement documentation detected. "
                    "Verify the provider has given the authorised representative the resources "
                    "and access needed to perform all tasks specified in the mandate per Art. 22(2)."
                ),
                false_description=(
                    "No representative enablement documentation detected. "
                    "Art. 22(2) requires the provider to enable its authorised representative "
                    "to perform the tasks specified in the mandate."
                ),
                none_description=(
                    "AI could not determine whether the provider enables the authorised representative "
                    "to perform mandate tasks. Art. 22(2) requires provider enablement."
                ),
                gap_type=GapType.PROCESS,
            ))

            # ── ART22-OBL-4: Mandate empowers representative for authority contact ──
            findings.append(self._finding_from_answer(
                obligation_id="ART22-OBL-4",
                answer=has_mandate_authority_contact,
                true_description=(
                    "Mandate authority contact clause detected. "
                    "Verify the mandate empowers the representative to be addressed by competent "
                    "authorities on all compliance issues per Art. 22(3)."
                ),
                false_description=(
                    "No mandate authority contact clause detected. "
                    "Art. 22(3) requires the mandate to empower the authorised representative "
                    "to be addressed, in addition to or instead of the provider, by competent "
                    "authorities on all issues related to ensuring compliance."
                ),
                none_description=(
                    "AI could not determine whether the mandate includes authority contact empowerment. "
                    "Art. 22(3) requires the mandate to empower the representative for authority contact."
                ),
                gap_type=GapType.PROCESS,
            ))

        # Build details dict
        details = {
            "is_eu_established_provider": is_eu_established,
            "has_authorised_representative": has_authorised_representative,
            "has_representative_enablement": has_representative_enablement,
            "has_mandate_authority_contact": has_mandate_authority_contact,
        }

        # ── Obligation Engine: enrich findings + identify gaps ──
        # OBL-3 (manual, addressee=authorised_representative) is handled as a gap finding.
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
            article_number=22,
            article_title="Authorised representatives of providers of high-risk AI systems",
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
            article_number=22,
            article_title="Authorised representatives of providers of high-risk AI systems",
            one_sentence=(
                "Non-EU providers of high-risk AI systems must appoint an authorised "
                "representative in the Union by written mandate."
            ),
            official_summary=(
                "Art. 22 requires providers of high-risk AI systems established in third countries "
                "to: (1) appoint an authorised representative established in the Union by written "
                "mandate, prior to making systems available on the Union market (Art. 22(1)); "
                "(2) enable the authorised representative to perform the tasks specified in the "
                "mandate (Art. 22(2)); (3) ensure the mandate empowers the representative to be "
                "addressed by competent authorities on all compliance issues (Art. 22(3)). "
                "The authorised representative must perform mandate tasks including verifying "
                "conformity documentation, keeping documents for 10 years, cooperating with "
                "authorities, and terminating the mandate if the provider acts contrary to its "
                "obligations (Art. 22(3))."
            ),
            related_articles={
                "Art. 6": "High-risk classification (prerequisite for Art. 22)",
                "Art. 11": "Technical documentation (representative must verify existence)",
                "Art. 12": "Record-keeping (representative must provide log access to authorities)",
                "Art. 47": "EU declaration of conformity (representative must verify existence)",
                "Art. 49": "Registration (representative may handle registration obligations)",
                "Art. 74(10)": "Mandate requirements cross-reference",
            },
            recital=(
                "Recital 93: In order to facilitate the work of national competent authorities "
                "and to ensure that providers established outside the Union can fulfil their "
                "obligations, providers should appoint an authorised representative."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Authorised representative documentation detection",
                    "Mandate agreement detection",
                    "Authority contact clause detection",
                ],
                "requires_human_judgment": [
                    "Whether the representative is established in the Union",
                    "Whether the mandate covers all required tasks",
                    "Whether the provider has enabled the representative effectively",
                    "Whether the representative performs all mandate tasks",
                    "Whether documents are retained for 10 years",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) documented appointment of an "
                "EU-based authorised representative by written mandate; (2) evidence the provider "
                "enables the representative to perform mandate tasks; (3) mandate includes authority "
                "contact empowerment clause. "
                "Based on: ISO/IEC 42001:2023 (governance and accountability controls)."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for authorised representatives (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("is_eu_established_provider") is True:
            actions.append(ActionItem(
                priority="LOW",
                article="Art. 22",
                action="Confirm EU establishment status",
                details=(
                    "Your system indicates the provider is established in the EU. "
                    "Art. 22 authorised representative obligations only apply to third-country "
                    "providers. Verify your EU establishment status is correctly documented."
                ),
                effort="30 minutes",
                action_type="human_judgment_required",
            ))
        else:
            if details.get("has_authorised_representative") is False:
                actions.append(ActionItem(
                    priority="CRITICAL",
                    article="Art. 22(1)",
                    action="Appoint an authorised representative in the EU",
                    details=(
                        "Art. 22(1) requires non-EU providers to appoint an authorised "
                        "representative established in the Union by written mandate before "
                        "making high-risk AI systems available on the Union market. Steps:\n"
                        "  - Identify a suitable EU-based representative (legal entity or person)\n"
                        "  - Draft a written mandate specifying all required tasks\n"
                        "  - Ensure the mandate covers authority contact empowerment\n"
                        "  - Execute the mandate before market placement"
                    ),
                    effort="16-40 hours",
                    action_type="human_judgment_required",
                ))

            if details.get("has_representative_enablement") is False:
                actions.append(ActionItem(
                    priority="HIGH",
                    article="Art. 22(2)",
                    action="Enable authorised representative to perform mandate tasks",
                    details=(
                        "Art. 22(2) requires providers to enable their authorised representative "
                        "to perform mandate tasks. Ensure:\n"
                        "  - Representative has access to all required documentation\n"
                        "  - Representative has authority to act on provider's behalf\n"
                        "  - Communication channels are established\n"
                        "  - Document all enablement measures"
                    ),
                    effort="4-8 hours",
                    action_type="human_judgment_required",
                ))

            if details.get("has_mandate_authority_contact") is False:
                actions.append(ActionItem(
                    priority="HIGH",
                    article="Art. 22(3)",
                    action="Add authority contact clause to mandate",
                    details=(
                        "Art. 22(3) requires the mandate to empower the authorised representative "
                        "to be addressed by competent authorities on all compliance issues. "
                        "Update the mandate to include explicit authority contact empowerment."
                    ),
                    effort="2-4 hours",
                    action_type="human_judgment_required",
                ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 22(3)",
            action="Verify authorised representative performs all mandate tasks",
            details=(
                "Art. 22(3) requires the authorised representative to perform mandate tasks "
                "including: providing mandate copies to AI Office, verifying conformity documentation, "
                "keeping documents for 10 years, cooperating with authorities, and terminating "
                "the mandate if the provider acts contrary to its obligations."
            ),
            effort="4-8 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=22,
            article_title="Authorised representatives of providers of high-risk AI systems",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 22 is a provider obligation for high-risk AI systems, primarily targeting "
                "non-EU providers. Based on ComplianceLint compliance checklist. Official CEN-CENELEC "
                "standards (expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art22Module:
    return Art22Module()
