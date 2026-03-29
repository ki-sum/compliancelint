"""
Article 5: Prohibited AI Practices — Module implementation using unified protocol.

Article 5 of the EU AI Act defines AI practices that are completely BANNED.
Unlike other articles that impose requirements on high-risk systems, Art. 5
establishes absolute prohibitions (with narrow law-enforcement exceptions for
real-time biometric identification).

This module reads AI-provided compliance_answers (via ctx.get_article_answers)
and maps each answer to a Finding. No regex or keyword scanning is performed —
detection is 100% the AI's responsibility.
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


# ── Practice → obligation mapping ──

# Maps practice name (from AI answer) to prohibition ID(s).
# biometric_surveillance covers two prohibitions: PRO-1e (scraping) and PRO-1g (categorization).
_PRACTICE_TO_OBLIGATIONS: dict[str, list[str]] = {
    "subliminal_manipulation":          ["ART05-PRO-1a"],
    "vulnerability_exploitation":       ["ART05-PRO-1b"],
    "social_scoring":                   ["ART05-PRO-1c"],
    "criminal_profiling":               ["ART05-PRO-1d"],
    "biometric_surveillance":           ["ART05-PRO-1e", "ART05-PRO-1g"],
    "prohibited_emotion_recognition":   ["ART05-PRO-1f"],
    "prohibited_real_time_biometrics":  ["ART05-PRO-1h"],
}

# Human-readable labels for each practice (used in descriptions)
_PRACTICE_LABELS: dict[str, str] = {
    "subliminal_manipulation":         "subliminal / manipulative techniques (Art. 5(1)(a))",
    "vulnerability_exploitation":      "exploitation of age, disability, or socioeconomic vulnerability (Art. 5(1)(b))",
    "social_scoring":                  "social scoring (Art. 5(1)(c))",
    "criminal_profiling":              "criminal risk assessment from profiling/personality traits alone (Art. 5(1)(d))",
    "biometric_surveillance":          "biometric surveillance — facial scraping (Art. 5(1)(e)) / categorization (Art. 5(1)(g))",
    "prohibited_emotion_recognition":  "prohibited emotion recognition in workplace/education (Art. 5(1)(f))",
    "prohibited_real_time_biometrics": "real-time remote biometric identification in public spaces (Art. 5(1)(h))",
}

# All expected practices; used to generate UNABLE_TO_DETERMINE findings when AI provides none
_EXPECTED_PRACTICES = list(_PRACTICE_TO_OBLIGATIONS.keys())


class Art05Module(BaseArticleModule):
    """Article 5: Prohibited AI Practices compliance module.

    Art. 5 defines absolute prohibitions. detected=True means the AI found
    evidence of the practice — this is NON_COMPLIANT (a violation signal).
    detected=False means the AI found no evidence — this is COMPLIANT.
    detected=None means the AI could not determine — UNABLE_TO_DETERMINE.
    """

    def __init__(self):
        super().__init__(
            module_dir=os.path.dirname(os.path.abspath(__file__)),
            article_number=5,
            article_title="Prohibited AI Practices",
        )

    def scan(self, project_path: str) -> ScanResult:
        """Scan a project for prohibited AI practices using AI-provided answers.

        Reads compliance_answers["art5"] from the AI context. Each answer entry
        maps a detected practice to one or more obligation IDs. Because Art. 5
        defines prohibitions, a positive detection (detected=True) yields
        NON_COMPLIANT rather than COMPLIANT.

        Args:
            project_path: Absolute path to the project directory to scan.

        Returns:
            ScanResult with findings for each practice.
        """
        project_path = os.path.abspath(project_path)
        ctx = self._effective_ctx(project_path)
        na = self._scope_gate(ctx, project_path)
        if na:
            return na
        index = self._build_index(project_path)
        language = self._detect_language(project_path)
        file_count = index.source_file_count
        findings: list[Finding] = self._ctx_warnings(ctx)

        answers = ctx.get_article_answers("art5")

        # ── Unified _finding_from_answer() pattern (same as Art.9-15) ──
        # Art.5 is a prohibition: detected=true → violation, detected=false → compliant
        # We invert the answer so _finding_from_answer works correctly:
        #   not False = True → true path (COMPLIANT via true_level)
        #   not True = False → false path (NON_COMPLIANT)
        #   not None = kept as None → UTD path

        # Field → obligation mapping (same structure as Art.12's pattern)
        _PROHIBITION_FIELDS = [
            ("has_subliminal_manipulation",      "ART05-PRO-1a", "subliminal / manipulative techniques (Art. 5(1)(a))"),
            ("has_exploitation_of_vulnerabilities", "ART05-PRO-1b", "exploitation of age, disability, or socioeconomic vulnerability (Art. 5(1)(b))"),
            ("has_social_scoring",               "ART05-PRO-1c", "social scoring (Art. 5(1)(c))"),
            ("has_predictive_policing",          "ART05-PRO-1d", "criminal risk assessment from profiling (Art. 5(1)(d))"),
            ("has_facial_recognition_scraping",  "ART05-PRO-1e", "untargeted facial image scraping (Art. 5(1)(e))"),
            ("has_emotion_recognition_workplace","ART05-PRO-1f", "emotion recognition in workplace/education (Art. 5(1)(f))"),
            ("has_biometric_categorization",     "ART05-PRO-1g", "biometric categorization for sensitive attributes (Art. 5(1)(g))"),
            ("has_real_time_biometric_id",       "ART05-PRO-1h", "real-time remote biometric identification (Art. 5(1)(h))"),
        ]

        for field_name, obl_id, label in _PROHIBITION_FIELDS:
            detected = answers.get(field_name)  # True | False | None
            evidence_field = answers.get(field_name.replace("has_", "") + "_evidence", "")
            evidence_list = [evidence_field] if evidence_field else []

            # Invert for _finding_from_answer: not-detected = compliant
            inverted = None if detected is None else (not detected)

            findings.append(self._finding_from_answer(
                obligation_id=obl_id,
                answer=inverted,
                true_description=f"No {label} detected.",
                false_description=(
                    f"[REQUIRES LEGAL REVIEW] AI detected patterns consistent with {label}. "
                    "Verify with legal counsel — code presence alone does not constitute a violation."
                ),
                none_description=(
                    f"AI could not determine whether {label} is present. "
                    "Manual legal review required."
                ),
                true_level=ComplianceLevel.COMPLIANT,  # Not PARTIAL — prohibition absence is definitive
                evidence=evidence_list or None,
                gap_type=GapType.CODE,
            ))

        details = {
            "scan_type": "ai_compliance_answers",
            "note": (
                "Art. 5 defines ABSOLUTE PROHIBITIONS. detected=false means no prohibited "
                "practice found (COMPLIANT). detected=true means a signal was found "
                "(NON_COMPLIANT — requires legal review). A clean scan does NOT guarantee compliance."
            ),
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
            article_number=5,
            article_title="Prohibited AI Practices",
            project_path=project_path,
            scan_date=datetime.now(timezone.utc).isoformat(),
            files_scanned=file_count,
            language_detected=language,
            overall_level=self._compute_overall_level(findings),
            overall_confidence=Confidence.MEDIUM,
            findings=findings,
            details=details,
        )

    def explain(self) -> Explanation:
        """Explain what Article 5 prohibits in plain language.

        Returns:
            Explanation with full details of all prohibited practices,
            exceptions, and enforcement information.
        """
        return Explanation(
            article_number=5,
            article_title="Prohibited AI Practices",
            one_sentence=(
                "Article 5 defines AI practices that are completely BANNED in the EU, "
                "including social scoring, real-time biometric surveillance (with narrow "
                "law enforcement exceptions), workplace emotion recognition, and AI that "
                "manipulates or exploits vulnerable groups."
            ),
            official_summary=(
                "Art. 5 establishes a list of AI practices that are prohibited outright. "
                "These include: (a) AI using subliminal or manipulative techniques causing "
                "significant harm; (b) AI exploiting vulnerabilities of specific groups; "
                "(c) social scoring systems leading to detrimental treatment; "
                "(d) individual criminal risk assessment based solely on profiling; "
                "(e) untargeted scraping of facial images to build recognition databases; "
                "(f) emotion recognition in workplaces and educational institutions "
                "(except for medical/safety); (g) biometric categorization to infer "
                "sensitive attributes (race, political opinions, etc.); "
                "(h) real-time remote biometric identification in public spaces for "
                "law enforcement (except in three narrowly defined situations with "
                "judicial authorization)."
            ),
            related_articles={
                "Art. 6": "Classification of high-risk AI systems (systems not banned by Art. 5 may still be high-risk)",
                "Art. 99(1)": "Penalties: fines up to EUR 35 million or 7% of global annual turnover for Art. 5 violations",
                "Annex II": "List of criminal offences for which Art. 5(1)(h) exception may apply",
                "Art. 5(2)-(7)": "Detailed conditions for the law enforcement biometric ID exception",
                "Recital 29": "Legislative intent: manipulation through subliminal techniques",
                "Recital 31": "Legislative intent: social scoring prohibition scope",
                "Recital 33": "Legislative intent: emotion recognition restrictions",
                "Recital 44": "Legislative intent: biometric categorization restrictions",
            },
            recital=(
                "Recitals 29-44 provide the legislative intent behind Art. 5 prohibitions. "
                "Key themes: (1) protecting human autonomy and dignity against manipulation; "
                "(2) preventing discriminatory profiling; (3) safeguarding fundamental rights "
                "in public spaces; (4) ensuring that AI does not exploit power asymmetries "
                "between deployers and affected persons."
            ),
            automation_summary={
                "fully_automatable": [
                    "Detection of facial recognition library imports",
                    "Detection of emotion recognition library imports",
                    "Detection of web scraping + face detection library combinations",
                    "Detection of social scoring code patterns",
                ],
                "partially_automatable": [
                    "Detection of biometric categorization for sensitive attributes",
                    "Detection of criminal risk profiling patterns",
                    "Detection of subliminal/manipulative technique indicators",
                    "Detection of vulnerable group targeting patterns",
                ],
                "requires_human_judgment": [
                    "Determining if a flagged library is used for a prohibited purpose vs. a legitimate one",
                    "Evaluating if emotion recognition falls under medical/safety exception",
                    "Assessing whether biometric processing infers prohibited sensitive attributes",
                    "Determining if behaviour nudging crosses into prohibited manipulation",
                    "Evaluating whether a scoring system constitutes prohibited social scoring",
                    "Legal assessment of law enforcement biometric ID exception applicability",
                ],
            },
            compliance_checklist_summary=(
                "ComplianceLint Compliance Checklist v0.1 for Art. 5 restates the prohibitions as "
                "checkable requirements. Since Art. 5 prohibitions are clear and absolute "
                "(unlike Art. 12's 'appropriate measures'), the standard primarily: "
                "(1) enumerates each prohibited practice with its exact legal scope; "
                "(2) defines narrow exceptions with required documentation; "
                "(3) provides heuristic code patterns for automated detection; "
                "(4) mandates human legal review for all flagged items. "
                "A clean automated scan is NECESSARY but NOT SUFFICIENT for compliance."
            ),
            enforcement_date="2025-02-02",
            waiting_for=(
                "Art. 5 prohibitions took effect 2025-02-02 (6 months after entry into force). "
                "No harmonized standard needed — the prohibitions are directly applicable. "
                "AI Office guidelines on Art. 5 interpretation may provide additional clarity."
            ),
        )

    def action_plan(self, scan_result: ScanResult) -> ActionPlan:
        """Generate a human action plan based on scan results.

        Because Art. 5 defines prohibitions (not requirements), the action plan
        focuses on investigation and legal review rather than technical remediation.

        Args:
            scan_result: The ScanResult from a previous scan() call.

        Returns:
            ActionPlan with prioritized actions for each flagged practice.
        """
        actions: list[ActionItem] = []
        details = scan_result.details
        detected_practices = details.get("detected_practices", [])

        # Generate actions for each detected practice
        for entry in detected_practices:
            practice_name = entry.get("practice", "")
            label = entry.get("label", practice_name)
            evidence = entry.get("evidence", "")
            evidence_paths = entry.get("evidence_paths", [])

            obl_ids = _PRACTICE_TO_OBLIGATIONS.get(practice_name, [])
            obl_refs = ", ".join(obl_ids)

            files_str = "; ".join(evidence_paths[:5])
            if len(evidence_paths) > 5:
                files_str += f" (and {len(evidence_paths) - 5} more)"

            actions.append(ActionItem(
                priority="CRITICAL",
                article=f"Art. 5 ({obl_refs})",
                action=f"LEGAL REVIEW REQUIRED: AI detected potential {label}",
                details=(
                    f"AI evidence: {evidence or 'see evidence_paths'}. "
                    f"Files: {files_str or 'see scan findings'}. "
                    f"Prohibition: {label}. "
                    "Penalty for violation: up to EUR 35M or 7% global turnover (Art. 99(1))."
                ),
                effort="Depends on scope — minimum 2-4 hours legal review per flagged practice",
                action_type="human_judgment_required",
            ))

        # If no practices detected, still recommend proactive review
        if not detected_practices:
            actions.append(ActionItem(
                priority="MEDIUM",
                article="Art. 5 (all)",
                action="Conduct proactive Art. 5 compliance review",
                details=(
                    "No prohibited practice signals detected by AI. "
                    "However, AI scanning cannot detect all prohibited practices "
                    "(e.g., deployment context, intent, effect on users). "
                    "Conduct a human review of the system's purpose and deployment "
                    "context against all Art. 5 prohibitions."
                ),
                effort="4-8 hours",
                action_type="human_judgment_required",
            ))

        # Always recommend documentation
        actions.append(ActionItem(
            priority="HIGH",
            article="Art. 5 (all)",
            action="Document Art. 5 compliance assessment",
            details=(
                "Create a written record of your Art. 5 compliance assessment. "
                "For each prohibited practice, document: (1) whether the system "
                "could be classified under that practice; (2) if applicable, which "
                "exception applies and the justification; (3) who conducted the "
                "review and when. This documentation is essential for demonstrating "
                "compliance during market surveillance inspections."
            ),
            effort="2-4 hours",
            action_type="human_judgment_required",
        ))

        return ActionPlan(
            article_number=5,
            article_title="Prohibited AI Practices",
            project_path=scan_result.project_path,
            actions=actions,
            disclaimer=(
                "Art. 5 prohibitions are in force since 2025-02-02. Violations carry "
                "the HIGHEST penalties under the EU AI Act (up to EUR 35M or 7% of "
                "global annual turnover). This action plan is based on AI-detected signals "
                "and CANNOT replace legal counsel. All flagged items require "
                "review by a qualified legal professional."
            ),
        )


# Module entry point — used by auto-discovery
def create_module() -> Art05Module:
    return Art05Module()
