"""
Article 14: Human Oversight — Module implementation.

Art. 14 requires high-risk AI systems to be designed for effective human
oversight, with measures proportionate to risks. Deployers must be enabled
to understand, monitor, override, and interrupt the system.

Obligation mapping:
  ART14-OBL-1  -> has_human_oversight (designed for oversight)
  ART14-OBL-2  -> UNABLE_TO_DETERMINE always (risk prevention aim - manual)
  ART14-OBL-3  -> has_override_mechanism (commensurate measures)
  ART14-OBL-4  -> has_human_oversight (deployer enablement a-e)
  ART14-OBL-5  -> conditional (biometric dual verification) - gap_findings
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


class Art14Module(BaseArticleModule):
    """Article 14: Human Oversight compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=14,
            article_title="Human Oversight",
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

        answers = ctx.get_article_answers("art14")

        has_oversight = answers.get("has_human_oversight")
        if has_oversight is None:
            has_oversight = answers.get("has_hitl")  # alias
        oversight_evidence = answers.get("oversight_evidence") or []
        has_override = answers.get("has_override_mechanism")
        if has_override is None:
            has_override = answers.get("has_kill_switch")  # alias
        override_evidence = answers.get("override_evidence") or []

        ov_evidence = oversight_evidence or None
        or_evidence = override_evidence or None

        # -- ART14-OBL-1: Designed for effective human oversight --
        findings.append(self._finding_from_answer(
            obligation_id="ART14-OBL-1",
            answer=has_oversight,
            true_description=(
                f"Human oversight mechanisms found: {', '.join(oversight_evidence)}."
                if oversight_evidence
                else "Human oversight mechanisms found."
            ),
            false_description=(
                "No human oversight mechanisms detected. Art. 14(1) requires systems "
                "to be designed for effective oversight by natural persons."
            ),
            none_description=(
                "AI could not determine whether human oversight mechanisms exist."
            ),
            evidence=ov_evidence,
            gap_type=GapType.CODE,
        ))

        # -- ART14-OBL-2: Oversight aims to prevent risks (always manual) --
        findings.append(Finding(
            obligation_id="ART14-OBL-2",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=(
                "Risk prevention effectiveness of human oversight requires human review. "
                "Art. 14(2) requires oversight to prevent or minimise risks to health, "
                "safety, or fundamental rights from intended use and foreseeable misuse."
            ),
            gap_type=GapType.PROCESS,
        ))

        # -- ART14-OBL-3: Oversight measures commensurate with risks --
        findings.append(self._finding_from_answer(
            obligation_id="ART14-OBL-3",
            answer=has_override,
            true_description=(
                f"Override/control mechanisms found: {', '.join(override_evidence)}."
                if override_evidence
                else "Override/control mechanisms found."
            ),
            false_description=(
                "No override or control mechanisms detected. Art. 14(3) requires "
                "oversight measures commensurate with risks, built into the system "
                "or provided for deployer implementation."
            ),
            none_description=(
                "AI could not determine whether override mechanisms exist."
            ),
            evidence=or_evidence,
            gap_type=GapType.CODE,
        ))

        # -- ART14-OBL-4: Deployer enablement (a)-(e) --
        findings.append(self._finding_from_answer(
            obligation_id="ART14-OBL-4",
            answer=has_oversight,
            true_description=(
                "Human oversight infrastructure found. Verify deployers are enabled to: "
                "(a) understand capabilities/limitations, (b) be aware of automation bias, "
                "(c) interpret output, (d) override/reverse output, (e) interrupt system."
            ),
            false_description=(
                "No human oversight infrastructure detected. Art. 14(4) requires "
                "deployers to be enabled to understand, monitor, interpret, override, "
                "and interrupt the system."
            ),
            none_description=(
                "AI could not determine whether deployer oversight enablement exists."
            ),
            evidence=ov_evidence,
            gap_type=GapType.PROCESS,
        ))

        details = {
            "has_human_oversight": has_oversight,
            "oversight_evidence": oversight_evidence,
            "has_override_mechanism": has_override,
            "override_evidence": override_evidence,
        }

        # -- Obligation Engine --
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
            article_number=14,
            article_title="Human Oversight",
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
            article_number=14,
            article_title="Human Oversight",
            one_sentence=(
                "High-risk AI systems must be designed for effective human oversight, "
                "with measures proportionate to risks and deployer capabilities."
            ),
            official_summary=(
                "Art. 14 requires systems to be designed for effective human oversight "
                "during use. Oversight must prevent risks to health, safety, and fundamental "
                "rights. Deployers must be enabled to understand, monitor, interpret, override, "
                "and interrupt the system. Biometric identification systems require dual-person "
                "verification of results."
            ),
            related_articles={
                "Art. 9": "Risk management (oversight linked to risk mitigation)",
                "Art. 13": "Transparency (deployer information enables oversight)",
                "Art. 26": "Deployer obligations (oversight implementation)",
                "Annex III(1)(a)": "Biometric identification (dual verification requirement)",
            },
            recital=(
                "Recital 73: Human oversight is crucial to minimise risks. "
                "Natural persons must be able to understand and override AI decisions."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of human-in-the-loop patterns",
                    "Detection of override/stop mechanisms",
                    "Detection of monitoring dashboards",
                    "Detection of automation bias warnings",
                ],
                "requires_human_judgment": [
                    "Whether oversight is truly 'effective'",
                    "Whether measures are commensurate with risks",
                    "Whether deployers can genuinely understand and override",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) human-in-the-loop mechanism, "
                "(2) override/stop capability, (3) deployer documentation for oversight, "
                "(4) dual-person verification for biometric systems. "
                "Based on: ISO/IEC 42001:2023."
            ),
            enforcement_date="2026-08-02",
            waiting_for="CEN-CENELEC harmonized standard (expected Q4 2026)",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_human_oversight") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 14(1), 14(4)",
                action="Implement human oversight mechanisms",
                details=(
                    "Art. 14(1) requires systems designed for effective human oversight. "
                    "Art. 14(4) requires deployers to be enabled to: understand the system, "
                    "be aware of automation bias, interpret output, override decisions, "
                    "and interrupt the system. Implement approval flows, review queues, "
                    "or manual review gates."
                ),
                effort="8-24 hours",
            ))

        if details.get("has_override_mechanism") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 14(3), 14(4)(d)(e)",
                action="Add override and stop mechanisms",
                details=(
                    "Art. 14(4)(d) requires ability to override/reverse output. "
                    "Art. 14(4)(e) requires a stop button or similar. "
                    "Implement: kill switch, manual override, emergency stop."
                ),
                effort="4-8 hours",
            ))

        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 14(4)(b)",
            action="Add automation bias awareness mechanisms",
            details=(
                "Art. 14(4)(b) requires awareness of automation bias tendency. "
                "Present outputs as suggestions, show confidence scores, "
                "add deliberate friction for high-stakes decisions."
            ),
            effort="4-8 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=14,
            article_title="Human Oversight",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 14 requires both technical mechanisms and organizational measures. "
                "Automated scanning detects technical patterns but cannot assess "
                "organizational oversight effectiveness."
            ),
        )


def create_module() -> Art14Module:
    return Art14Module()
