"""
Article 49: Registration — Module implementation using unified protocol.

Art. 49 requires providers and deployers of high-risk AI systems to register
themselves and their systems in the EU database (Art. 71) before market placement:
  - Provider must register themselves and their system (Art. 49(1))
  - Art. 6(3) exception providers must also register (Art. 49(2))
  - Public authority deployers must register their use (Art. 49(3))

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art49"). No regex or keyword scanning is performed.

Obligation mapping:
  ART49-OBL-1   → has_eu_database_registration (provider + system registered)
  ART49-OBL-2   → gap_findings (conditional on claims_art6_3_exception, context_skip_field)
  ART49-OBL-3   → gap_findings (conditional on is_public_authority, context_skip_field)
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


class Art49Module(BaseArticleModule):
    """Article 49: Registration compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=49,
            article_title="Registration",
        )

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for EU database registration compliance using AI-provided answers.

        Reads compliance_answers["art49"] from the AI context. Maps each field
        to obligation findings without any regex or file scanning.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for each registration obligation.
        """
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

        answers = ctx.get_article_answers("art49")

        has_eu_database_registration = answers.get("has_eu_database_registration")

        # ── ART49-OBL-1: Provider and system registration in EU database ──
        # Provider must register themselves and their system before market placement
        findings.append(self._finding_from_answer(
            obligation_id="ART49-OBL-1",
            answer=has_eu_database_registration,
            true_description=(
                "EU database registration documentation found. "
                "Verify that both the provider and the AI system are registered "
                "in the EU database (Art. 71) before market placement or putting "
                "into service per Art. 49(1)."
            ),
            false_description=(
                "No EU database registration documentation found. "
                "Art. 49(1) requires providers to register themselves and their "
                "high-risk AI system in the EU database (Art. 71) before placing "
                "on the market or putting into service."
            ),
            none_description=(
                "AI could not determine whether EU database registration has been "
                "completed. Art. 49(1) requires registration of both the provider "
                "and the system in the EU database (Art. 71)."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART49-OBL-2 and ART49-OBL-3 ──
        # Both have context_skip_field in the obligation JSON:
        #   OBL-2: claims_art6_3_exception (Art. 6(3) exception registration)
        #   OBL-3: is_public_authority (public authority deployer registration)
        # The obligation engine's gap_findings() handles them automatically:
        #   - context_skip_field=false → NOT_APPLICABLE
        #   - context_skip_field=true  → UTD [APPLICABLE]
        #   - field not provided       → UTD [CONDITIONAL]

        # Build details dict
        details = {
            "has_eu_database_registration": has_eu_database_registration,
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
            article_number=49,
            article_title="Registration",
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
            article_number=49,
            article_title="Registration",
            one_sentence=(
                "High-risk AI system providers must register themselves and their systems "
                "in the EU database before market placement."
            ),
            official_summary=(
                "Art. 49 requires providers of high-risk AI systems (Annex III, except "
                "point 2) to register themselves and their system in the EU database "
                "(Art. 71) before placing on the market or putting into service. "
                "Providers claiming Art. 6(3) exception must also register. Public "
                "authority deployers must register themselves, select the system, and "
                "register its use. Registration must include Annex VIII information."
            ),
            related_articles={
                "Art. 6": "High-risk classification determining registration scope",
                "Art. 6(3)": "Exception for systems not considered high-risk despite Annex III listing",
                "Art. 47": "EU Declaration of Conformity (precedes registration)",
                "Art. 48": "CE marking (precedes registration)",
                "Art. 71": "EU database for high-risk AI systems",
                "Annex III": "List of high-risk AI systems requiring registration",
                "Annex VIII": "Information to be submitted upon registration",
            },
            recital=(
                "Recital 131: To facilitate the work of the Commission and the Member States "
                "in the AI field as well as to increase the transparency towards the public, "
                "providers of high-risk AI systems should be required to register their system "
                "in an EU database."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of EU database registration documentation or confirmation",
                ],
                "requires_human_judgment": [
                    "Whether provider is actually registered in the EU database",
                    "Whether system is registered before market placement",
                    "Whether Art. 6(3) exception is validly claimed",
                    "Whether deployer qualifies as public authority",
                    "Whether deployer has completed use registration",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) provider registration "
                "in EU database (Art. 71), (2) system registration with Annex VIII information "
                "before market placement, (3) Art. 6(3) exception registration if applicable, "
                "(4) public authority deployer use registration if applicable. "
                "Based on: EU AI Act Art. 49, Annex VIII."
            ),
            enforcement_date="2026-08-02",
            waiting_for="EU database (Art. 71) operational availability",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_eu_database_registration") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 49(1)",
                action="Register provider and system in the EU database",
                details=(
                    "Art. 49(1) requires registration of both the provider and the high-risk "
                    "AI system in the EU database (Art. 71) BEFORE placing on the market or "
                    "putting into service.\n"
                    "\n"
                    "  Registration must include (per Annex VIII):\n"
                    "    1. Name, address, and contact details of the provider\n"
                    "    2. Name and description of the AI system\n"
                    "    3. Status of the AI system (on the market, in service, withdrawn)\n"
                    "    4. Intended purpose and conditions of use\n"
                    "    5. EU Declaration of Conformity reference\n"
                    "    6. Member States where the system is placed on market or in service"
                ),
                effort="2-4 hours",
                action_type="human_judgment_required",
            ))

        # Always add manual obligation items
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 49(2)",
            action="Verify Art. 6(3) exception registration if applicable",
            details=(
                "If you have concluded your system is not high-risk per Art. 6(3) "
                "(despite being listed in Annex III), Art. 49(2) still requires you "
                "to register yourself and the system in the EU database. Document your "
                "Art. 6(3) assessment rationale alongside the registration."
            ),
            effort="1-2 hours",
            action_type="human_judgment_required",
        ))

        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 49(3)",
            action="Verify public authority deployer registration if applicable",
            details=(
                "If the deployer is a public authority, Union institution, body, office, "
                "or agency, Art. 49(3) requires them to register themselves, select the "
                "system, and register its use in the EU database before putting into service."
            ),
            effort="1-2 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=49,
            article_title="Registration",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "EU database registration is a largely process-oriented obligation "
                "that cannot be fully verified from code. Human expert review is essential "
                "to verify registration completeness. Based on ComplianceLint compliance "
                "checklist. Official CEN-CENELEC standards (expected Q4 2026) may modify "
                "these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art49Module:
    return Art49Module()
