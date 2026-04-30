"""Phase 4 Task 12b — Paid-tier evidence completeness gate.

Pure function that decides, given a SaaS-narrowed questionnaire and the
evidence already on disk for a project, whether `cl_scan_all` should:
  - proceed (status="ok"), or
  - return an AI-first prompt asking the user to sync evidence first
    (status="pending_evidence_needs_sync").

Spec: 2026-04-29-pre-launch-paid-engine-spec
§B (SaaS Applicability Engine — enforcement_mode/questionnaire fields)
and §H (AI-First Onboarding — soft prompts, NOT hard errors).

Legal-asymmetry rules from §B (over-blocking is dangerous, but
silently HIDING obligations is 100x more dangerous):

  questionnaire=None / {}     → proceed (no narrowing to enforce against)
  enforcement_mode=None       → treated as "lenient" (default safe)
  enforcement_mode="lenient"  → status="ok" with `warnings` list
  enforcement_mode="strict"   → block on missing evidence
  evidence_min missing  → treated as 0 (no structural enforcement)
  completion_required missing → treated as False (don't enforce)

The function is intentionally I/O-free. The wrapper that loads
`.compliancelint/local/articles/*.json` and calls this lives in
`scanner/server.py:_check_paid_completion_gate`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# Sentinel for "the user explicitly opted into strict gating".
_STRICT_MODE = "strict"


@dataclass
class EnforceResult:
    """Outcome of a single enforcement check.

    `status="ok"` means the wrapper should NOT short-circuit cl_scan_all.
    `status="pending_evidence_needs_sync"` means the wrapper should
    return a JSON early-out using the prompt + auto_action_on_yes
    fields below. The shape is what AI clients (Claude Code, Cursor)
    parse to render a single "Want me to sync? (y/n)" question.
    """

    status: str  # "ok" | "pending_evidence_needs_sync"
    pending: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    prompt_to_user: str = ""
    auto_action_on_yes: str = ""  # "cl_sync" when status != "ok"
    then_continue: str = ""  # "cl_scan_all" when status != "ok"


def _coerce_int(v) -> int:
    """Treat None / missing / non-numeric as 0 — never throw on bad
    questionnaire data. Per §B, the safe default is 'no enforcement'."""
    if isinstance(v, bool):  # bool is subclass of int — exclude explicitly
        return 0
    if isinstance(v, int):
        return v
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _is_strict(mode) -> bool:
    """Per §B: ONLY the literal string "strict" enables blocking. Any
    other value (None, "", "garbage", "STRICT" with caps) is treated
    as lenient — never silently escalate."""
    return mode == _STRICT_MODE


def enforce_paid_completion(
    questionnaire: Optional[dict],
    evidence_counts: Optional[dict],
    enforcement_mode: Optional[str] = None,
) -> EnforceResult:
    """Check evidence completeness against the SaaS-narrowed questionnaire.

    Args:
        questionnaire: dict mapping obligation_id → spec row (with
          `evidence_min` int + `completion_required` bool fields),
          or None when SaaS returned no narrowing (free tier / fallback).
        evidence_counts: dict mapping obligation_id → int (current
          evidence array length on disk). Use evidence_counts_from_state
          to derive this from the on-disk state.json.
        enforcement_mode: "strict" enables blocking; anything else is
          lenient. Default lenient.

    Returns:
        EnforceResult — caller (cl_scan_all wrapper) reads `.status`
        and either proceeds (`ok`) or emits the AI-first prompt JSON
        from the other fields.
    """
    counts = evidence_counts or {}

    # Safe-fallback: nothing to enforce against → proceed.
    if not questionnaire:
        return EnforceResult(status="ok")

    pending: list[dict] = []
    for oid, row in questionnaire.items():
        if not isinstance(row, dict):
            continue
        if not row.get("completion_required"):
            continue
        expected = _coerce_int(row.get("evidence_min"))
        if expected <= 0:
            continue
        actual = _coerce_int(counts.get(oid))
        if actual < expected:
            pending.append(
                {
                    "obligation_id": oid,
                    "expected": expected,
                    "actual": actual,
                }
            )

    if not pending:
        return EnforceResult(status="ok")

    if not _is_strict(enforcement_mode):
        # Lenient (and the unknown-mode safe default): never block,
        # surface gaps as warnings only.
        warnings = [
            f"{p['obligation_id']}: {p['actual']} of {p['expected']} expected evidence"
            for p in pending
        ]
        return EnforceResult(status="ok", warnings=warnings)

    # Strict mode — block, return AI-first prompt shape.
    return EnforceResult(
        status="pending_evidence_needs_sync",
        pending=pending,
        prompt_to_user=_build_prompt(pending),
        auto_action_on_yes="cl_sync",
        then_continue="cl_scan_all",
    )


def _build_prompt(pending: list[dict]) -> str:
    """Single-line, user-facing prompt that AI clients render verbatim.

    The exact wording matters: must be a single short question ending
    in '?', under 300 chars, no newlines, no markdown — AI clients
    paste it into chat. Spec §H discourages framework jargon
    ('_scope', 'template') in user-facing copy.
    """
    n = len(pending)
    if n == 1:
        oid = pending[0]["obligation_id"]
        return (
            f"{oid} needs evidence on file before this scan can run. "
            f"Want me to run cl_sync to pull it from your dashboard?"
        )
    return (
        f"{n} obligations need evidence on file before this scan can run. "
        f"Want me to run cl_sync to pull them from your dashboard?"
    )


def evidence_counts_from_state(state: Optional[dict]) -> dict[str, int]:
    """Flatten the nested `load_state` shape to {obligation_id: count}.

    The on-disk shape is:
        state["articles"]["art9"]["findings"]["ART9-OBL-1"]["evidence"]
            → list of evidence dicts (count = len)

    Defensive: missing keys, malformed `evidence` (string/None instead
    of list), and absent articles all yield 0 — never raise. Older
    art{N}.json files (pre-Evidence-v4) lack the `evidence` key
    entirely; treat as 0, not missing.
    """
    if not isinstance(state, dict):
        return {}
    articles = state.get("articles")
    if not isinstance(articles, dict):
        return {}

    counts: dict[str, int] = {}
    for art_data in articles.values():
        if not isinstance(art_data, dict):
            continue
        findings = art_data.get("findings")
        if not isinstance(findings, dict):
            continue
        for oid, finding in findings.items():
            if not isinstance(finding, dict):
                counts[oid] = 0
                continue
            ev = finding.get("evidence")
            if isinstance(ev, list):
                counts[oid] = len(ev)
            else:
                counts[oid] = 0
    return counts
