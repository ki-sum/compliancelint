"""Tests for attestation functionality — attester identity, update_finding, state persistence."""
import json
import os
import tempfile
import pytest

from core.state import save_article_result, update_finding, load_state
from core.config import ProjectConfig


@pytest.fixture
def project_with_scan(tmp_path):
    """Create a project with one scanned article and a .compliancelintrc."""
    # Create .compliancelintrc with attester
    config = {
        "attester": {
            "name": "Test User",
            "email": "test@example.com",
            "role": "QA Engineer",
        }
    }
    with open(tmp_path / ".compliancelintrc", "w") as f:
        json.dump(config, f)

    # Save a scan result
    scan_result = {
        "overall_level": "partial",
        "overall_confidence": "medium",
        "assessed_by": "test",
        "findings": [
            {
                "obligation_id": "ART09-OBL-1",
                "level": "partial",
                "confidence": "medium",
                "description": "Risk docs found",
                "source_quote": "Test quote",
            },
            {
                "obligation_id": "ART09-OBL-2",
                "level": "non_compliant",
                "confidence": "medium",
                "description": "No risk process",
                "source_quote": "Test quote 2",
            },
        ],
    }
    save_article_result(str(tmp_path), 9, scan_result)
    return tmp_path


class TestAttesterIdentity:
    """Tests for attester identity reading from config."""

    def test_get_attester_from_config(self, project_with_scan):
        config = ProjectConfig.load(str(project_with_scan))
        attester = config.get_attester(str(project_with_scan))
        assert attester is not None
        assert attester["name"] == "Test User"
        assert attester["email"] == "test@example.com"
        assert attester["role"] == "QA Engineer"
        assert attester["source"] == "compliancelintrc"

    def test_get_attester_no_config(self, tmp_path):
        """No .compliancelintrc and no git → returns None or git config."""
        config = ProjectConfig.load(str(tmp_path))
        attester = config.get_attester(str(tmp_path))
        # May return git config or None depending on environment
        if attester is not None:
            assert attester["source"] == "git_config"
            assert attester["name"]  # git config should have a name


class TestUpdateFinding:
    """Tests for update_finding with attester."""

    def test_provide_evidence_records_attester(self, project_with_scan):
        attester = {"name": "Test User", "email": "test@example.com", "role": "QA", "source": "config"}
        result = update_finding(
            project_path=str(project_with_scan),
            obligation_id="ART09-OBL-1",
            action="provide_evidence",
            evidence_type="text",
            evidence_value="Risk management doc reviewed and confirmed complete.",
            attester=attester,
        )
        assert result["status"] == "updated"
        finding = result["finding"]
        assert finding["status"] == "evidence_provided"
        # Check evidence has attester
        assert len(finding["evidence"]) == 1
        ev = finding["evidence"][0]
        assert ev["provided_by"]["name"] == "Test User"
        assert ev["provided_by"]["email"] == "test@example.com"
        # Check history has structured attester
        last_history = finding["history"][-1]
        assert last_history["action"] == "provide_evidence"
        assert last_history["by"]["name"] == "Test User"
        assert last_history["by"]["source"] == "config"

    def test_rebut_records_attester(self, project_with_scan):
        attester = {"name": "CTO", "email": "cto@co.com", "role": "CTO", "source": "config"}
        result = update_finding(
            project_path=str(project_with_scan),
            obligation_id="ART09-OBL-2",
            action="rebut",
            justification="This is a false positive.",
            attester=attester,
        )
        assert result["status"] == "updated"
        finding = result["finding"]
        assert finding["status"] == "rebutted"
        assert finding["suppression"]["submitted_by"]["name"] == "CTO"

    def test_resolve_action(self, project_with_scan):
        attester = {"name": "Dev", "email": "dev@co.com", "role": "Dev", "source": "config"}
        result = update_finding(
            project_path=str(project_with_scan),
            obligation_id="ART09-OBL-2",
            action="resolve",
            evidence_value="Fixed in PR #123",
            attester=attester,
        )
        assert result["status"] == "updated"
        assert result["finding"]["status"] == "resolved"

    def test_acknowledge_action(self, project_with_scan):
        attester = {"name": "PM", "email": "pm@co.com", "role": "PM", "source": "config"}
        result = update_finding(
            project_path=str(project_with_scan),
            obligation_id="ART09-OBL-2",
            action="acknowledge",
            attester=attester,
        )
        assert result["status"] == "updated"
        assert result["finding"]["status"] == "acknowledged"

    def test_defer_action(self, project_with_scan):
        attester = {"name": "PM", "email": "pm@co.com", "role": "PM", "source": "config"}
        result = update_finding(
            project_path=str(project_with_scan),
            obligation_id="ART09-OBL-2",
            action="defer",
            attester=attester,
        )
        assert result["status"] == "updated"
        assert result["finding"]["status"] == "deferred"

    def test_unknown_action_rejected(self, project_with_scan):
        result = update_finding(
            project_path=str(project_with_scan),
            obligation_id="ART09-OBL-1",
            action="invalid_action",
        )
        assert "error" in result

    def test_nonexistent_obligation_rejected(self, project_with_scan):
        result = update_finding(
            project_path=str(project_with_scan),
            obligation_id="ART99-OBL-999",
            action="acknowledge",
        )
        assert "error" in result

    def test_no_scan_data_rejected(self, tmp_path):
        result = update_finding(
            project_path=str(tmp_path),
            obligation_id="ART09-OBL-1",
            action="acknowledge",
        )
        assert "error" in result


class TestAttestationPersistence:
    """Tests for attestation data surviving rescans."""

    def test_rescan_preserves_evidence(self, project_with_scan):
        # First: attest
        attester = {"name": "Test", "email": "t@t.com", "role": "", "source": "config"}
        update_finding(
            project_path=str(project_with_scan),
            obligation_id="ART09-OBL-1",
            action="provide_evidence",
            evidence_type="text",
            evidence_value="Confirmed compliant",
            attester=attester,
        )

        # Verify evidence is there
        state = load_state(str(project_with_scan))
        finding = state["articles"]["art9"]["findings"]["ART09-OBL-1"]
        assert finding["status"] == "evidence_provided"
        assert len(finding["evidence"]) == 1

        # Now rescan (simulates a new scan overwriting)
        new_scan = {
            "overall_level": "partial",
            "overall_confidence": "medium",
            "assessed_by": "test",
            "findings": [
                {"obligation_id": "ART09-OBL-1", "level": "partial", "confidence": "medium", "description": "Updated", "source_quote": "Q"},
                {"obligation_id": "ART09-OBL-2", "level": "non_compliant", "confidence": "medium", "description": "Still NC", "source_quote": "Q2"},
            ],
        }
        save_article_result(str(project_with_scan), 9, new_scan)

        # Verify evidence survives rescan
        state2 = load_state(str(project_with_scan))
        finding2 = state2["articles"]["art9"]["findings"]["ART09-OBL-1"]
        assert finding2["status"] == "evidence_provided"  # preserved!
        assert len(finding2["evidence"]) == 1  # evidence preserved!
        assert finding2["evidence"][0]["value"] == "Confirmed compliant"

    def test_multiple_attestations_append(self, project_with_scan):
        attester1 = {"name": "User1", "email": "u1@co.com", "role": "Dev", "source": "config"}
        attester2 = {"name": "User2", "email": "u2@co.com", "role": "QA", "source": "config"}

        update_finding(str(project_with_scan), "ART09-OBL-1", "provide_evidence", "text", "Evidence 1", attester=attester1)
        update_finding(str(project_with_scan), "ART09-OBL-1", "provide_evidence", "text", "Evidence 2", attester=attester2)

        state = load_state(str(project_with_scan))
        finding = state["articles"]["art9"]["findings"]["ART09-OBL-1"]
        assert len(finding["evidence"]) == 2
        assert finding["evidence"][0]["provided_by"]["name"] == "User1"
        assert finding["evidence"][1]["provided_by"]["name"] == "User2"

    def test_evidence_provided_upgrades_to_compliant_on_rescan(self, project_with_scan):
        """When human provides evidence and scanner says partial/utd, level → compliant."""
        attester = {"name": "QA", "email": "qa@co.com", "role": "QA", "source": "config"}
        update_finding(
            str(project_with_scan), "ART09-OBL-1", "provide_evidence",
            "text", "Confirmed complete", attester=attester,
        )
        # Rescan — scanner still says partial
        new_scan = {
            "overall_level": "partial", "overall_confidence": "medium", "assessed_by": "test",
            "findings": [
                {"obligation_id": "ART09-OBL-1", "level": "partial", "description": "Still partial", "source_quote": "Q"},
            ],
        }
        save_article_result(str(project_with_scan), 9, new_scan)
        state = load_state(str(project_with_scan))
        finding = state["articles"]["art9"]["findings"]["ART09-OBL-1"]
        # Should be upgraded to compliant because human provided evidence
        assert finding["level"] == "compliant"
        assert finding["status"] == "evidence_provided"

    def test_evidence_provided_does_not_upgrade_nc(self, project_with_scan):
        """When human provides evidence but scanner says NC, level stays NC."""
        attester = {"name": "QA", "email": "qa@co.com", "role": "QA", "source": "config"}
        update_finding(
            str(project_with_scan), "ART09-OBL-2", "provide_evidence",
            "text", "We think this is fine", attester=attester,
        )
        # Rescan — scanner says non_compliant (real issue)
        new_scan = {
            "overall_level": "non_compliant", "overall_confidence": "medium", "assessed_by": "test",
            "findings": [
                {"obligation_id": "ART09-OBL-2", "level": "non_compliant", "description": "Still NC", "source_quote": "Q"},
            ],
        }
        save_article_result(str(project_with_scan), 9, new_scan)
        state = load_state(str(project_with_scan))
        finding = state["articles"]["art9"]["findings"]["ART09-OBL-2"]
        # Should NOT be upgraded — NC is a real issue
        assert finding["level"] == "non_compliant"

    def test_source_quote_preserved_across_rescan(self, project_with_scan):
        state = load_state(str(project_with_scan))
        sq = state["articles"]["art9"]["findings"]["ART09-OBL-1"].get("source_quote", "")
        assert sq == "Test quote"

        # Rescan with source_quote
        new_scan = {
            "overall_level": "partial",
            "overall_confidence": "medium",
            "assessed_by": "test",
            "findings": [
                {"obligation_id": "ART09-OBL-1", "level": "partial", "confidence": "medium", "description": "Updated", "source_quote": "New quote"},
            ],
        }
        save_article_result(str(project_with_scan), 9, new_scan)

        state2 = load_state(str(project_with_scan))
        sq2 = state2["articles"]["art9"]["findings"]["ART09-OBL-1"].get("source_quote", "")
        assert sq2 == "New quote"
