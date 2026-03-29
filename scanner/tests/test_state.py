"""Tests for state.json persistence layer (per-article file architecture)."""
import json
import os
import sys
import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.state import load_state, save_article_result, update_finding, export_report


@pytest.fixture
def project_dir(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')")
    return str(tmp_path)


@pytest.fixture
def scan_result():
    return {
        "overall_level": "non_compliant",
        "overall_confidence": "medium",
        "assessed_by": "test-model",
        "findings": [
            {"obligation_id": "ART12-OBL-1", "level": "non_compliant",
             "confidence": "medium", "description": "No logging found.",
             "remediation": "Install structlog."},
            {"obligation_id": "ART12-OBL-2a", "level": "partial",
             "confidence": "medium", "description": "Some logging found."},
        ],
    }


class TestLoadState:
    def test_empty_project_returns_empty_state(self, project_dir):
        state = load_state(project_dir)
        assert state["project_path"] == project_dir
        assert state["articles"] == {}
        assert state["overall_compliance"] == "no_data"

    def test_load_merges_article_files(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        save_article_result(project_dir, 9, {
            "overall_level": "partial", "findings": [
                {"obligation_id": "ART09-OBL-1", "level": "partial",
                 "confidence": "medium", "description": "Risk docs found."},
            ],
        })
        state = load_state(project_dir)
        assert "art12" in state["articles"]
        assert "art9" in state["articles"]

    def test_overall_compliance_computed(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        state = load_state(project_dir)
        assert state["overall_compliance"] == "non_compliant"


class TestSaveArticleResult:
    def test_creates_per_article_file(self, project_dir, scan_result):
        path = save_article_result(project_dir, 12, scan_result)
        assert path is not None
        assert path.endswith("art12.json")
        assert os.path.isfile(path)

    def test_findings_stored_correctly(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        state = load_state(project_dir)
        art12 = state["articles"]["art12"]
        assert art12["overall_level"] == "non_compliant"
        assert "ART12-OBL-1" in art12["findings"]
        assert art12["findings"]["ART12-OBL-1"]["level"] == "non_compliant"
        assert art12["findings"]["ART12-OBL-1"]["baselineState"] == "new"

    def test_description_not_truncated(self, project_dir, scan_result):
        """Full descriptions preserved (not truncated to 500 chars)."""
        long_desc = "x" * 1000
        scan_result["findings"][0]["description"] = long_desc
        save_article_result(project_dir, 12, scan_result)
        state = load_state(project_dir)
        stored = state["articles"]["art12"]["findings"]["ART12-OBL-1"]["description"]
        assert len(stored) == 1000

    def test_remediation_stored(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        state = load_state(project_dir)
        f = state["articles"]["art12"]["findings"]["ART12-OBL-1"]
        assert f["remediation"] == "Install structlog."

    def test_second_scan_updates_baseline(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        save_article_result(project_dir, 12, scan_result)
        state = load_state(project_dir)
        assert state["articles"]["art12"]["findings"]["ART12-OBL-1"]["baselineState"] == "unchanged"

    def test_changed_level_marks_updated(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        scan_result["findings"][0]["level"] = "partial"
        save_article_result(project_dir, 12, scan_result)
        state = load_state(project_dir)
        assert state["articles"]["art12"]["findings"]["ART12-OBL-1"]["baselineState"] == "updated"

    def test_absent_finding_marked(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        scan_result["findings"] = [scan_result["findings"][0]]
        save_article_result(project_dir, 12, scan_result)
        state = load_state(project_dir)
        assert state["articles"]["art12"]["findings"]["ART12-OBL-2a"]["baselineState"] == "absent"

    def test_preserves_user_evidence(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        update_finding(project_dir, "ART12-OBL-1", "provide_evidence",
                      evidence_type="url", evidence_value="https://example.com/policy")
        save_article_result(project_dir, 12, scan_result)
        state = load_state(project_dir)
        ev = state["articles"]["art12"]["findings"]["ART12-OBL-1"]["evidence"]
        assert len(ev) == 1
        assert ev[0]["value"] == "https://example.com/policy"

    def test_preserves_user_suppression(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        update_finding(project_dir, "ART12-OBL-1", "rebut",
                      justification="We are not an AI system")
        save_article_result(project_dir, 12, scan_result)
        state = load_state(project_dir)
        supp = state["articles"]["art12"]["findings"]["ART12-OBL-1"]["suppression"]
        assert supp["justification"] == "We are not an AI system"

    def test_creates_baseline_snapshot(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        baselines_dir = os.path.join(project_dir, ".compliancelint", "baselines")
        assert os.path.isdir(baselines_dir)
        assert len(os.listdir(baselines_dir)) >= 1

    def test_baseline_cleanup_keeps_max_20(self, project_dir, scan_result):
        """Baseline snapshots capped at 20."""
        for _ in range(25):
            save_article_result(project_dir, 12, scan_result)
        baselines_dir = os.path.join(project_dir, ".compliancelint", "baselines")
        assert len(os.listdir(baselines_dir)) <= 20

    def test_concurrent_different_articles_safe(self, project_dir, scan_result):
        """Different articles write to different files — no conflict."""
        save_article_result(project_dir, 12, scan_result)
        save_article_result(project_dir, 9, {
            "overall_level": "partial", "findings": [
                {"obligation_id": "ART09-OBL-1", "level": "partial",
                 "confidence": "medium", "description": "Found."},
            ],
        })
        state = load_state(project_dir)
        assert "art12" in state["articles"]
        assert "art9" in state["articles"]
        assert state["articles"]["art12"]["findings"]["ART12-OBL-1"]["level"] == "non_compliant"
        assert state["articles"]["art9"]["findings"]["ART09-OBL-1"]["level"] == "partial"

    def test_merged_state_json_created(self, project_dir, scan_result):
        """Merged state.json is created for convenience."""
        save_article_result(project_dir, 12, scan_result)
        merged = os.path.join(project_dir, ".compliancelint", "state.json")
        assert os.path.isfile(merged)
        with open(merged) as f:
            data = json.load(f)
        assert "art12" in data["articles"]


class TestOverallCompliance:
    def test_all_compliant(self, project_dir):
        save_article_result(project_dir, 12, {
            "overall_level": "compliant", "findings": []})
        save_article_result(project_dir, 9, {
            "overall_level": "not_applicable", "findings": []})
        state = load_state(project_dir)
        assert state["overall_compliance"] == "compliant"

    def test_any_non_compliant(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)  # non_compliant
        save_article_result(project_dir, 9, {
            "overall_level": "partial", "findings": []})
        state = load_state(project_dir)
        assert state["overall_compliance"] == "non_compliant"

    def test_partial_without_non_compliant(self, project_dir):
        save_article_result(project_dir, 12, {
            "overall_level": "partial", "findings": []})
        save_article_result(project_dir, 9, {
            "overall_level": "compliant", "findings": []})
        state = load_state(project_dir)
        assert state["overall_compliance"] == "partial"


class TestUpdateFinding:
    def test_provide_evidence(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        result = update_finding(project_dir, "ART12-OBL-1", "provide_evidence",
                               evidence_type="file", evidence_value="docs/risk.md")
        assert result["status"] == "updated"
        state = load_state(project_dir)
        f = state["articles"]["art12"]["findings"]["ART12-OBL-1"]
        assert f["status"] == "evidence_provided"
        assert len(f["evidence"]) == 1

    def test_rebut(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        result = update_finding(project_dir, "ART12-OBL-1", "rebut",
                               justification="Not applicable")
        assert result["status"] == "updated"
        state = load_state(project_dir)
        f = state["articles"]["art12"]["findings"]["ART12-OBL-1"]
        assert f["status"] == "rebutted"
        assert f["suppression"]["status"] == "underReview"

    def test_acknowledge(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        result = update_finding(project_dir, "ART12-OBL-1", "acknowledge")
        assert result["status"] == "updated"

    def test_defer(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        result = update_finding(project_dir, "ART12-OBL-1", "defer")
        assert result["status"] == "updated"

    def test_nonexistent_returns_error(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        result = update_finding(project_dir, "ART99-OBL-1", "acknowledge")
        assert "error" in result

    def test_unknown_action_returns_error(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        result = update_finding(project_dir, "ART12-OBL-1", "invalid")
        assert "error" in result

    def test_history_tracked(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        update_finding(project_dir, "ART12-OBL-1", "acknowledge")
        update_finding(project_dir, "ART12-OBL-1", "provide_evidence",
                      evidence_type="text", evidence_value="Fixed")
        state = load_state(project_dir)
        history = state["articles"]["art12"]["findings"]["ART12-OBL-1"]["history"]
        assert len(history) >= 3


class TestExportReport:
    def test_markdown_export(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        result = export_report(project_dir, fmt="md")
        assert "path" in result
        assert "# EU AI Act Compliance Report" in result["content"]
        assert "ART12-OBL-1" in result["content"]
        assert "NON_COMPLIANT" in result["content"]

    def test_markdown_includes_details(self, project_dir, scan_result):
        """Markdown report includes descriptions and remediation."""
        save_article_result(project_dir, 12, scan_result)
        result = export_report(project_dir, fmt="md")
        assert "No logging found" in result["content"]
        assert "Install structlog" in result["content"]

    def test_markdown_includes_evidence(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        update_finding(project_dir, "ART12-OBL-1", "provide_evidence",
                      evidence_type="url", evidence_value="https://example.com")
        result = export_report(project_dir, fmt="md")
        assert "https://example.com" in result["content"]

    def test_markdown_includes_overall(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        result = export_report(project_dir, fmt="md")
        assert "NON_COMPLIANT" in result["content"]

    def test_json_export(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        result = export_report(project_dir, fmt="json")
        data = json.loads(result["content"])
        assert "articles" in data
        assert "overall_compliance" in data

    def test_no_state_returns_error(self, project_dir):
        result = export_report(project_dir, fmt="md")
        assert "error" in result

    def test_unknown_format_returns_error(self, project_dir, scan_result):
        save_article_result(project_dir, 12, scan_result)
        result = export_report(project_dir, fmt="pdf")
        assert "error" in result
