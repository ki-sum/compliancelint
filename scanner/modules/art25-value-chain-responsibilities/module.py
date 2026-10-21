"""
Article 25: Responsibilities along the AI value chain — Module implementation.

Art. 25 addresses how provider responsibilities transfer when third parties
rebrand, substantially modify, or change the intended purpose of an AI system.
It also requires written agreements between providers and third parties supplying AI systems,
AI models, tools, services, components or processes (Art. 25(4), as amended by Reg (EU) 2026/1744).

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art25"). No regex or keyword scanning is performed.

Obligation mapping:
  ART25-CLS-1   → has_rebranding_or_modification (classification: triggers provider status)
  ART25-OBL-2   → has_provider_cooperation_documentation (initial provider cooperation)
  ART25-EXC-2   → gap finding (exception: initial provider opt-out)
  ART25-CLS-3   → is_safety_component_annex_i (classification: product manufacturer = provider)
  ART25-OBL-4   → has_third_party_written_agreement (written agreement with suppliers)
  ART25-EXC-4   → gap finding (exception: open-source components)
  ART25-SAV-5   → always UTD (manual — IP/trade secret preservation)

Classification rules (CLS-1, CLS-3) use custom Finding() construction since they
determine a legal classification, not a compliance requirement.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.application_dates import applicable_from
from core.harmonised_standards import standard_status
from core.protocol import (
    BaseArticleModule, ScanResult, Explanation, ActionPlan, ActionItem,
    Finding, ComplianceLevel, Confidence, GapType,
)
from core.obligation_engine import ObligationEngine


class Art25Module(BaseArticleModule):
    """Article 25: Responsibilities along the AI value chain compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=25,
            article_title="Responsibilities along the AI value chain",
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

        answers = ctx.get_article_answers("art25")

        has_rebranding_or_modification = answers.get("has_rebranding_or_modification")
        has_provider_cooperation_documentation = answers.get("has_provider_cooperation_documentation")
        is_safety_component_annex_i = answers.get("is_safety_component_annex_i")
        has_third_party_written_agreement = answers.get("has_third_party_written_agreement")
        has_open_source_exception = answers.get("has_open_source_exception")

        # ── ART25-CLS-1: Rebranding/modification triggers provider status ──
        # Classification rule: informational — tells user if they may be considered a provider.
        if has_rebranding_or_modification is True:
            findings.append(Finding(
                obligation_id="ART25-CLS-1",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.PARTIAL,
                confidence=Confidence.MEDIUM,
                description=(
                    "Rebranding, substantial modification, or intended purpose change detected. "
                    "Under Art. 25(1), any party that (a) puts their name or trademark on a "
                    "high-risk AI system, (b) makes a substantial modification per Art. 6, or "
                    "(c) modifies the intended purpose making it high-risk, SHALL be considered "
                    "a provider and subject to Art. 16 obligations. Confirm provider status with "
                    "legal counsel."
                ),
                gap_type=GapType.PROCESS,
                is_informational=True,
            ))
        elif has_rebranding_or_modification is False:
            findings.append(Finding(
                obligation_id="ART25-CLS-1",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.COMPLIANT,
                confidence=Confidence.MEDIUM,
                description=(
                    "No rebranding, substantial modification, or intended purpose change detected. "
                    "Art. 25(1) provider reclassification does not apply to this system."
                ),
                gap_type=GapType.PROCESS,
                is_informational=True,
            ))
        else:
            findings.append(Finding(
                obligation_id="ART25-CLS-1",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "AI could not determine whether this system involves rebranding, substantial "
                    "modification, or intended purpose change. Art. 25(1) classifies parties that "
                    "rebrand, substantially modify, or change the intended purpose of a high-risk "
                    "AI system as providers under Art. 16. Manual review recommended."
                ),
                gap_type=GapType.PROCESS,
                is_informational=True,
            ))

        # ── ART25-OBL-2: Initial provider cooperation ──
        findings.append(self._finding_from_answer(
            obligation_id="ART25-OBL-2",
            answer=has_provider_cooperation_documentation,
            true_description=(
                "Provider cooperation documentation detected. "
                "Verify the initial provider closely cooperates with new providers and makes "
                "available necessary information, technical access, and assistance required "
                "for compliance with this Regulation, including, where relevant, technical "
                "documentation sufficient to assess compliance with the requirements laid down "
                "in Art. 16, information on known limitations and failure modes, and targeted "
                "technical access, including for testing and validation, per Art. 25(2)."
            ),
            false_description=(
                "No provider cooperation documentation detected. "
                "Art. 25(2) requires the initial provider to closely cooperate with new "
                "providers and make available necessary information, technical access, and "
                "other assistance for fulfilment of the obligations set out in this Regulation; "
                "where relevant, this includes technical documentation, information on known "
                "limitations and failure modes, and targeted technical access."
            ),
            none_description=(
                "AI could not determine whether provider cooperation documentation exists. "
                "Art. 25(2) requires the initial provider to cooperate with new providers "
                "and share necessary information and technical access."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART25-CLS-3: Product manufacturer = provider (Annex I safety component) ──
        # Classification rule with context_skip_field: is_safety_component_annex_i
        if is_safety_component_annex_i is False:
            findings.append(Finding(
                obligation_id="ART25-CLS-3",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.HIGH,
                description=(
                    "System is not a safety component of a product covered by Annex I. "
                    "Art. 25(3) product manufacturer classification does not apply."
                ),
                gap_type=GapType.PROCESS,
                is_informational=True,
            ))
        elif is_safety_component_annex_i is True:
            findings.append(Finding(
                obligation_id="ART25-CLS-3",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.PARTIAL,
                confidence=Confidence.MEDIUM,
                description=(
                    "System identified as a safety component of a product covered by Annex I "
                    "Union harmonisation legislation. Under Art. 25(3), the product manufacturer "
                    "SHALL be considered the provider and subject to Art. 16 obligations when the "
                    "AI system is placed on market or put into service under their name or trademark. "
                    "Confirm classification with legal counsel."
                ),
                gap_type=GapType.PROCESS,
                is_informational=True,
            ))
        else:
            findings.append(Finding(
                obligation_id="ART25-CLS-3",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "AI could not determine whether this system is a safety component of a "
                    "product covered by Annex I Union harmonisation legislation. Art. 25(3) "
                    "classifies the product manufacturer as the provider in such cases. "
                    "Manual review recommended."
                ),
                gap_type=GapType.PROCESS,
                is_informational=True,
            ))

        # ── ART25-OBL-4: Written agreement with third-party suppliers ──
        findings.append(self._finding_from_answer(
            obligation_id="ART25-OBL-4",
            answer=has_third_party_written_agreement,
            true_description=(
                "Written agreement with third-party AI component suppliers detected. "
                "Verify the agreement specifies necessary information, capabilities, technical "
                "access, and other assistance based on the generally acknowledged state of the "
                "art, enabling full compliance with this Regulation, per Art. 25(4)."
            ),
            false_description=(
                "No written agreement with third-party AI component suppliers detected. Art. "
                "25(4) requires the provider of a high-risk AI system and a third party "
                "supplying an AI system, AI model, tools, services, components, or processes "
                "used or integrated in the high-risk AI system to specify by written agreement "
                "the necessary information, capabilities, technical access and other assistance "
                "based on the generally acknowledged state of the art needed to enable full "
                "compliance, subject to the free and open-source exception in the second "
                "sentence of Art. 25(4)."
            ),
            none_description=(
                "AI could not determine whether written agreements exist with third-party "
                "AI component suppliers. Art. 25(4) requires written agreements specifying "
                "information, capabilities, and technical access for regulatory compliance."
            ),
            gap_type=GapType.PROCESS,
        ))

        # Build details dict
        details = {
            "has_rebranding_or_modification": has_rebranding_or_modification,
            "has_provider_cooperation_documentation": has_provider_cooperation_documentation,
            "is_safety_component_annex_i": is_safety_component_annex_i,
            "has_third_party_written_agreement": has_third_party_written_agreement,
            "has_open_source_exception": has_open_source_exception,
        }

        # ── Obligation Engine: enrich findings + identify gaps ──
        # EXC-2, EXC-4, SAV-5 appear as gap findings.
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
            article_number=25,
            article_title="Responsibilities along the AI value chain",
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
            article_number=25,
            article_title="Responsibilities along the AI value chain",
            one_sentence=(
                "When a third party rebrands, modifies, or changes the purpose of an AI system "
                "to make it high-risk, they become the provider and must comply with provider obligations."
            ),
            official_summary=(
                "Art. 25 determines responsibilities along the AI value chain. (1) A "
                "distributor, importer, deployer or other third party becomes the provider of a "
                "high-risk AI system, and is subject to Art. 16, in the circumstances listed in "
                "Art. 25(1). (2) The initial provider must closely cooperate with new providers "
                "by making available the necessary information and providing reasonably "
                "expected technical access and other assistance; where relevant, this includes "
                "technical documentation sufficient to assess compliance with Art. 16, "
                "information on known limitations and failure modes, and targeted technical "
                "access for testing and validation. Paragraph 2 does not apply where the "
                "initial provider clearly specified that its AI system is not to be changed "
                "into a high-risk AI system. (3) For high-risk AI systems that are safety "
                "components of products covered by Section A of Annex I, the product "
                "manufacturer is the provider where the high-risk AI system is placed on the "
                "market together with the product under the manufacturer's name or trademark, "
                "or is put into service under that name or trademark after the product has been "
                "placed on the market. (4) The provider of a high-risk AI system and third "
                "parties supplying AI systems, AI models, tools, services, components or "
                "processes used or integrated in it must specify by written agreement the "
                "information, capabilities, technical access and other assistance based on the "
                "generally acknowledged state of the art needed for compliance, subject to the "
                "second-sentence free/open-source exception. (5) Paragraphs 2 and 3 are without "
                "prejudice to the protection of intellectual property rights, confidential "
                "business information and trade secrets. Art. 99(4), point (da), subjects "
                "non-compliance with obligations of providers and operators under Art. 25(2) "
                "and (4) to the fines specified there."
            ),
            related_articles={
                "Art. 6": "High-risk classification (referenced for substantial modification)",
                "Art. 16": "Provider obligations (transferred to new provider under Art. 25)",
                "Art. 22(1)": "Authorised representative appointment",
                "Art. 43": "Conformity assessment (new provider must complete)",
                "Annex I Section A": "Union harmonisation legislation (safety components)",
            },
            recital=(
                "Recital 84: To ensure legal certainty, it is necessary to clarify that, under "
                "certain specific conditions, any distributor, importer, deployer or other "
                "third-party should be considered to be a provider of a high-risk AI system and "
                "therefore assume all the relevant obligations."
            ),
            automation_summary={
                "fully_automatable": [
                    "Open-source license detection for third-party components (EXC-4)",
                ],
                "partially_automatable": [
                    "Rebranding or modification indicator detection (CLS-1)",
                    "Provider cooperation documentation detection (OBL-2)",
                    "Safety component classification (CLS-3)",
                    "Third-party written agreement detection (OBL-4)",
                ],
                "requires_human_judgment": [
                    "Whether a modification is 'substantial' under Art. 6",
                    "Whether provider cooperation is adequate and complete",
                    "Whether written agreements are legally sufficient",
                    "IP and trade secret protection assessment (SAV-5)",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) assessment of whether rebranding "
                "or modification triggers provider reclassification under Art. 25(1); "
                "(2) documented cooperation with upstream/downstream providers per Art. 25(2); "
                "(3) Annex I safety component classification check per Art. 25(3); "
                "(4) written agreements with all third-party AI component suppliers per Art. 25(4); "
                "(5) IP/trade secret protection review per Art. 25(5). "
                "Based on: ISO/IEC 42001:2023 (supply chain governance controls)."
            ),
            enforcement_date=applicable_from(25),
            waiting_for=standard_status(25),
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_rebranding_or_modification") is True:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 25(1)",
                action="Confirm provider status after rebranding or modification",
                details=(
                    "Art. 25(1) reclassifies any party that rebrands, substantially modifies, "
                    "or changes the intended purpose of a high-risk AI system as a provider. "
                    "If confirmed:\n"
                    "  - Complete conformity assessment per Art. 43\n"
                    "  - Fulfil all provider obligations under Art. 16\n"
                    "  - Obtain cooperation from the initial provider per Art. 25(2)\n"
                    "  - Document the modification and its impact on compliance"
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_provider_cooperation_documentation") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 25(2)",
                action="Establish provider cooperation documentation",
                details=(
                    "Art. 25(2) requires the initial provider to closely cooperate with new "
                    "providers, make available the necessary information, and provide "
                    "reasonably expected technical access and other assistance required for "
                    "fulfilment of obligations under the Regulation, in particular conformity "
                    "assessment. Where relevant, this includes: (a) technical documentation "
                    "sufficient to assess compliance with Art. 16; (b) information on known "
                    "limitations and failure modes; and (c) targeted technical access, "
                    "including for testing and validation. Paragraph 2 does not apply where the "
                    "initial provider clearly specified that its AI system is not to be changed "
                    "into a high-risk AI system.\n\nArt. 25(2) does not prescribe how cooperation "
                    "is documented; for example, you can keep a record of:\n  - The information "
                    "and documentation made available to each new provider\n  - The technical "
                    "access provided, including for testing and validation\n  - Cooperation "
                    "contact points"
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_third_party_written_agreement") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 25(4)",
                action="Establish written agreements with third-party AI suppliers",
                details=(
                    "Art. 25(4) requires written agreements between the provider of a high-risk "
                    "AI system and third parties supplying AI systems, AI models, tools, "
                    "services, components, or processes used or integrated in that high-risk AI "
                    "system. Agreements must specify the necessary information, capabilities, "
                    "technical access and other assistance based on the generally acknowledged "
                    "state of the art needed to enable full compliance with the Regulation. "
                    "Note: The second-sentence exception applies to third parties making tools, "
                    "services, processes or components accessible to the public under a free "
                    "and open-source licence, but expressly excludes general-purpose AI models. "
                    "It does not add AI systems or AI models as categories benefiting from the "
                    "exception."
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 25(5)",
            action="Review IP and trade secret protections in value chain agreements",
            details=(
                "Art. 25(5) preserves intellectual property rights, confidential business "
                "information, and trade secrets. Review all cooperation and information-sharing "
                "obligations (Art. 25(2)-(3)) to ensure they do not conflict with IP protections "
                "under Union and national law."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        if details.get("is_safety_component_annex_i") is True:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 25(3)",
                action="Confirm product manufacturer provider obligations for Annex I safety component",
                details=(
                    "Art. 25(3) classifies the product manufacturer as the provider when the "
                    "AI system is a safety component of a product covered by Annex I Union "
                    "harmonisation legislation. Confirm:\n"
                    "  - Whether the AI system is placed on market under manufacturer's name\n"
                    "  - Whether Art. 16 provider obligations are being fulfilled\n"
                    "  - Whether conformity assessment per Art. 43 is completed"
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        return ActionPlan(
            article_number=25,
            article_title="Responsibilities along the AI value chain",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 25 addresses value chain responsibilities for high-risk AI systems. Based on ComplianceLint "
                "compliance checklist."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art25Module:
    return Art25Module()
