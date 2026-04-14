"""
Obligation Engine — maps structured legal obligations to scan findings.

This is the core differentiator: detection logic reads from obligations JSON
instead of hard-coding legal requirements in Python. Each obligation carries
its own automation_assessment describing what to check and how.

The engine does NOT duplicate detection logic. It:
1. Maps existing scan results to legal obligations
2. Enriches findings with source quotes and obligation IDs
3. Identifies coverage gaps (obligations with no corresponding scan check)
4. Generates action items from unmet obligations

Usage:
    obligations_data = json.load(open("art12-record-keeping.json"))
    engine = ObligationEngine(obligations_data)
    findings = engine.evaluate(index, scan_details)
    gaps = engine.coverage_gaps(existing_findings)
    actions = engine.get_action_items(findings)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.protocol import (
    Finding, ComplianceLevel, Confidence, ActionItem, GapType,
    ProjectIndex, SOURCE_EXTS, CONFIG_EXTS, DOC_EXTS,
)


@dataclass
class Obligation:
    """A single parsed obligation from the JSON."""
    id: str
    source: str
    source_quote: str
    deontic_type: str
    modality: str
    addressee: str
    atoms: list[dict]
    automation_level: str          # "full", "partial", "manual"
    automation_confidence: str     # "high", "medium", "low"
    detection_method: str
    what_to_scan: list[str]
    human_judgment_needed: Optional[str] = None
    scope_limitation: Optional[str] = None
    context_skip_field: Optional[str] = None   # compliance_answers field that, if False, makes this NOT_APPLICABLE
    context_skip_value: bool = False           # the value that triggers NOT_APPLICABLE (default: False = skip when field is False)
    cross_references: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Obligation:
        """Parse an obligation from the JSON structure."""
        auto = data.get("automation_assessment", {})
        return cls(
            id=data.get("id", "UNKNOWN"),
            source=data.get("source", ""),
            source_quote=data.get("source_quote", ""),
            deontic_type=data.get("deontic_type", "obligation"),
            modality=data.get("modality", "shall"),
            addressee=data.get("addressee", "provider"),
            atoms=data.get("decomposed_atoms", []),
            automation_level=auto.get("level", "manual"),
            automation_confidence=auto.get("confidence", "low"),
            detection_method=auto.get("detection_method", ""),
            what_to_scan=auto.get("what_to_scan", []),
            human_judgment_needed=auto.get("human_judgment_needed"),
            scope_limitation=data.get("scope_limitation"),
            context_skip_field=data.get("context_skip_field"),
            context_skip_value=data.get("context_skip_value", False),
            cross_references=data.get("cross_references", []),
        )


class ObligationEngine:
    """Evaluates project state against structured legal obligations.

    The engine augments existing scan logic — it does not replace it.
    It provides:
    - Obligation-to-finding mapping with source quotes
    - Coverage gap analysis (which obligations have no scan check)
    - Action item generation from unmet obligations
    """

    def __init__(self, obligations_json: dict):
        """Load obligations from parsed JSON.

        Args:
            obligations_json: Full parsed obligations JSON including
                              _metadata, obligations, and summary.
        """
        self._raw = obligations_json
        self._metadata = obligations_json.get("_metadata", {})
        self._obligations: list[Obligation] = []

        for obl_data in obligations_json.get("obligations", []):
            self._obligations.append(Obligation.from_dict(obl_data))

    @property
    def obligations(self) -> list[Obligation]:
        return self._obligations

    @property
    def article_number(self) -> int:
        return self._metadata.get("article", 0)

    @property
    def article_title(self) -> str:
        return self._metadata.get("title", "Unknown")

    def get_obligation(self, obligation_id: str) -> Optional[Obligation]:
        """Get a specific obligation by ID."""
        for obl in self._obligations:
            if obl.id == obligation_id:
                return obl
        return None

    def automatable_obligations(self) -> list[Obligation]:
        """Return obligations that can be fully or partially automated."""
        return [o for o in self._obligations
                if o.automation_level in ("full", "partial")]

    def manual_obligations(self) -> list[Obligation]:
        """Return obligations that require human judgment."""
        return [o for o in self._obligations
                if o.automation_level == "manual"]

    # ── Core evaluation ──

    def evaluate(self, index: ProjectIndex, scan_details: dict) -> list[Finding]:
        """Evaluate all obligations against project state.

        This runs lightweight checks based on what_to_scan and detection_method
        from each obligation. It is designed to augment (not replace) the
        module's existing detailed scan logic.

        Args:
            index: ProjectIndex for the project
            scan_details: dict of scan results from the module's scan()

        Returns:
            List of Finding objects, one per automatable obligation
        """
        findings = []

        for obl in self._obligations:
            if obl.automation_level == "manual":
                # Manual obligations get a reminder finding
                findings.append(Finding(
                    obligation_id=obl.id,
                    file_path="project-wide",
                    line_number=None,
                    level=ComplianceLevel.UNABLE_TO_DETERMINE,
                    confidence=Confidence.LOW,
                    description=(
                        f"Requires human judgment. "
                        f"{obl.human_judgment_needed or 'Manual review needed.'}"
                    ),
                    source_quote=obl.source_quote,
                    gap_type=GapType.PROCESS,
                    human_gate_hint="Complete this Human Gate at compliancelint.dev/dashboard \u2192 Human Gates",
                ))
                continue

            # For automatable obligations, run detection based on what_to_scan
            finding = self._evaluate_obligation(obl, index, scan_details)
            findings.append(finding)

        return findings

    def _evaluate_obligation(self, obl: Obligation,
                             index: ProjectIndex,
                             scan_details: dict) -> Finding:
        """Evaluate a single obligation against project state.

        Uses the obligation's what_to_scan and detection_method to determine
        what to look for. Returns a Finding with the source quote included.
        """
        scan_types = set(obl.what_to_scan)
        evidence_found = []
        evidence_missing = []

        # Check code-level evidence
        if "code" in scan_types:
            source_files = index.files(SOURCE_EXTS)
            if source_files:
                evidence_found.append(f"{len(source_files)} source files available")
            else:
                evidence_missing.append("no source files found")

        # Check config-level evidence
        if "config" in scan_types:
            config_files = index.files(CONFIG_EXTS)
            if config_files:
                evidence_found.append(f"{len(config_files)} config files found")
            else:
                evidence_missing.append("no configuration files found")

        # Check documentation evidence
        if "documentation" in scan_types or "docs" in scan_types:
            doc_files = index.files(DOC_EXTS)
            if doc_files:
                evidence_found.append(f"{len(doc_files)} documentation files found")
            else:
                evidence_missing.append("no documentation files found")

        # Check monitoring / infrastructure evidence
        if "monitoring" in scan_types or "infrastructure" in scan_types:
            monitoring_patterns = [
                "monitor", "metrics", "prometheus", "grafana",
                "datadog", "observability", "alert",
            ]
            results = index.search_content(
                monitoring_patterns,
                extensions=SOURCE_EXTS | CONFIG_EXTS,
                max_matches=50,
            )
            if results:
                evidence_found.append(f"monitoring references in {len(results)} file(s)")
            else:
                evidence_missing.append("no monitoring infrastructure detected")

        # Check API evidence
        if "api" in scan_types:
            api_patterns = [
                "api", "endpoint", "route", "swagger", "openapi",
            ]
            results = index.search_content(
                api_patterns,
                extensions=SOURCE_EXTS | CONFIG_EXTS,
                max_matches=50,
            )
            if results:
                evidence_found.append(f"API references in {len(results)} file(s)")
            else:
                evidence_missing.append("no API definitions detected")

        # Determine compliance level based on evidence
        if not evidence_missing:
            level = ComplianceLevel.PARTIAL  # Evidence exists but needs human review
            confidence = Confidence.LOW
        elif not evidence_found:
            level = ComplianceLevel.UNABLE_TO_DETERMINE
            confidence = Confidence.LOW
        else:
            level = ComplianceLevel.PARTIAL
            confidence = Confidence.LOW

        # Determine gap_type based on what_to_scan
        if "documentation" in scan_types or "docs" in scan_types:
            gap_type = GapType.PROCESS
        elif "monitoring" in scan_types or "infrastructure" in scan_types:
            gap_type = GapType.TECHNICAL
        elif "code" in scan_types:
            gap_type = GapType.CODE
        else:
            gap_type = GapType.CODE

        # Build description — AI analysis only. Legal citation is in source_quote separately.
        parts = []
        if evidence_found:
            parts.append(f"Evidence: {'; '.join(evidence_found)}.")
        if evidence_missing:
            parts.append(f"Gaps: {'; '.join(evidence_missing)}.")
        if obl.human_judgment_needed:
            parts.append(f"Note: {obl.human_judgment_needed}")
        if not parts:
            parts.append(f"{obl.source} compliance check.")

        return Finding(
            obligation_id=obl.id,
            file_path="project-wide",
            line_number=None,
            level=level,
            confidence=confidence,
            description=" ".join(parts),
            source_quote=obl.source_quote,
            gap_type=gap_type,
        )

    # ── Coverage gap analysis ──

    def coverage_gaps(self, existing_findings: list[Finding]) -> list[Obligation]:
        """Identify obligations that have no corresponding finding.

        Args:
            existing_findings: Findings from the module's own scan logic

        Returns:
            List of Obligation objects that have no matching finding
        """
        covered_ids = {f.obligation_id for f in existing_findings}
        return [o for o in self._obligations if o.id not in covered_ids]

    # ── Action item generation ──

    def get_action_items(self, findings: list[Finding]) -> list[ActionItem]:
        """Generate action items from findings.

        Creates action items for findings that are non-compliant or
        unable to determine, using the obligation's source text and
        detection method for guidance.
        """
        actions = []
        actionable_levels = {
            ComplianceLevel.NON_COMPLIANT,
            ComplianceLevel.UNABLE_TO_DETERMINE,
        }

        for finding in findings:
            if finding.level not in actionable_levels:
                continue

            obl = self.get_obligation(finding.obligation_id)
            if not obl:
                continue

            # Determine priority from automation level and modality
            if obl.modality == "shall" and obl.automation_level == "full":
                priority = "CRITICAL"
            elif obl.modality == "shall":
                priority = "HIGH"
            else:
                priority = "MEDIUM"

            action_type = "automated"
            if obl.automation_level == "manual" or obl.human_judgment_needed:
                action_type = "human_judgment_required"

            # Build action description from atoms
            atom_descriptions = [a.get("requirement", a.get("description", ""))
                                 for a in obl.atoms[:3]]
            atom_text = " ".join(atom_descriptions) if atom_descriptions else obl.detection_method

            actions.append(ActionItem(
                priority=priority,
                article=obl.source,
                action=f"Address {obl.id}: {obl.source}",
                details=(
                    f"Legal requirement: \"{obl.source_quote[:200]}\" "
                    f"— Detection: {obl.detection_method}. "
                    f"Requirements: {atom_text[:300]}"
                ),
                effort="",
                action_type=action_type,
            ))

        return actions

    def gap_findings(self, existing_findings: list[Finding],
                     compliance_answers: dict = None) -> list[Finding]:
        """Generate findings for obligations not covered by existing scan.

        This method is the reason module.py does NOT need to be edited when
        new obligations are added to the JSON. Any obligation in the JSON that
        doesn't already have a Finding from the module's explicit scan() code
        is automatically caught here and emitted as UNABLE_TO_DETERMINE.

        ── Processing order (matters — earlier rules take precedence) ──

        1. scope_limitation is not None
           → Handled first, regardless of deontic_type.
           → If context provides context_skip_field=False → NOT_APPLICABLE (informational).
           → If context provides context_skip_field=True  → UNABLE_TO_DETERMINE [APPLICABLE].
           → If context field absent                      → UNABLE_TO_DETERMINE [CONDITIONAL].
           → Always continues (never falls through to rule 2).
           ⚠️  This means an exception or permission WITH scope_limitation WILL generate
               a finding (it is not skipped). Example: ART14-EXC-5b appears in findings
               because it has scope_limitation even though deontic_type="exception".

        2. deontic_type in skip set → silently skipped, NO finding generated.
           Skip set: "permission", "exception", "exception_criterion",
                     "empowerment", "exemption", "prohibition",
                     "classification_rule", "recommendation"
           ⚠️  Only reaches here if scope_limitation is None (rule 1 did not apply).
           ⚠️  "savings_clause" is NOT in the skip set — it generates a finding.

        3. obligation (and savings_clause) without scope_limitation
           → manual → UNABLE_TO_DETERMINE [COVERAGE GAP — manual]
           → partial/full → UNABLE_TO_DETERMINE [COVERAGE GAP]

        ── Maintenance rule ──
        When adding a new obligation to an obligation JSON:
          - Do NOT add a findings.append() to module.py.
          - gap_findings() will emit the appropriate finding automatically.
          - Only add to module.py if you need CUSTOM logic (e.g., mapping
            a specific compliance_answers field to the obligation's level).
          - Update test_all_N_obligations_in_findings: increment N, add the
            new OBL ID to the assertion IF it is deontic_type="obligation"
            without scope_limitation (those always appear). For scope_limitation
            obligations, they appear as CONDITIONAL — add only if the test context
            doesn't set the skip field to False.

        Args:
            existing_findings: Findings already produced by the module's scan().
            compliance_answers: AI-provided answers dict (e.g., ctx.compliance_answers).
                Used to auto-skip conditional obligations when context provides
                a definitive answer (e.g., is_biometric_system=False → OBL-3a NOT_APPLICABLE).
        """
        gaps = self.coverage_gaps(existing_findings)
        findings = []
        answers_flat = {}
        if compliance_answers:
            # Flatten all article answers into one dict for field lookup
            for key, val in compliance_answers.items():
                if isinstance(val, dict):
                    answers_flat.update(val)

        # Types that never generate findings — even with scope_limitation.
        # Permissions and empowerments are rights, not obligations.
        # Not exercising a right is not a violation.
        _permission_types = ("permission", "empowerment")

        for obl in gaps:
            # Skip permissions/empowerments first — they are rights, not checkable
            # obligations.  Even when they have a scope_limitation, asking the user
            # "does this condition apply?" is noise because the answer doesn't
            # change any compliance requirement.
            if obl.deontic_type in _permission_types:
                continue

            # Conditional obligations — check if context provides a skip signal
            if obl.scope_limitation is not None:
                # If context_skip_field is set and context has a definitive answer,
                # auto-determine NOT_APPLICABLE instead of asking the user
                if obl.context_skip_field and obl.context_skip_field in answers_flat:
                    field_value = answers_flat[obl.context_skip_field]
                    if field_value is obl.context_skip_value or field_value == obl.context_skip_value:
                        findings.append(Finding(
                            obligation_id=obl.id,
                            file_path="project-wide",
                            line_number=None,
                            level=ComplianceLevel.NOT_APPLICABLE,
                            confidence=Confidence.HIGH,
                            description=(
                                f"[NOT APPLICABLE] {obl.source}: {obl.scope_limitation}. "
                                f"Project context indicates {obl.context_skip_field}="
                                f"{field_value}, so this obligation does not apply."
                            ),
                            source_quote=obl.source_quote,
                            gap_type=GapType.PROCESS,
                            is_informational=True,
                        ))
                        continue
                    else:
                        # Field provided but value does NOT trigger skip
                        # → obligation IS applicable, but we can't auto-check it
                        findings.append(Finding(
                            obligation_id=obl.id,
                            file_path="project-wide",
                            line_number=None,
                            level=ComplianceLevel.UNABLE_TO_DETERMINE,
                            confidence=Confidence.LOW,
                            description=(
                                f"[APPLICABLE] {obl.source}: "
                                f"This obligation applies to your system "
                                f"({obl.context_skip_field}={field_value}). "
                                f"Manual verification required."
                            ),
                            source_quote=obl.source_quote,
                            gap_type=GapType.PROCESS,
                            is_informational=True,
                            human_gate_hint="Complete this Human Gate at compliancelint.dev/dashboard \u2192 Human Gates" if obl.automation_level == "manual" else None,
                        ))
                        continue

                # No context or field not provided — emit as CONDITIONAL
                findings.append(Finding(
                    obligation_id=obl.id,
                    file_path="project-wide",
                    line_number=None,
                    level=ComplianceLevel.UNABLE_TO_DETERMINE,
                    confidence=Confidence.LOW,
                    description=(
                        f"[CONDITIONAL] {obl.source}: "
                        f"This obligation has a scope limitation: {obl.scope_limitation}. "
                        f"If this condition applies to your system, verify compliance manually."
                    ),
                    source_quote=obl.source_quote,
                    gap_type=GapType.PROCESS,
                    is_informational=True,
                ))
                continue

            # Skip non-obligation types that don't create coverage gaps:
            # - permission/exception/exemption: grant latitude, not requirements
            # - prohibition: absence of a finding = compliant (not doing the prohibited thing)
            # - classification_rule: definitional fact, not a checkable obligation
            # - recommendation: "may" suggestions, not mandatory requirements
            if obl.deontic_type in (
                "permission", "exception", "exception_criterion", "empowerment", "exemption",
                "prohibition", "classification_rule", "recommendation",
            ):
                continue
            if obl.automation_level == "manual":
                description = (
                    f"[COVERAGE GAP — manual] {obl.source}: "
                    f"This obligation requires human judgment. "
                    f"{obl.human_judgment_needed or ''}"
                )
                level = ComplianceLevel.UNABLE_TO_DETERMINE
                gap_type = GapType.PROCESS
                human_gate_hint = "Complete this Human Gate at compliancelint.dev/dashboard \u2192 Human Gates"
            else:
                description = (
                    f"[COVERAGE GAP] {obl.source}: "
                    f"No automated check exists for this obligation. "
                    f"Detection method: {obl.detection_method}"
                )
                level = ComplianceLevel.UNABLE_TO_DETERMINE
                human_gate_hint = None
                scan_types = set(obl.what_to_scan)
                if "documentation" in scan_types or "docs" in scan_types:
                    gap_type = GapType.PROCESS
                elif "monitoring" in scan_types or "infrastructure" in scan_types:
                    gap_type = GapType.TECHNICAL
                else:
                    gap_type = GapType.CODE

            findings.append(Finding(
                obligation_id=obl.id,
                file_path="project-wide",
                line_number=None,
                level=level,
                confidence=Confidence.LOW,
                description=description,
                source_quote=obl.source_quote,
                gap_type=gap_type,
                is_informational=True,
                human_gate_hint=human_gate_hint,
            ))

        return findings

    def enrich_finding(self, finding: Finding) -> Finding:
        """Enrich an existing finding with obligation source quote.

        If the finding's obligation_id matches a known obligation,
        prepend the source quote to the description.
        """
        obl = self.get_obligation(finding.obligation_id)
        if not obl:
            return finding

        # Don't double-enrich
        if finding.description.startswith(f"[{obl.source}]"):
            return finding

        return Finding(
            obligation_id=finding.obligation_id,
            file_path=finding.file_path,
            line_number=finding.line_number,
            level=finding.level,
            confidence=finding.confidence,
            description=finding.description,
            remediation=finding.remediation,
            source_quote=obl.source_quote,
            gap_type=finding.gap_type,
        )
