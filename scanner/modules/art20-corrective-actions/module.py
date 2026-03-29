"""
Article 20: Corrective actions and duty of information — Module implementation.

Art. 20 requires providers of high-risk AI systems to take corrective actions
when non-conformity is identified, inform supply chain stakeholders, and
investigate and report risks to authorities.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art20"). No regex or keyword scanning is performed.

Obligation mapping:
  ART20-OBL-1   → has_corrective_action_procedure (corrective action framework)
  ART20-OBL-1b  → has_supply_chain_notification (inform distributors/deployers)
  ART20-OBL-2   → has_risk_investigation_procedure (investigate + inform authorities)
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


class Art20Module(BaseArticleModule):
    """Article 20: Corrective actions and duty of information compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=20,
            article_title="Corrective actions and duty of information",
        )

    def scan(self, project_path: str) -> ScanResult:
        project_path = os.path.abspath(project_path)
        ctx = self._effective_ctx(project_path)
        na = self._scope_gate(ctx, project_path)
        if na:
            return na
        # Art. 20 applies only to high-risk AI systems.
        risk = (ctx.risk_classification or "").lower().strip()
        conf = (ctx.risk_classification_confidence or "").lower().strip()
        if risk in self._NOT_HIGH_RISK_VALUES and conf in ("high", "medium"):
            return self._not_applicable_result(
                project_path,
                ctx.primary_language or "unknown",
                "ART20",
                legal_basis="Art. 6",
                reason=(
                    "Art. 20 obligations apply only to providers of high-risk AI systems "
                    "(as classified under Art. 6). This system has been classified as "
                    f"'{ctx.risk_classification}' with {conf} confidence."
                ),
            )

        index = self._build_index(project_path)
        language = self._detect_language(project_path)
        file_count = index.source_file_count
        findings: list[Finding] = self._ctx_warnings(ctx)

        answers = ctx.get_article_answers("art20")

        has_corrective_action_procedure = answers.get("has_corrective_action_procedure")
        has_supply_chain_notification = answers.get("has_supply_chain_notification")
        has_risk_investigation_procedure = answers.get("has_risk_investigation_procedure")

        # ── ART20-OBL-1: Corrective action procedure ──
        findings.append(self._finding_from_answer(
            obligation_id="ART20-OBL-1",
            answer=has_corrective_action_procedure,
            true_description=(
                "Corrective action procedure detected. "
                "Verify it covers bringing the system into conformity, withdrawal, "
                "disabling, or recall as appropriate per Art. 20(1)."
            ),
            false_description=(
                "No corrective action procedure detected. "
                "Art. 20(1) requires providers to immediately take corrective actions "
                "when non-conformity is identified, including bringing the system into "
                "conformity, withdrawing, disabling, or recalling it."
            ),
            none_description=(
                "AI could not determine whether a corrective action procedure exists. "
                "Art. 20(1) requires immediate corrective actions for non-conforming systems."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART20-OBL-1b: Supply chain notification ──
        findings.append(self._finding_from_answer(
            obligation_id="ART20-OBL-1b",
            answer=has_supply_chain_notification,
            true_description=(
                "Supply chain notification procedure detected. "
                "Verify it covers informing distributors, deployers, authorised "
                "representative, and importers per Art. 20(1)."
            ),
            false_description=(
                "No supply chain notification procedure detected. "
                "Art. 20(1) requires providers to inform distributors and, where "
                "applicable, deployers, authorised representative, and importers "
                "of non-conformity and corrective actions taken."
            ),
            none_description=(
                "AI could not determine whether a supply chain notification procedure exists. "
                "Art. 20(1) requires informing distributors and other stakeholders."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART20-OBL-2: Risk investigation and authority notification ──
        findings.append(self._finding_from_answer(
            obligation_id="ART20-OBL-2",
            answer=has_risk_investigation_procedure,
            true_description=(
                "Risk investigation procedure detected. "
                "Verify it covers immediate investigation of causes, collaboration "
                "with reporting deployers, and informing market surveillance authorities "
                "and notified bodies per Art. 20(2)."
            ),
            false_description=(
                "No risk investigation procedure detected. "
                "Art. 20(2) requires providers to immediately investigate causes when "
                "a system presents a risk per Art. 79(1), and to inform market surveillance "
                "authorities and the notified body of non-compliance and corrective actions."
            ),
            none_description=(
                "AI could not determine whether a risk investigation procedure exists. "
                "Art. 20(2) requires investigation and authority notification when a system "
                "presents a risk."
            ),
            gap_type=GapType.PROCESS,
        ))

        # Build details dict
        details = {
            "has_corrective_action_procedure": has_corrective_action_procedure,
            "has_supply_chain_notification": has_supply_chain_notification,
            "has_risk_investigation_procedure": has_risk_investigation_procedure,
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
            article_number=20,
            article_title="Corrective actions and duty of information",
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
            article_number=20,
            article_title="Corrective actions and duty of information",
            one_sentence=(
                "Providers of high-risk AI systems must take immediate corrective actions "
                "for non-conforming systems and inform supply chain stakeholders and authorities."
            ),
            official_summary=(
                "Art. 20 requires providers of high-risk AI systems to: (1) immediately take "
                "corrective actions (bring into conformity, withdraw, disable, or recall) when "
                "they consider a system is not in conformity with the Regulation (Art. 20(1)); "
                "(2) inform distributors, deployers, authorised representative, and importers "
                "of non-conformity and actions taken (Art. 20(1)); (3) when a system presents "
                "a risk per Art. 79(1), immediately investigate causes in collaboration with "
                "deployers and inform market surveillance authorities and the notified body "
                "(Art. 20(2))."
            ),
            related_articles={
                "Art. 6": "High-risk classification (prerequisite for Art. 20)",
                "Art. 16": "Provider obligations (Art. 20 is part of provider duties)",
                "Art. 44": "Notified body certificates (must be informed of non-conformity)",
                "Art. 73": "Reporting of serious incidents (related reporting obligations)",
                "Art. 79": "Definition of when a system presents a risk",
            },
            recital=(
                "Recital 97: Where non-compliance is identified, providers should take "
                "corrective actions and inform supply chain stakeholders to ensure timely "
                "resolution of compliance issues."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Corrective action procedure detection",
                    "Supply chain notification procedure detection",
                    "Risk investigation procedure detection",
                ],
                "requires_human_judgment": [
                    "Whether the system is actually non-conforming",
                    "Which corrective action is appropriate (conformity, withdrawal, disable, recall)",
                    "Whether all relevant stakeholders have been identified and informed",
                    "Whether the risk investigation is sufficiently thorough",
                    "Whether market surveillance authorities have been properly informed",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) documented corrective "
                "action procedure covering conformity, withdrawal, disable, and recall options; "
                "(2) supply chain notification procedure for distributors, deployers, and "
                "authorised representatives; (3) risk investigation procedure with authority "
                "notification protocol. "
                "Based on: ISO/IEC 42001:2023 (corrective action controls)."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for AI corrective actions (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_corrective_action_procedure") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 20(1)",
                action="Create a corrective action procedure for non-conforming systems",
                details=(
                    "Art. 20(1) requires immediate corrective actions when non-conformity "
                    "is identified. Create documentation covering:\n"
                    "  - Non-conformity detection and assessment process\n"
                    "  - Decision criteria for corrective action type (conformity, withdrawal, disable, recall)\n"
                    "  - Timeline requirements (immediate action)\n"
                    "  - Responsible persons and escalation chain\n"
                    "  - Documentation and record-keeping of actions taken\n\n"
                    "Consider using docs/corrective-actions.md as the primary document."
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_supply_chain_notification") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 20(1)",
                action="Create supply chain notification procedure",
                details=(
                    "Art. 20(1) requires informing distributors, deployers, authorised "
                    "representative, and importers of non-conformity. Create:\n"
                    "  - Stakeholder contact registry\n"
                    "  - Notification templates for different corrective action types\n"
                    "  - Communication timeline and escalation procedures\n"
                    "  - Record of notifications sent"
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_risk_investigation_procedure") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 20(2)",
                action="Create risk investigation and authority notification procedure",
                details=(
                    "Art. 20(2) requires immediate investigation when a system presents "
                    "a risk per Art. 79(1). Create documentation covering:\n"
                    "  - Risk identification and investigation methodology\n"
                    "  - Collaboration protocol with reporting deployers\n"
                    "  - Market surveillance authority contact information\n"
                    "  - Notified body notification procedure (if applicable)\n"
                    "  - Required content of authority notifications"
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 20(1)-(2)",
            action="Verify corrective action procedures align with AI Act definitions",
            details=(
                "Verify your procedures correctly define non-conformity per the AI Act "
                "and that staff can distinguish between situations requiring conformity "
                "correction, withdrawal, disabling, or recall."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=20,
            article_title="Corrective actions and duty of information",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 20 is a provider obligation for high-risk AI systems. Corrective actions "
                "require operational readiness and supply chain relationships beyond documentation. "
                "Based on ComplianceLint compliance checklist. Official CEN-CENELEC standards "
                "(expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art20Module:
    return Art20Module()
