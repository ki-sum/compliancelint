"""
Article 48: CE marking — Module implementation using unified protocol.

Art. 48 sets the rules for the CE marking of high-risk AI systems. Art. 16(h) makes affixing
the CE marking in accordance with Art. 48 an obligation of the provider:
  - The CE marking follows the general principles of Article 30 of Regulation (EC) No 765/2008
  - A digital CE marking is used for systems provided digitally, where it is easily accessible
  - The CE marking is affixed visibly, legibly and indelibly, or to the packaging or the
    accompanying documentation where that is not possible or not warranted
  - Where a notified body is involved, its identification number follows the CE marking and
    appears in promotional material that mentions CE conformity
  - Where other Union law also provides for the CE marking, the marking covers that law too

Scanning is AI-First: all detection is driven by compliance_answers provided by
ctx.get_article_answers("art48"). No regex or keyword scanning is performed.

Obligation mapping:
  ART48-OBL-1   → always UTD (manual: general principles of Regulation (EC) No 765/2008)
  ART48-OBL-2   → has_digital_ce_marking (conditional: is_provided_digitally)
  ART48-OBL-3   → has_ce_marking
  ART48-OBL-4a  → has_notified_body_number (conditional: has_notified_body_assessment)
  ART48-OBL-4b  → always UTD (manual; conditional: has_notified_body_assessment)
  ART48-OBL-4c  → has_notified_body_number_in_promotion (conditional: has_notified_body_assessment)
  ART48-OBL-5   → always UTD (manual; conditional: is_subject_to_other_ce_marking_law)

Conditional records (three states of the condition field):
  - true  → the record is assessed: from its answer, or UTD for the manual records.
  - false → no direct finding; the ObligationEngine marks the record NOT_APPLICABLE via its
            context_skip_field.
  - null  → UNABLE_TO_DETERMINE, and the finding says that the condition itself is open. The
            answer alone never decides a conditional record: a system assessed under internal
            control has no notified body number, and that is not a breach of Art. 48(4).

Boundary cases (custom Finding instead of _finding_from_answer):
  - ART48-OBL-1, ART48-OBL-4b and ART48-OBL-5 are manual: no answer field can settle them.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.application_dates import applicable_from
from core.protocol import (
    BaseArticleModule, ScanResult, Explanation, ActionPlan, ActionItem,
    Finding, ComplianceLevel, Confidence, GapType,
)
from core.obligation_engine import ObligationEngine


# Same text the ObligationEngine puts on the manual obligations it emits.
_HUMAN_GATE_HINT = "Complete this Human Gate at compliancelint.dev/dashboard → Human Gates"

_NOTIFIED_BODY_OPEN = (
    "AI could not determine whether a notified body is responsible for the conformity assessment "
    "procedure set out in Art. 43. "
)


class Art48Module(BaseArticleModule):
    """Article 48: CE marking compliance module."""

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=48,
            article_title="CE marking",
        )

    def _manual_finding(self, obligation_id: str, description: str, remediation: str) -> Finding:
        """A manual obligation: UNABLE_TO_DETERMINE until a person answers it in Human Gates."""
        return Finding(
            obligation_id=obligation_id,
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=Confidence.LOW,
            description=description,
            remediation=remediation,
            gap_type=GapType.PROCESS,
            human_gate_hint=_HUMAN_GATE_HINT,
        )

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for CE marking compliance using AI-provided answers.

        Reads compliance_answers["art48"] from the AI context. Maps each field
        to obligation findings without any regex or file scanning.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for each CE marking obligation.
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

        answers = ctx.get_article_answers("art48")

        has_ce_marking = answers.get("has_ce_marking")
        is_provided_digitally = answers.get("is_provided_digitally")
        has_digital_ce_marking = answers.get("has_digital_ce_marking")
        has_notified_body_assessment = answers.get("has_notified_body_assessment")
        has_notified_body_number = answers.get("has_notified_body_number")
        has_notified_body_number_in_promotion = answers.get("has_notified_body_number_in_promotion")
        is_subject_to_other_ce_marking_law = answers.get("is_subject_to_other_ce_marking_law")

        # ── ART48-OBL-1: general principles of Article 30 of Regulation (EC) No 765/2008 ──
        # Manual obligation: whether the marking follows the principles of another Regulation
        # cannot be read from a project.
        findings.append(self._manual_finding(
            "ART48-OBL-1",
            description=(
                "Whether the CE marking follows the general principles set out in Article 30 of "
                "Regulation (EC) No 765/2008 requires human review. AI cannot determine from a "
                "project whether those principles are met."
            ),
            remediation=(
                "Review the CE marking of the high-risk AI system against the general principles "
                "set out in Article 30 of Regulation (EC) No 765/2008 and record the result."
            ),
        ))

        # ── ART48-OBL-2: digital CE marking (conditional: system provided digitally) ──
        # is_provided_digitally False → NOT_APPLICABLE via the ObligationEngine (context_skip_field).
        if is_provided_digitally is not False:
            findings.append(self._finding_from_answer(
                obligation_id="ART48-OBL-2",
                answer=has_digital_ce_marking if is_provided_digitally is True else None,
                true_description=(
                    "A digital CE marking was found for this digitally provided system. Verify that it "
                    "can easily be accessed via the interface from which the system is accessed or via "
                    "an easily accessible machine-readable code or other electronic means."
                ),
                false_description=(
                    "No easily accessible digital CE marking was found for this digitally provided "
                    "system. Art. 48(2) requires a digital CE marking that can easily be accessed via "
                    "the interface from which the system is accessed or via an easily accessible "
                    "machine-readable code or other electronic means."
                ),
                none_description=(
                    "AI could not determine whether this high-risk AI system is provided digitally. "
                    "Art. 48(2) requires a digital CE marking only for systems provided digitally; "
                    "confirm how the system is provided."
                    if is_provided_digitally is None else
                    "AI could not determine whether this digitally provided system uses a digital CE "
                    "marking that can easily be accessed as Art. 48(2) requires."
                ),
                gap_type=GapType.PROCESS,
            ))

        # ── ART48-OBL-3: affixed visibly, legibly and indelibly ──
        findings.append(self._finding_from_answer(
            obligation_id="ART48-OBL-3",
            answer=has_ce_marking,
            true_description=(
                "A CE marking was found for the high-risk AI system. Verify that it is affixed "
                "visibly, legibly and indelibly or, where that is not possible or not warranted on "
                "account of the nature of the system, to the packaging or to the accompanying "
                "documentation."
            ),
            false_description=(
                "No CE marking was found for the high-risk AI system. Art. 48(3) requires the CE "
                "marking to be affixed visibly, legibly and indelibly or, where that is not possible "
                "or not warranted on account of the nature of the system, to the packaging or to the "
                "accompanying documentation."
            ),
            none_description=(
                "AI could not determine whether the CE marking is affixed to the high-risk AI system, "
                "its packaging or its accompanying documentation as Art. 48(3) requires."
            ),
            gap_type=GapType.PROCESS,
        ))

        # ── ART48-OBL-4a / 4b / 4c: notified body identification number (conditional) ──
        # has_notified_body_assessment False → all three NOT_APPLICABLE via the ObligationEngine.
        if has_notified_body_assessment is not False:
            notified_body = has_notified_body_assessment is True

            findings.append(self._finding_from_answer(
                obligation_id="ART48-OBL-4a",
                answer=has_notified_body_number if notified_body else None,
                true_description=(
                    "The CE marking is followed by an identification number of a notified body. Verify "
                    "that it is the number of the notified body responsible for the conformity "
                    "assessment procedure set out in Art. 43."
                ),
                false_description=(
                    "The CE marking is not followed by the identification number of the notified body. "
                    "Art. 48(4) requires the CE marking to be followed by the identification number of "
                    "the notified body responsible for the conformity assessment procedure set out in "
                    "Art. 43."
                ),
                none_description=(
                    "AI could not determine whether the CE marking is followed by the identification "
                    "number of the notified body as Art. 48(4) requires."
                    if notified_body else
                    _NOTIFIED_BODY_OPEN + "Art. 48(4) requires its identification number after the CE "
                    "marking only where a notified body is involved; confirm the conformity assessment "
                    "procedure that applies."
                ),
                gap_type=GapType.PROCESS,
            ))

            # Manual: who affixed the number cannot be read from a project.
            findings.append(self._manual_finding(
                "ART48-OBL-4b",
                description=(
                    "Whether the identification number of the notified body was affixed by the body "
                    "itself or, under its instructions, by the provider or by the provider's authorised "
                    "representative requires human review."
                    if notified_body else
                    _NOTIFIED_BODY_OPEN + "Art. 48(4) sets who affixes its identification number only "
                    "where a notified body is involved; confirm the conformity assessment procedure "
                    "that applies."
                ),
                remediation=(
                    "Record who affixed the identification number of the notified body and, where it "
                    "was the provider or the provider's authorised representative, the instructions of "
                    "the notified body under which it was affixed."
                ),
            ))

            findings.append(self._finding_from_answer(
                obligation_id="ART48-OBL-4c",
                answer=has_notified_body_number_in_promotion if notified_body else None,
                true_description=(
                    "Promotional material that mentions CE conformity indicates an identification "
                    "number of a notified body. Verify that all promotional material which mentions "
                    "that the system fulfils the requirements for CE marking indicates the number."
                ),
                false_description=(
                    "Promotional material mentions that the system fulfils the requirements for CE "
                    "marking without indicating the identification number of the notified body. "
                    "Art. 48(4) requires the number in any such promotional material."
                ),
                none_description=(
                    "AI could not determine whether promotional material that mentions CE conformity "
                    "indicates the identification number of the notified body as Art. 48(4) requires."
                    if notified_body else
                    _NOTIFIED_BODY_OPEN + "Art. 48(4) requires its identification number in promotional "
                    "material that mentions CE conformity only where a notified body is involved; "
                    "confirm the conformity assessment procedure that applies."
                ),
                gap_type=GapType.PROCESS,
            ))

        # ── ART48-OBL-5: other Union law that also provides for the CE marking (conditional, manual) ──
        # is_subject_to_other_ce_marking_law False → NOT_APPLICABLE via the ObligationEngine.
        if is_subject_to_other_ce_marking_law is not False:
            findings.append(self._manual_finding(
                "ART48-OBL-5",
                description=(
                    "This high-risk AI system is subject to other Union law which also provides for the "
                    "affixing of the CE marking. Whether the system also fulfils the requirements of "
                    "that other law, as the CE marking then indicates under Art. 48(5), requires human "
                    "review."
                    if is_subject_to_other_ce_marking_law is True else
                    "AI could not determine whether this high-risk AI system is subject to other Union "
                    "law which also provides for the affixing of the CE marking. Art. 48(5) applies "
                    "only in that case; confirm which Union law applies to the system."
                ),
                remediation=(
                    "Identify the other Union law that provides for the affixing of the CE marking and "
                    "confirm that the high-risk AI system fulfils its requirements before the CE "
                    "marking is affixed."
                ),
            ))

        details = {
            "has_ce_marking": has_ce_marking,
            "is_provided_digitally": is_provided_digitally,
            "has_digital_ce_marking": has_digital_ce_marking,
            "has_notified_body_assessment": has_notified_body_assessment,
            "has_notified_body_number": has_notified_body_number,
            "has_notified_body_number_in_promotion": has_notified_body_number_in_promotion,
            "is_subject_to_other_ce_marking_law": is_subject_to_other_ce_marking_law,
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
            article_number=48,
            article_title="CE marking",
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
            article_number=48,
            article_title="CE marking",
            one_sentence=(
                "The CE marking of a high-risk AI system must be affixed visibly, legibly and "
                "indelibly, in digital form for systems provided digitally, and be followed by the "
                "notified body's identification number where a notified body is involved."
            ),
            official_summary=(
                "Art. 48 makes the CE marking of high-risk AI systems subject to the general "
                "principles set out in Article 30 of Regulation (EC) No 765/2008. For systems "
                "provided digitally a digital CE marking is used, only if it can easily be accessed "
                "via the interface from which the system is accessed or via an easily accessible "
                "machine-readable code or other electronic means. The CE marking is affixed visibly, "
                "legibly and indelibly or, where that is not possible or not warranted on account of "
                "the nature of the system, to the packaging or to the accompanying documentation. "
                "Where applicable, it is followed by the identification number of the notified body "
                "responsible for the Art. 43 conformity assessment procedures, and that number is "
                "also indicated in promotional material which mentions that the system fulfils the "
                "requirements for CE marking. Where other Union law also provides for the CE "
                "marking, the marking indicates that the system also fulfils that law."
            ),
            related_articles={
                "Art. 16": "Art. 16(h) makes affixing the CE marking in accordance with Art. 48 a provider obligation",
                "Art. 43": "Conformity assessment procedures, including those involving a notified body",
                "Art. 47": "EU declaration of conformity drawn up for the high-risk AI system",
                "Art. 49": "Registration in the EU database",
                "Regulation (EC) No 765/2008 Art. 30": "General principles of the CE marking",
            },
            recital=(
                "Recital 129 addresses the CE marking of high-risk AI systems. Its verbatim text is "
                "in the official text of the Regulation."
            ),
            automation_summary={
                "fully_automatable": [],
                "partially_automatable": [
                    "Detection of a CE marking in the system, its packaging or its accompanying documentation",
                    "Detection of a digital CE marking in the interface of a digitally provided system",
                    "Detection of a notified body identification number after the CE marking",
                    "Detection of the notified body identification number in promotional material",
                ],
                "requires_human_judgment": [
                    "Whether the CE marking follows the general principles of Article 30 of Regulation (EC) No 765/2008",
                    "Whether the CE marking is visible, legible and indelible",
                    "Whether the digital CE marking can easily be accessed",
                    "Whether a notified body is responsible for the Art. 43 conformity assessment procedure",
                    "Who affixes the notified body identification number",
                    "Whether other Union law also provides for the affixing of the CE marking",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 requires: (1) a CE marking affixed visibly, "
                "legibly and indelibly, or to the packaging or the accompanying documentation, "
                "(2) for systems provided digitally, an easily accessible digital CE marking, "
                "(3) where a notified body is involved, its identification number after the CE "
                "marking and in promotional material that mentions CE conformity. "
                "Based on: EU AI Act Art. 48(1)-(5)."
            ),
            enforcement_date=applicable_from(48),
            waiting_for=(
                "None specified: Art. 48 refers to the general principles of the CE marking in "
                "Article 30 of Regulation (EC) No 765/2008"
            ),
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        actions = []
        details = scan_result.details

        if details.get("has_ce_marking") is False:
            actions.append(ActionItem(
                priority="CRITICAL",
                article="Art. 48(3)",
                action="Affix the CE marking to the high-risk AI system",
                details=(
                    "Art. 48(3) requires the CE marking to be affixed visibly, legibly and indelibly "
                    "for high-risk AI systems. Where that is not possible or not warranted on account "
                    "of the nature of the system, affix it to the packaging or to the accompanying "
                    "documentation, as appropriate."
                ),
                effort="1-4 hours",
                action_type="human_judgment_required",
            ))

        if details.get("is_provided_digitally") is True and details.get("has_digital_ce_marking") is False:
            actions.append(ActionItem(
                priority="HIGH",
                article="Art. 48(2)",
                action="Provide an easily accessible digital CE marking",
                details=(
                    "Art. 48(2) requires a digital CE marking for high-risk AI systems provided "
                    "digitally. It must be easily accessible via the interface from which the system "
                    "is accessed or via an easily accessible machine-readable code or other electronic "
                    "means."
                ),
                effort="2-8 hours",
                action_type="human_judgment_required",
            ))

        if details.get("has_notified_body_assessment") is True:
            if details.get("has_notified_body_number") is False:
                actions.append(ActionItem(
                    priority="HIGH",
                    article="Art. 48(4)",
                    action="Add the notified body's identification number after the CE marking",
                    details=(
                        "Art. 48(4) requires the CE marking to be followed by the identification number "
                        "of the notified body responsible for the conformity assessment procedure set "
                        "out in Art. 43. The number is affixed by the body itself or, under its "
                        "instructions, by the provider or by the provider's authorised representative."
                    ),
                    effort="1-2 hours",
                    action_type="human_judgment_required",
                ))
            if details.get("has_notified_body_number_in_promotion") is False:
                actions.append(ActionItem(
                    priority="MEDIUM",
                    article="Art. 48(4)",
                    action="Indicate the notified body's identification number in promotional material",
                    details=(
                        "Art. 48(4) requires the identification number of the notified body in any "
                        "promotional material which mentions that the high-risk AI system fulfils the "
                        "requirements for CE marking."
                    ),
                    effort="1-4 hours",
                    action_type="human_judgment_required",
                ))

        # Always add the manual obligation item
        actions.append(ActionItem(
            priority="MEDIUM",
            article="Art. 48(1)",
            action="Review the CE marking against Article 30 of Regulation (EC) No 765/2008",
            details=(
                "Art. 48(1) makes the CE marking subject to the general principles set out in "
                "Article 30 of Regulation (EC) No 765/2008. Review the marking against those "
                "principles and record the result."
            ),
            effort="1-2 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=48,
            article_title="CE marking",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "The CE marking cannot be fully verified from code. Human review is needed to "
                "confirm how and where the marking is affixed and whether a notified body is "
                "involved. Based on the ComplianceLint compliance checklist, which is not an "
                "official standard."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art48Module:
    return Art48Module()
