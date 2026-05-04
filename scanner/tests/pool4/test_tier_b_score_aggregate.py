"""Pool 4 — Tier-B score-aggregate consistency cell.

The dashboard's POST /api/v1/scans handler writes per-scan aggregate
counts into the `scans` row (`totalObligations`, `compliantCount`,
`nonCompliantCount`, `notApplicableCount`, `overallStatus`) AND the
per-finding rows into `findings`. These two writes must stay in sync —
if the route's aggregate code drifts from the per-finding cascade,
the dashboard's "X of Y compliant" UI silently lies.

This Tier-B cell covers the invariant: after a single cl_sync, the
aggregate counts on the scans row are internally consistent AND the
per-finding cascade has AT LEAST as many rows as totalObligations.

Audit-first observation 2026-05-04: the route handler defines
  totalObligations = compliantCount + nonCompliantCount + notApplicableCount
which means UNABLE_TO_DETERMINE findings are written to the `findings`
table but DELIBERATELY excluded from `totalObligations`. Synthetic
contexts (no real evidence) produce all UTDs, so totalObligations=0 is
the correct outcome there — that's NOT a bug. The cell below therefore
tests the *consistency* invariants without requiring total > 0.

Verifications:
  - totalObligations is a non-negative int (sanity: not NULL, not negative)
  - compliantCount + nonCompliantCount + notApplicableCount ==
    totalObligations (route's own arithmetic — would fail if a future
    refactor reads `total` from one source and bucket counts from
    another and they drift)
  - count_findings_for_scan(scan_id) >= totalObligations (the per-
    finding cascade has at least every COUNTED obligation; UTDs may
    add to the count but never reduce it below total)
  - overallStatus is one of the documented values

This complements the tier-A pipeline cells (which prove the chain
runs end-to-end) by anchoring the cross-system data invariant.

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport
  - C2: live :3000 prod server
  - C3: real seeded test-business persona
  - C7: tmp_path Pattern B (full isolation)
  - C8: purge_repo cleanup; tmp_path auto-cleaned

Verified-via: scanner/server.py:cl_sync HTTP-POST branch + the SaaS
POST /api/v1/scans handler's aggregate-count computation
(`computeOverallStatus(counts)` + `compliantCount`/`nonCompliantCount`/
`notApplicableCount` writes to the scans row).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from .cell_loader import ToolCell
from .cleanup import CleanupError, purge_repo
from .dispatcher import invoke_tool
from .fixtures import PERSONAS
from .mcp_client import McpStdioClient, parse_first_json
from .saas_introspection import (
    count_findings_for_scan,
    fetch_latest_scan_for_repo,
    fetch_repo_by_name,
    open_readonly,
)


SAAS_URL = "http://localhost:3000"

# overallStatus values produced by the dashboard's computeOverallStatus()
# — the ComplianceStatus type enumerates four UPPERCASE_SNAKE_CASE values:
#   COMPLIANT | PARTIALLY_COMPLIANT | NON_COMPLIANT | NEEDS_REVIEW
# If a future PR adds a status the assertion below fails so the
# contract change surfaces.
KNOWN_OVERALL_STATUSES = {
    "COMPLIANT",
    "PARTIALLY_COMPLIANT",
    "NON_COMPLIANT",
    "NEEDS_REVIEW",
}


def _build_synthetic_context(client: McpStdioClient, project_path: Path) -> str:
    """Same template-driven helper used by the tier-A pipeline cells."""
    raw = client.call_tool(
        "cl_analyze_project", {"project_path": str(project_path)},
    )
    analyze = parse_first_json(raw)
    template = analyze.get("compliance_answers_template")
    if not template:
        raise RuntimeError(
            f"cl_analyze_project did not return template; "
            f"keys={list(analyze.keys())}"
        )
    answers = dict(template)
    answers["_scope"] = {
        **answers.get("_scope", {}),
        "risk_classification": "high-risk",
        "risk_classification_confidence": "high",
        "is_ai_system": True,
        "operator_role": ["provider"],
        "annex_iii_category": "annex_iii_pt5_essential_services",
        "is_annex_i_product": False,
        "uses_training_data": True,
        "is_gpai": False,
        "is_gpai_provider": False,
        "eu_established": True,
        "territorial_scope_applies": True,
        "is_open_source": False,
        "is_military_defense": False,
        "is_research_only": False,
        "is_biometric_system": False,
        "is_financial_institution": False,
        "is_distributor": False,
        "is_importer": False,
        "is_authorised_representative": False,
    }
    return json.dumps({
        "framework": "python",
        "stack": ["python"],
        "compliance_answers": answers,
    })


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_tier_b_score_aggregate_internal_consistency(
    tmp_path: Path,
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end: scan + sync, then verify scans row aggregates are
    internally consistent + match the findings cascade count."""
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    persona = PERSONAS["business"]
    unique_suffix = str(int(time.time() * 1000) % 1_000_000_000)
    repo_name = f"test-business/pool4-tier-b-aggregate-{unique_suffix}"

    project_dir = tmp_path / "fixture"
    project_dir.mkdir()
    (project_dir / ".compliancelintrc").write_text(
        json.dumps({
            "purpose": "Pool 4 tier-B score-aggregate fixture",
            "repo_name": repo_name,
            "saas_url": SAAS_URL,
            "saas_api_key": persona.api_key,
            "scope": {
                "operator_role": ["provider"],
                "risk_classification": "high-risk",
            },
            "attester_name": "Pool 4 Tier-B Test",
            "attester_email": "pool4-tier-b@test.invalid",
        }, indent=2),
        encoding="utf-8",
    )

    repo_id_for_cleanup: str | None = None
    client = McpStdioClient.spawn()
    try:
        project_context_json = _build_synthetic_context(client, project_dir)

        scan_cell = ToolCell(
            cell_id="tier-b-aggregate-step1-cl_scan-art09",
            tier="S",
            tool="cl_scan",
            scenario="synthetic_context_single_article",
            persona="business",
            preconditions=["fixture_with_rc"],
            cleanup=["chain_step"],
            cleanup_justification="chain step — purge runs at chain end",
            invoke={
                "tool": "cl_scan",
                "args": {
                    "project_path": str(project_dir),
                    "project_context": project_context_json,
                    "articles": "9",
                    "ai_provider": "Pool4 Tier-B Synthetic",
                },
            },
            expected_response={"status": "ok"},
        )
        scan_raw = invoke_tool(scan_cell, ctx={}, client=client)
        scan_resp = parse_first_json(scan_raw)
        if "error" in scan_resp:
            pytest.skip(
                f"cl_scan rejected synthetic context: {scan_resp.get('error')}"
            )

        sync_cell = ToolCell(
            cell_id="tier-b-aggregate-step2-cl_sync",
            tier="S",
            tool="cl_sync",
            scenario="success",
            persona="business",
            preconditions=["scan_completed"],
            cleanup=["purge_repo"],
            cleanup_justification=None,
            invoke={
                "tool": "cl_sync",
                "args": {"project_path": str(project_dir)},
            },
            expected_response={"status": "ok"},
        )
        sync_raw = invoke_tool(sync_cell, ctx={}, client=client)
    finally:
        client.close()

    sync_resp = parse_first_json(sync_raw)
    assert "error" not in sync_resp, f"cl_sync errored: {sync_resp}"
    scan_id = sync_resp.get("scan_id")
    assert scan_id, f"cl_sync returned no scan_id; got {sync_resp}"

    # ── Aggregate consistency invariants ──
    with open_readonly() as conn:
        repo_row = fetch_repo_by_name(conn, repo_name)
        assert repo_row is not None, (
            f"DB has no repos row for {repo_name!r} after sync"
        )
        repo_id_for_cleanup = repo_row["id"]

        scan_row = fetch_latest_scan_for_repo(conn, repo_id_for_cleanup)
        assert scan_row is not None, "no scan row for the new repo"

        total = scan_row["totalObligations"]
        compliant = scan_row["compliantCount"]
        non_compliant = scan_row["nonCompliantCount"]
        not_applicable = scan_row["notApplicableCount"]
        overall = scan_row["overallStatus"]

        # Sanity: scan row has valid integer aggregates (not NULL,
        # not negative). Synthetic context can legitimately produce
        # total=0 if all findings are UNABLE_TO_DETERMINE — that's not
        # a bug, just an artifact of having no real evidence.
        for label, val in [
            ("totalObligations", total),
            ("compliantCount", compliant),
            ("nonCompliantCount", non_compliant),
            ("notApplicableCount", not_applicable),
        ]:
            assert isinstance(val, int) and val >= 0, (
                f"{label} should be a non-negative int; got {val!r}"
            )

        # Internal consistency on the scans row: total IS the sum of
        # the three buckets (per route handler line 180). A future
        # refactor that reads total from a different source than the
        # buckets would surface here.
        bucket_sum = compliant + non_compliant + not_applicable
        assert bucket_sum == total, (
            f"score-aggregate drift: totalObligations={total} but "
            f"compliantCount({compliant}) + nonCompliantCount({non_compliant}) "
            f"+ notApplicableCount({not_applicable}) = {bucket_sum}. "
            f"The dashboard's per-bucket counts don't add up to its own "
            f"total — silently corrupts 'X of Y compliant' UI text."
        )

        # Cross-table consistency: per-finding cascade has AT LEAST
        # the counted obligations. UTDs may add extra rows so the
        # cascade count can be > total, but never less. Use the
        # dashboard's actual row id (scan_row["id"]); cl_sync's
        # response scan_id may be the scanner-side payload UUID and
        # not all routes upsert it as the row id.
        findings_via_dashboard_id = count_findings_for_scan(
            conn, scan_row["id"],
        )
        assert findings_via_dashboard_id >= total, (
            f"findings cascade count ({findings_via_dashboard_id}) "
            f"is LESS than scans.totalObligations ({total}) for "
            f"scan_id={scan_row['id']}. Per-finding writes are missing "
            f"rows that the aggregate counted — UI total and detail "
            f"list disagree (regression in route handler's findings "
            f"cascade)."
        )

        # Audit-first observation: the scanner-side scan_id (from
        # cl_sync's response) may be a different UUID than the
        # dashboard's scans.id. Document the divergence for future
        # readers; non-load-bearing.
        findings_via_scanner_id = count_findings_for_scan(conn, scan_id)
        # If the two ids point at different row sets we just record it.
        # No assertion either way — the load-bearing check above used
        # the dashboard's authoritative row id.
        _ = findings_via_scanner_id  # noqa: F841 — intentional probe

        # overallStatus is one of the documented values.
        assert overall in KNOWN_OVERALL_STATUSES, (
            f"overallStatus={overall!r} is not in the documented set "
            f"{sorted(KNOWN_OVERALL_STATUSES)}. New status value = "
            f"explicit choice; update KNOWN_OVERALL_STATUSES + audit "
            f"how scoreboard UI handles it."
        )

    # ── Cleanup ──
    if repo_id_for_cleanup is not None:
        try:
            purge_repo(
                SAAS_URL, persona.api_key, repo_id_for_cleanup,
                confirm_name=repo_name,
            )
        except CleanupError as e:
            pytest.fail(
                f"tier-B cleanup purge failed: {e}; orphan at id="
                f"{repo_id_for_cleanup}"
            )
