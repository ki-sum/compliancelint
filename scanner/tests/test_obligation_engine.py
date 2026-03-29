"""Tests for ObligationEngine."""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.protocol import (
    ProjectIndex, Finding, ComplianceLevel, Confidence, GapType, BaseArticleModule,
)
from core.obligation_engine import ObligationEngine, Obligation


class TestObligationParsing:
    @pytest.fixture
    def art12_obligations(self):
        path = os.path.join(os.path.dirname(__file__), "..", "obligations", "art12-record-keeping.json")
        with open(path, "r") as f:
            return json.load(f)

    def test_loads_obligations(self, art12_obligations):
        engine = ObligationEngine(art12_obligations)
        assert len(engine.obligations) == 11

    def test_obligation_has_required_fields(self, art12_obligations):
        engine = ObligationEngine(art12_obligations)
        for obl in engine.obligations:
            assert obl.id
            assert obl.source
            assert obl.source_quote
            assert obl.modality in ("shall", "shall not", "may")

    def test_get_obligation_by_id(self, art12_obligations):
        engine = ObligationEngine(art12_obligations)
        obl = engine.get_obligation("ART12-OBL-1")
        assert obl is not None
        assert obl.source == "Art. 12(1)"

    def test_get_nonexistent_obligation(self, art12_obligations):
        engine = ObligationEngine(art12_obligations)
        obl = engine.get_obligation("NONEXISTENT")
        assert obl is None

    def test_automatable_vs_manual(self, art12_obligations):
        engine = ObligationEngine(art12_obligations)
        auto = engine.automatable_obligations()
        manual = engine.manual_obligations()
        assert len(auto) + len(manual) == len(engine.obligations)


class TestCoverageGaps:
    @pytest.fixture
    def art12_obligations(self):
        path = os.path.join(os.path.dirname(__file__), "..", "obligations", "art12-record-keeping.json")
        with open(path, "r") as f:
            return json.load(f)

    def test_full_coverage_no_gaps(self, art12_obligations):
        engine = ObligationEngine(art12_obligations)
        # Create findings covering all obligations
        findings = [
            Finding(obligation_id=obl.id, file_path="test.py", line_number=None,
                    level=ComplianceLevel.COMPLIANT, confidence=Confidence.HIGH,
                    description="test")
            for obl in engine.obligations
        ]
        gaps = engine.coverage_gaps(findings)
        assert len(gaps) == 0

    def test_missing_coverage_shows_gaps(self, art12_obligations):
        engine = ObligationEngine(art12_obligations)
        # Only cover first obligation
        findings = [
            Finding(obligation_id=engine.obligations[0].id, file_path="test.py",
                    line_number=None, level=ComplianceLevel.COMPLIANT,
                    confidence=Confidence.HIGH, description="test")
        ]
        gaps = engine.coverage_gaps(findings)
        assert len(gaps) == len(engine.obligations) - 1


class TestEnrichFinding:
    @pytest.fixture
    def art12_obligations(self):
        path = os.path.join(os.path.dirname(__file__), "..", "obligations", "art12-record-keeping.json")
        with open(path, "r") as f:
            return json.load(f)

    def test_enriches_with_source_quote(self, art12_obligations):
        engine = ObligationEngine(art12_obligations)
        finding = Finding(
            obligation_id="ART12-OBL-1", file_path="test.py", line_number=None,
            level=ComplianceLevel.COMPLIANT, confidence=Confidence.HIGH,
            description="Logging detected",
        )
        enriched = engine.enrich_finding(finding)
        # Description should contain AI analysis (not legal citation — that's in source_quote)
        assert enriched.description == "Logging detected"
        # source_quote should have the legal text
        assert "automatic recording" in enriched.source_quote.lower()

    def test_no_double_enrich(self, art12_obligations):
        engine = ObligationEngine(art12_obligations)
        finding = Finding(
            obligation_id="ART12-OBL-1", file_path="test.py", line_number=None,
            level=ComplianceLevel.COMPLIANT, confidence=Confidence.HIGH,
            description="[Art. 12(1)] Already enriched",
        )
        enriched = engine.enrich_finding(finding)
        # Should not double-prefix
        assert enriched.description.count("[Art. 12(1)]") == 1


class TestAllObligationFiles:
    def test_all_obligation_files_load(self):
        """Every obligation JSON should parse and have at least 1 obligation."""
        obligations_dir = os.path.join(os.path.dirname(__file__), "..", "obligations")
        files = [f for f in os.listdir(obligations_dir) if f.endswith(".json")]
        assert len(files) >= 25, f"Expected at least 25 obligation files, found {len(files)}"
        for fname in files:
            path = os.path.join(obligations_dir, fname)
            with open(path, "r") as f:
                data = json.load(f)
            engine = ObligationEngine(data)
            assert len(engine.obligations) > 0, f"{fname} has no obligations"

    def test_total_obligations_at_least_247(self):
        """Total across all obligation files should be at least 247."""
        obligations_dir = os.path.join(os.path.dirname(__file__), "..", "obligations")
        total = 0
        for fname in os.listdir(obligations_dir):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(obligations_dir, fname), "r") as f:
                data = json.load(f)
            total += len(data.get("obligations", []))
        assert total >= 247, f"Expected at least 247 obligations, found {total}"
