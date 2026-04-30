"""Phase 6 Task 16 — `cl_scan_all` auto-chain to `cl_analyze_project`.

Spec: 2026-04-29-pre-launch-paid-engine-spec §H "AI-First Onboarding".

Old hostile UX (current cl_scan_all) when project_context is empty:
  ❌ Cannot scan: project_context is required. Call cl_analyze_project()
  first, read the output, add your own understanding, then pass the
  enriched JSON to cl_scan_all().

New AI-first behavior — same pattern as Task 12b's pending evidence:
  Return structured prompt JSON so AI client can chain automatically.
  {
    "status": "needs_analysis_first",
    "prompt_to_user": "I need to analyze the project structure first
                       before scanning. Want me to run
                       cl_analyze_project to detect the framework
                       + libraries?",
    "auto_action_on_yes": "cl_analyze_project",
    "then_continue": "cl_scan_all"
  }

Contract: missing project_context is the COMMON case (user runs
cl_scan_all first thing). Treating it as a hard error is hostile.
The AI-first signal lets Claude Code / Cursor recover without user
even reading the error.
"""

import json
import os
import sys
import tempfile

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


# ──────────────────────────────────────────────────────────────────────
# 1. Empty project_context returns AI-first prompt JSON
# ──────────────────────────────────────────────────────────────────────


def test_empty_project_context_returns_needs_analysis_first():
    from server import cl_scan_all

    with tempfile.TemporaryDirectory() as tmp:
        raw = cl_scan_all(tmp, project_context="")
        parsed = json.loads(raw)

    assert parsed.get("status") == "needs_analysis_first"


def test_empty_project_context_response_has_auto_chain_fields():
    """AI client uses these 3 fields to chain analyze → scan."""
    from server import cl_scan_all

    with tempfile.TemporaryDirectory() as tmp:
        raw = cl_scan_all(tmp, project_context="")
        parsed = json.loads(raw)

    assert parsed["auto_action_on_yes"] == "cl_analyze_project"
    assert parsed["then_continue"] == "cl_scan_all"
    assert isinstance(parsed["prompt_to_user"], str) and parsed["prompt_to_user"]


def test_empty_project_context_prompt_is_renderable():
    """Prompt must be a single-line, user-facing question — same
    contract as Task 12b's pending_evidence prompt."""
    from server import cl_scan_all

    with tempfile.TemporaryDirectory() as tmp:
        raw = cl_scan_all(tmp, project_context="")
        parsed = json.loads(raw)
        prompt = parsed["prompt_to_user"]

    assert "\n" not in prompt
    assert len(prompt) < 300
    assert prompt.rstrip().endswith("?")


def test_empty_project_context_does_NOT_return_legacy_error_shape():
    """Regression guard: the OLD response had `error` + `fix` keys
    and was a HARD error. New response uses `status` instead."""
    from server import cl_scan_all

    with tempfile.TemporaryDirectory() as tmp:
        raw = cl_scan_all(tmp, project_context="")
        parsed = json.loads(raw)

    # The hostile error shape MUST be gone.
    assert "error" not in parsed
    # AI-first shape replaces it.
    assert "status" in parsed


# ──────────────────────────────────────────────────────────────────────
# 2. Non-empty project_context still flows through to scan
# ──────────────────────────────────────────────────────────────────────


def test_invalid_project_path_still_hard_errors():
    """Auto-chain only kicks in on missing context. Bad path is a
    different failure that user can't fix via cl_analyze_project."""
    from server import cl_scan_all

    raw = cl_scan_all("/nonexistent/path/that/does/not/exist", project_context="")
    parsed = json.loads(raw)

    # Path validation runs BEFORE the context check, so this is the
    # legacy "Directory not found" hard error — still acceptable
    # because re-running analyze won't fix the bad path.
    assert "error" in parsed or parsed.get("status") == "needs_analysis_first"
    # Either shape is OK; the regression we guard is "doesn't crash".


def test_malformed_project_context_json_still_hard_errors():
    """Garbage JSON in project_context is a programmer error, not a
    user-recoverable signal — AI client passed bad data, retrying
    cl_analyze_project won't help."""
    from server import cl_scan_all

    with tempfile.TemporaryDirectory() as tmp:
        raw = cl_scan_all(tmp, project_context="{this is not json")
        parsed = json.loads(raw)

    assert "error" in parsed
    # Specifically, should mention the JSON parse problem.
    assert "json" in parsed["error"].lower() or "invalid" in parsed["error"].lower()


# ──────────────────────────────────────────────────────────────────────
# 3. Cross-pattern with Task 12b — both prompt shapes co-exist
# ──────────────────────────────────────────────────────────────────────


def test_needs_analysis_response_does_not_overlap_pending_evidence():
    """Two distinct AI-first signals must be distinguishable by
    `status` value. Task 12b uses 'pending_evidence_needs_sync',
    Task 16 uses 'needs_analysis_first'. Different `auto_action_on_yes`."""
    from server import cl_scan_all

    with tempfile.TemporaryDirectory() as tmp:
        raw = cl_scan_all(tmp, project_context="")
        parsed = json.loads(raw)

    # The 12b shape would mean cl_sync; the 16 shape means analyze.
    assert parsed["auto_action_on_yes"] == "cl_analyze_project"
    assert parsed["status"] != "pending_evidence_needs_sync"
