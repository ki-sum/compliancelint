"""
Article 61: Informed consent to participate in testing in real world conditions — Module implementation.

Art. 61 requires providers conducting real-world testing of Annex III high-risk AI
systems outside regulatory sandboxes to obtain freely-given informed consent from
test subjects, providing them with specific information, and to document consent
properly with copies given to subjects.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art61"). No regex or keyword scanning is performed.

Obligation mapping:
  ART61-OBL-1   → has_informed_consent_procedure (freely-given informed consent with required info elements)
  ART61-OBL-2   → has_consent_documentation (consent dated, documented, copy given to subject)

Scope gate: conducts_real_world_testing — all obligations skip when false.
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


class Art61Module(BaseArticleModule):
    """Article 61: Informed consent to participate in testing in real world conditions compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=61,
            article_title="Informed consent to participate in testing in real world conditions",
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

        answers = ctx.get_article_answers("art61")

        has_informed_consent_procedure = answers.get("has_informed_consent_procedure")
        has_consent_documentation = answers.get("has_consent_documentation")

        # ── ART61-OBL-1: Freely-given informed consent with required information (Art. 61(1)) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART61-OBL-1",
            answer=has_informed_consent_procedure,
            true_description=(
                "Informed consent procedure for real-world testing detected. "
                "Verify it covers all required information elements: "
                "(a) nature and objectives of testing and possible inconvenience, "
                "(b) conditions and expected duration of participation, "
                "(c) rights and guarantees including right to refuse and withdraw, "
                "(d) arrangements for reversal or disregarding of AI predictions, "
                "(e) EU-wide unique testing ID per Art. 60(4)(c) and provider contact details."
            ),
            false_description=(
                "No informed consent procedure for real-world testing detected. "
                "Art. 61(1) requires freely-given informed consent obtained from test subjects "
                "prior to participation, with concise, clear, relevant, and understandable "
                "information covering: nature/objectives, conditions/duration, rights/withdrawal, "
                "reversal arrangements, and testing ID/contact details."
            ),
            none_description=(
                "AI could not determine whether an informed consent procedure for real-world "
                "testing exists. Art. 61(1) requires freely-given informed consent with "
                "comprehensive information disclosure to test subjects."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART61-OBL-2: Consent documentation and copy to subject (Art. 61(2)) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART61-OBL-2",
            answer=has_consent_documentation,
            true_description=(
                "Consent documentation procedure detected. "
                "Verify that consent is dated and documented, and that a copy is given to "
                "the test subject or their legal representative."
            ),
            false_description=(
                "No consent documentation procedure detected. "
                "Art. 61(2) requires that informed consent shall be dated and documented, "
                "and a copy shall be given to the subjects of testing or their legal representative."
            ),
            none_description=(
                "AI could not determine whether consent documentation procedures exist. "
                "Art. 61(2) requires dated and documented consent with copies to subjects."
            ),
            gap_type=GapType.PROCESS,
        ))

        # Build details dict
        details = {
            "has_informed_consent_procedure": has_informed_consent_procedure,
            "has_consent_documentation": has_consent_documentation,
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
            article_number=61,
            article_title="Informed consent to participate in testing in real world conditions",
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
            article_number=61,
            article_title="Informed consent to participate in testing in real world conditions",
            one_sentence=(
                "Providers conducting real-world testing must obtain freely-given informed consent "
                "from test subjects with comprehensive information disclosure."
            ),
            official_summary=(
                "Art. 61 governs informed consent for testing high-risk AI systems in real world "
                "conditions outside regulatory sandboxes. Providers must: (1) obtain freely-given "
                "informed consent from test subjects prior to participation (Art. 61(1)); "
                "(2) provide concise, clear, relevant, and understandable information covering: "
                "(a) nature and objectives of testing and possible inconvenience, "
                "(b) conditions and expected duration, (c) rights including withdrawal, "
                "(d) reversal arrangements for AI predictions, "
                "(e) EU-wide testing ID and provider contact details; "
                "(3) date and document the consent and provide a copy to the subject or their "
                "legal representative (Art. 61(2))."
            ),
            related_articles={
                "Art. 60": "Real-world testing conditions (Art. 61 consent is required by Art. 60(4)(k))",
                "Art. 6": "High-risk classification (prerequisite for Art. 60/61)",
                "Annex III": "High-risk AI system categories (Art. 60 applies to Annex III systems)",
            },
            recital=(
                "Recital 140: Testing in real world conditions outside regulatory sandboxes "
                "should be subject to specific conditions and safeguards to protect the "
                "rights and safety of test subjects, including informed consent."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Informed consent procedure documentation detection",
                    "Consent form template detection",
                    "Consent documentation and record-keeping detection",
                ],
                "requires_human_judgment": [
                    "Whether consent is truly freely given",
                    "Whether information provided is sufficiently clear and understandable",
                    "Whether all five required information elements are adequately covered",
                    "Whether consent documentation is properly dated and stored",
                    "Whether copies are actually given to test subjects",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) informed consent procedure "
                "with documented consent forms, (2) information covering all five Art. 61(1)(a)-(e) "
                "elements, (3) consent dated and documented per Art. 61(2), (4) copy distribution "
                "to test subjects or their legal representatives. "
                "Based on: EU AI Act Art. 61."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard for AI real-world testing (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_informed_consent_procedure") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 61(1)",
                action="Create informed consent procedure for real-world testing",
                details=(
                    "Art. 61(1) requires freely-given informed consent from test subjects.\n"
                    "Create a consent procedure that provides information on:\n"
                    "  (a) Nature and objectives of testing, and possible inconvenience\n"
                    "  (b) Conditions and expected duration of participation\n"
                    "  (c) Rights and guarantees, especially right to refuse and withdraw\n"
                    "      without detriment and without justification\n"
                    "  (d) Arrangements for reversal or disregarding AI predictions\n"
                    "  (e) EU-wide unique testing ID per Art. 60(4)(c) and provider contact details\n\n"
                    "Information must be concise, clear, relevant, and understandable.\n"
                    "Consent must be obtained prior to participation."
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_consent_documentation") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 61(2)",
                action="Implement consent documentation and copy distribution",
                details=(
                    "Art. 61(2) requires:\n"
                    "  - Consent shall be dated and documented\n"
                    "  - A copy shall be given to the test subject or their legal representative\n\n"
                    "Establish a system for:\n"
                    "  1. Recording consent with date stamps\n"
                    "  2. Storing consent records securely\n"
                    "  3. Distributing copies to subjects (physical or digital)"
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 61(1)",
            action="Verify informed consent covers all five required information elements",
            details=(
                "Even if a consent procedure exists, verify it covers all elements of "
                "Art. 61(1)(a)-(e): nature/objectives, conditions/duration, rights/withdrawal, "
                "reversal arrangements, and testing ID/contact details. Ensure the information "
                "is truly concise, clear, relevant, and understandable to subjects."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 61(1)(c)",
            action="Verify withdrawal rights are clearly communicated",
            details=(
                "Art. 61(1)(c) specifically requires informing subjects of their right to "
                "refuse and withdraw from testing at any time without detriment and without "
                "having to provide justification. Verify this is prominently communicated."
            ),
            effort="1-2 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=61,
            article_title="Informed consent to participate in testing in real world conditions",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 61 applies to providers conducting real-world testing of Annex III "
                "high-risk AI systems outside regulatory sandboxes. Testing requires informed "
                "consent from all test subjects. Based on ComplianceLint compliance checklist. "
                "Official CEN-CENELEC standards (expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art61Module:
    return Art61Module()
