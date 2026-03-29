"""
Article 11: Technical Documentation — Module implementation using unified protocol.

Art. 11 requires providers of high-risk AI systems to draw up technical
documentation before placing on market. Documentation must demonstrate
compliance, be clear and comprehensive, and contain Annex IV elements.

Obligation mapping:
  ART11-OBL-1   → has_technical_docs (drawn up + kept up-to-date)
  ART11-OBL-1b  → has_technical_docs (demonstrates compliance, clear + comprehensive)
  ART11-OBL-1c  → UNABLE_TO_DETERMINE always (Annex IV coverage — manual)
  ART11-OBL-2   → conditional (Annex I product) — handled by gap_findings
  ART11-EMP-3   → empowerment — handled by gap_findings
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


class Art11Module(BaseArticleModule):
    """Article 11: Technical Documentation compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=11,
            article_title="Technical Documentation",
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

        answers = ctx.get_article_answers("art11")

        has_tech_docs = answers.get("has_technical_docs")
        if has_tech_docs is None:
            has_tech_docs = answers.get("has_documentation")  # alias
        doc_paths = answers.get("doc_paths") or []
        documented_aspects = answers.get("documented_aspects") or []

        doc_evidence = doc_paths or None

        # ── ART11-OBL-1: Technical documentation drawn up + kept up-to-date ──
        findings.append(self._finding_from_answer(
            obligation_id="ART11-OBL-1",
            answer=has_tech_docs,
            true_description=(
                f"Technical documentation found: {', '.join(doc_paths)}."
                if doc_paths
                else "Technical documentation found."
            ),
            false_description=(
                "No technical documentation found. Art. 11(1) requires technical "
                "documentation to be drawn up before placing on market and kept up-to-date."
            ),
            none_description=(
                "AI could not determine whether technical documentation exists."
            ),
            evidence=doc_evidence,
            gap_type=GapType.PROCESS,
        ))

        # ── ART11-OBL-1b: Demonstrates compliance, clear + comprehensive ──
        findings.append(self._finding_from_answer(
            obligation_id="ART11-OBL-1b",
            answer=has_tech_docs,
            true_description=(
                "Technical documentation found. Verify it demonstrates compliance "
                "with Section requirements and provides clear, comprehensive information "
                "for authority assessment per Art. 11(1)."
            ),
            false_description=(
                "No technical documentation found. Art. 11(1) requires documentation "
                "that demonstrates compliance and provides information in a clear and "
                "comprehensive form for authority assessment."
            ),
            none_description=(
                "AI could not determine whether documentation demonstrates compliance."
            ),
            evidence=doc_evidence,
            gap_type=GapType.PROCESS,
        ))

        # ── ART11-OBL-1c: Annex IV elements (always manual) ──
        findings.append(Finding(
            obligation_id="ART11-OBL-1c",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Annex IV coverage requires human review. Art. 11(1) requires "
                "documentation to contain, at a minimum, the elements set out in "
                "Annex IV (general description, detailed design, monitoring, testing, "
                "risk management, changes, standards, EU declaration)."
            ),
            gap_type=GapType.PROCESS,
        ))

        details = {
            "has_technical_docs": has_tech_docs,
            "doc_paths": doc_paths,
            "documented_aspects": documented_aspects,
        }

        # ── Obligation Engine ──
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
            article_number=11,
            article_title="Technical Documentation",
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
            article_number=11,
            article_title="Technical Documentation",
            one_sentence=(
                "High-risk AI systems must have technical documentation drawn up before "
                "market placement, containing at minimum the elements of Annex IV."
            ),
            official_summary=(
                "Art. 11 requires providers to create and maintain technical documentation "
                "that demonstrates compliance with all Section requirements. The documentation "
                "must be clear and comprehensive, enabling authorities to assess compliance. "
                "It must contain at minimum all Annex IV elements (general description, "
                "design, development process, monitoring, testing, risk management)."
            ),
            related_articles={
                "Annex IV": "Technical documentation content requirements",
                "Art. 9": "Risk management (must be documented)",
                "Art. 10": "Data governance (must be documented)",
                "Art. 43": "Conformity assessment (uses technical documentation)",
            },
            recital=(
                "Recital 68: Technical documentation is essential for traceability "
                "and for enabling competent authorities to assess compliance."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of documentation files (README, docs/, model cards)",
                    "Detection of architecture documentation",
                    "Detection of version tracking (CHANGELOG)",
                ],
                "requires_human_judgment": [
                    "Annex IV coverage completeness",
                    "Documentation clarity and comprehensiveness",
                    "Whether documentation enables authority assessment",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) README with substantive "
                "content, (2) architecture documentation, (3) model card or equivalent, "
                "(4) testing documentation, (5) Annex IV elements coverage. "
                "Based on: ISO/IEC 42001:2023."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_technical_docs") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 11(1)",
                action="Create technical documentation",
                details=(
                    "Art. 11(1) requires technical documentation before market placement. "
                    "Create: (1) README.md with system description, (2) architecture docs, "
                    "(3) model card, (4) testing documentation. Must cover all Annex IV elements."
                ),
                effort="16-40 hours",
                action_type="human_judgment_required",
            ))

        actions.append(ActionItem(
            priority="HIGH",
            article="Art. 11(1), Annex IV",
            action="Verify Annex IV coverage",
            details=(
                "Art. 11(1) requires documentation to contain at minimum all Annex IV "
                "elements: (1) general description, (2) detailed design + development, "
                "(3) monitoring system, (4) testing/validation, (5) risk management, "
                "(6) changes log, (7) standards applied, (8) EU declaration of conformity."
            ),
            effort="4-8 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=11,
            article_title="Technical Documentation",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 11 is primarily a documentation requirement. Automated scanning "
                "detects documentation presence but cannot assess Annex IV coverage "
                "or documentation quality. Human expert review is essential."
            ),
        )


def create_module() -> Art11Module:
    return Art11Module()
