"""Tests for cl_update_finding_batch and related batch operations."""

import json
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def project_dir():
    """Create a temp project with realistic scan data for batch testing."""
    tmpdir = tempfile.mkdtemp(prefix="cl_batch_")
    articles_dir = os.path.join(tmpdir, ".compliancelint", "local", "articles")
    os.makedirs(articles_dir)

    # Art 9 — 3 findings (2 open UTD, 1 compliant)
    art9 = {
        "overall_level": "unable_to_determine",
        "overall_confidence": "low",
        "scan_date": "2026-04-07T00:00:00+00:00",
        "last_updated": "2026-04-07T00:00:00+00:00",
        "assessed_by": "test",
        "findings": {
            "ART09-OBL-1": {
                "status": "open",
                "level": "unable_to_determine",
                "confidence": "low",
                "description": "Risk management system not found.",
                "source_quote": "Art 9(1) quote",
                "remediation": None,
                "evidence": [],
                "history": [],
            },
            "ART09-OBL-2": {
                "status": "open",
                "level": "partial",
                "confidence": "low",
                "description": "Some risk documentation found.",
                "source_quote": "Art 9(2) quote",
                "remediation": None,
                "evidence": [],
                "history": [],
            },
            "ART09-OBL-3": {
                "status": "open",
                "level": "compliant",
                "confidence": "high",
                "description": "Risk assessment complete.",
                "source_quote": "Art 9(3) quote",
                "remediation": None,
                "evidence": [],
                "history": [],
            },
        },
    }
    with open(os.path.join(articles_dir, "art9.json"), "w") as f:
        json.dump(art9, f)

    # Art 12 — 2 findings (both open)
    art12 = {
        "overall_level": "non_compliant",
        "overall_confidence": "medium",
        "scan_date": "2026-04-07T00:00:00+00:00",
        "last_updated": "2026-04-07T00:00:00+00:00",
        "assessed_by": "test",
        "findings": {
            "ART12-OBL-1": {
                "status": "open",
                "level": "non_compliant",
                "confidence": "medium",
                "description": "No logging found.",
                "source_quote": "Art 12(1) quote",
                "remediation": "Add structured logging.",
                "evidence": [],
                "history": [],
            },
            "ART12-OBL-2": {
                "status": "open",
                "level": "unable_to_determine",
                "confidence": "low",
                "description": "Log retention not configured.",
                "source_quote": "Art 12(2) quote",
                "remediation": None,
                "evidence": [],
                "history": [],
            },
        },
    }
    with open(os.path.join(articles_dir, "art12.json"), "w") as f:
        json.dump(art12, f)

    # Art 82 — 1 finding (deployer-specific, open)
    art82 = {
        "overall_level": "unable_to_determine",
        "overall_confidence": "low",
        "scan_date": "2026-04-07T00:00:00+00:00",
        "last_updated": "2026-04-07T00:00:00+00:00",
        "assessed_by": "test",
        "findings": {
            "ART82-OBL-1": {
                "status": "open",
                "level": "unable_to_determine",
                "confidence": "low",
                "description": "Deployer obligation.",
                "source_quote": "Art 82 quote",
                "remediation": None,
                "evidence": [],
                "history": [],
            },
        },
    }
    with open(os.path.join(articles_dir, "art82.json"), "w") as f:
        json.dump(art82, f)

    # Metadata + state (for _save_merged_state)
    with open(os.path.join(tmpdir, ".compliancelint", "local", "metadata.json"), "w") as f:
        json.dump({"regulation": "eu-ai-act"}, f)

    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


ATTESTER = {"name": "Test User", "email": "test@example.com", "role": "CTO", "source": "test"}


# ── update_findings_batch ──

class TestUpdateFindingsBatch:
    def test_basic_batch_update(self, project_dir):
        from core.state import update_findings_batch

        updates = [
            {"obligation_id": "ART09-OBL-1", "action": "provide_evidence",
             "evidence_type": "file", "evidence_value": "docs/risk.md"},
            {"obligation_id": "ART12-OBL-1", "action": "provide_evidence",
             "evidence_type": "file", "evidence_value": "src/logging.py"},
        ]
        result = update_findings_batch(project_dir, updates, attester=ATTESTER)

        assert result["updated"] == 2
        assert result["total_requested"] == 2
        assert len(result["errors"]) == 0

    def test_batch_persists_to_files(self, project_dir):
        from core.state import update_findings_batch

        updates = [
            {"obligation_id": "ART09-OBL-1", "action": "provide_evidence",
             "evidence_type": "file", "evidence_value": "docs/risk.md"},
        ]
        update_findings_batch(project_dir, updates, attester=ATTESTER)

        # Read art9.json and verify
        art9_path = os.path.join(project_dir, ".compliancelint", "local", "articles", "art9.json")
        with open(art9_path) as f:
            data = json.load(f)
        finding = data["findings"]["ART09-OBL-1"]
        assert finding["status"] == "evidence_provided"
        assert len(finding["evidence"]) == 1
        assert finding["evidence"][0]["value"] == "docs/risk.md"
        assert finding["evidence"][0]["provided_by"]["name"] == "Test User"

    def test_batch_updates_merged_state(self, project_dir):
        from core.state import update_findings_batch

        updates = [
            {"obligation_id": "ART09-OBL-1", "action": "provide_evidence",
             "evidence_type": "file", "evidence_value": "docs/risk.md"},
        ]
        update_findings_batch(project_dir, updates, attester=ATTESTER)

        # Verify merged state.json exists and reflects the update
        state_path = os.path.join(project_dir, ".compliancelint", "local", "state.json")
        assert os.path.exists(state_path)
        with open(state_path) as f:
            state = json.load(f)
        finding = state["articles"]["art9"]["findings"]["ART09-OBL-1"]
        assert finding["status"] == "evidence_provided"

    def test_batch_rebut(self, project_dir):
        from core.state import update_findings_batch

        updates = [
            {"obligation_id": "ART82-OBL-1", "action": "rebut",
             "justification": "Deployer-specific, not applicable to provider"},
        ]
        result = update_findings_batch(project_dir, updates, attester=ATTESTER)

        assert result["updated"] == 1
        art82_path = os.path.join(project_dir, ".compliancelint", "local", "articles", "art82.json")
        with open(art82_path) as f:
            data = json.load(f)
        finding = data["findings"]["ART82-OBL-1"]
        assert finding["status"] == "rebutted"
        assert finding["suppression"]["justification"] == "Deployer-specific, not applicable to provider"

    def test_batch_mixed_actions(self, project_dir):
        from core.state import update_findings_batch

        updates = [
            {"obligation_id": "ART09-OBL-1", "action": "provide_evidence",
             "evidence_type": "file", "evidence_value": "docs/risk.md"},
            {"obligation_id": "ART82-OBL-1", "action": "rebut",
             "justification": "Not applicable"},
            {"obligation_id": "ART12-OBL-2", "action": "acknowledge"},
        ]
        result = update_findings_batch(project_dir, updates, attester=ATTESTER)
        assert result["updated"] == 3
        assert len(result["errors"]) == 0

    def test_batch_invalid_obligation_id(self, project_dir):
        from core.state import update_findings_batch

        updates = [
            {"obligation_id": "ART09-OBL-1", "action": "provide_evidence",
             "evidence_type": "file", "evidence_value": "docs/risk.md"},
            {"obligation_id": "FAKE-OBL-99", "action": "provide_evidence",
             "evidence_type": "file", "evidence_value": "fake.md"},
        ]
        result = update_findings_batch(project_dir, updates, attester=ATTESTER)
        assert result["updated"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["obligation_id"] == "FAKE-OBL-99"

    def test_batch_invalid_action(self, project_dir):
        from core.state import update_findings_batch

        updates = [
            {"obligation_id": "ART09-OBL-1", "action": "invalid_action"},
        ]
        result = update_findings_batch(project_dir, updates, attester=ATTESTER)
        assert result["updated"] == 0
        assert len(result["errors"]) == 1

    def test_batch_no_scan_data(self):
        from core.state import update_findings_batch

        tmpdir = tempfile.mkdtemp()
        try:
            result = update_findings_batch(tmpdir, [{"obligation_id": "ART09-OBL-1", "action": "acknowledge"}])
            assert "error" in result
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_batch_writes_only_dirty_files(self, project_dir):
        from core.state import update_findings_batch

        # Only update art9, not art12
        updates = [
            {"obligation_id": "ART09-OBL-1", "action": "acknowledge"},
        ]

        # Record art12 mtime before
        art12_path = os.path.join(project_dir, ".compliancelint", "local", "articles", "art12.json")
        mtime_before = os.path.getmtime(art12_path)

        import time
        time.sleep(0.05)  # ensure mtime would differ if written

        update_findings_batch(project_dir, updates, attester=ATTESTER)

        # art12 should NOT have been modified
        mtime_after = os.path.getmtime(art12_path)
        assert mtime_before == mtime_after

    def test_batch_history_records_attester(self, project_dir):
        from core.state import update_findings_batch

        updates = [
            {"obligation_id": "ART09-OBL-1", "action": "provide_evidence",
             "evidence_type": "text", "evidence_value": "Risk plan exists"},
        ]
        update_findings_batch(project_dir, updates, attester=ATTESTER)

        art9_path = os.path.join(project_dir, ".compliancelint", "local", "articles", "art9.json")
        with open(art9_path) as f:
            data = json.load(f)
        history = data["findings"]["ART09-OBL-1"]["history"]
        assert len(history) == 1
        assert history[0]["by"]["name"] == "Test User"
        assert history[0]["by"]["email"] == "test@example.com"
        assert history[0]["action"] == "provide_evidence"


# ── expand_article_evidence ──

class TestExpandArticleEvidence:
    def test_expand_single_article(self, project_dir):
        from core.state import expand_article_evidence

        items = [
            {"article": "art9", "action": "provide_evidence",
             "evidence_type": "file", "evidence_value": "docs/risk.md"},
        ]
        expanded = expand_article_evidence(project_dir, items)

        # art9 has 3 findings: OBL-1 (UTD, open), OBL-2 (partial, open), OBL-3 (compliant, open)
        # Only UTD and partial are actionable → 2 expanded
        assert len(expanded) == 2
        obl_ids = {e["obligation_id"] for e in expanded}
        assert "ART09-OBL-1" in obl_ids
        assert "ART09-OBL-2" in obl_ids
        assert "ART09-OBL-3" not in obl_ids  # compliant — skipped

        # All should have the same evidence
        for e in expanded:
            assert e["evidence_value"] == "docs/risk.md"
            assert e["action"] == "provide_evidence"

    def test_expand_multiple_articles(self, project_dir):
        from core.state import expand_article_evidence

        items = [
            {"article": "art9", "action": "provide_evidence",
             "evidence_type": "file", "evidence_value": "docs/risk.md"},
            {"article": "art12", "action": "provide_evidence",
             "evidence_type": "file", "evidence_value": "src/logging.py"},
        ]
        expanded = expand_article_evidence(project_dir, items)

        # art9: 2 actionable, art12: 2 actionable
        assert len(expanded) == 4
        art9_obls = [e for e in expanded if e["obligation_id"].startswith("ART09-")]
        art12_obls = [e for e in expanded if e["obligation_id"].startswith("ART12-")]
        assert len(art9_obls) == 2
        assert len(art12_obls) == 2
        # Verify evidence is different per article
        assert all(e["evidence_value"] == "docs/risk.md" for e in art9_obls)
        assert all(e["evidence_value"] == "src/logging.py" for e in art12_obls)

    def test_expand_rebut(self, project_dir):
        from core.state import expand_article_evidence

        items = [
            {"article": "art82", "action": "rebut",
             "justification": "Deployer-specific, not applicable"},
        ]
        expanded = expand_article_evidence(project_dir, items)

        assert len(expanded) == 1
        assert expanded[0]["obligation_id"] == "ART82-OBL-1"
        assert expanded[0]["action"] == "rebut"
        assert expanded[0]["justification"] == "Deployer-specific, not applicable"

    def test_expand_skips_already_provided(self, project_dir):
        """Findings with status 'rebutted' should not be expanded."""
        from core.state import expand_article_evidence, update_findings_batch

        # First rebut ART82-OBL-1
        update_findings_batch(project_dir, [
            {"obligation_id": "ART82-OBL-1", "action": "rebut",
             "justification": "Not applicable"},
        ], attester=ATTESTER)

        # Now try to expand art82 evidence — should find 0 (rebutted ≠ open)
        items = [{"article": "art82", "action": "provide_evidence",
                  "evidence_type": "text", "evidence_value": "test"}]
        expanded = expand_article_evidence(project_dir, items)
        assert len(expanded) == 0

    def test_expand_nonexistent_article(self, project_dir):
        from core.state import expand_article_evidence

        items = [{"article": "art99", "action": "provide_evidence",
                  "evidence_type": "text", "evidence_value": "test"}]
        expanded = expand_article_evidence(project_dir, items)
        assert len(expanded) == 0


# ── Integration: expand + batch ──

class TestExpandThenBatch:
    def test_full_flow_article_evidence(self, project_dir):
        """Simulate the real workflow: article-level evidence → expand → batch update."""
        from core.state import expand_article_evidence, update_findings_batch

        # Step 1: Expand article-level evidence
        items = [
            {"article": "art9", "action": "provide_evidence",
             "evidence_type": "file", "evidence_value": "docs/risk.md"},
            {"article": "art82", "action": "rebut",
             "justification": "Deployer-specific"},
        ]
        expanded = expand_article_evidence(project_dir, items)
        assert len(expanded) == 3  # 2 from art9 + 1 from art82

        # Step 2: Batch update
        result = update_findings_batch(project_dir, expanded, attester=ATTESTER)
        assert result["updated"] == 3
        assert len(result["errors"]) == 0

        # Step 3: Verify state
        state_path = os.path.join(project_dir, ".compliancelint", "local", "state.json")
        with open(state_path) as f:
            state = json.load(f)

        # art9 findings should be evidence_provided
        assert state["articles"]["art9"]["findings"]["ART09-OBL-1"]["status"] == "evidence_provided"
        assert state["articles"]["art9"]["findings"]["ART09-OBL-2"]["status"] == "evidence_provided"
        # art9 OBL-3 was compliant — untouched
        assert state["articles"]["art9"]["findings"]["ART09-OBL-3"]["status"] == "open"
        # art82 should be rebutted
        assert state["articles"]["art82"]["findings"]["ART82-OBL-1"]["status"] == "rebutted"

    def test_full_flow_mixed_modes(self, project_dir):
        """Mix article-level and per-obligation updates."""
        from core.state import expand_article_evidence, update_findings_batch

        # Article-level for art9
        article_items = [
            {"article": "art9", "action": "provide_evidence",
             "evidence_type": "file", "evidence_value": "docs/risk.md"},
        ]
        expanded = expand_article_evidence(project_dir, article_items)

        # Per-obligation for art12
        per_obl = [
            {"obligation_id": "ART12-OBL-1", "action": "provide_evidence",
             "evidence_type": "file", "evidence_value": "src/logging.py"},
        ]

        # Combine and batch
        all_updates = expanded + per_obl
        result = update_findings_batch(project_dir, all_updates, attester=ATTESTER)
        assert result["updated"] == 3  # 2 from art9 + 1 from art12
