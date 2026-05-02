"""§AA Option C Step 4 follow-up — end-to-end e2e for cl_scan-with-classification.

Spec acceptance from `2026-05-02-aa-option-c-implementation-spec.md` Step 4:
  > One e2e (Playwright or pytest) verifies end-to-end:
  > cl_connect → cl_scan against fixture → classifications fetched +
  > finding produced

Step 4 commit `491b88b` deferred this with rationale "would be a copy
of test_cl_action_guide_enriched with cl_scan swapped". §Z Z.2 audit
follow-up 2026-05-02 closes the gap — we DO need to exercise the full
cl_scan pipeline (context.py / module.py / ScanResult / Finding
emission), not just the obligation_lookup merge layer that
test_obligation_lookup_classification_merge.py covers.

What this file pins:

  T1 — Merged mode (cl_connect happened): scanner module load triggers
       fetch_classifications → 5 SaaS fields merged into
       automation_assessment, mod.scan() emits findings whose
       obligation IDs map to the merged rows.

  T2 — Degraded mode (no cl_connect): fetch returns None → rows have
       only `level`, `_classification_unavailable=True` flag set,
       mod.scan() still emits findings (graceful degrade, not crash).

  T3 — Cross-pipeline integrity: the obligation_id in a Finding maps
       back to a row in the merged index — no orphan IDs, no silent
       drops between scan emission and engine enrichment.

These tests use a real article module (art04 — universal applicability
that always emits findings regardless of compliance_answers content),
real obligation JSON on disk, and mocked classification_client.fetch.
The mock-vs-real boundary mirrors what production looks like:
classification_client is the only network-bound layer; everything
downstream (obligation_lookup → engine → module) runs on real code.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from scanner.core import classification_client, obligation_lookup  # noqa: E402
from scanner.core.context import ProjectContext  # noqa: E402
from scanner.core.protocol import BaseArticleModule  # noqa: E402


def _load_module(article_dir_name: str):
    """Mirror conftest._load_module — load a scanner module by directory."""
    module_dir = os.path.join(SCANNER_ROOT, "modules", article_dir_name)
    sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(
        article_dir_name.replace("-", "_"),
        os.path.join(module_dir, "module.py"),
        submodule_search_locations=[module_dir],
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    BaseArticleModule.clear_index_cache()
    return mod.create_module()


@pytest.fixture(autouse=True)
def _reset_state():
    obligation_lookup.reset_cache()
    classification_client.reset_degraded_notice_flag()
    BaseArticleModule.clear_index_cache()
    yield
    obligation_lookup.reset_cache()
    classification_client.reset_degraded_notice_flag()
    BaseArticleModule.clear_index_cache()


# Realistic SaaS classification payload — what the API endpoint would
# return for art04 if the user has a valid api_key in config.json.
ART04_FIXTURE = {
    "ART04-OBL-1": {
        "detection_method": "Check for AI training documentation, AI usage policies, competency frameworks, staff onboarding materials mentioning AI, and internal AI guidelines",
        "rationale": "Can detect documentation artifacts (AI policy, training docs) but cannot verify that staff have actually been trained or that the training is adequate",
        "what_to_scan": ["documentation", "config"],
        "confidence": "medium",
        "human_judgment_needed": "Whether the measures taken are sufficient and proportionate to the context. AI literacy is an organizational obligation — code scanning can detect documentation artifacts but cannot assess training quality or organizational compliance.",
    }
}


def _ctx_for_art04(answer: bool | None = None) -> ProjectContext:
    """Build a ProjectContext exercising art04 with one user answer.
    None answer → UNABLE_TO_DETERMINE finding; True/False → COMPLIANT/NON_COMPLIANT.
    """
    return ProjectContext(
        primary_language="python",
        risk_classification="likely high-risk",
        risk_classification_confidence="medium",
        compliance_answers={
            "art4": {
                "has_ai_literacy_measures": answer,
                "literacy_description": "Test description" if answer else "",
                "literacy_evidence": ["docs/ai-policy.md"] if answer else [],
            },
        },
    )


# ── T1 ─────────────────────────────────────────────────────────────


def test_cl_scan_e2e_merged_mode_emits_findings_with_classification(tmp_path):
    """T1 — Full pipeline exercise: cl_connect simulated by mocked
    fetch returning the SaaS fixture. After mod.scan(), the engine
    has merged the 5 SaaS fields into ART04-OBL-1's
    automation_assessment, and mod.scan() emits findings whose
    obligation IDs match merged rows."""

    def fake_fetch(article_number):
        return ART04_FIXTURE if article_number == 4 else None

    with patch.object(
        classification_client, "fetch_classifications", side_effect=fake_fetch
    ):
        # Sanity: lookup confirms the merge worked.
        row = obligation_lookup.lookup_obligation("ART04-OBL-1")
        assert row is not None
        aa = row["automation_assessment"]
        assert aa.get("detection_method", "").startswith("Check for AI training"), (
            "merged classification did not land in automation_assessment"
        )
        assert aa.get("confidence") == "medium"
        assert "level" in aa, "public level field must survive merge"
        assert not row.get("_classification_unavailable"), (
            "merged mode must NOT set degraded flag"
        )

        # Now run cl_scan's underlying scan flow.
        ctx = _ctx_for_art04(answer=False)  # NON_COMPLIANT scenario
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        try:
            mod = _load_module("art04-ai-literacy")
            result = mod.scan(str(tmp_path))
            payload = result.to_dict()
        finally:
            BaseArticleModule.set_context(None)

    # Findings must be emitted. ART04-OBL-1 (the only obligation in art04)
    # must appear among them — confirming the obligation_id ↔ index
    # mapping survived the classification merge.
    findings = payload.get("findings", [])
    assert len(findings) > 0, "art04 scan must emit at least one finding"

    found_oids = {f.get("obligation_id") for f in findings}
    assert "ART04-OBL-1" in found_oids, (
        f"ART04-OBL-1 missing from findings; got {sorted(found_oids)}"
    )


# ── T2 ─────────────────────────────────────────────────────────────


def test_cl_scan_e2e_degraded_mode_still_scans(tmp_path, capsys):
    """T2 — Degraded mode (cl_connect not run / no api_key in config):
    fetch returns None → rows degrade to public-only (`level` only),
    `_classification_unavailable=True` flag is set, but mod.scan()
    STILL produces findings without crashing."""
    with patch.object(
        classification_client, "fetch_classifications", return_value=None
    ):
        # Confirm degraded state at the index layer
        row = obligation_lookup.lookup_obligation("ART04-OBL-1")
        aa = row["automation_assessment"]
        assert "detection_method" not in aa, (
            "degraded mode must not have SaaS field"
        )
        assert row.get("_classification_unavailable") is True, (
            "degraded rows must set the unavailable flag (Z.2 follow-up)"
        )

        ctx = _ctx_for_art04(answer=None)  # UTD scenario
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        try:
            mod = _load_module("art04-ai-literacy")
            result = mod.scan(str(tmp_path))
            payload = result.to_dict()
        finally:
            BaseArticleModule.set_context(None)

    findings = payload.get("findings", [])
    assert len(findings) > 0, (
        "degraded mode must STILL produce findings — graceful degrade, "
        "not silent skip"
    )
    # The one-time degraded notice must have fired on stderr
    captured = capsys.readouterr()
    assert "Offline mode" in captured.err, (
        "degraded mode must emit the one-time CLI notice"
    )


# ── T3 ─────────────────────────────────────────────────────────────


def test_cl_scan_e2e_no_orphan_obligation_ids_after_merge(tmp_path):
    """T3 — Cross-pipeline integrity: every obligation_id in scan
    findings must resolve back to a row in the obligation_lookup
    index (merged or degraded — both pathways). A regression where
    classification merge silently drops a row would surface here as
    a finding referencing an OID that no longer exists in the index."""

    def fake_fetch(article_number):
        return ART04_FIXTURE if article_number == 4 else None

    with patch.object(
        classification_client, "fetch_classifications", side_effect=fake_fetch
    ):
        ctx = _ctx_for_art04(answer=True)  # COMPLIANT scenario
        BaseArticleModule.set_context(ctx)
        BaseArticleModule.set_config(None)
        try:
            mod = _load_module("art04-ai-literacy")
            result = mod.scan(str(tmp_path))
            payload = result.to_dict()
        finally:
            BaseArticleModule.set_context(None)

        for finding in payload.get("findings", []):
            oid = finding.get("obligation_id")
            if not oid:
                continue
            # Engine-emitted findings reference the OID; it MUST
            # resolve in the merged index.
            row = obligation_lookup.lookup_obligation(oid)
            assert row is not None, (
                f"finding references {oid} but obligation_lookup returned None — "
                f"orphan ID indicates merge step dropped this row"
            )
            assert row["id"].upper() == oid.upper(), (
                f"index returned wrong row for {oid}: got {row.get('id')!r}"
            )
