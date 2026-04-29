"""RED tests — upgrade_hint footer for cross-AI-client contextual paywall.

Phase 5 Task 15 (Spec §A + §H 2026-04-29).

Each MCP tool whose response would benefit from a tier upgrade nudge
appends a formatted footer when the user's tier is free / unconnected.
Paid tiers (starter / pro / business / enterprise) get no footer —
they're already paying customers and the nudge would be noise.

Tier detection uses a local cache at
`{project_path}/.compliancelint/local/tier.json`. Tools that hit the
SaaS scan-settings endpoint (which returns tier_at_scan) refresh this
cache; tools that don't read whatever the last cached value was, OR
fall back to "unconnected" when no cache exists.

Hints are per-tool. cl_scan_all gets a long-form pitch about scope
narrowing; cl_check_updates gets a Business-tier pitch about
regulation update notifications. Some tools (cl_version,
cl_report_bug, cl_disconnect) get NO hint by design — they're utility
tools where a paywall nudge would be intrusive.
"""
import json
import os
import tempfile

import pytest


# ──────────────────────────────────────────────────────────────────────
# Cache helpers
# ──────────────────────────────────────────────────────────────────────


def test_cache_tier_creates_file_with_value():
    from core.upgrade_hint import cache_tier, get_cached_tier

    with tempfile.TemporaryDirectory() as tmp:
        cache_tier(tmp, "pro")
        assert get_cached_tier(tmp) == "pro"


def test_get_cached_tier_returns_unconnected_when_no_cache():
    from core.upgrade_hint import get_cached_tier

    with tempfile.TemporaryDirectory() as tmp:
        assert get_cached_tier(tmp) == "unconnected"


def test_get_cached_tier_returns_unconnected_on_corrupt_json():
    from core.upgrade_hint import get_cached_tier

    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = os.path.join(tmp, ".compliancelint", "local")
        os.makedirs(cache_dir)
        with open(os.path.join(cache_dir, "tier.json"), "w") as f:
            f.write("{not valid json")
        assert get_cached_tier(tmp) == "unconnected"


def test_cache_tier_overwrites_existing_value():
    from core.upgrade_hint import cache_tier, get_cached_tier

    with tempfile.TemporaryDirectory() as tmp:
        cache_tier(tmp, "free")
        cache_tier(tmp, "pro")
        assert get_cached_tier(tmp) == "pro"


# ──────────────────────────────────────────────────────────────────────
# Footer building — per-tier behaviour
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("paid_tier", ["starter", "pro", "business", "enterprise"])
def test_footer_empty_for_paid_tiers(paid_tier):
    """Paid tiers see no upgrade footer — they're already customers."""
    from core.upgrade_hint import build_upgrade_hint_footer

    out = build_upgrade_hint_footer("cl_scan_all", paid_tier)
    assert out == ""


@pytest.mark.parametrize(
    "free_or_unconnected",
    ["free", "unconnected"],
)
def test_footer_shown_for_free_and_unconnected(free_or_unconnected):
    """Free + unconnected users see the upgrade footer."""
    from core.upgrade_hint import build_upgrade_hint_footer

    out = build_upgrade_hint_footer("cl_scan_all", free_or_unconnected)
    # Footer must be non-empty and visually distinct (separator).
    assert out != ""
    assert "---" in out
    # Must include the dashboard URL for direct CTA.
    assert "compliancelint.dev" in out.lower() or "/dashboard/plans" in out


def test_footer_empty_for_tools_without_hint_registered():
    """Utility tools (cl_version etc.) don't have a hint; footer is empty."""
    from core.upgrade_hint import build_upgrade_hint_footer

    assert build_upgrade_hint_footer("cl_version", "free") == ""
    assert build_upgrade_hint_footer("cl_report_bug", "free") == ""
    assert build_upgrade_hint_footer("cl_disconnect", "free") == ""


def test_footer_empty_for_unknown_tool_name():
    """Defensive: future tools without a registered hint don't blow up."""
    from core.upgrade_hint import build_upgrade_hint_footer

    assert build_upgrade_hint_footer("cl_nonexistent", "free") == ""


# ──────────────────────────────────────────────────────────────────────
# Per-tool hint content — at-least-the-key-message-is-there
# ──────────────────────────────────────────────────────────────────────


def test_cl_scan_all_footer_mentions_scope_narrowing():
    from core.upgrade_hint import build_upgrade_hint_footer

    out = build_upgrade_hint_footer("cl_scan_all", "free")
    # The defining pitch for cl_scan_all is "narrow scope" — verifies
    # the registry mapped the right message to the right tool.
    assert "narrow" in out.lower() or "scope" in out.lower()


def test_cl_action_plan_footer_mentions_scope_or_role():
    from core.upgrade_hint import build_upgrade_hint_footer

    out = build_upgrade_hint_footer("cl_action_plan", "free")
    msg = out.lower()
    assert "scope" in msg or "role" in msg or "narrow" in msg


def test_cl_check_updates_footer_mentions_business_or_notifications():
    from core.upgrade_hint import build_upgrade_hint_footer

    out = build_upgrade_hint_footer("cl_check_updates", "free")
    msg = out.lower()
    assert "business" in msg or "notification" in msg or "update" in msg


def test_cl_explain_footer_mentions_history_or_tracking():
    from core.upgrade_hint import build_upgrade_hint_footer

    out = build_upgrade_hint_footer("cl_explain", "free")
    msg = out.lower()
    assert "history" in msg or "track" in msg or "progress" in msg


# ──────────────────────────────────────────────────────────────────────
# Footer always includes plans URL + missing features
# ──────────────────────────────────────────────────────────────────────


def test_footer_includes_plans_url_for_every_registered_tool():
    """Every registered tool's free footer must include the plans URL
    so the AI client can render a clickable CTA."""
    from core.upgrade_hint import TOOL_HINTS, build_upgrade_hint_footer

    for tool_name in TOOL_HINTS.keys():
        out = build_upgrade_hint_footer(tool_name, "free")
        assert "/dashboard/plans" in out, f"{tool_name} footer missing plans URL"


def test_footer_includes_missing_features_list():
    from core.upgrade_hint import build_upgrade_hint_footer

    out = build_upgrade_hint_footer("cl_scan_all", "free")
    # The footer should list the missing features by name so the
    # AI client can decide which to highlight contextually.
    assert "scope_narrowing" in out or "questionnaire" in out


# ──────────────────────────────────────────────────────────────────────
# Footer round-trip with cache
# ──────────────────────────────────────────────────────────────────────


def test_full_round_trip_cache_then_footer():
    """Realistic flow: SaaS sync caches tier, next tool call reads it."""
    from core.upgrade_hint import (
        build_upgrade_hint_footer,
        cache_tier,
        get_cached_tier,
    )

    with tempfile.TemporaryDirectory() as tmp:
        # Initial state: unconnected → footer shown.
        tier = get_cached_tier(tmp)
        assert tier == "unconnected"
        assert build_upgrade_hint_footer("cl_scan_all", tier) != ""

        # User runs cl_sync; SaaS returns tier=pro; we cache it.
        cache_tier(tmp, "pro")

        # Next tool call: tier=pro, footer empty.
        tier = get_cached_tier(tmp)
        assert tier == "pro"
        assert build_upgrade_hint_footer("cl_scan_all", tier) == ""


# ──────────────────────────────────────────────────────────────────────
# JSON-aware injection (spec §H structured form for json.dumps callers)
# ──────────────────────────────────────────────────────────────────────


def test_append_upgrade_hint_injects_meta_for_json_object_response():
    """JSON-shaped response → upgrade_hint embedded in `_meta` key, not
    appended as text. Existing json.loads consumers see a regular dict
    with one extra `_meta` key."""
    from core.upgrade_hint import append_upgrade_hint

    response = json.dumps({"obligation_id": "ART04-OBL-1", "title": "AI Literacy"})
    out = append_upgrade_hint(response, "cl_action_guide", tier="free")
    parsed = json.loads(out)
    assert parsed["obligation_id"] == "ART04-OBL-1"
    assert parsed["title"] == "AI Literacy"
    assert "_meta" in parsed
    assert "upgrade_hint" in parsed["_meta"]
    hint = parsed["_meta"]["upgrade_hint"]
    assert hint["tier_at_scan"] == "free"
    assert "message" in hint
    assert hint["url"].endswith("/dashboard/plans")
    assert isinstance(hint["missing_features"], list)


def test_append_upgrade_hint_preserves_existing_meta_dict():
    """If the response already has an `_meta` key as dict, merge in
    (don't clobber sibling fields)."""
    from core.upgrade_hint import append_upgrade_hint

    response = json.dumps(
        {
            "data": "x",
            "_meta": {"version": "1.2.3", "scanned_at": "2026-04-29"},
        }
    )
    out = append_upgrade_hint(response, "cl_explain", tier="free")
    parsed = json.loads(out)
    assert parsed["_meta"]["version"] == "1.2.3"
    assert parsed["_meta"]["scanned_at"] == "2026-04-29"
    assert parsed["_meta"]["upgrade_hint"]["tier_at_scan"] == "free"


def test_append_upgrade_hint_no_meta_for_paid_json_response():
    """Paid tier → JSON response unchanged (no _meta added)."""
    from core.upgrade_hint import append_upgrade_hint

    response = json.dumps({"data": "x"})
    out = append_upgrade_hint(response, "cl_explain", tier="pro")
    parsed = json.loads(out)
    assert "_meta" not in parsed
    assert parsed == {"data": "x"}


def test_append_upgrade_hint_wraps_json_array_response():
    """JSON array response → wrap in {results, _meta} envelope."""
    from core.upgrade_hint import append_upgrade_hint

    response = json.dumps([{"a": 1}, {"a": 2}])
    out = append_upgrade_hint(response, "cl_action_plan", tier="free")
    parsed = json.loads(out)
    assert parsed["results"] == [{"a": 1}, {"a": 2}]
    assert parsed["_meta"]["upgrade_hint"]["tier_at_scan"] == "free"


def test_append_upgrade_hint_falls_back_to_text_for_non_json():
    """Plain text response (e.g. cl_scan_all markdown output) → footer
    appended as text per legacy behavior."""
    from core.upgrade_hint import append_upgrade_hint

    response = "Scan complete. 3 issues found."
    out = append_upgrade_hint(response, "cl_scan_all", tier="free")
    assert out.startswith("Scan complete. 3 issues found.")
    assert "ComplianceLint hint" in out
    assert "/dashboard/plans" in out


def test_append_upgrade_hint_falls_back_to_text_on_invalid_json():
    """Response that LOOKS like JSON (starts with `{`) but is malformed
    → fall back to text-append rather than crashing."""
    from core.upgrade_hint import append_upgrade_hint

    response = "{not valid json at all}"
    out = append_upgrade_hint(response, "cl_scan_all", tier="free")
    assert out.startswith("{not valid json at all}")
    assert "ComplianceLint hint" in out


def test_build_upgrade_hint_meta_returns_structured_dict():
    """Direct API for callers that build their own response shape."""
    from core.upgrade_hint import build_upgrade_hint_meta

    meta = build_upgrade_hint_meta("cl_scan_all", "free")
    assert meta is not None
    assert meta["tier_at_scan"] == "free"
    assert isinstance(meta["message"], str) and len(meta["message"]) > 20
    assert meta["url"].endswith("/dashboard/plans")
    assert isinstance(meta["missing_features"], list)
    assert len(meta["missing_features"]) > 0


def test_build_upgrade_hint_meta_returns_none_for_paid():
    from core.upgrade_hint import build_upgrade_hint_meta

    assert build_upgrade_hint_meta("cl_scan_all", "pro") is None
    assert build_upgrade_hint_meta("cl_scan_all", "starter") is None
    assert build_upgrade_hint_meta("cl_scan_all", "business") is None


def test_build_upgrade_hint_meta_returns_none_for_unregistered_tool():
    from core.upgrade_hint import build_upgrade_hint_meta

    assert build_upgrade_hint_meta("cl_version", "free") is None
    assert build_upgrade_hint_meta("cl_disconnect", "free") is None


def test_cache_tier_invalid_value_rejected_falls_back():
    """Cache file with an invalid tier value should fall back to
    'unconnected' rather than passing through unchecked strings."""
    from core.upgrade_hint import get_cached_tier

    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = os.path.join(tmp, ".compliancelint", "local")
        os.makedirs(cache_dir)
        with open(os.path.join(cache_dir, "tier.json"), "w") as f:
            json.dump({"tier_at_scan": "ultra_premium"}, f)
        # Unknown tier → treat as unconnected (legal-safe, force re-fetch).
        assert get_cached_tier(tmp) == "unconnected"
