"""
Article 18: Documentation keeping — Module implementation using unified protocol.

Art. 18 requires providers of high-risk AI systems to keep specified documentation
at the disposal of national competent authorities for 10 years after market
placement or service start.

This module reads AI-provided compliance_answers["art18"] and maps each answer
to a Finding. No regex, keyword, or detector.py scanning is performed —
detection is entirely the AI's responsibility.

Obligation mapping:
  ART18-OBL-1  → has_documentation_retention_policy (10-year documentation retention)
  ART18-OBL-3  → context_skip_field: is_financial_institution (gap_findings handles this)
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


class Art18Module(BaseArticleModule):
    """Article 18: Documentation keeping compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=18,
            article_title="Documentation keeping",
        )

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for documentation keeping compliance using AI-provided answers.

        Reads compliance_answers["art18"] from the AI context. Maps each field
        to obligation findings without any regex or file scanning.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for each documentation keeping obligation.
        """
        project_path = os.path.abspath(project_path)
        ctx = self._effective_ctx(project_path)
        na = self._scope_gate(ctx, project_path)
        if na:
            return na

        # Art. 18 applies only to high-risk AI systems.
        risk = (ctx.risk_classification or "").lower().strip()
        conf = (ctx.risk_classification_confidence or "").lower().strip()
        if risk in self._NOT_HIGH_RISK_VALUES and conf in ("high", "medium"):
            return self._not_applicable_result(
                project_path,
                ctx.primary_language or "unknown",
                "ART18",
                legal_basis="Art. 6",
                reason=(
                    "Art. 18 obligations apply only to providers of high-risk AI systems "
                    "(as classified under Art. 6). This system has been classified as "
                    f"'{ctx.risk_classification}' with {conf} confidence."
                ),
            )

        index = self._build_index(project_path)
        language = self._detect_language(project_path)
        file_count = index.source_file_count
        findings: list[Finding] = self._ctx_warnings(ctx)

        answers = ctx.get_article_answers("art18")

        has_documentation_retention_policy = answers.get("has_documentation_retention_policy")
        retention_evidence = answers.get("retention_policy_evidence", "")

        # ── ART18-OBL-1: Documentation retention for 10 years ──
        findings.append(self._finding_from_answer(
            obligation_id="ART18-OBL-1",
            answer=has_documentation_retention_policy,
            true_description=(
                "Documentation retention policy detected. "
                "Verify it covers all required documents (technical documentation per Art. 11, "
                "QMS documentation per Art. 17, notified body decisions where applicable, "
                "and EU declaration of conformity per Art. 47) and ensures retention for "
                "10 years after market placement or service start."
                + (f" Evidence: {retention_evidence}" if retention_evidence else "")
            ),
            false_description=(
                "No documentation retention policy detected. Art. 18(1) requires the provider "
                "to keep technical documentation (Art. 11), QMS documentation (Art. 17), "
                "notified body documentation where applicable, and the EU declaration of "
                "conformity (Art. 47) at the disposal of national competent authorities for "
                "10 years after the system has been placed on the market or put into service."
            ),
            none_description=(
                "AI could not determine whether a documentation retention policy is in place. "
                "Art. 18(1) requires keeping specified documentation for 10 years. "
                "Review project documentation for retention policies, archival configurations, "
                "or compliance documentation directories."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ART18-OBL-3 (financial institution documentation integration) is handled
        # by the obligation engine's gap_findings via context_skip_field "is_financial_institution".
        # When is_financial_institution=false -> NOT_APPLICABLE.
        # When is_financial_institution=true -> gap finding (manual verification needed).
        # When not provided -> CONDITIONAL (ask user).

        # Build details dict
        details = {
            "has_documentation_retention_policy": has_documentation_retention_policy,
            "retention_policy_evidence": retention_evidence,
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
            article_number=18,
            article_title="Documentation keeping",
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
            article_number=18,
            article_title="Documentation keeping",
            one_sentence=(
                "Providers of high-risk AI systems must retain specified documentation "
                "for 10 years and make it available to national competent authorities."
            ),
            official_summary=(
                "Art. 18 requires providers of high-risk AI systems to keep at the disposal "
                "of national competent authorities, for a period of 10 years after market "
                "placement or service start: (a) technical documentation per Art. 11, "
                "(b) QMS documentation per Art. 17, (c) changes approved by notified bodies "
                "where applicable, (d) decisions and other documents issued by notified bodies "
                "where applicable, and (e) the EU declaration of conformity per Art. 47. "
                "Financial institutions must integrate AI technical documentation into their "
                "existing financial services law documentation."
            ),
            related_articles={
                "Art. 11": "Technical documentation to be retained",
                "Art. 17": "Quality management system documentation to be retained",
                "Art. 47": "EU declaration of conformity to be retained",
                "Art. 16(d)": "Provider obligation to keep Art. 18 documentation",
            },
            recital=(
                "Recital 74: Documentation requirements ensure traceability and allow "
                "national competent authorities to verify compliance with this Regulation."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Documentation retention policy detection",
                    "Archival configuration detection",
                    "Compliance documentation directory detection",
                ],
                "requires_human_judgment": [
                    "Verification of 10-year retention period adequacy",
                    "Verification of all required document types being retained",
                    "Financial institution documentation integration assessment",
                    "Notified body documentation retention verification",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) documented retention "
                "policy specifying 10-year minimum, (2) coverage of all five document categories "
                "(technical docs, QMS docs, notified body changes, notified body decisions, "
                "EU declaration), (3) availability mechanism for national competent authorities. "
                "Financial institutions must additionally integrate AI docs into financial "
                "services law documentation. "
                "Based on: ISO/IEC 42001:2023 (documentation controls)."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_documentation_retention_policy") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 18(1)",
                action="Establish a documentation retention policy for 10 years",
                details=(
                    "Art. 18(1) requires keeping documentation at the disposal of national "
                    "competent authorities for 10 years after the high-risk AI system has been "
                    "placed on the market or put into service. Create a retention policy covering:\n"
                    "  (a) Technical documentation (Art. 11)\n"
                    "  (b) QMS documentation (Art. 17)\n"
                    "  (c) Changes approved by notified bodies (where applicable)\n"
                    "  (d) Decisions and documents from notified bodies (where applicable)\n"
                    "  (e) EU declaration of conformity (Art. 47)\n"
                    "\n"
                    "Recommended: create a docs/retention-policy.md specifying:\n"
                    "  - What documents are retained\n"
                    "  - Where they are stored (e.g., version-controlled repository, archive)\n"
                    "  - Retention period (10 years from market placement)\n"
                    "  - Access procedure for national competent authorities"
                ),
                effort="4-8 hours",
            ))
        elif details.get("has_documentation_retention_policy") is None:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 18(1)",
                action="Review and document retention policy for compliance documentation",
                details=(
                    "AI could not determine whether a documentation retention policy exists. "
                    "Review project documentation for existing retention policies and ensure "
                    "they cover the 10-year requirement per Art. 18(1)."
                ),
                effort="2-4 hours",
                action_type="human_judgment_required",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 18(1)",
            action="Verify all five document categories are covered by retention policy",
            details=(
                "Art. 18(1) requires retention of five specific document categories. "
                "Verify each is addressed: (a) technical documentation per Art. 11, "
                "(b) QMS documentation per Art. 17, (c) notified body approved changes, "
                "(d) notified body decisions/documents, (e) EU declaration of conformity per Art. 47."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="LOW",
            article="Art. 18(3)",
            action="Check if financial services documentation integration applies",
            details=(
                "If the provider is a financial institution subject to Union financial services "
                "law, Art. 18(3) requires maintaining AI technical documentation as part of "
                "the documentation kept under relevant financial services law."
            ),
            effort="1 hour",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=18,
            article_title="Documentation keeping",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Based on ComplianceLint compliance checklist. Official CEN-CENELEC "
                "standards (expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art18Module:
    return Art18Module()
