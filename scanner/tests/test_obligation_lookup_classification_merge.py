"""§AA Option C Step 3 — tests for the merge step in obligation_lookup._build_index.

Verifies that the public-only `automation_assessment` (containing only `level`
post-Step-1 strip) gets merged with SaaS-fetched 5 fields when
classification_client returns a payload, and stays public-only when it
returns None (degraded mode).

These tests use the REAL on-disk obligation JSONs (which were stripped to
public-only in commit ca31b2e), so they document the post-split behavior
of the index builder.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from scanner.core import classification_client, obligation_lookup


@pytest.fixture(autouse=True)
def _reset_state():
    """Ensure each test starts with a fresh index + degraded-notice flag."""
    obligation_lookup.reset_cache()
    classification_client.reset_degraded_notice_flag()
    yield
    obligation_lookup.reset_cache()
    classification_client.reset_degraded_notice_flag()


def test_degraded_mode_leaves_only_level_in_automation_assessment():
    """No SaaS fetch (None returned) — rows have public `level` only.
    Verifies the post-Step-1 strip is in effect on disk."""
    with patch.object(
        classification_client, "fetch_classifications", return_value=None
    ):
        row = obligation_lookup.lookup_obligation("ART04-OBL-1")
    assert row is not None, "ART04-OBL-1 must exist in public obligations"
    aa = row.get("automation_assessment", {})
    # Public split: only `level` remains
    assert "level" in aa
    # Per Step 1, the 5 SaaS fields are stripped from public JSON
    for stripped in (
        "detection_method",
        "rationale",
        "what_to_scan",
        "confidence",
        "human_judgment_needed",
    ):
        assert stripped not in aa, (
            f"{stripped} should be stripped from public JSON post-§AA Step 1"
        )


def test_merged_mode_carries_all_6_fields():
    """SaaS fetch returns 5 fields → merged into row.automation_assessment
    so it has all 6 keys (level + 5 SaaS)."""
    fake_classifications = {
        "ART04-OBL-1": {
            "detection_method": "Mocked detection",
            "rationale": "Mocked rationale",
            "what_to_scan": ["mock_scan_target"],
            "confidence": "high",
            "human_judgment_needed": "Mocked judgment",
        }
    }

    def fake_fetch(article_number):
        # Return the mock only for art 4; everything else degrades
        return fake_classifications if article_number == 4 else None

    with patch.object(
        classification_client, "fetch_classifications", side_effect=fake_fetch
    ):
        row = obligation_lookup.lookup_obligation("ART04-OBL-1")

    assert row is not None
    aa = row["automation_assessment"]
    assert aa.get("detection_method") == "Mocked detection"
    assert aa.get("rationale") == "Mocked rationale"
    assert aa.get("what_to_scan") == ["mock_scan_target"]
    assert aa.get("confidence") == "high"
    assert aa.get("human_judgment_needed") == "Mocked judgment"
    # Public `level` MUST still be there post-merge
    assert "level" in aa


def test_public_level_wins_on_merge_conflict():
    """If SaaS payload (incorrectly) contains `level`, the public value
    wins. Public file is the canonical taxonomy; this is a defensive
    invariant in the merge logic."""
    fake_classifications = {
        "ART04-OBL-1": {
            "level": "WRONG",  # SaaS shouldn't have this; if it does, ignore
            "detection_method": "x",
        }
    }

    def fake_fetch(article_number):
        return fake_classifications if article_number == 4 else None

    with patch.object(
        classification_client, "fetch_classifications", side_effect=fake_fetch
    ):
        row = obligation_lookup.lookup_obligation("ART04-OBL-1")

    assert row is not None
    aa = row["automation_assessment"]
    # Public level was "partial" pre-split; it stays "partial" post-merge.
    assert aa["level"] != "WRONG"


def test_degraded_notice_emitted_once_when_first_article_fetch_fails(capsys):
    """When ALL articles fail fetch (degraded mode), the one-time CLI
    notice is emitted exactly once (not 44 times)."""
    with patch.object(
        classification_client, "fetch_classifications", return_value=None
    ):
        # Trigger a build by looking up any OID
        obligation_lookup.lookup_obligation("ART04-OBL-1")

    captured = capsys.readouterr()
    # Notice text comes from emit_degraded_notice_once
    assert captured.err.count("Offline mode") == 1


def test_loaded_oid_count_includes_all_247_obligations():
    """Sanity: post-merge, the index should still have 247 OIDs (the
    merge doesn't add or drop entries, just enriches them)."""
    with patch.object(
        classification_client, "fetch_classifications", return_value=None
    ):
        count = obligation_lookup.loaded_oid_count()
    # 247 unique OIDs across 44 articles. Some OIDs are
    # cross-referenced into multiple files but de-duped at index
    # insertion (first-write-wins on legitimate cross-refs).
    assert count >= 244, f"expected >=244 OIDs, got {count}"
    assert count <= 250, f"expected <=250 OIDs, got {count}"


# ── §Z Z.2 follow-up (2026-05-02) — _classification_unavailable flag ──
# Spec said callers should be able to detect degraded state explicitly
# via row["_classification_unavailable"] = True, but Step 3 commit
# d11e563 didn't implement this. Z.2 audit + fresh-clone verify
# closed the gap. These tests pin both states (degraded + merged).

def test_degraded_mode_sets_classification_unavailable_flag():
    """When fetch_classifications returns None, every row in that
    article must be flagged so callers (cl_action_guide, cl_action_plan,
    UI) can detect degraded state explicitly without inferring from
    absent fields."""
    with patch.object(
        classification_client, "fetch_classifications", return_value=None
    ):
        # Sample one OID per addressee class to confirm flag is uniform
        for oid in [
            "ART04-OBL-1",        # provider_and_deployer
            "ART22-OBL-3",        # authorised_representative
            "ART50-OBL-7",        # ai_office
            "ART54-OBL-1",        # provider
        ]:
            row = obligation_lookup.lookup_obligation(oid)
            assert row is not None, f"{oid} must exist"
            assert row.get("_classification_unavailable") is True, (
                f"{oid} missing _classification_unavailable=True flag in "
                f"degraded mode (got {row.get('_classification_unavailable')!r})"
            )


def test_merged_mode_does_not_set_classification_unavailable_flag():
    """When SaaS fetch succeeds for an article, rows in that article
    must NOT have the unavailable flag (or must have it falsy)."""
    fake_classifications = {
        "ART04-OBL-1": {
            "detection_method": "real",
            "rationale": "real",
            "what_to_scan": ["docs"],
            "confidence": "high",
            "human_judgment_needed": "real",
        }
    }

    def fake_fetch(article_number):
        return fake_classifications if article_number == 4 else None

    with patch.object(
        classification_client, "fetch_classifications", side_effect=fake_fetch
    ):
        # Article 4 succeeded → no flag
        row_art4 = obligation_lookup.lookup_obligation("ART04-OBL-1")
        # Article 22 degraded (fetch returned None) → flag set
        row_art22 = obligation_lookup.lookup_obligation("ART22-OBL-3")

    assert not row_art4.get("_classification_unavailable"), (
        "ART04-OBL-1 had a successful classification fetch; flag should be falsy"
    )
    assert row_art22.get("_classification_unavailable") is True, (
        "ART22-OBL-3 had a None fetch; flag should be True"
    )
