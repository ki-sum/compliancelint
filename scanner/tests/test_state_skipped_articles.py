"""Tests for state saving of skipped (not-high-risk) articles.

When cl_scan_all skips Art. 9-15 because the project is not high-risk,
those articles should still be saved to state with overall_level = "not_applicable".
"""
import json
import os
import sys
import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.state import load_state, save_article_result
from core.protocol import (
    ScanResult,
    Finding,
    ComplianceLevel,
    Confidence,
)

ALL_ARTICLES = [5, 6, 9, 10, 11, 12, 13, 14, 15, 50]
HIGH_RISK_ONLY = [9, 10, 11, 12, 13, 14, 15]


@pytest.fixture
def project_dir(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')")
    return str(tmp_path)


def _make_skip_result(art_num: int) -> dict:
    """Create a ScanResult dict for a skipped (not-high-risk) article."""
    result = ScanResult(
        article_number=art_num,
        article_title=f"Article {art_num}",
        project_path="/tmp/test",
        scan_date="2026-03-26T00:00:00+00:00",
        files_scanned=0,
        language_detected="python",
        overall_level=ComplianceLevel.NOT_APPLICABLE,
        overall_confidence=Confidence.HIGH,
        findings=[
            Finding(
                obligation_id=f"ART{art_num:02d}-NOT-APPLICABLE",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.HIGH,
                description=(
                    f"Art. {art_num} applies only to high-risk AI systems. "
                    "AI classification: 'not high-risk' (confidence: high). "
                    "This article scan is skipped."
                ),
                remediation="Override via .compliancelintrc if incorrect.",
            )
        ],
        details={
            "skip_reason": "not_high_risk_system",
            "risk_classification": "not high-risk",
        },
    )
    return result.to_dict()


def _make_normal_result(art_num: int, level: str = "compliant") -> dict:
    """Create a simple scan result for a non-skipped article."""
    return {
        "overall_level": level,
        "overall_confidence": "high",
        "assessed_by": "test-model",
        "findings": [
            {
                "obligation_id": f"ART{art_num:02d}-OBL-1",
                "level": level,
                "confidence": "high",
                "description": f"Test finding for Art. {art_num}",
            }
        ],
    }


class TestSkippedArticleStateSaving:
    def test_skipped_article_saved_to_state(self, project_dir):
        """A skipped article should produce a state file."""
        result = _make_skip_result(12)
        path = save_article_result(project_dir, 12, result)
        assert path is not None
        assert os.path.isfile(path)

    def test_skipped_article_overall_level_is_not_applicable(self, project_dir):
        """Skipped article's overall_level should be 'not_applicable'."""
        save_article_result(project_dir, 14, _make_skip_result(14))
        state = load_state(project_dir)
        art14 = state["articles"]["art14"]
        assert art14["overall_level"] == "not_applicable"

    def test_skipped_article_has_single_finding(self, project_dir):
        """Skipped article should have exactly one NOT-APPLICABLE finding."""
        save_article_result(project_dir, 9, _make_skip_result(9))
        state = load_state(project_dir)
        findings = state["articles"]["art9"]["findings"]
        assert len(findings) == 1
        obl_id = list(findings.keys())[0]
        assert "NOT-APPLICABLE" in obl_id
        assert findings[obl_id]["level"] == "not_applicable"

    def test_all_10_articles_present_in_state(self, project_dir):
        """After scanning all 10 articles (some skipped), state.json has all 10."""
        # Save normal results for non-high-risk articles
        for art in [5, 6, 50]:
            save_article_result(project_dir, art, _make_normal_result(art))

        # Save skipped results for high-risk-only articles
        for art in HIGH_RISK_ONLY:
            save_article_result(project_dir, art, _make_skip_result(art))

        state = load_state(project_dir)
        assert len(state["articles"]) == 10

        for art in ALL_ARTICLES:
            key = f"art{art}"
            assert key in state["articles"], f"{key} missing from state"

    def test_skipped_articles_overall_level_all_not_applicable(self, project_dir):
        """All skipped (high-risk-only) articles have not_applicable level."""
        for art in HIGH_RISK_ONLY:
            save_article_result(project_dir, art, _make_skip_result(art))

        state = load_state(project_dir)
        for art in HIGH_RISK_ONLY:
            key = f"art{art}"
            assert state["articles"][key]["overall_level"] == "not_applicable", (
                f"{key} should be not_applicable"
            )

    def test_state_json_file_created(self, project_dir):
        """state.json merged file should be created after saving."""
        save_article_result(project_dir, 12, _make_skip_result(12))
        state_path = os.path.join(project_dir, ".compliancelint", "state.json")
        assert os.path.isfile(state_path)

        with open(state_path) as f:
            merged = json.load(f)
        assert "art12" in merged["articles"]

    def test_mixed_scan_overall_compliance(self, project_dir):
        """Overall compliance = 'not_applicable' when all non-skipped are compliant
        and skipped are not_applicable."""
        save_article_result(project_dir, 5, _make_normal_result(5, "compliant"))
        save_article_result(project_dir, 6, _make_normal_result(6, "compliant"))
        save_article_result(project_dir, 50, _make_normal_result(50, "compliant"))
        for art in HIGH_RISK_ONLY:
            save_article_result(project_dir, art, _make_skip_result(art))

        state = load_state(project_dir)
        # With 3 compliant + 7 not_applicable, overall should be compliant
        assert state["overall_compliance"] == "compliant"
