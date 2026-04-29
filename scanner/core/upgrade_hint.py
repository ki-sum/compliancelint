"""Cross-AI-client contextual paywall — Phase 5 Task 15 (2026-04-29).

MCP tool responses are consumed by AI clients (Claude / Cursor / Cline)
in heterogeneous UIs. To get a free / unconnected user to upgrade, the
hint must travel with the tool's normal response, not in a separate
channel the AI client may strip.

Solution: append a formatted footer to the tool response when the user's
tier is `free` or `unconnected`. Paid tiers (`starter`+) get no footer
— they are already paying customers and the nudge becomes noise.

Tier detection: a small JSON cache at
`{project_path}/.compliancelint/local/tier.json` stores the most recent
`tier_at_scan` seen on a SaaS scan-settings response. Tools that hit
SaaS (cl_scan_all, cl_sync, cl_analyze_project) refresh it; tools that
don't read the last cached value, OR fall back to `"unconnected"` if no
cache exists.

Per-tool registry: the message should reflect the SPECIFIC paywalled
benefit the user would unlock, not a generic "upgrade now" CTA. E.g.
`cl_scan_all`'s pitch is scope narrowing; `cl_check_updates`'s pitch
is regulation update notifications (Business-tier).
"""
import json
import os
from typing import Final, Literal

TierStatus = Literal[
    "unconnected", "free", "starter", "pro", "business", "enterprise"
]

_VALID_TIERS: Final[frozenset[str]] = frozenset(
    {"unconnected", "free", "starter", "pro", "business", "enterprise"}
)
_PAID_TIERS: Final[frozenset[str]] = frozenset(
    {"starter", "pro", "business", "enterprise"}
)

PLANS_URL: Final[str] = "https://compliancelint.dev/dashboard/plans"


# Per-tool hint registry. The message names the SPECIFIC paywalled
# benefit so the AI client / user sees a tailored pitch rather than a
# generic "upgrade now" footer.
TOOL_HINTS: Final[dict[str, dict]] = {
    "cl_scan_all": {
        "free_message": (
            "You're seeing all 247 obligations across 44 articles. "
            "Connect to Starter+ to narrow scope to your specific AI "
            "system (saves ~70% review time) and unlock per-obligation "
            "questionnaires that prevent AI hallucination."
        ),
        "missing_features": [
            "scope_narrowing",
            "questionnaire",
            "evidence_enforcement",
        ],
    },
    "cl_scan": {
        "free_message": (
            "Single-article scan. Run cl_scan_all + Connect to Starter+ "
            "to see only the articles applicable to YOUR system, with "
            "per-obligation questionnaires."
        ),
        "missing_features": ["scope_narrowing", "questionnaire"],
    },
    "cl_action_plan": {
        "free_message": (
            "Action plan covers all obligations. Connect to Starter+ "
            "to filter by your system's role (provider / deployer / etc.) "
            "and risk classification — typically halves the actionable "
            "list."
        ),
        "missing_features": ["scope_narrowing", "smart_remediation"],
    },
    "cl_explain": {
        "free_message": (
            "Legal text + interpretation. Connect to ComplianceLint "
            "dashboard to track compliance progress over time, generate "
            "audit-ready PDF reports, and see history trends."
        ),
        "missing_features": ["history", "trend_tracking", "pdf_reports"],
    },
    "cl_action_guide": {
        "free_message": (
            "Manual obligation guide. Connect to Pro to fill Human Gates "
            "questionnaires inline + attach evidence directly from your "
            "git repo."
        ),
        "missing_features": ["humanGatesFill", "evidenceReferences"],
    },
    "cl_check_updates": {
        "free_message": (
            "Auto-notifications for EU AI Act regulation updates are a "
            "Business-tier feature. Connect to Business plan to receive "
            "automatic alerts when new harmonised standards or guidance "
            "are published."
        ),
        "missing_features": ["regulation_updates"],
    },
    "cl_interim_standard": {
        "free_message": (
            "Interim standards reference. Connect to ComplianceLint "
            "dashboard for full audit-trail of which standards your "
            "system claims compliance with + version history."
        ),
        "missing_features": ["audit_trail", "history"],
    },
    "cl_analyze_project": {
        "free_message": (
            "AI project analysis. Connect to Starter+ for SaaS-confirmed "
            "applicability scoping (vs AI-only inference) and persistent "
            "scan history."
        ),
        "missing_features": ["scope_narrowing", "history"],
    },
    "cl_verify_evidence": {
        "free_message": (
            "Evidence quality check. Connect to Pro to upload evidence "
            "files directly from the dashboard + cross-vendor evidence "
            "verification across scans."
        ),
        "missing_features": ["fileUploadToRepo", "evidenceReferences"],
    },
}


def _cache_path(project_path: str) -> str:
    return os.path.join(project_path, ".compliancelint", "local", "tier.json")


def cache_tier(project_path: str, tier: str) -> None:
    """Persist the user's tier from a SaaS response so future tool calls
    can read it without an extra HTTP roundtrip."""
    cache_dir = os.path.join(project_path, ".compliancelint", "local")
    os.makedirs(cache_dir, exist_ok=True)
    with open(_cache_path(project_path), "w", encoding="utf-8") as f:
        json.dump({"tier_at_scan": tier}, f)


def get_cached_tier(project_path: str) -> str:
    """Read the cached tier; return "unconnected" if no cache exists,
    cache file is corrupt, or the stored value is not a known tier."""
    try:
        with open(_cache_path(project_path), encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return "unconnected"
    tier = data.get("tier_at_scan")
    if not isinstance(tier, str) or tier not in _VALID_TIERS:
        return "unconnected"
    return tier


def build_upgrade_hint_footer(tool_name: str, tier: str) -> str:
    """Return the formatted footer text to append, or empty string when
    no hint applies (paid tier, unregistered tool, etc.)."""
    if tier in _PAID_TIERS:
        return ""
    info = TOOL_HINTS.get(tool_name)
    if info is None:
        return ""
    features = ", ".join(info["missing_features"])
    return (
        "\n\n---\n"
        f"\U0001F4A1 ComplianceLint hint: {info['free_message']}\n"
        f"Plans: {PLANS_URL}\n"
        f"Tier: {tier} | Missing features: {features}"
    )


def build_upgrade_hint_meta(tool_name: str, tier: str) -> dict | None:
    """Return a structured `meta.upgrade_hint` object suitable for
    embedding in JSON responses, or None when no hint applies."""
    if tier in _PAID_TIERS:
        return None
    info = TOOL_HINTS.get(tool_name)
    if info is None:
        return None
    return {
        "tier_at_scan": tier,
        "message": info["free_message"],
        "url": PLANS_URL,
        "missing_features": list(info["missing_features"]),
    }


def append_upgrade_hint(
    response_text: str,
    tool_name: str,
    project_path: str | None = None,
    tier: str | None = None,
) -> str:
    """Convenience wrapper: read tier from cache (or use override) and
    attach the upgrade hint to the response.

    Detects whether the response is JSON-shaped:
      - JSON object → inject `_meta.upgrade_hint` field, re-serialize.
        This is the spec §H structured form. Existing JSON consumers
        (json.loads + key access) continue to work; the extra `_meta`
        field is additive.
      - JSON array → wrap in {"results": [...], "_meta": {...}}.
        Less common; covered for completeness.
      - Plain text / non-JSON → append the human-readable footer.

    Use `tier` override when the caller has fresh tier info (e.g. from
    a SaaS response just received). Otherwise reads cache via
    `project_path`.
    """
    if tier is None:
        if project_path is None:
            tier = "unconnected"
        else:
            tier = get_cached_tier(project_path)

    meta = build_upgrade_hint_meta(tool_name, tier)
    if meta is None:
        return response_text

    # Best-effort JSON detection: parse + re-serialize when possible.
    # Falls back to text-footer append on parse failure.
    stripped = response_text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                # Preserve existing _meta if present; merge upgrade_hint in.
                existing_meta = parsed.get("_meta")
                if isinstance(existing_meta, dict):
                    existing_meta["upgrade_hint"] = meta
                    parsed["_meta"] = existing_meta
                else:
                    parsed["_meta"] = {"upgrade_hint": meta}
                return json.dumps(parsed, indent=2, ensure_ascii=False)
            if isinstance(parsed, list):
                return json.dumps(
                    {"results": parsed, "_meta": {"upgrade_hint": meta}},
                    indent=2,
                    ensure_ascii=False,
                )
        except (json.JSONDecodeError, ValueError):
            pass

    # Plain text response — append the human-readable footer.
    return response_text + build_upgrade_hint_footer(tool_name, tier)
