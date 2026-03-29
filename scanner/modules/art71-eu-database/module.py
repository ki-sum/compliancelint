"""
Article 71: EU database for high-risk AI systems listed in Annex III —
Module implementation using unified protocol.

Art. 71 establishes the EU database for high-risk AI systems. Providers and
public-authority deployers must enter data into this database:
  - Providers enter Sections A and B of Annex VIII (Art. 71(2))
  - Public-authority deployers enter Section C of Annex VIII (Art. 71(3))

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art71"). No regex or keyword scanning is performed.

Obligation mapping:
  ART71-OBL-2   → has_provider_database_entry (provider entered Annex VIII A+B data)
  ART71-OBL-3   → gap_findings (conditional on is_public_authority_deployer, context_skip_field)
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


class Art71Module(BaseArticleModule):
    """Article 71: EU database for high-risk AI systems compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=71,
            article_title="EU database for high-risk AI systems listed in Annex III",
        )

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for EU database compliance using AI-provided answers.

        Reads compliance_answers["art71"] from the AI context. Maps each field
        to obligation findings without any regex or file scanning.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for each EU database obligation.
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

        answers = ctx.get_article_answers("art71")

        has_provider_database_entry = answers.get("has_provider_database_entry")

        # ── ART71-OBL-2: Provider data entry in EU database (Annex VIII Sections A and B) ──
        findings.append(self._finding_from_answer(
            obligation_id="ART71-OBL-2",
            answer=has_provider_database_entry,
            true_description=(
                "EU database entry documentation found. "
                "Verify that the provider (or authorised representative) has entered "
                "the data listed in Sections A and B of Annex VIII into the EU database "
                "per Art. 71(2)."
            ),
            false_description=(
                "No EU database entry documentation found. "
                "Art. 71(2) requires the provider (or authorised representative) to enter "
                "the data listed in Sections A and B of Annex VIII into the EU database."
            ),
            none_description=(
                "AI could not determine whether provider data has been entered into the "
                "EU database. Art. 71(2) requires Sections A and B of Annex VIII data "
                "to be entered by the provider or authorised representative."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART71-OBL-3: Public-authority deployer data entry ──
        # Has context_skip_field in the obligation JSON (is_public_authority_deployer):
        #   - is_public_authority_deployer=false → NOT_APPLICABLE
        #   - is_public_authority_deployer=true  → UTD [APPLICABLE]
        #   - field not provided                 → UTD [CONDITIONAL]
        # The obligation engine's gap_findings() handles this automatically.

        # Build details dict
        details = {
            "has_provider_database_entry": has_provider_database_entry,
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
            article_number=71,
            article_title="EU database for high-risk AI systems listed in Annex III",
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
            article_number=71,
            article_title="EU database for high-risk AI systems listed in Annex III",
            one_sentence=(
                "The EU database for high-risk AI systems must contain registration "
                "data from providers and public-authority deployers."
            ),
            official_summary=(
                "Art. 71 establishes the EU database for high-risk AI systems listed "
                "in Annex III. Providers (or authorised representatives) must enter "
                "Sections A and B of Annex VIII data. Public-authority deployers must "
                "enter Section C data. The database is publicly accessible and "
                "machine-readable, except for law enforcement and migration systems "
                "registered in a restricted, non-public section."
            ),
            related_articles={
                "Art. 49": "Registration obligation (providers and deployers must register before market placement)",
                "Art. 49(3)": "Public authority deployer registration requirement",
                "Art. 49(4)": "Law enforcement registration in restricted section",
                "Annex III": "List of high-risk AI systems requiring registration",
                "Annex VIII": "Information to be submitted upon registration (Sections A, B, C)",
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
                    "Whether provider has entered all required Annex VIII data",
                    "Whether public-authority deployer has entered Section C data",
                    "Whether the database entry is current and accurate",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) provider has entered "
                "Annex VIII Sections A and B data into the EU database, (2) if applicable, "
                "public-authority deployer has entered Section C data. "
                "Based on: EU AI Act Art. 71, Annex VIII."
            ),
            enforcement_date="2026-08-02",
            waiting_for="EU database (Art. 71) operational availability",
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_provider_database_entry") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 71(2)",
                action="Enter provider data into the EU database",
                details=(
                    "Art. 71(2) requires the provider (or authorised representative) to enter "
                    "Sections A and B of Annex VIII data into the EU database.\n"
                    "\n"
                    "  Required data includes (per Annex VIII):\n"
                    "    Section A: Provider information\n"
                    "      - Name, address, contact details\n"
                    "      - Authorised representative details (if applicable)\n"
                    "    Section B: AI system information\n"
                    "      - Name and description of the AI system\n"
                    "      - Intended purpose and conditions of use\n"
                    "      - EU Declaration of Conformity reference\n"
                    "      - Member States where the system is placed on market or in service\n"
                    "\n"
                    "  Access the EU database at the official EU portal to complete registration."
                ),
                effort="2-4 hours",
                action_type="human_judgment_required",
            ))

        # Always add deployer obligation item
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 71(3)",
            action="Verify public-authority deployer data entry if applicable",
            details=(
                "If the deployer is a public authority, agency, or body (or acts on behalf "
                "of one), Art. 71(3) requires them to enter Section C of Annex VIII data "
                "into the EU database per Art. 49(3) and (4). Confirm whether this applies "
                "to your deployment context."
            ),
            effort="1-2 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=71,
            article_title="EU database for high-risk AI systems listed in Annex III",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "EU database data entry is a largely process-oriented obligation "
                "that cannot be fully verified from code. Human expert review is essential "
                "to verify data completeness. Based on ComplianceLint compliance checklist. "
                "Official CEN-CENELEC standards (expected Q4 2026) may modify these requirements."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art71Module:
    return Art71Module()
