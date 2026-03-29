"""
Article 10: Data and Data Governance — Module implementation using unified protocol.

Art. 10 requires training, validation, and testing datasets for high-risk AI systems
to be subject to appropriate data governance practices, including bias examination,
representativeness, and data quality assessment.

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art10"). No regex or keyword scanning is performed here.

Obligation mapping:
  ART10-OBL-1   → has_data_governance_doc (quality criteria)
  ART10-OBL-2   → has_data_governance_doc (governance practices a-e)
  ART10-OBL-2f  → has_bias_mitigation (bias examination)
  ART10-OBL-2g  → has_bias_mitigation (bias detection/prevention/mitigation measures)
  ART10-OBL-2h  → UNABLE_TO_DETERMINE always (data gap identification — manual)
  ART10-OBL-3   → UNABLE_TO_DETERMINE always (data quality — manual)
  ART10-OBL-3b  → UNABLE_TO_DETERMINE always (statistical properties — manual)
  ART10-OBL-4   → UNABLE_TO_DETERMINE always (deployment context — manual)
  ART10-PERM-5  → permission — handled by gap_findings
  ART10-OBL-6   → scope rule — handled by gap_findings
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


class Art10Module(BaseArticleModule):
    """Article 10: Data and Data Governance compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=10,
            article_title="Data and Data Governance",
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

        answers = ctx.get_article_answers("art10")

        has_data_doc = answers.get("has_data_governance_doc")
        data_doc_paths = answers.get("data_doc_paths") or []
        has_bias = answers.get("has_bias_mitigation")
        if has_bias is None:
            has_bias = answers.get("has_bias_detection")  # alias
        bias_evidence = answers.get("bias_evidence") or []
        has_lineage = answers.get("has_data_lineage")
        if has_lineage is None:
            has_lineage = answers.get("has_data_versioning")  # alias

        doc_evidence = data_doc_paths or None
        bias_ev = bias_evidence or None

        # ── ART10-OBL-1: Data quality criteria ──
        findings.append(self._finding_from_answer(
            obligation_id="ART10-OBL-1",
            answer=has_data_doc,
            true_description=(
                f"Data governance documentation found: {', '.join(data_doc_paths)}."
                if data_doc_paths
                else "Data governance documentation found."
            ),
            false_description=(
                "No data governance documentation found. Art. 10(1) requires "
                "training, validation and testing data sets to meet quality criteria."
            ),
            none_description=(
                "AI could not determine whether data governance documentation exists."
            ),
            evidence=doc_evidence,
        ))

        # ── ART10-OBL-2: Data governance practices (a-e) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART10-OBL-2",
            answer=has_data_doc,
            true_description=(
                "Data governance documentation found. Verify it covers all Art. 10(2) "
                "requirements: (a) design choices, (b) data collection/origin, "
                "(c) data preparation, (d) assumptions, (e) availability/suitability assessment."
            ),
            false_description=(
                "No data governance documentation found. Art. 10(2) requires data governance "
                "and management practices covering design choices, collection processes, "
                "preparation operations, assumptions, and availability assessment."
            ),
            none_description=(
                "AI could not determine whether data governance practices are documented."
            ),
            evidence=doc_evidence,
        ))

        # ── ART10-OBL-2f: Bias examination ──
        findings.append(self._finding_from_answer(
            obligation_id="ART10-OBL-2f",
            answer=has_bias,
            true_description=(
                f"Bias examination evidence found: {', '.join(bias_evidence)}."
                if bias_evidence
                else "Bias examination evidence found."
            ),
            false_description=(
                "No bias examination detected. Art. 10(2)(f) requires examination "
                "of possible biases affecting health, safety, fundamental rights, "
                "or leading to prohibited discrimination."
            ),
            none_description=(
                "AI could not determine whether bias examination has been performed."
            ),
            evidence=bias_ev,
        ))

        # ── ART10-OBL-2g: Bias mitigation measures ──
        findings.append(self._finding_from_answer(
            obligation_id="ART10-OBL-2g",
            answer=has_bias,
            true_description=(
                "Bias mitigation measures found. Art. 10(2)(g) requires measures to "
                "detect, prevent and mitigate biases identified in (f)."
            ),
            false_description=(
                "No bias mitigation measures detected. Art. 10(2)(g) requires "
                "appropriate measures to detect, prevent and mitigate possible biases."
            ),
            none_description=(
                "AI could not determine whether bias mitigation measures exist."
            ),
            evidence=bias_ev,
        ))

        # ── ART10-OBL-2h: Data gap identification (always manual) ──
        findings.append(Finding(
            obligation_id="ART10-OBL-2h",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Data gap identification requires human review. Art. 10(2)(h) requires "
                "identification of relevant data gaps or shortcomings that prevent "
                "compliance, and how they can be addressed."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART10-OBL-3: Data quality (representativeness, errors, completeness) ──
        findings.append(Finding(
            obligation_id="ART10-OBL-3",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Data quality assessment requires human review. Art. 10(3) requires "
                "data sets to be relevant, sufficiently representative, and to the best "
                "extent possible free of errors and complete."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART10-OBL-3b: Statistical properties ──
        findings.append(Finding(
            obligation_id="ART10-OBL-3b",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Statistical properties assessment requires human review. Art. 10(3) "
                "requires appropriate statistical properties, including as regards the "
                "persons or groups the system is intended to be used on."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART10-OBL-4: Deployment context (always manual) ──
        findings.append(Finding(
            obligation_id="ART10-OBL-4",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Deployment context assessment requires human review. Art. 10(4) requires "
                "data to account for geographical, contextual, behavioural and functional "
                "setting particularities."
            ),
            gap_type=GapType.PROCESS,
        ))

        details = {
            "has_data_governance_doc": has_data_doc,
            "data_doc_paths": data_doc_paths,
            "has_bias_mitigation": has_bias,
            "bias_evidence": bias_evidence,
            "has_data_lineage": has_lineage,
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
            article_number=10,
            article_title="Data and Data Governance",
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
            article_number=10,
            article_title="Data and Data Governance",
            one_sentence=(
                "High-risk AI systems must use training, validation and testing data "
                "that meets quality criteria with documented governance practices."
            ),
            official_summary=(
                "Art. 10 requires data governance covering design choices, collection "
                "processes, preparation operations, assumptions, and availability. Data must "
                "be examined for biases with appropriate mitigation. Datasets must be relevant, "
                "representative, error-free (best effort), and complete. Special category "
                "personal data may be processed for bias detection under strict conditions."
            ),
            related_articles={
                "Art. 9": "Risk management (data risks feed into risk assessment)",
                "Art. 15": "Accuracy (data quality directly affects accuracy)",
                "Art. 71": "AI regulatory sandboxes (may allow controlled data testing)",
                "GDPR": "Art. 10(5) references Regulation (EU) 2016/679",
            },
            recital=(
                "Recital 67: Data governance is critical for ensuring AI system quality. "
                "Training data must be representative and bias-free to the extent possible."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of data governance documentation",
                    "Detection of bias detection/mitigation tooling",
                    "Detection of data pipeline code",
                    "Detection of data versioning systems",
                ],
                "requires_human_judgment": [
                    "Data quality assessment (relevance, representativeness, completeness)",
                    "Statistical property adequacy",
                    "Deployment context coverage",
                    "Data gap identification",
                    "Bias examination thoroughness",
                    "Special category data processing necessity",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) documented data governance "
                "practices covering Art. 10(2)(a-h), (2) bias examination and mitigation evidence, "
                "(3) data quality documentation, (4) deployment context analysis. "
                "Based on: ISO/IEC 5259 series, ISO/IEC TR 24027:2021."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_data_governance_doc") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 10(1)-(2)",
                action="Create data governance documentation",
                details=(
                    "Art. 10(2) requires documented data governance practices covering: "
                    "(a) design choices, (b) data collection and origin, "
                    "(c) data preparation operations, (d) assumptions, "
                    "(e) availability assessment. Create a data_governance.md or datasheet."
                ),
                effort="8-16 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_bias_mitigation") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 10(2)(f)(g)",
                action="Implement bias examination and mitigation",
                details=(
                    "Art. 10(2)(f) requires examination of biases affecting health, safety, "
                    "and fundamental rights. Art. 10(2)(g) requires measures to detect, "
                    "prevent and mitigate biases. Consider: fairlearn, aif360, or manual "
                    "demographic analysis of training data."
                ),
                effort="4-16 hours",
            ))

        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 10(3)",
            action="Document data quality assessment",
            details=(
                "Art. 10(3) requires data to be relevant, representative, error-free "
                "(best effort), and complete. Document your data quality analysis "
                "including statistical properties and demographic representation."
            ),
            effort="4-8 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 10(4)",
            action="Document deployment context coverage",
            details=(
                "Art. 10(4) requires data to account for geographical, contextual, "
                "behavioural and functional setting particularities. Document how "
                "your data covers the intended deployment context."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=10,
            article_title="Data and Data Governance",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 10 is primarily a data quality and documentation requirement. "
                "Automated scanning detects tooling and documentation presence but "
                "cannot assess data quality. Human expert review is essential."
            ),
        )


def create_module() -> Art10Module:
    return Art10Module()
