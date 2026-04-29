"""End-to-end tests verifying that the 9 wrapped MCP tools actually
include the upgrade_hint in their response when tier is unconnected.

Phase 5 Task 15 follow-up audit: my unit tests verified the helper
behaves correctly, but did NOT verify each tool actually CALLS the
helper. If a tool's wrap was forgotten or misnamed, unit tests stay
green while shipping a bug. This file closes the gap.

Pattern: call each tool with no SaaS connection (= no api_key →
"unconnected" tier per upgrade_hint cache miss) and assert the
response carries either:
  - JSON: `_meta.upgrade_hint` field (spec §H structured form)
  - Text: footer with "ComplianceLint hint" + "/dashboard/plans"

The 7 utility tools (cl_version, cl_report_bug, cl_disconnect,
cl_delete, cl_update_finding, cl_update_finding_batch, cl_connect,
cl_sync) are intentionally NOT wrapped — paywall nudge would be
intrusive. Spot-check at least cl_version stays clean (no hint).

**Coverage note**: this file directly verifies 5 of the 9 wrapped
tools (cl_explain, cl_action_guide, cl_check_updates,
cl_interim_standard, cl_analyze_project). The other 4 (cl_scan,
cl_scan_all, cl_action_plan, cl_verify_evidence) need a full project
fixture with .compliancelint/local/state.json + compliance_answers,
which is heavier than this audit-fix batch warrants. Their wrap
pattern is the same as cl_analyze_project's (single return statement,
project_path arg) and is verified by code review on
`scanner/server.py`. Add e2e coverage for those 4 in a follow-up
when broader fixture infra is in place.
"""
import json
import os
import sys
import tempfile

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


def _has_upgrade_hint(response: str, tool_name: str) -> bool:
    """Detect whether response carries the upgrade_hint in either form.

    Returns True iff the response embeds the structured `_meta.
    upgrade_hint` (JSON form) OR the text footer "ComplianceLint hint"
    + "/dashboard/plans" (plain-text form). This mirrors the dual-shape
    contract documented in `core/upgrade_hint.append_upgrade_hint`.
    """
    # Try JSON form first (most tools return JSON)
    try:
        parsed = json.loads(response)
        if isinstance(parsed, dict):
            meta = parsed.get("_meta")
            if isinstance(meta, dict) and "upgrade_hint" in meta:
                hint = meta["upgrade_hint"]
                # Validate the hint shape so a stub `_meta:{}` doesn't pass
                if (
                    isinstance(hint, dict)
                    and isinstance(hint.get("message"), str)
                    and hint.get("url", "").endswith("/dashboard/plans")
                ):
                    return True
    except (json.JSONDecodeError, ValueError):
        pass

    # Text footer form (cl_scan_all returns text, not JSON)
    if "ComplianceLint hint" in response and "/dashboard/plans" in response:
        return True

    return False


# ──────────────────────────────────────────────────────────────────────
# Tools that should ALWAYS embed an upgrade_hint when tier=unconnected
# ──────────────────────────────────────────────────────────────────────


def test_cl_explain_response_has_upgrade_hint():
    """cl_explain returns json.dumps response — wrap should inject
    _meta.upgrade_hint."""
    from server import cl_explain

    response = cl_explain(article=4)
    assert _has_upgrade_hint(response, "cl_explain"), (
        f"cl_explain response missing upgrade_hint: {response[:200]}"
    )


def test_cl_explain_unknown_article_still_has_upgrade_hint():
    """Even error response (article number not loaded) should carry the
    hint — error path was a separate return statement that also needed
    wrapping."""
    from server import cl_explain

    # Article 99999 won't be loaded → returns error JSON
    response = cl_explain(article=99999)
    assert _has_upgrade_hint(response, "cl_explain"), (
        f"cl_explain error path missing upgrade_hint: {response[:200]}"
    )


def test_cl_action_guide_response_has_upgrade_hint():
    """cl_action_guide has TWO return points (validation error + main).
    Both must be wrapped."""
    from server import cl_action_guide

    response = cl_action_guide("ART26-OBL-2")
    assert _has_upgrade_hint(response, "cl_action_guide"), (
        f"cl_action_guide main path missing upgrade_hint: {response[:200]}"
    )


def test_cl_action_guide_validation_error_path_has_upgrade_hint():
    from server import cl_action_guide

    # Invalid format → validation error early-return path
    response = cl_action_guide("not-a-valid-id")
    assert _has_upgrade_hint(response, "cl_action_guide"), (
        f"cl_action_guide validation error missing upgrade_hint: {response[:200]}"
    )


def test_cl_check_updates_response_has_upgrade_hint():
    """cl_check_updates response should embed Business-tier pitch."""
    from server import cl_check_updates

    response = cl_check_updates()
    assert _has_upgrade_hint(response, "cl_check_updates"), (
        f"cl_check_updates response missing upgrade_hint: {response[:200]}"
    )


def test_cl_interim_standard_response_has_upgrade_hint():
    """cl_interim_standard has 3 return points (success + 2 error
    paths). All wrapped."""
    from server import cl_interim_standard

    # Article 4 should have a checklist
    response = cl_interim_standard(article_number=4)
    assert _has_upgrade_hint(response, "cl_interim_standard"), (
        f"cl_interim_standard response missing upgrade_hint: {response[:200]}"
    )


def test_cl_interim_standard_unknown_article_has_upgrade_hint():
    """Unknown article number → error response path."""
    from server import cl_interim_standard

    response = cl_interim_standard(article_number=99999)
    assert _has_upgrade_hint(response, "cl_interim_standard"), (
        f"cl_interim_standard error path missing upgrade_hint: {response[:200]}"
    )


def test_cl_analyze_project_response_has_upgrade_hint():
    """cl_analyze_project takes project_path. Use a temp dir so we
    don't hit a real project's .compliancelint cache."""
    from server import cl_analyze_project

    with tempfile.TemporaryDirectory() as tmp:
        response = cl_analyze_project(tmp)
        assert _has_upgrade_hint(response, "cl_analyze_project"), (
            f"cl_analyze_project response missing upgrade_hint: {response[:200]}"
        )


# ──────────────────────────────────────────────────────────────────────
# Tools that should NEVER carry an upgrade_hint (utility / write ops)
# ──────────────────────────────────────────────────────────────────────


def test_cl_version_response_does_not_have_upgrade_hint():
    """cl_version is a utility tool — paywall nudge would be intrusive.
    Should NOT be wrapped."""
    from server import cl_version

    response = cl_version()
    assert not _has_upgrade_hint(response, "cl_version"), (
        f"cl_version unexpectedly carries upgrade_hint (should NOT be wrapped)"
    )


def test_cl_report_bug_response_does_not_have_upgrade_hint():
    from server import cl_report_bug

    response = cl_report_bug()
    assert not _has_upgrade_hint(response, "cl_report_bug")


# ──────────────────────────────────────────────────────────────────────
# Tier-conditional behaviour (cache says paid → no hint)
# ──────────────────────────────────────────────────────────────────────


def test_paid_tier_response_does_not_have_upgrade_hint():
    """When tier cache says 'pro', the wrapped tool's response should
    NOT carry an upgrade_hint — paid tier already paying."""
    from core.upgrade_hint import cache_tier
    from server import cl_analyze_project

    with tempfile.TemporaryDirectory() as tmp:
        cache_tier(tmp, "pro")
        response = cl_analyze_project(tmp)
        # Pro tier → no hint inserted
        assert not _has_upgrade_hint(response, "cl_analyze_project"), (
            f"Pro-tier response unexpectedly carries upgrade_hint:\n{response[:300]}"
        )


def test_starter_tier_response_does_not_have_upgrade_hint():
    from core.upgrade_hint import cache_tier
    from server import cl_analyze_project

    with tempfile.TemporaryDirectory() as tmp:
        cache_tier(tmp, "starter")
        response = cl_analyze_project(tmp)
        assert not _has_upgrade_hint(response, "cl_analyze_project")


def test_free_tier_response_has_upgrade_hint():
    """Explicit 'free' (not just 'unconnected') should also trigger
    the hint — these are two distinct unpaid states per the helper."""
    from core.upgrade_hint import cache_tier
    from server import cl_analyze_project

    with tempfile.TemporaryDirectory() as tmp:
        cache_tier(tmp, "free")
        response = cl_analyze_project(tmp)
        assert _has_upgrade_hint(response, "cl_analyze_project")


# ──────────────────────────────────────────────────────────────────────
# JSON shape assertions — embedded form is structured, not stringy
# ──────────────────────────────────────────────────────────────────────


def test_cl_explain_upgrade_hint_is_structured_meta_not_text():
    """For JSON-returning tools, the hint MUST live under
    `_meta.upgrade_hint` as a dict (spec §H), NOT as a stringified
    text suffix that would break json.loads consumers."""
    from server import cl_explain

    response = cl_explain(article=4)
    parsed = json.loads(response)  # MUST not throw
    assert "_meta" in parsed
    hint = parsed["_meta"]["upgrade_hint"]
    assert isinstance(hint, dict)
    assert hint["tier_at_scan"] in ("free", "unconnected")
    assert isinstance(hint["missing_features"], list)
    assert len(hint["missing_features"]) > 0


def test_cl_action_guide_upgrade_hint_preserves_existing_keys():
    """Wrap must NOT clobber the tool's existing JSON keys —
    `obligation_id`, `title`, `dashboard_url`, `note`, etc. all stay."""
    from server import cl_action_guide

    response = cl_action_guide("ART26-OBL-2")
    parsed = json.loads(response)
    # Pre-existing keys all present
    assert parsed["obligation_id"] == "ART26-OBL-2"
    assert "title" in parsed
    assert "dashboard_url" in parsed
    assert "is_human_gate" in parsed
    # Plus the new _meta key
    assert "_meta" in parsed
