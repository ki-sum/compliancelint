"""
Article 17: Quality Management System — Module implementation using unified protocol.

Art. 17 requires providers of high-risk AI systems to establish a documented
quality management system covering 13 aspects (a-m). This is primarily a
documentation/process requirement.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art17"). No regex or keyword scanning is performed here.

Obligation mapping:
  ART17-OBL-1   → has_qms_documentation (QMS exists, documented)
  ART17-OBL-1a  → has_compliance_strategy (regulatory compliance strategy)
  ART17-OBL-1b  → has_design_procedures (design control and verification)
  ART17-OBL-1c  → has_qa_procedures (development QC/QA)
  ART17-OBL-1d  → has_testing_procedures (testing and validation)
  ART17-OBL-1e  → has_technical_specifications (standards and specs)
  ART17-OBL-1f  → has_data_management (data management procedures)
  ART17-OBL-1g  → has_risk_management_in_qms (Art. 9 RMS in QMS)
  ART17-OBL-1h  → has_post_market_monitoring (Art. 72 monitoring)
  ART17-OBL-1i  → handled by gap_findings (manual — incident reporting)
  ART17-OBL-1j  → handled by gap_findings (manual — authority communication)
  ART17-OBL-1k  → has_record_keeping (record-keeping systems)
  ART17-OBL-1l  → handled by gap_findings (manual — resource management)
  ART17-OBL-1m  → has_accountability_framework (RACI/roles)
  ART17-OBL-2   → handled by gap_findings (manual — proportionality)
  ART17-PERM-3  → permission — handled by gap_findings (skipped, no finding)

NOTE — "handled by gap_findings" means:
  ObligationEngine.gap_findings() auto-generates the finding for any obligation
  in the JSON that this scan() has NOT explicitly emitted a Finding for.

  Rules (see obligation_engine.py gap_findings() docstring for full detail):
  - obligation (manual, no scope_limitation) → UNABLE_TO_DETERMINE [COVERAGE GAP]
  - permission (no scope_limitation) → SKIPPED entirely

  Consequence for maintenance:
  Do NOT add a findings.append() here for new obligations added to the JSON.
  gap_findings() will handle them automatically. Only add explicit scan() code
  when you need to map a compliance_answers field to that obligation's level
  (i.e., you want something better than UNABLE_TO_DETERMINE).
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


class Art17Module(BaseArticleModule):
    """Article 17: Quality Management System compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=17,
            article_title="Quality Management System",
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

        answers = ctx.get_article_answers("art17")

        has_qms = answers.get("has_qms_documentation")
        qms_evidence = answers.get("qms_evidence") or []
        has_compliance_strategy = answers.get("has_compliance_strategy")
        has_design_procedures = answers.get("has_design_procedures")
        has_qa_procedures = answers.get("has_qa_procedures")
        has_testing_procedures = answers.get("has_testing_procedures")
        has_technical_specifications = answers.get("has_technical_specifications")
        has_data_management = answers.get("has_data_management")
        has_risk_management_in_qms = answers.get("has_risk_management_in_qms")
        has_post_market_monitoring = answers.get("has_post_market_monitoring")
        has_record_keeping = answers.get("has_record_keeping")
        has_accountability_framework = answers.get("has_accountability_framework")

        doc_evidence = qms_evidence or None

        # ── ART17-OBL-1: QMS exists, documented ──
        findings.append(self._finding_from_answer(
            obligation_id="ART17-OBL-1",
            answer=has_qms,
            true_description=(
                "Quality management system documentation found."
            ),
            false_description=(
                "No quality management system documentation found. Art. 17(1) requires "
                "a documented QMS in the form of written policies, procedures, and instructions."
            ),
            none_description=(
                "AI could not determine whether a quality management system is documented."
            ),
            evidence=doc_evidence,
            gap_type=GapType.PROCESS,
        ))

        # ── ART17-OBL-1a: Regulatory compliance strategy ──
        findings.append(self._finding_from_answer(
            obligation_id="ART17-OBL-1a",
            answer=has_compliance_strategy,
            true_description=(
                "Regulatory compliance strategy documentation found. Verify it covers "
                "conformity assessment procedures and modification management per Art. 17(1)(a)."
            ),
            false_description=(
                "No regulatory compliance strategy found. Art. 17(1)(a) requires a strategy "
                "for regulatory compliance including conformity assessment and modification management."
            ),
            none_description=(
                "AI could not determine whether a regulatory compliance strategy exists."
            ),
            evidence=doc_evidence,
            gap_type=GapType.PROCESS,
        ))

        # ── ART17-OBL-1b: Design procedures ──
        findings.append(self._finding_from_answer(
            obligation_id="ART17-OBL-1b",
            answer=has_design_procedures,
            true_description=(
                "Design control and verification procedures found. Verify they include "
                "systematic techniques for design, design control, and design verification "
                "per Art. 17(1)(b)."
            ),
            false_description=(
                "No design control procedures found. Art. 17(1)(b) requires techniques, "
                "procedures, and systematic actions for design, design control, and verification."
            ),
            none_description=(
                "AI could not determine whether design control procedures exist."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART17-OBL-1c: Development QC/QA procedures ──
        findings.append(self._finding_from_answer(
            obligation_id="ART17-OBL-1c",
            answer=has_qa_procedures,
            true_description=(
                "Development quality control and assurance procedures found. Verify they "
                "cover the full development lifecycle per Art. 17(1)(c)."
            ),
            false_description=(
                "No development QC/QA procedures found. Art. 17(1)(c) requires techniques, "
                "procedures, and systematic actions for development, quality control, and "
                "quality assurance."
            ),
            none_description=(
                "AI could not determine whether development QC/QA procedures exist."
            ),
            gap_type=GapType.CODE,
        ))

        # ── ART17-OBL-1d: Testing and validation procedures ──
        findings.append(self._finding_from_answer(
            obligation_id="ART17-OBL-1d",
            answer=has_testing_procedures,
            true_description=(
                "Testing and validation procedures found. Verify they cover before, during, "
                "and after development with defined frequency per Art. 17(1)(d)."
            ),
            false_description=(
                "No testing and validation procedures found. Art. 17(1)(d) requires "
                "examination, test, and validation procedures with defined frequency."
            ),
            none_description=(
                "AI could not determine whether testing and validation procedures exist."
            ),
            gap_type=GapType.CODE,
        ))

        # ── ART17-OBL-1e: Technical specifications and standards ──
        findings.append(self._finding_from_answer(
            obligation_id="ART17-OBL-1e",
            answer=has_technical_specifications,
            true_description=(
                "Technical specifications and standards documentation found. Verify all "
                "applicable harmonised standards are identified per Art. 17(1)(e)."
            ),
            false_description=(
                "No technical specifications documentation found. Art. 17(1)(e) requires "
                "documentation of applicable standards and specifications."
            ),
            none_description=(
                "AI could not determine whether technical specifications are documented."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART17-OBL-1f: Data management procedures ──
        findings.append(self._finding_from_answer(
            obligation_id="ART17-OBL-1f",
            answer=has_data_management,
            true_description=(
                "Data management procedures found. Verify they cover the full data lifecycle "
                "(acquisition, collection, analysis, labelling, storage, filtration, mining, "
                "aggregation, retention) per Art. 17(1)(f)."
            ),
            false_description=(
                "No data management procedures found. Art. 17(1)(f) requires comprehensive "
                "data management covering acquisition through retention."
            ),
            none_description=(
                "AI could not determine whether data management procedures exist."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART17-OBL-1g: Risk management in QMS ──
        findings.append(self._finding_from_answer(
            obligation_id="ART17-OBL-1g",
            answer=has_risk_management_in_qms,
            true_description=(
                "Risk management system referenced in QMS. Verify it integrates the "
                "Art. 9 risk management system per Art. 17(1)(g)."
            ),
            false_description=(
                "No risk management system referenced in QMS. Art. 17(1)(g) requires "
                "inclusion of the Art. 9 risk management system."
            ),
            none_description=(
                "AI could not determine whether risk management is integrated into QMS."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART17-OBL-1h: Post-market monitoring ──
        findings.append(self._finding_from_answer(
            obligation_id="ART17-OBL-1h",
            answer=has_post_market_monitoring,
            true_description=(
                "Post-market monitoring system found in QMS. Verify it meets "
                "Art. 72 requirements per Art. 17(1)(h)."
            ),
            false_description=(
                "No post-market monitoring system found in QMS. Art. 17(1)(h) requires "
                "a post-market monitoring system per Art. 72."
            ),
            none_description=(
                "AI could not determine whether post-market monitoring is in the QMS."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART17-OBL-1k: Record-keeping systems ──
        findings.append(self._finding_from_answer(
            obligation_id="ART17-OBL-1k",
            answer=has_record_keeping,
            true_description=(
                "Record-keeping systems found. Verify they cover all relevant "
                "documentation and information per Art. 17(1)(k)."
            ),
            false_description=(
                "No record-keeping systems found. Art. 17(1)(k) requires systems and "
                "procedures for record-keeping of all relevant documentation."
            ),
            none_description=(
                "AI could not determine whether record-keeping systems exist."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART17-OBL-1m: Accountability framework ──
        findings.append(self._finding_from_answer(
            obligation_id="ART17-OBL-1m",
            answer=has_accountability_framework,
            true_description=(
                "Accountability framework found. Verify it defines responsibilities "
                "for management and staff across all QMS aspects per Art. 17(1)(m)."
            ),
            false_description=(
                "No accountability framework found. Art. 17(1)(m) requires a framework "
                "setting out management and staff responsibilities for all QMS aspects."
            ),
            none_description=(
                "AI could not determine whether an accountability framework exists."
            ),
            gap_type=GapType.PROCESS,
        ))

        # Build details dict
        details = {
            "has_qms_documentation": has_qms,
            "has_compliance_strategy": has_compliance_strategy,
            "has_design_procedures": has_design_procedures,
            "has_qa_procedures": has_qa_procedures,
            "has_testing_procedures": has_testing_procedures,
            "has_technical_specifications": has_technical_specifications,
            "has_data_management": has_data_management,
            "has_risk_management_in_qms": has_risk_management_in_qms,
            "has_post_market_monitoring": has_post_market_monitoring,
            "has_record_keeping": has_record_keeping,
            "has_accountability_framework": has_accountability_framework,
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
            article_number=17,
            article_title="Quality Management System",
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
            article_number=17,
            article_title="Quality Management System",
            one_sentence=(
                "High-risk AI system providers must establish a documented quality management "
                "system covering 13 aspects from compliance strategy to accountability."
            ),
            official_summary=(
                "Art. 17 requires providers of high-risk AI systems to put in place a quality "
                "management system documented as written policies, procedures, and instructions. "
                "It must cover: (a) regulatory compliance strategy, (b) design procedures, "
                "(c) development QC/QA, (d) testing and validation, (e) technical specifications, "
                "(f) data management, (g) risk management (Art. 9), (h) post-market monitoring "
                "(Art. 72), (i) incident reporting (Art. 73), (j) authority communication, "
                "(k) record-keeping, (l) resource management, and (m) accountability framework. "
                "Implementation must be proportionate to organisation size."
            ),
            related_articles={
                "Art. 9": "Risk management system (must be included in QMS)",
                "Art. 72": "Post-market monitoring (must be included in QMS)",
                "Art. 73": "Serious incident reporting (must be included in QMS)",
            },
            recital=(
                "Recital 76: Quality management is central to ensuring that high-risk AI systems "
                "comply with the requirements throughout their lifecycle."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of QMS documentation",
                    "Detection of design and QA procedures",
                    "Detection of testing infrastructure",
                    "Detection of data management documentation",
                    "Detection of accountability framework",
                ],
                "requires_human_judgment": [
                    "QMS adequacy and completeness",
                    "Incident reporting procedures (Art. 73)",
                    "Authority communication procedures",
                    "Resource management adequacy",
                    "Proportionality assessment",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) documented QMS with "
                "quality policy and procedures, (2) development QA with CI/CD and testing, "
                "(3) comprehensive data management procedures, (4) accountability framework "
                "with RACI matrix or equivalent. "
                "Based on: ISO 9001:2015, ISO/IEC 42001:2023."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_qms_documentation") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 17(1)",
                action="Create a documented quality management system",
                details=(
                    "Art. 17(1) requires a QMS documented as written policies, procedures, "
                    "and instructions. Create a quality manual or equivalent covering all "
                    "13 aspects listed in Art. 17(1)(a)-(m). Consider using ISO 9001:2015 "
                    "or ISO/IEC 42001:2023 as a framework."
                ),
                effort="16-40 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_qa_procedures") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 17(1)(c)-(d)",
                action="Establish development QA and testing procedures",
                details=(
                    "Art. 17(1)(c)(d) requires QC/QA and testing procedures. Set up CI/CD "
                    "pipelines, code review processes, test suites with defined pass/fail "
                    "criteria, and validation protocols with frequency schedules."
                ),
                effort="8-16 hours",
            ))

        if details.get("has_data_management") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 17(1)(f)",
                action="Document data management procedures",
                details=(
                    "Art. 17(1)(f) requires comprehensive data management covering "
                    "acquisition, collection, analysis, labelling, storage, filtration, "
                    "mining, aggregation, and retention. Create data management documentation."
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_accountability_framework") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 17(1)(m)",
                action="Create accountability framework",
                details=(
                    "Art. 17(1)(m) requires an accountability framework with roles and "
                    "responsibilities. Create a RACI matrix or equivalent document covering "
                    "all 13 QMS aspects."
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        # Always add human judgment items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 17(1)(i)",
            action="Establish serious incident reporting procedures",
            details=(
                "Art. 17(1)(i) requires procedures for reporting serious incidents per Art. 73. "
                "Define incident classification, reporting channels, and timelines."
            ),
            effort="4-8 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 17(2)",
            action="Assess proportionality of QMS to organisation size",
            details=(
                "Art. 17(2) requires QMS implementation to be proportionate to the provider's "
                "organisation size while ensuring compliance. Document the proportionality rationale."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=17,
            article_title="Quality Management System",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 17 is primarily a documentation and process requirement. Automated "
                "scanning can detect presence of artifacts but cannot assess quality or "
                "completeness. Human expert review is essential."
            ),
        )


def create_module() -> Art17Module:
    return Art17Module()
