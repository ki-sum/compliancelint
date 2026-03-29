"""
Article 23: Obligations of importers — Module implementation.

Art. 23 imposes obligations on importers of high-risk AI systems regarding
pre-market conformity verification, non-placement of non-conforming systems,
importer identification, storage/transport conditions, document retention,
authority cooperation, and information provision.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art23"). No regex or keyword scanning is performed.

Obligation mapping:
  ART23-OBL-1   → has_pre_market_verification (verify conformity before placement)
  ART23-OBL-2   → has_conformity_review (prohibition: don't place non-conforming systems)
  ART23-OBL-3   → has_importer_identification (importer name/trademark on system)
  ART23-OBL-4   → always UTD (manual — storage/transport conditions)
  ART23-OBL-2b  → always UTD (manual — inform provider/authorities of risk)
  ART23-OBL-5   → has_documentation_retention (keep documents for 10 years)
  ART23-OBL-6   → has_authority_documentation (provide info to authorities on request)
  ART23-OBL-7   → always UTD (manual — cooperate with authorities)

Conditional logic:
  All obligations apply only to importers. When is_importer=False → NOT_APPLICABLE.
  When is_importer=None → obligations proceed normally (conservative: assume may be importer).
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


class Art23Module(BaseArticleModule):
    """Article 23: Obligations of importers compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=23,
            article_title="Obligations of importers",
        )

    def scan(self, project_path: str) -> ScanResult:
        project_path = os.path.abspath(project_path)
        ctx = self._effective_ctx(project_path)
        na = self._scope_gate(ctx, project_path)
        if na:
            return na
        # Art. 23 applies only to high-risk AI systems.
        risk = (ctx.risk_classification or "").lower().strip()
        conf = (ctx.risk_classification_confidence or "").lower().strip()
        if risk in self._NOT_HIGH_RISK_VALUES and conf in ("high", "medium"):
            return self._not_applicable_result(
                project_path,
                ctx.primary_language or "unknown",
                "ART23",
                legal_basis="Art. 6",
                reason=(
                    "Art. 23 obligations apply only to importers of high-risk AI systems "
                    "(as classified under Art. 6). This system has been classified as "
                    f"'{ctx.risk_classification}' with {conf} confidence."
                ),
            )

        index = self._build_index(project_path)
        language = self._detect_language(project_path)
        file_count = index.source_file_count
        findings: list[Finding] = self._ctx_warnings(ctx)

        answers = ctx.get_article_answers("art23")

        is_importer = answers.get("is_importer")
        has_pre_market_verification = answers.get("has_pre_market_verification")
        has_conformity_review = answers.get("has_conformity_review")
        has_importer_identification = answers.get("has_importer_identification")
        has_documentation_retention = answers.get("has_documentation_retention")
        has_authority_documentation = answers.get("has_authority_documentation")

        # ── Conditional: non-importers don't need Art. 23 ──
        if is_importer is False:
            for obl_id in ["ART23-OBL-1", "ART23-OBL-2", "ART23-OBL-3",
                           "ART23-OBL-4", "ART23-OBL-2b", "ART23-OBL-5",
                           "ART23-OBL-6", "ART23-OBL-7"]:
                findings.append(Finding(
                    obligation_id=obl_id,
                    file_path="project-wide",
                    line_number=None,
                    level=ComplianceLevel.NOT_APPLICABLE,
                    confidence=Confidence.HIGH,
                    description=(
                        "Organisation is not an importer. Art. 23 obligations apply only to "
                        "importers of high-risk AI systems."
                    ),
                    gap_type=GapType.PROCESS,
                    is_informational=True,
                ))
        else:
            # ── ART23-OBL-1: Pre-market conformity verification ──
            findings.append(self._finding_from_answer(
                obligation_id="ART23-OBL-1",
                answer=has_pre_market_verification,
                true_description=(
                    "Pre-market conformity verification documentation detected. "
                    "Verify the importer checks that conformity assessment (Art. 43) has been "
                    "carried out, technical documentation (Art. 11, Annex IV) exists, CE marking "
                    "and EU declaration of conformity (Art. 47) are present, and the provider has "
                    "appointed an authorised representative (Art. 22(1)), per Art. 23(1)."
                ),
                false_description=(
                    "No pre-market conformity verification documentation detected. "
                    "Art. 23(1) requires importers to verify before placing a high-risk AI system "
                    "on the market: (a) conformity assessment per Art. 43, (b) technical documentation "
                    "per Art. 11 and Annex IV, (c) CE marking and EU declaration of conformity, "
                    "(d) provider has appointed an authorised representative per Art. 22(1)."
                ),
                none_description=(
                    "AI could not determine whether pre-market conformity verification procedures "
                    "exist. Art. 23(1) requires importers to verify conformity assessment, technical "
                    "documentation, CE marking, EU declaration, and authorised representative "
                    "appointment before market placement."
                ),
                gap_type=GapType.PROCESS,
            ))

            # ── ART23-OBL-2: Do not place non-conforming systems (prohibition) ──
            findings.append(self._finding_from_answer(
                obligation_id="ART23-OBL-2",
                answer=has_conformity_review,
                true_description=(
                    "Conformity review procedures detected. "
                    "Verify that the importer does not place high-risk AI systems on the market "
                    "when there is sufficient reason to consider them non-conforming, falsified, "
                    "or accompanied by falsified documentation, per Art. 23(2)."
                ),
                false_description=(
                    "No conformity review procedures detected. "
                    "Art. 23(2) prohibits importers from placing high-risk AI systems on the market "
                    "when they have sufficient reason to consider the system non-conforming, "
                    "falsified, or accompanied by falsified documentation."
                ),
                none_description=(
                    "AI could not determine whether conformity review procedures exist. "
                    "Art. 23(2) prohibits placement of non-conforming or falsified systems."
                ),
                gap_type=GapType.PROCESS,
            ))

            # ── ART23-OBL-3: Importer identification on system ──
            findings.append(self._finding_from_answer(
                obligation_id="ART23-OBL-3",
                answer=has_importer_identification,
                true_description=(
                    "Importer identification detected on system, packaging, or documentation. "
                    "Verify that the importer's name, registered trade name or trade mark, and "
                    "contact address are indicated on the system, packaging, or accompanying "
                    "documentation per Art. 23(3)."
                ),
                false_description=(
                    "No importer identification detected on system, packaging, or documentation. "
                    "Art. 23(3) requires importers to indicate their name, registered trade name "
                    "or trade mark, and contact address on the high-risk AI system, its packaging, "
                    "or accompanying documentation."
                ),
                none_description=(
                    "AI could not determine whether importer identification is present. "
                    "Art. 23(3) requires importer name, trade name/mark, and contact address "
                    "on the system, packaging, or documentation."
                ),
                gap_type=GapType.PROCESS,
            ))

            # ── ART23-OBL-5: Document retention (10 years) ──
            findings.append(self._finding_from_answer(
                obligation_id="ART23-OBL-5",
                answer=has_documentation_retention,
                true_description=(
                    "Documentation retention procedures detected. "
                    "Verify that the importer keeps, for 10 years after market placement or "
                    "putting into service: notified body certificate (where applicable), "
                    "instructions for use, and EU declaration of conformity (Art. 47), "
                    "per Art. 23(5)."
                ),
                false_description=(
                    "No documentation retention procedures detected. "
                    "Art. 23(5) requires importers to keep, for 10 years after placing on the "
                    "market or putting into service: the notified body certificate (where applicable), "
                    "instructions for use, and EU declaration of conformity (Art. 47)."
                ),
                none_description=(
                    "AI could not determine whether documentation retention procedures exist. "
                    "Art. 23(5) requires 10-year retention of certificates, instructions for use, "
                    "and EU declaration of conformity."
                ),
                gap_type=GapType.PROCESS,
            ))

            # ── ART23-OBL-6: Provide information to authorities on request ──
            findings.append(self._finding_from_answer(
                obligation_id="ART23-OBL-6",
                answer=has_authority_documentation,
                true_description=(
                    "Authority documentation capability detected. "
                    "Verify the importer can provide all necessary information and documentation "
                    "to demonstrate conformity with Section 2 requirements upon reasoned request "
                    "from competent authorities, in an easily understood language, and that "
                    "technical documentation can be made available per Art. 23(6)."
                ),
                false_description=(
                    "No authority documentation capability detected. "
                    "Art. 23(6) requires importers to provide competent authorities, upon a "
                    "reasoned request, with all necessary information and documentation to "
                    "demonstrate conformity with Section 2, in an easily understood language, "
                    "and to ensure technical documentation can be made available."
                ),
                none_description=(
                    "AI could not determine whether authority documentation capability exists. "
                    "Art. 23(6) requires importers to provide information and documentation "
                    "to competent authorities upon reasoned request."
                ),
                gap_type=GapType.PROCESS,
            ))

        # Build details dict
        details = {
            "is_importer": is_importer,
            "has_pre_market_verification": has_pre_market_verification,
            "has_conformity_review": has_conformity_review,
            "has_importer_identification": has_importer_identification,
            "has_documentation_retention": has_documentation_retention,
            "has_authority_documentation": has_authority_documentation,
        }

        # ── Obligation Engine: enrich findings + identify gaps ──
        # Manual obligations (OBL-4, OBL-2b, OBL-7) appear as gap findings.
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
            article_number=23,
            article_title="Obligations of importers",
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
            article_number=23,
            article_title="Obligations of importers",
            one_sentence=(
                "Importers of high-risk AI systems must verify conformity before market "
                "placement and maintain documentation for 10 years."
            ),
            official_summary=(
                "Art. 23 requires importers of high-risk AI systems to: "
                "(1) verify conformity assessment, technical documentation, CE marking, EU "
                "declaration, and authorised representative appointment before market placement "
                "(Art. 23(1)); "
                "(2) not place non-conforming or falsified systems on the market (Art. 23(2)); "
                "(3) indicate their name, trade name/mark, and contact address on the system, "
                "packaging, or documentation (Art. 23(3)); "
                "(4) ensure storage/transport conditions don't jeopardise compliance (Art. 23(4)); "
                "(5) keep certificates, instructions, and EU declaration for 10 years (Art. 23(5)); "
                "(6) provide information and documentation to authorities upon request (Art. 23(6)); "
                "(7) cooperate with authorities to reduce and mitigate risks (Art. 23(7))."
            ),
            related_articles={
                "Art. 6": "High-risk classification (prerequisite for Art. 23)",
                "Art. 11": "Technical documentation (importer must verify existence)",
                "Art. 22(1)": "Authorised representative appointment (importer must verify)",
                "Art. 43": "Conformity assessment (importer must verify completion)",
                "Art. 47": "EU declaration of conformity (must accompany the system)",
                "Art. 79(1)": "Definition of when a system 'presents a risk'",
                "Annex IV": "Technical documentation requirements",
            },
            recital=(
                "Recital 92: Importers play a role in the supply chain of AI systems "
                "and should be subject to proportionate obligations to ensure that high-risk "
                "AI systems placed on the market comply with the requirements of this Regulation."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Pre-market conformity verification documentation detection",
                    "Conformity review procedure detection",
                    "Importer identification detection",
                    "Documentation retention procedure detection",
                    "Authority documentation capability detection",
                ],
                "requires_human_judgment": [
                    "Whether conformity assessment was actually carried out properly",
                    "Whether technical documentation is complete and adequate",
                    "Whether CE marking is valid and properly applied",
                    "Whether storage/transport conditions are adequate",
                    "Whether authority cooperation is sufficient",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) documented pre-market "
                "conformity verification checklist covering Art. 43, Art. 11/Annex IV, CE marking, "
                "Art. 47 declaration, and Art. 22(1) representative; "
                "(2) conformity review procedures to prevent placement of non-conforming systems; "
                "(3) importer identification on system/packaging/documentation; "
                "(4) 10-year document retention plan; "
                "(5) documented authority response procedures. "
                "Based on: ISO/IEC 42001:2023 (supply chain governance controls)."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for importer obligations (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("is_importer") is False:
            actions.append(ActionItem(
                priority="LOW",
                article="Art. 23",
                action="Confirm non-importer status",
                details=(
                    "Your system indicates the organisation is not an importer. "
                    "Art. 23 obligations apply only to importers of high-risk AI systems. "
                    "Verify this classification is correct — an importer is any natural or "
                    "legal person established in the Union that places on the market an AI system "
                    "that bears the name or trademark of a natural or legal person established in "
                    "a third country."
                ),
                effort="30 minutes",
                action_type="human_judgment_required",
            ))
        else:
            if details.get("has_pre_market_verification") is False:
                actions.append(ActionItem(
                    priority="CRITICAL",
                    article="Art. 23(1)",
                    action="Establish pre-market conformity verification checklist",
                    details=(
                        "Art. 23(1) requires importers to verify before market placement:\n"
                        "  - Conformity assessment per Art. 43 has been carried out\n"
                        "  - Technical documentation per Art. 11 and Annex IV exists\n"
                        "  - CE marking is present on the system\n"
                        "  - EU declaration of conformity (Art. 47) accompanies the system\n"
                        "  - Instructions for use accompany the system\n"
                        "  - Provider has appointed an authorised representative per Art. 22(1)\n"
                        "Create a documented verification checklist for each system before import."
                    ),
                    effort="4-8 hours",
                    action_type="human_judgment_required",
                ))

            if details.get("has_conformity_review") is False:
                actions.append(ActionItem(
                    priority="CRITICAL",
                    article="Art. 23(2)",
                    action="Establish conformity review procedures",
                    details=(
                        "Art. 23(2) prohibits placing non-conforming or falsified systems. "
                        "Establish procedures to:\n"
                        "  - Review conformity information before import\n"
                        "  - Flag systems that may not conform or appear falsified\n"
                        "  - Hold placement until conformity is established\n"
                        "  - Inform provider, authorised representative, and market surveillance "
                        "authorities of risk per Art. 79(1)"
                    ),
                    effort="4-8 hours",
                    action_type="human_judgment_required",
                ))

            if details.get("has_importer_identification") is False:
                actions.append(ActionItem(
                    priority="HIGH",
                    article="Art. 23(3)",
                    action="Add importer identification to system and documentation",
                    details=(
                        "Art. 23(3) requires importers to indicate their name, registered trade "
                        "name or trade mark, and contact address on the high-risk AI system, "
                        "its packaging, or accompanying documentation. Ensure:\n"
                        "  - Legal entity name is displayed\n"
                        "  - Trade name or registered trade mark is included\n"
                        "  - Contact address (postal or email) is provided"
                    ),
                    effort="1-2 hours",
                    action_type="human_judgment_required",
                ))

            if details.get("has_documentation_retention") is False:
                actions.append(ActionItem(
                    priority="HIGH",
                    article="Art. 23(5)",
                    action="Establish 10-year document retention plan",
                    details=(
                        "Art. 23(5) requires importers to keep for 10 years after market placement:\n"
                        "  - Notified body certificate (where applicable)\n"
                        "  - Instructions for use\n"
                        "  - EU declaration of conformity (Art. 47)\n"
                        "Implement a document management system or archive with 10-year retention."
                    ),
                    effort="4-8 hours",
                    action_type="human_judgment_required",
                ))

            if details.get("has_authority_documentation") is False:
                actions.append(ActionItem(
                    priority="HIGH",
                    article="Art. 23(6)",
                    action="Establish authority documentation capability",
                    details=(
                        "Art. 23(6) requires importers to provide all information and "
                        "documentation to demonstrate conformity upon reasoned request from "
                        "competent authorities, in an easily understood language. Ensure:\n"
                        "  - All verification records from Art. 23(5) are retained and accessible\n"
                        "  - Technical documentation can be made available to authorities\n"
                        "  - A designated contact person can respond to authority requests\n"
                        "  - Documentation is available in the relevant EU language(s)"
                    ),
                    effort="4-8 hours",
                    action_type="human_judgment_required",
                ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 23(4)",
            action="Review storage and transport conditions",
            details=(
                "Art. 23(4) requires importers to ensure storage or transport conditions "
                "do not jeopardise compliance with Section 2 requirements. Review and document "
                "storage/transport procedures for AI system components."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 23(7)",
            action="Establish authority cooperation procedures",
            details=(
                "Art. 23(7) requires importers to cooperate with competent authorities "
                "in any action taken in relation to the high-risk AI system, in particular "
                "to reduce and mitigate risks. Document cooperation procedures and designate "
                "a responsible person."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=23,
            article_title="Obligations of importers",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 23 is an importer obligation for high-risk AI systems. "
                "Based on ComplianceLint compliance checklist. Official CEN-CENELEC "
                "standards (expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art23Module:
    return Art23Module()
