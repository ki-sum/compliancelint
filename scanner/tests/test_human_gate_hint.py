"""Tests for human_gate_hint field on manual obligation findings.

Verifies that the obligation engine adds human_gate_hint to all
manual obligation findings (automation_level="manual"), directing
users to the SaaS dashboard to complete Human Gates.
"""
import json
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.obligation_engine import ObligationEngine
from core.protocol import Finding, ComplianceLevel


class TestHumanGateHintInObligationEngine:

    def test_manual_obligations_have_hint(self):
        """All manual obligations from the engine get human_gate_hint."""
        # Load Art. 26 obligations (known to have manual ones)
        obligations_dir = os.path.join(SCANNER_ROOT, "obligations")
        art26_path = os.path.join(obligations_dir, "art26.json")
        if not os.path.exists(art26_path):
            return  # Skip if obligation file not present

        with open(art26_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        engine = ObligationEngine(data.get("obligations", []))

        # Get gap findings (no scan details → all obligations appear as gaps)
        from core.protocol import ProjectIndex
        idx = ProjectIndex(files=[], metadata={})
        findings = engine.gap_findings([], idx)

        manual_findings = [
            f for f in findings
            if "manual" in (f.description or "").lower()
            or "COVERAGE GAP — manual" in (f.description or "")
        ]

        for finding in manual_findings:
            assert finding.human_gate_hint is not None, (
                f"{finding.obligation_id} is manual but has no human_gate_hint"
            )
            assert "compliancelint.dev" in finding.human_gate_hint

    def test_non_manual_gap_findings_no_hint(self):
        """Non-manual gap findings should NOT have human_gate_hint."""
        obligations_dir = os.path.join(SCANNER_ROOT, "obligations")
        art12_path = os.path.join(obligations_dir, "art12.json")
        if not os.path.exists(art12_path):
            return

        with open(art12_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        engine = ObligationEngine(data.get("obligations", []))
        from core.protocol import ProjectIndex
        idx = ProjectIndex(files=[], metadata={})
        findings = engine.gap_findings([], idx)

        non_manual_gaps = [
            f for f in findings
            if "[COVERAGE GAP]" in (f.description or "")
            and "[COVERAGE GAP — manual]" not in (f.description or "")
        ]

        for finding in non_manual_gaps:
            assert finding.human_gate_hint is None, (
                f"{finding.obligation_id} is not manual but has human_gate_hint"
            )


class TestFindingToDict:

    def test_human_gate_hint_in_to_dict(self):
        """human_gate_hint should appear in finding.to_dict() output."""
        finding = Finding(
            obligation_id="ART26-OBL-2",
            file_path="project-wide",
            line_number=None,
            level=ComplianceLevel.UNABLE_TO_DETERMINE,
            confidence=ComplianceLevel.UNABLE_TO_DETERMINE,  # wrong but doesn't matter for this test
            description="Manual",
            human_gate_hint="Complete at dashboard",
        )
        d = finding.to_dict()
        assert "human_gate_hint" in d
        assert d["human_gate_hint"] == "Complete at dashboard"

    def test_no_hint_in_to_dict(self):
        """Findings without human_gate_hint should have None."""
        finding = Finding(
            obligation_id="ART12-OBL-1",
            file_path="src/app.py",
            line_number=42,
            level=ComplianceLevel.COMPLIANT,
            confidence=ComplianceLevel.COMPLIANT,
            description="Logging found",
        )
        d = finding.to_dict()
        assert d.get("human_gate_hint") is None
