"""§AT.19 Phase 2d (2026-05-13) — Approach (b) post-process test.

Pins: hybrid obligations (`automation_level == "partial"`) ALWAYS get
rewritten to UTD + HG hint regardless of what the module's scan() said.
AI cannot reliably judge the legal-interpretation half of a hybrid
obligation. Final attestation must come from user via cl_update_finding
or SaaS HG wizard.

Scope:
- HYBRID findings: rewritten to UTD + HG hint + low confidence
- CODE (full) findings: untouched — AI is authoritative for code detection
- MANUAL findings: untouched — gap_findings already emits UTD + HG hint
- UNKNOWN obligations: untouched (defensive — don't break anything)
"""
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from server import _apply_approach_b_post_process  # noqa: E402


class TestPostProcessRewritesHybrid:
    """Hybrid obligations get rewritten regardless of original status."""

    def test_hybrid_COMPLIANT_becomes_UTD_plus_HG_hint(self):
        """AI thought ART50-OBL-3 (hybrid) was COMPLIANT. Post-process
        rewrites to UTD because hybrid needs human attestation."""
        findings = [
            {
                "obligation_id": "ART50-OBL-3",  # type=hybrid in classification.json
                "level": "compliant",
                "description": "AI detected disclosure in src/api.py",
                "confidence": "high",
            },
        ]
        _apply_approach_b_post_process(findings)
        assert findings[0]["level"] == "unable_to_determine"
        assert "Human Gates" in findings[0]["human_gate_hint"]
        assert "ART50-OBL-3" in findings[0]["human_gate_hint"]
        assert findings[0]["confidence"] == "low"
        assert "HYBRID" in findings[0]["description"]

    def test_hybrid_NON_COMPLIANT_also_becomes_UTD(self):
        findings = [
            {
                "obligation_id": "ART50-OBL-3",
                "level": "non_compliant",
                "description": "AI: no disclosure found",
                "confidence": "high",
            },
        ]
        _apply_approach_b_post_process(findings)
        assert findings[0]["level"] == "unable_to_determine"
        assert "human_gate_hint" in findings[0]

    def test_hybrid_NOT_APPLICABLE_preserved(self):
        """§AT.19 root cause fix (2026-05-14) — NA emitted by scanner
        modules is deterministic (driven by context_skip_field /
        prerequisites matching the user's profile), NOT AI variance.

        Pre-fix this rewrote NA → UTD, causing non-high-risk providers
        to see Art 41/43/47/49/60/61/71/72/73/82/86/111 as "needs
        Human Gate" attestation in the dashboard. The articles should
        stay NA because the user's profile structurally excludes them.

        Variance elimination (test_three_AI_runs_on_hybrid_OID_*)
        still fires for C/NC/UTD where AI judgment legitimately
        fluctuates between scans.
        """
        findings = [
            {
                "obligation_id": "ART50-OBL-3",
                "level": "not_applicable",
                "description": "Skipped: user profile excludes emotion system",
            },
        ]
        _apply_approach_b_post_process(findings)
        assert findings[0]["level"] == "not_applicable", (
            "NA must be preserved — scanner modules' deterministic NA "
            "decisions are not AI variance"
        )
        # Description should NOT be rewritten either — preserve scanner intent.
        assert "Skipped" in findings[0]["description"]
        # No HG hint should be added — NA means it doesn't apply at all.
        assert "human_gate_hint" not in findings[0]


class TestPostProcessLeavesCodeAndManualAlone:
    """Non-hybrid findings should not be touched."""

    def test_code_obligation_COMPLIANT_untouched(self):
        """ART50-OBL-1 is type=code. Scanner is authoritative."""
        findings = [
            {
                "obligation_id": "ART50-OBL-1",  # type=code
                "level": "compliant",
                "description": "AI detected chatbot + disclosure",
                "confidence": "high",
            },
        ]
        _apply_approach_b_post_process(findings)
        assert findings[0]["level"] == "compliant"
        assert findings[0]["confidence"] == "high"
        assert "HYBRID" not in findings[0].get("description", "")

    def test_human_obligation_untouched(self):
        """ART50-OBL-6 (saving clause) is type=human. gap_findings already
        emits UTD + HG. Post-process should NOT touch it."""
        findings = [
            {
                "obligation_id": "ART50-OBL-6",  # type=human
                "level": "unable_to_determine",
                "description": "[COVERAGE GAP — manual] Art. 50(6)",
                "human_gate_hint": "Complete this Human Gate at compliancelint.dev/dashboard → Human Gates",
            },
        ]
        before = dict(findings[0])
        _apply_approach_b_post_process(findings)
        assert findings[0]["level"] == before["level"]
        assert findings[0]["description"] == before["description"]


class TestPostProcessHandlesEdgeCases:
    """Defensive: malformed input / unknown OIDs don't crash."""

    def test_unknown_obligation_id_untouched(self):
        findings = [
            {
                "obligation_id": "ART999-OBL-999",
                "level": "compliant",
                "description": "test",
            },
        ]
        _apply_approach_b_post_process(findings)
        # No mutation — lookup_obligation returns None, post-process skips.
        assert findings[0]["level"] == "compliant"

    def test_missing_obligation_id_skipped(self):
        findings = [
            {
                "level": "compliant",
                "description": "no obligation_id",
            },
        ]
        _apply_approach_b_post_process(findings)
        # Should not crash; finding untouched.
        assert findings[0]["level"] == "compliant"

    def test_non_dict_finding_skipped(self):
        findings = [
            "this is not a dict",
            {"obligation_id": "ART50-OBL-3", "level": "compliant"},
        ]
        _apply_approach_b_post_process(findings)
        # The dict one gets processed; the string is silently skipped.
        assert findings[0] == "this is not a dict"
        assert findings[1]["level"] == "unable_to_determine"

    def test_empty_list(self):
        findings: list = []
        result = _apply_approach_b_post_process(findings)
        assert result == []


class TestPostProcessVarianceElimination:
    """The Bug 2 fix: hybrid findings collapse to deterministic UTD
    regardless of what the underlying AI guess was on each scan run."""

    def test_three_AI_runs_on_hybrid_OID_all_collapse_to_UTD(self):
        """Simulate AI run-1 said COMPLIANT, run-2 said NC, run-3 said UTD.
        Post-process makes all three identical UTD outcomes.

        Excludes NA — NA is a deterministic context-skip decision (not
        AI variance) and is intentionally preserved (see
        test_hybrid_NOT_APPLICABLE_preserved).
        """
        runs = []
        for original_level in ("compliant", "non_compliant", "unable_to_determine"):
            findings = [
                {
                    "obligation_id": "ART50-OBL-3",
                    "level": original_level,
                    "description": f"AI run with level={original_level}",
                    "confidence": "high",
                },
            ]
            _apply_approach_b_post_process(findings)
            runs.append((findings[0]["level"], findings[0]["confidence"]))
        # All three runs produce identical post-process state.
        assert runs[0] == runs[1] == runs[2]
        assert runs[0] == ("unable_to_determine", "low")

    def test_three_scans_all_emit_NA_preserve_NA(self):
        """§AT.19 root cause fix (2026-05-14) — three scans against the
        same hybrid obligation that all emit NA (because the user's
        profile structurally excludes the obligation) MUST preserve NA
        across all three runs. This is determinism in the OPPOSITE
        direction from the C/NC/UTD variance — NA is already
        deterministic, post-process must not perturb it.
        """
        runs = []
        for description in (
            "Skipped: not_high_risk_provider",
            "Skipped: not_high_risk_provider",
            "Skipped: not_high_risk_provider",
        ):
            findings = [
                {
                    "obligation_id": "ART50-OBL-3",
                    "level": "not_applicable",
                    "description": description,
                },
            ]
            _apply_approach_b_post_process(findings)
            runs.append(findings[0]["level"])
        assert runs == ["not_applicable", "not_applicable", "not_applicable"]
