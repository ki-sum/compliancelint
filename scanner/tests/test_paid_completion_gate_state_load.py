"""B4 self-audit follow-up — state-load failure classification in
`_check_paid_completion_gate`.

Spec gap fixed (LEAST_CONFIDENT line of public commit 136149f):
"state-load safe-fallback degrades to 'proceed' on any exception.
Correct per Spec §B legal asymmetry, but a corrupted articles dir
silently disables the gate. Future enhancement should distinguish
'no articles dir' (true zero state) from 'OSError' (suspicious)."

This fix surfaces the corrupted-dir case so customers don't ship
"strict mode passed" claims when the gate actually bypassed silently.

Three behavior buckets after this fix:

  1. NO articles dir (project never scanned) → empty evidence counts,
     gate runs normally, NO warning logged or surfaced. This is
     legitimate zero state.

  2. articles dir EXISTS + readable → normal load_state path.

  3. articles dir EXISTS but unreadable (permission, corruption, disk
     error during listdir) → log ERROR (not warning) with traceback,
     mutate scope to add `_paid_gate_state_load_warning` so cl_scan_all
     surfaces the issue to the user, return None (proceed — legal
     asymmetry safe).

The 3rd path is the bug class: regulator audits a "strict scan"
report, customer says yes, but gate was silently bypassed.
"""

import json
import os
import sys
import tempfile

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


class _StubCtx:
    def __init__(self, scope: dict):
        self.compliance_answers = {"_scope": scope}


# ──────────────────────────────────────────────────────────────────────
# Bucket 1 — no articles dir, no warning surfaced
# ──────────────────────────────────────────────────────────────────────


def test_no_articles_dir_proceeds_silently_no_warning_surfaced():
    """Project never scanned → no .compliancelint/local/articles dir.
    `load_state` returns empty state. Gate runs normally. No warning
    in scope, no error log."""
    from server import _check_paid_completion_gate

    scope = {
        "_saas_questionnaire": {
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        "_saas_enforcement_mode": "lenient",
    }
    ctx = _StubCtx(scope)

    with tempfile.TemporaryDirectory() as tmp:
        # No .compliancelint/local/articles created — pristine project
        result = _check_paid_completion_gate(ctx, tmp)

    # Lenient + 0 evidence + 1 required → status="ok" with warnings
    # internal to enforce_paid_completion. Wrapper returns None.
    assert result is None
    # Critically: NO state-load warning surfaced (this is zero state,
    # not a corruption case).
    assert "_paid_gate_state_load_warning" not in scope


# ──────────────────────────────────────────────────────────────────────
# Bucket 3 — articles dir unreadable, warning MUST surface
# ──────────────────────────────────────────────────────────────────────


def test_load_state_oserror_surfaces_warning_in_scope(monkeypatch):
    """When load_state raises (e.g. permission denied on listdir,
    disk error), the gate MUST:
      - Still return None (legal-asymmetry safe — never block scan)
      - Mutate scope[_paid_gate_state_load_warning] so cl_scan_all
        surfaces the error to the user.
    Without this, the gate silently bypasses and the customer can't
    tell from scan output that strict mode was effectively disabled."""
    from server import _check_paid_completion_gate

    def raising_load_state(_path):
        raise OSError("Permission denied")

    monkeypatch.setattr("core.state.load_state", raising_load_state)

    scope = {
        "_saas_questionnaire": {
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        "_saas_enforcement_mode": "strict",
    }
    ctx = _StubCtx(scope)

    with tempfile.TemporaryDirectory() as tmp:
        result = _check_paid_completion_gate(ctx, tmp)

    # Legal asymmetry: must still proceed.
    assert result is None
    # But MUST surface the failure.
    assert "_paid_gate_state_load_warning" in scope
    warning = scope["_paid_gate_state_load_warning"]
    assert isinstance(warning, str) and len(warning) > 0
    # Warning must mention what went wrong + remediation
    assert "permission" in warning.lower() or "OSError" in warning
    # Customer-facing intent: tell them strict was disabled
    assert "bypass" in warning.lower() or "disabled" in warning.lower() or "could not" in warning.lower()


def test_load_state_unexpected_exception_also_surfaces_warning(monkeypatch):
    """Any exception type (not just OSError) must surface — defensive."""
    from server import _check_paid_completion_gate

    def raising_load_state(_path):
        raise RuntimeError("evidence dir corruption")

    monkeypatch.setattr("core.state.load_state", raising_load_state)

    scope = {
        "_saas_questionnaire": {
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        "_saas_enforcement_mode": "strict",
    }
    ctx = _StubCtx(scope)

    with tempfile.TemporaryDirectory() as tmp:
        result = _check_paid_completion_gate(ctx, tmp)

    assert result is None
    assert "_paid_gate_state_load_warning" in scope


def test_state_load_failure_logs_at_error_level(monkeypatch, caplog):
    """Severity matters. Warning logs are easy to ignore; ERROR shows
    up in monitoring + ops dashboards. The original code logged at
    `warning` — upgrade to `error` so corrupted-state events surface
    in alerting."""
    import logging

    from server import _check_paid_completion_gate

    def boom(_path):
        raise OSError("boom")

    monkeypatch.setattr("core.state.load_state", boom)

    ctx = _StubCtx({
        "_saas_questionnaire": {
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        "_saas_enforcement_mode": "strict",
    })
    with tempfile.TemporaryDirectory() as tmp:
        with caplog.at_level(logging.ERROR, logger="compliancelint"):
            _check_paid_completion_gate(ctx, tmp)

    # At least one ERROR record from this gate
    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(error_records) >= 1
    # And it should mention the gate context
    assert any("paid completion gate" in r.message for r in error_records)


# ──────────────────────────────────────────────────────────────────────
# Bucket 2 — happy path unchanged
# ──────────────────────────────────────────────────────────────────────


def test_happy_path_still_works_no_warning_set():
    """Sanity: existing behavior unchanged when state loads cleanly."""
    from core import paths
    from server import _check_paid_completion_gate

    scope = {
        "_saas_questionnaire": {
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        "_saas_enforcement_mode": "strict",
    }
    ctx = _StubCtx(scope)

    with tempfile.TemporaryDirectory() as tmp:
        # Seed an articles dir with one finding having 1 evidence item
        paths.ensure_local_dir(tmp)
        articles_dir = os.path.join(tmp, ".compliancelint", "local", "articles")
        os.makedirs(articles_dir, exist_ok=True)
        with open(os.path.join(articles_dir, "art9.json"), "w", encoding="utf-8") as f:
            json.dump({
                "overall_level": "compliant",
                "scan_date": "2026-04-30T00:00:00Z",
                "findings": {
                    "ART9-OBL-1": {"status": "open", "evidence": [{"id": "e1"}]},
                },
            }, f)

        result = _check_paid_completion_gate(ctx, tmp)

    assert result is None
    assert "_paid_gate_state_load_warning" not in scope
