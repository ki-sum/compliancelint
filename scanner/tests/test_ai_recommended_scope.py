"""Phase 6 Task 16 — `_ai_recommended_scope` field on cl_analyze_project.

Spec: 2026-04-29-pre-launch-paid-engine-spec §H "AI-First Onboarding".

Old hostile UX:
  user: cl_scan_all
  scanner: ❌ Cannot scan: _scope.risk_classification missing.
           Use the compliance_answers_template from cl_analyze_project()...

New AI-first flow:
  cl_analyze_project response carries `_ai_recommended_scope` —
  structured scaffolding the AI client uses to:
    1. Render a user-facing summary of detected stack + AI judgment
    2. Ask user "Continue scan? (y/n)" BEFORE calling cl_scan_all
    3. (When user confirms) chain into cl_scan_all with filled scope

The scanner does NOT run AI itself. `_ai_recommended_scope` is
scaffolding only:
  - `detected_indicators`: structured list of frameworks / AI libs /
    biometric libs / languages parsed from config_contents — pure
    keyword extraction, no AI.
  - `confirmation_required: true` — semantic flag for AI client.
  - `tier_at_scan`: cached tier string — drives the "Connect to
    Starter+" warning copy in the user-facing template.
  - `user_facing_summary_template`: the printable template AI client
    fills + renders verbatim.
  - `ai_classification_instructions`: short instruction string that
    tells AI client what to do with detected_indicators.

The contract is: every cl_analyze_project response has this field
(non-null), even when no indicators are detected — the AI client
must always know to confirm before scanning.
"""

import json
import os
import sys
import tempfile

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


# ──────────────────────────────────────────────────────────────────────
# Fixture helpers
# ──────────────────────────────────────────────────────────────────────


def _seed_python_project(tmp: str, requirements: str) -> None:
    with open(os.path.join(tmp, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write(requirements)
    with open(os.path.join(tmp, "main.py"), "w", encoding="utf-8") as f:
        f.write("print('hello')\n")


def _seed_node_project(tmp: str, package_json: dict) -> None:
    with open(os.path.join(tmp, "package.json"), "w", encoding="utf-8") as f:
        json.dump(package_json, f)
    with open(os.path.join(tmp, "index.js"), "w", encoding="utf-8") as f:
        f.write("console.log('hi');\n")


def _analyze(tmp: str) -> dict:
    """Call cl_analyze_project and parse the JSON response, stripping
    any cross-AI-client upgrade_hint footer that may follow."""
    from server import cl_analyze_project

    raw = cl_analyze_project(tmp)
    # Strip footer if present (text-form upgrade hint appended after JSON).
    # cl_analyze_project returns JSON object → has _meta.upgrade_hint
    # injected, no footer issue. Plain json.loads should work.
    return json.loads(raw)


# ──────────────────────────────────────────────────────────────────────
# 1. Field always present (contract surface)
# ──────────────────────────────────────────────────────────────────────


def test_ai_recommended_scope_field_always_present():
    """Even an empty project must carry the field — AI client uses
    `confirmation_required` even when no indicators detected."""
    from server import cl_analyze_project

    with tempfile.TemporaryDirectory() as tmp:
        response = cl_analyze_project(tmp)
        parsed = json.loads(response)

    assert "_ai_recommended_scope" in parsed
    assert isinstance(parsed["_ai_recommended_scope"], dict)


def test_ai_recommended_scope_has_required_keys():
    """The 5-key contract that AI clients depend on."""
    with tempfile.TemporaryDirectory() as tmp:
        parsed = _analyze(tmp)
        scope = parsed["_ai_recommended_scope"]

    assert "detected_indicators" in scope
    assert "confirmation_required" in scope
    assert "tier_at_scan" in scope
    assert "user_facing_summary_template" in scope
    assert "ai_classification_instructions" in scope


def test_confirmation_required_is_always_true():
    """Per Spec §H, AI client MUST get user y/n confirmation before
    chaining cl_scan_all. The flag is contract-level, not optional."""
    with tempfile.TemporaryDirectory() as tmp:
        parsed = _analyze(tmp)

    assert parsed["_ai_recommended_scope"]["confirmation_required"] is True


# ──────────────────────────────────────────────────────────────────────
# 2. detected_indicators — keyword extraction from config files
# ──────────────────────────────────────────────────────────────────────


def test_detected_indicators_has_4_subkeys():
    """frameworks / ai_libraries / biometric_libraries / languages —
    the 4-bucket split AI client renders to user."""
    with tempfile.TemporaryDirectory() as tmp:
        parsed = _analyze(tmp)
        ind = parsed["_ai_recommended_scope"]["detected_indicators"]

    assert "frameworks" in ind and isinstance(ind["frameworks"], list)
    assert "ai_libraries" in ind and isinstance(ind["ai_libraries"], list)
    assert "biometric_libraries" in ind and isinstance(ind["biometric_libraries"], list)
    assert "languages" in ind and isinstance(ind["languages"], list)


def test_detected_indicators_python_fastapi_transformers():
    """Spec §H example: a project with FastAPI + transformers must
    surface both in detected_indicators."""
    with tempfile.TemporaryDirectory() as tmp:
        _seed_python_project(tmp, "fastapi==0.100\ntransformers==4.30\n")
        parsed = _analyze(tmp)
        ind = parsed["_ai_recommended_scope"]["detected_indicators"]

    assert "fastapi" in ind["frameworks"]
    assert "transformers" in ind["ai_libraries"]


def test_detected_indicators_biometric_lib_separately_classified():
    """face_recognition / dlib / mediapipe go into biometric_libraries
    (not generic ai_libraries) so AI client can flag Annex III §1."""
    with tempfile.TemporaryDirectory() as tmp:
        _seed_python_project(tmp, "fastapi==0.100\nface_recognition==1.3\n")
        parsed = _analyze(tmp)
        ind = parsed["_ai_recommended_scope"]["detected_indicators"]

    assert "face_recognition" in ind["biometric_libraries"]
    # face_recognition must NOT also appear in ai_libraries (avoid
    # double-counting that would mislead AI judgment).
    assert "face_recognition" not in ind["ai_libraries"]


def test_detected_indicators_javascript_react():
    """Node project with react in package.json deps."""
    with tempfile.TemporaryDirectory() as tmp:
        _seed_node_project(
            tmp,
            {"name": "demo", "dependencies": {"react": "18.0.0", "openai": "4.0.0"}},
        )
        parsed = _analyze(tmp)
        ind = parsed["_ai_recommended_scope"]["detected_indicators"]

    assert "react" in ind["frameworks"]
    assert "openai" in ind["ai_libraries"]


def test_detected_indicators_languages_inferred_from_file_extensions():
    """Spec §H summary line shows 'Detected: ... language' — derive
    from existing file_types extension counts."""
    with tempfile.TemporaryDirectory() as tmp:
        _seed_python_project(tmp, "")
        parsed = _analyze(tmp)
        ind = parsed["_ai_recommended_scope"]["detected_indicators"]

    assert "python" in ind["languages"]


def test_empty_project_has_empty_indicator_lists_not_null():
    """No false-positives: a bare empty dir returns [] for each bucket,
    NEVER null. AI client iterates over lists; null would crash."""
    with tempfile.TemporaryDirectory() as tmp:
        parsed = _analyze(tmp)
        ind = parsed["_ai_recommended_scope"]["detected_indicators"]

    assert ind["frameworks"] == []
    assert ind["ai_libraries"] == []
    assert ind["biometric_libraries"] == []
    # Languages may also be [] — empty dir has no source files.
    assert isinstance(ind["languages"], list)


def test_indicator_lists_deduplicate_when_lib_in_multiple_manifests():
    """react listed in both package.json and pyproject.toml-equivalent
    must appear once, not twice. (Edge case — but de-duplication is
    the simplest correct contract.)"""
    with tempfile.TemporaryDirectory() as tmp:
        _seed_node_project(tmp, {"dependencies": {"react": "18.0.0"}})
        # Also create a stray requirements.txt that mentions react —
        # unusual, but tests dedup logic.
        with open(os.path.join(tmp, "requirements.txt"), "w") as f:
            f.write("react\n")
        parsed = _analyze(tmp)
        ind = parsed["_ai_recommended_scope"]["detected_indicators"]

    assert ind["frameworks"].count("react") == 1


# ──────────────────────────────────────────────────────────────────────
# 3. tier_at_scan reflects cached tier
# ──────────────────────────────────────────────────────────────────────


def test_tier_at_scan_defaults_to_unconnected_when_no_cache():
    from server import cl_analyze_project

    with tempfile.TemporaryDirectory() as tmp:
        parsed = json.loads(cl_analyze_project(tmp))

    assert parsed["_ai_recommended_scope"]["tier_at_scan"] in ("unconnected", "free")


def test_tier_at_scan_reflects_cached_pro_tier():
    from core.upgrade_hint import cache_tier
    from server import cl_analyze_project

    with tempfile.TemporaryDirectory() as tmp:
        cache_tier(tmp, "pro")
        parsed = json.loads(cl_analyze_project(tmp))

    assert parsed["_ai_recommended_scope"]["tier_at_scan"] == "pro"


# ──────────────────────────────────────────────────────────────────────
# 4. Templates carry the right substitution placeholders
# ──────────────────────────────────────────────────────────────────────


def test_user_facing_template_is_a_renderable_string():
    """Must be non-empty string with the placeholders AI client fills."""
    with tempfile.TemporaryDirectory() as tmp:
        parsed = _analyze(tmp)
        template = parsed["_ai_recommended_scope"]["user_facing_summary_template"]

    assert isinstance(template, str) and len(template) > 0
    # Placeholders required for AI client to fill.
    # `{stack}` (detected libs) and `{risk}` (AI judgment) are the
    # minimum two AI client renders verbatim.
    assert "{" in template and "}" in template


def test_user_facing_template_includes_continue_prompt():
    """The template ends with the y/n question — Spec §H verbatim."""
    with tempfile.TemporaryDirectory() as tmp:
        parsed = _analyze(tmp)
        template = parsed["_ai_recommended_scope"]["user_facing_summary_template"]

    # Looking for the y/n confirmation pattern.
    lower = template.lower()
    assert "continue" in lower or "scan?" in lower or "(y/n)" in lower


def test_ai_classification_instructions_is_non_empty_string():
    with tempfile.TemporaryDirectory() as tmp:
        parsed = _analyze(tmp)
        instr = parsed["_ai_recommended_scope"]["ai_classification_instructions"]

    assert isinstance(instr, str) and len(instr) > 30


# ──────────────────────────────────────────────────────────────────────
# 5. Defensive: malformed manifest does not crash the analysis
# ──────────────────────────────────────────────────────────────────────


def test_malformed_package_json_does_not_crash():
    """package.json with broken JSON must NOT crash cl_analyze_project.
    detected_indicators just lists what it could parse; no exception."""
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "package.json"), "w") as f:
            f.write("{ broken json }}}")
        # Should not raise
        parsed = _analyze(tmp)

    assert "_ai_recommended_scope" in parsed
    assert "detected_indicators" in parsed["_ai_recommended_scope"]
