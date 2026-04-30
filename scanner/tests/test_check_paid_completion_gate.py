"""Phase 4 Task 12b — Integration test for `_check_paid_completion_gate`,
the helper that wires `enforce_paid_completion` into cl_scan_all
(scanner/server.py).

Spec: 2026-04-29-pre-launch-paid-engine-spec §B + §H.

Contract under test:
  - Reads `_scope._saas_questionnaire` + `_scope._saas_enforcement_mode`
    from the merged scope (already populated by
    `_apply_saas_settings_to_scope`).
  - Loads evidence counts from `.compliancelint/local/articles/*.json`
    via `load_state` + `evidence_counts_from_state`.
  - Returns either:
      None       → proceed with scan (ok / lenient / no-questionnaire)
      str (JSON) → early-return shape with status, prompt, auto_action,
                   then_continue, pending_obligations
  - Safe fallbacks: any exception loading state → return None (proceed).
    Never block the scan on infrastructure failure.

The helper is a single-purpose seam: pure I/O wrapper around the pure
`enforce_paid_completion`. Splitting it out keeps cl_scan_all's main
flow short and lets us unit-test the wiring without booting the whole
44-module scanner.
"""

import json
import os
import sys
import tempfile

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


# ──────────────────────────────────────────────────────────────────────
# Fixtures: minimal ProjectContext-like object + state.json on disk
# ──────────────────────────────────────────────────────────────────────


class _StubCtx:
    """Minimum ctx surface that the gate helper reads:
    `compliance_answers` dict with a `_scope` sub-dict."""

    def __init__(self, scope: dict):
        self.compliance_answers = {"_scope": scope}


def _seed_articles_dir(project_path: str, evidence_per_oid: dict[str, int]) -> None:
    """Write fake .compliancelint/local/articles/artN.json so load_state
    sees the evidence counts the test wants."""
    from core import paths

    paths.ensure_local_dir(project_path)
    articles_dir = os.path.join(
        project_path, ".compliancelint", "local", "articles"
    )
    os.makedirs(articles_dir, exist_ok=True)

    # Group OIDs by article number prefix.
    by_art: dict[str, dict[str, int]] = {}
    for oid, count in evidence_per_oid.items():
        # Parse "ART9-OBL-1" → article 9 → "art9.json"
        m = oid.split("-")[0]
        if not m.startswith("ART"):
            continue
        art_num = m[3:].lstrip("0") or "0"
        art_key = f"art{art_num}"
        by_art.setdefault(art_key, {})[oid] = count

    for art_key, oids in by_art.items():
        findings = {
            oid: {
                "status": "open",
                "evidence": [{"id": f"e{i}"} for i in range(count)],
            }
            for oid, count in oids.items()
        }
        article_data = {
            "overall_level": "compliant",
            "scan_date": "2026-04-29T00:00:00Z",
            "findings": findings,
        }
        with open(
            os.path.join(articles_dir, f"{art_key}.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(article_data, f)


# ──────────────────────────────────────────────────────────────────────
# 1. None-returning paths (proceed with scan)
# ──────────────────────────────────────────────────────────────────────


def test_no_questionnaire_returns_none_proceeds_with_scan():
    """Free tier or legacy SaaS — no questionnaire key in scope.
    Helper MUST return None so cl_scan_all proceeds."""
    from server import _check_paid_completion_gate

    ctx = _StubCtx({})  # no _saas_questionnaire
    with tempfile.TemporaryDirectory() as tmp:
        result = _check_paid_completion_gate(ctx, tmp)
    assert result is None


def test_questionnaire_none_explicit_returns_none():
    """Spec §B: SaaS may explicitly set questionnaire=None for free
    tier. Helper must treat as 'no narrowing' = proceed."""
    from server import _check_paid_completion_gate

    ctx = _StubCtx({"_saas_questionnaire": None})
    with tempfile.TemporaryDirectory() as tmp:
        result = _check_paid_completion_gate(ctx, tmp)
    assert result is None


def test_lenient_mode_with_pending_evidence_returns_none():
    """Lenient + pending evidence → proceed (warnings only). The
    safe-fallback rule: scanner never blocks user when SaaS hasn't
    explicitly opted into strict gating."""
    from server import _check_paid_completion_gate

    ctx = _StubCtx({
        "_saas_questionnaire": {
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        "_saas_enforcement_mode": "lenient",
    })
    with tempfile.TemporaryDirectory() as tmp:
        # No articles seeded → 0 evidence
        result = _check_paid_completion_gate(ctx, tmp)
    assert result is None


def test_strict_mode_with_complete_evidence_returns_none():
    """Strict but all required obligations satisfied → proceed."""
    from server import _check_paid_completion_gate

    ctx = _StubCtx({
        "_saas_questionnaire": {
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        "_saas_enforcement_mode": "strict",
    })
    with tempfile.TemporaryDirectory() as tmp:
        _seed_articles_dir(tmp, {"ART9-OBL-1": 1})
        result = _check_paid_completion_gate(ctx, tmp)
    assert result is None


# ──────────────────────────────────────────────────────────────────────
# 2. JSON-returning paths (early-return AI-first prompt)
# ──────────────────────────────────────────────────────────────────────


def test_strict_mode_with_missing_evidence_returns_pending_json():
    """The headline behavior: strict + 0 evidence → return AI-first
    prompt JSON with auto_action_on_yes='cl_sync'."""
    from server import _check_paid_completion_gate

    ctx = _StubCtx({
        "_saas_questionnaire": {
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        "_saas_enforcement_mode": "strict",
    })
    with tempfile.TemporaryDirectory() as tmp:
        result = _check_paid_completion_gate(ctx, tmp)

    assert isinstance(result, str)
    parsed = json.loads(result)
    assert parsed["status"] == "pending_evidence_needs_sync"
    assert parsed["auto_action_on_yes"] == "cl_sync"
    assert parsed["then_continue"] == "cl_scan_all"
    assert isinstance(parsed["prompt_to_user"], str) and parsed["prompt_to_user"]
    assert isinstance(parsed["pending_obligations"], list)
    assert len(parsed["pending_obligations"]) == 1
    assert parsed["pending_obligations"][0]["obligation_id"] == "ART9-OBL-1"


def test_strict_mode_with_partial_evidence_returns_pending_json():
    """Strict + 1 of 2 expected → block, list ART11 only."""
    from server import _check_paid_completion_gate

    ctx = _StubCtx({
        "_saas_questionnaire": {
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
            "ART11-OBL-1": {"evidence_min": 2, "completion_required": True},
        },
        "_saas_enforcement_mode": "strict",
    })
    with tempfile.TemporaryDirectory() as tmp:
        _seed_articles_dir(tmp, {"ART9-OBL-1": 1, "ART11-OBL-1": 1})
        result = _check_paid_completion_gate(ctx, tmp)

    assert isinstance(result, str)
    parsed = json.loads(result)
    assert parsed["status"] == "pending_evidence_needs_sync"
    pending_ids = [p["obligation_id"] for p in parsed["pending_obligations"]]
    assert pending_ids == ["ART11-OBL-1"]


# ──────────────────────────────────────────────────────────────────────
# 3. Safe-fallback paths (state load failure must NEVER block)
# ──────────────────────────────────────────────────────────────────────


def test_load_state_exception_degrades_to_proceed(monkeypatch):
    """Spec §B: SaaS or filesystem failure during evidence read MUST
    NOT block the scan. Legal asymmetry — hiding obligations is 100x
    worse than over-reporting; same applies to over-blocking."""
    from server import _check_paid_completion_gate

    def boom(_path):
        raise OSError("disk on fire")

    monkeypatch.setattr("core.state.load_state", boom)

    ctx = _StubCtx({
        "_saas_questionnaire": {
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        "_saas_enforcement_mode": "strict",
    })
    with tempfile.TemporaryDirectory() as tmp:
        result = _check_paid_completion_gate(ctx, tmp)

    assert result is None  # MUST proceed, even though strict + would-block


def test_strict_mode_default_when_mode_missing_in_scope():
    """Per spec §B legal-safe rule, missing _saas_enforcement_mode key
    defaults to lenient — NEVER silently 'strict'. So a strict scenario
    is only reachable when SaaS explicitly opts in."""
    from server import _check_paid_completion_gate

    ctx = _StubCtx({
        "_saas_questionnaire": {
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        # _saas_enforcement_mode INTENTIONALLY omitted
    })
    with tempfile.TemporaryDirectory() as tmp:
        result = _check_paid_completion_gate(ctx, tmp)

    # Default lenient → proceed even with 0 evidence
    assert result is None


def test_optional_oids_not_blocking_in_strict_mode():
    """OIDs without completion_required=True are advisory; even strict
    mode must not block on them."""
    from server import _check_paid_completion_gate

    ctx = _StubCtx({
        "_saas_questionnaire": {
            "ART50-OBL-1": {"evidence_min": 1, "completion_required": False},
        },
        "_saas_enforcement_mode": "strict",
    })
    with tempfile.TemporaryDirectory() as tmp:
        result = _check_paid_completion_gate(ctx, tmp)
    assert result is None
