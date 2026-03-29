"""
Article 24: Obligations of distributors — Module implementation.

Art. 24 imposes obligations on distributors of high-risk AI systems regarding
pre-market verification, non-conformity handling, storage/transport conditions,
corrective actions, authority cooperation, and information provision.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art24"). No regex or keyword scanning is performed.

Obligation mapping:
  ART24-OBL-1   → has_pre_market_verification (verify CE marking, declaration, instructions)
  ART24-OBL-2   → has_conformity_review (prohibition: don't distribute if non-conforming)
  ART24-OBL-3   → always UTD (manual — storage/transport conditions)
  ART24-OBL-2b  → always UTD (manual — inform provider/importer of risk)
  ART24-OBL-4   → always UTD (manual — corrective actions for non-conforming systems)
  ART24-OBL-4b  → always UTD (manual — immediately inform provider/importer and authorities of risk)
  ART24-OBL-5   → has_authority_documentation (provide info/documentation on request)
  ART24-OBL-6   → always UTD (manual — cooperate with authorities)

Conditional logic:
  All obligations apply only to distributors. When is_distributor=False → NOT_APPLICABLE.
  When is_distributor=None → obligations proceed normally (conservative: assume may be distributor).
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


class Art24Module(BaseArticleModule):
    """Article 24: Obligations of distributors compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=24,
            article_title="Obligations of distributors",
        )

    def scan(self, project_path: str) -> ScanResult:
        project_path = os.path.abspath(project_path)
        ctx = self._effective_ctx(project_path)
        na = self._scope_gate(ctx, project_path)
        if na:
            return na
        # Art. 24 applies only to high-risk AI systems.
        risk = (ctx.risk_classification or "").lower().strip()
        conf = (ctx.risk_classification_confidence or "").lower().strip()
        if risk in self._NOT_HIGH_RISK_VALUES and conf in ("high", "medium"):
            return self._not_applicable_result(
                project_path,
                ctx.primary_language or "unknown",
                "ART24",
                legal_basis="Art. 6",
                reason=(
                    "Art. 24 obligations apply only to distributors of high-risk AI systems "
                    "(as classified under Art. 6). This system has been classified as "
                    f"'{ctx.risk_classification}' with {conf} confidence."
                ),
            )

        index = self._build_index(project_path)
        language = self._detect_language(project_path)
        file_count = index.source_file_count
        findings: list[Finding] = self._ctx_warnings(ctx)

        answers = ctx.get_article_answers("art24")

        is_distributor = answers.get("is_distributor")
        has_pre_market_verification = answers.get("has_pre_market_verification")
        has_conformity_review = answers.get("has_conformity_review")
        has_authority_documentation = answers.get("has_authority_documentation")

        # ── Conditional: non-distributors don't need Art. 24 ──
        if is_distributor is False:
            for obl_id in ["ART24-OBL-1", "ART24-OBL-2", "ART24-OBL-3",
                           "ART24-OBL-2b", "ART24-OBL-4", "ART24-OBL-4b",
                           "ART24-OBL-5", "ART24-OBL-6"]:
                findings.append(Finding(
                    obligation_id=obl_id,
                    file_path="project-wide",
                    line_number=None,
                    level=ComplianceLevel.NOT_APPLICABLE,
                    confidence=Confidence.HIGH,
                    description=(
                        "Organisation is not a distributor. Art. 24 obligations apply only to "
                        "distributors of high-risk AI systems."
                    ),
                    gap_type=GapType.PROCESS,
                    is_informational=True,
                ))
        else:
            # ── ART24-OBL-1: Pre-market verification ──
            findings.append(self._finding_from_answer(
                obligation_id="ART24-OBL-1",
                answer=has_pre_market_verification,
                true_description=(
                    "Pre-market verification documentation detected. "
                    "Verify the distributor checks CE marking, EU declaration of conformity "
                    "(Art. 47), instructions for use, and provider/importer compliance "
                    "(Art. 16(b)(c), Art. 23(3)) before making the system available on the market "
                    "per Art. 24(1)."
                ),
                false_description=(
                    "No pre-market verification documentation detected. "
                    "Art. 24(1) requires distributors to verify CE marking, EU declaration of "
                    "conformity, instructions for use, and provider/importer compliance before "
                    "making high-risk AI systems available on the market."
                ),
                none_description=(
                    "AI could not determine whether pre-market verification procedures exist. "
                    "Art. 24(1) requires distributors to verify CE marking, EU declaration, and "
                    "instructions for use before market placement."
                ),
                gap_type=GapType.PROCESS,
            ))

            # ── ART24-OBL-2: Do not distribute non-conforming systems (prohibition) ──
            # This is a prohibition: having conformity_review=True means the distributor
            # has procedures to prevent distributing non-conforming systems.
            findings.append(self._finding_from_answer(
                obligation_id="ART24-OBL-2",
                answer=has_conformity_review,
                true_description=(
                    "Conformity review procedures detected. "
                    "Verify that the distributor does not make high-risk AI systems available "
                    "on the market when there is reason to consider them non-conforming with "
                    "Section 2 requirements, per Art. 24(2)."
                ),
                false_description=(
                    "No conformity review procedures detected. "
                    "Art. 24(2) prohibits distributors from making high-risk AI systems "
                    "available on the market when they have reason to consider the system "
                    "non-conforming with Section 2 requirements."
                ),
                none_description=(
                    "AI could not determine whether conformity review procedures exist. "
                    "Art. 24(2) prohibits distribution of non-conforming high-risk AI systems."
                ),
                gap_type=GapType.PROCESS,
            ))

            # ── ART24-OBL-5: Provide information on authority request ──
            findings.append(self._finding_from_answer(
                obligation_id="ART24-OBL-5",
                answer=has_authority_documentation,
                true_description=(
                    "Authority documentation capability detected. "
                    "Verify the distributor can provide all information and documentation "
                    "regarding actions under Art. 24(1)-(4) to demonstrate conformity upon "
                    "reasoned request from competent authorities, per Art. 24(5)."
                ),
                false_description=(
                    "No authority documentation capability detected. "
                    "Art. 24(5) requires distributors to provide all information and documentation "
                    "regarding their actions under paragraphs 1-4 to competent authorities upon "
                    "reasoned request."
                ),
                none_description=(
                    "AI could not determine whether authority documentation capability exists. "
                    "Art. 24(5) requires distributors to provide information and documentation "
                    "to competent authorities upon reasoned request."
                ),
                gap_type=GapType.PROCESS,
            ))

        # Build details dict
        details = {
            "is_distributor": is_distributor,
            "has_pre_market_verification": has_pre_market_verification,
            "has_conformity_review": has_conformity_review,
            "has_authority_documentation": has_authority_documentation,
        }

        # ── Obligation Engine: enrich findings + identify gaps ──
        # Manual obligations (OBL-3, OBL-2b, OBL-4, OBL-4b, OBL-6) appear as gap findings.
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
            article_number=24,
            article_title="Obligations of distributors",
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
            article_number=24,
            article_title="Obligations of distributors",
            one_sentence=(
                "Distributors of high-risk AI systems must verify compliance before market "
                "placement and take corrective actions when non-conformity is identified."
            ),
            official_summary=(
                "Art. 24 requires distributors of high-risk AI systems to: "
                "(1) verify CE marking, EU declaration of conformity, instructions for use, "
                "and provider/importer compliance before market placement (Art. 24(1)); "
                "(2) not make non-conforming systems available on the market (Art. 24(2)); "
                "(3) ensure storage/transport conditions don't jeopardise compliance (Art. 24(3)); "
                "(4) take corrective actions or ensure others do for non-conforming systems "
                "already on the market (Art. 24(4)); "
                "(5) provide information and documentation to authorities upon request (Art. 24(5)); "
                "(6) cooperate with authorities to reduce or mitigate risks (Art. 24(6))."
            ),
            related_articles={
                "Art. 6": "High-risk classification (prerequisite for Art. 24)",
                "Art. 16(b)(c)": "Provider identification obligations (distributor must verify)",
                "Art. 23(3)": "Importer obligations (distributor must verify compliance)",
                "Art. 47": "EU declaration of conformity (must accompany the system)",
                "Art. 79(1)": "Definition of when a system 'presents a risk'",
                "Art. 20": "Corrective actions and duty of information",
            },
            recital=(
                "Recital 92: Distributors play a role in the supply chain of AI systems "
                "and should be subject to proportionate obligations to ensure that high-risk "
                "AI systems placed on the market comply with the requirements of this Regulation."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Pre-market verification documentation detection",
                    "Conformity review procedure detection",
                    "Authority documentation capability detection",
                ],
                "requires_human_judgment": [
                    "Whether CE marking is valid and properly applied",
                    "Whether EU declaration of conformity is complete",
                    "Whether provider/importer have met their obligations",
                    "Whether storage/transport conditions are adequate",
                    "Whether corrective actions are sufficient",
                    "Whether authority cooperation is adequate",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) documented pre-market "
                "verification checklist covering CE marking, EU declaration, and instructions; "
                "(2) conformity review procedures to prevent distribution of non-conforming systems; "
                "(3) documented authority response procedures. "
                "Based on: ISO/IEC 42001:2023 (supply chain governance controls)."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for distributor obligations (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("is_distributor") is False:
            actions.append(ActionItem(
                priority="LOW",
                article="Art. 24",
                action="Confirm non-distributor status",
                details=(
                    "Your system indicates the organisation is not a distributor. "
                    "Art. 24 obligations apply only to distributors of high-risk AI systems. "
                    "Verify this classification is correct — a distributor is any natural or "
                    "legal person in the supply chain that makes an AI system available on the "
                    "market without affecting its properties."
                ),
                effort="30 minutes",
                action_type="human_judgment_required",
            ))
        else:
            if details.get("has_pre_market_verification") is False:
                actions.append(ActionItem(
                    priority="CRITICAL",
                    article="Art. 24(1)",
                    action="Establish pre-market verification checklist",
                    details=(
                        "Art. 24(1) requires distributors to verify before market placement:\n"
                        "  - CE marking is present on the system\n"
                        "  - EU declaration of conformity (Art. 47) accompanies the system\n"
                        "  - Instructions for use accompany the system\n"
                        "  - Provider has complied with Art. 16(b) and (c)\n"
                        "  - Importer has complied with Art. 23(3)\n"
                        "Create a documented verification checklist for each system before distribution."
                    ),
                    effort="4-8 hours",
                    action_type="human_judgment_required",
                ))

            if details.get("has_conformity_review") is False:
                actions.append(ActionItem(
                    priority="CRITICAL",
                    article="Art. 24(2)",
                    action="Establish conformity review procedures",
                    details=(
                        "Art. 24(2) prohibits making non-conforming systems available. "
                        "Establish procedures to:\n"
                        "  - Review conformity information before distribution\n"
                        "  - Flag systems that may not conform to Section 2 requirements\n"
                        "  - Hold distribution until conformity is established\n"
                        "  - Inform provider/importer of risk per Art. 79(1)"
                    ),
                    effort="4-8 hours",
                    action_type="human_judgment_required",
                ))

            if details.get("has_authority_documentation") is False:
                actions.append(ActionItem(
                    priority="HIGH",
                    article="Art. 24(5)",
                    action="Establish authority documentation capability",
                    details=(
                        "Art. 24(5) requires distributors to provide all information and "
                        "documentation regarding their actions under Art. 24(1)-(4) to "
                        "competent authorities upon reasoned request. Ensure:\n"
                        "  - All verification records are retained\n"
                        "  - Conformity review records are accessible\n"
                        "  - Corrective action documentation is maintained\n"
                        "  - A designated contact person can respond to authority requests"
                    ),
                    effort="4-8 hours",
                    action_type="human_judgment_required",
                ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 24(3)",
            action="Review storage and transport conditions",
            details=(
                "Art. 24(3) requires distributors to ensure storage or transport conditions "
                "do not jeopardise compliance with Section 2 requirements. Review and document "
                "storage/transport procedures for AI system components."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 24(4)",
            action="Establish corrective action procedures",
            details=(
                "Art. 24(4) requires distributors to take corrective actions for non-conforming "
                "systems already on the market, or ensure the provider/importer does so. "
                "Document: corrective action procedures, withdrawal/recall processes, and "
                "authority notification protocols."
            ),
            effort="4-8 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=24,
            article_title="Obligations of distributors",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 24 is a distributor obligation for high-risk AI systems. "
                "Based on ComplianceLint compliance checklist. Official CEN-CENELEC "
                "standards (expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art24Module:
    return Art24Module()
