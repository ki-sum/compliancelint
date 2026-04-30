"""Phase 4 Task 12b — `enforce_paid_completion` pure-function unit tests.

Spec: 2026-04-29-pre-launch-paid-engine-spec §B + §H.

Behavior contract (legal-asymmetry safe — never silently hide
obligations):

  Lenient mode (default; free tier; SaaS down):
    → status="ok" always; pending OIDs surface as `warnings` only.
    → cl_scan_all proceeds (NEVER blocks).

  Strict mode (paid tier with active SaaS questionnaire):
    → all completion_required OIDs satisfied → status="ok".
    → any OID below evidence_min → status="pending_evidence_needs_sync"
      with structured `prompt_to_user` + `auto_action_on_yes="cl_sync"`
      + `then_continue="cl_scan_all"`. AI client renders the prompt,
      user confirms, chain auto-continues.

  Safe fallbacks (legal asymmetry — hiding obligations is 100x worse
  than over-reporting):
    - questionnaire=None (no SaaS narrowing) → status="ok".
    - enforcement_mode="strict" but questionnaire=None → degrade to
      lenient (cannot enforce against an empty contract).
    - completion_required absent on an OID → treat as False (do not
      enforce); no over-blocking.
    - evidence_min absent → treat as 0; structural enforcement skipped.

The pure function takes `evidence_counts` as a flat dict
{obligation_id: int} so unit tests can run without disk I/O.
A separate helper `evidence_counts_from_state` flattens the nested
load_state() shape — also tested below.
"""

import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def questionnaire_two_required_one_optional():
    """Realistic 3-OID questionnaire shape from SaaS Applicability Engine."""
    return {
        "ART9-OBL-1": {
            "prompt": "Has a risk management system been established?",
            "evidence_min_count": 1,
            "completion_required": True,
            "evidence_types_allowed": ["repo_file", "text"],
        },
        "ART11-OBL-1": {
            "prompt": "Is technical documentation maintained?",
            "evidence_min_count": 2,
            "completion_required": True,
            "evidence_types_allowed": ["repo_file"],
        },
        "ART50-OBL-1": {
            "prompt": "Are users informed of AI interaction (chatbot disclosure)?",
            "evidence_min_count": 0,
            "completion_required": False,
            "evidence_types_allowed": [],
        },
    }


# ──────────────────────────────────────────────────────────────────────
# 1. Lenient mode — never blocks (safe-fallback rule)
# ──────────────────────────────────────────────────────────────────────


def test_lenient_mode_with_complete_evidence_returns_ok():
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {
                "evidence_min_count": 1,
                "completion_required": True,
            },
        },
        evidence_counts={"ART9-OBL-1": 3},
        enforcement_mode="lenient",
    )
    assert result.status == "ok"
    assert result.pending == []
    assert result.warnings == []


def test_lenient_mode_with_missing_evidence_returns_ok_with_warnings():
    """Lenient + pending evidence → status MUST stay 'ok' (per spec safe-
    fallback). The pending OID surfaces as a warning, NOT a block."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {
                "evidence_min_count": 1,
                "completion_required": True,
            },
        },
        evidence_counts={},  # no evidence
        enforcement_mode="lenient",
    )
    assert result.status == "ok"
    assert len(result.warnings) == 1
    # Warning must name the OID so the user/AI can act on it later.
    assert "ART9-OBL-1" in result.warnings[0]


def test_lenient_mode_with_partial_evidence_returns_ok_with_warning():
    """Some evidence present but < evidence_min → still ok in lenient,
    warning lists the gap (1 of 2 expected)."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART11-OBL-1": {
                "evidence_min_count": 2,
                "completion_required": True,
            },
        },
        evidence_counts={"ART11-OBL-1": 1},
        enforcement_mode="lenient",
    )
    assert result.status == "ok"
    assert any("ART11-OBL-1" in w for w in result.warnings)


def test_default_mode_when_none_passed_is_lenient():
    """Spec §B legal-asymmetry: default MUST be lenient. Missing/None
    enforcement_mode means lenient — never silently 'strict'."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min_count": 1, "completion_required": True},
        },
        evidence_counts={},
        enforcement_mode=None,
    )
    assert result.status == "ok"


def test_unknown_mode_string_is_treated_as_lenient():
    """Any unrecognized mode → lenient. Never escalate on garbage input."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min_count": 1, "completion_required": True},
        },
        evidence_counts={},
        enforcement_mode="garbage_unknown_mode",
    )
    assert result.status == "ok"


# ──────────────────────────────────────────────────────────────────────
# 2. Strict mode — blocks on missing evidence (paid-tier flow)
# ──────────────────────────────────────────────────────────────────────


def test_strict_mode_with_complete_evidence_returns_ok():
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min_count": 1, "completion_required": True},
            "ART11-OBL-1": {"evidence_min_count": 2, "completion_required": True},
        },
        evidence_counts={"ART9-OBL-1": 1, "ART11-OBL-1": 5},
        enforcement_mode="strict",
    )
    assert result.status == "ok"
    assert result.pending == []
    assert result.prompt_to_user == ""


def test_strict_mode_with_missing_evidence_returns_pending_signal():
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min_count": 1, "completion_required": True},
        },
        evidence_counts={},
        enforcement_mode="strict",
    )
    assert result.status == "pending_evidence_needs_sync"
    assert len(result.pending) == 1
    assert result.pending[0]["obligation_id"] == "ART9-OBL-1"
    assert result.pending[0]["expected"] == 1
    assert result.pending[0]["actual"] == 0
    # Spec §H — structured AI-first prompt fields
    assert result.auto_action_on_yes == "cl_sync"
    assert result.then_continue == "cl_scan_all"
    assert "ART9-OBL-1" in result.prompt_to_user
    assert "cl_sync" in result.prompt_to_user.lower()


def test_strict_mode_with_partial_evidence_returns_pending(
    questionnaire_two_required_one_optional,
):
    """ART11 needs 2 items, has 1 — must be flagged. ART9 satisfied,
    ART50 not required so it's irrelevant."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire=questionnaire_two_required_one_optional,
        evidence_counts={"ART9-OBL-1": 1, "ART11-OBL-1": 1},
        enforcement_mode="strict",
    )
    assert result.status == "pending_evidence_needs_sync"
    pending_ids = [p["obligation_id"] for p in result.pending]
    assert pending_ids == ["ART11-OBL-1"]
    assert result.pending[0]["expected"] == 2
    assert result.pending[0]["actual"] == 1


def test_strict_mode_optional_oids_never_block(
    questionnaire_two_required_one_optional,
):
    """OID with completion_required=False MUST never block, even in
    strict mode, even with 0 evidence."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire=questionnaire_two_required_one_optional,
        # ART50 (optional) has 0 evidence; ART9 + ART11 fully satisfied
        evidence_counts={"ART9-OBL-1": 1, "ART11-OBL-1": 2},
        enforcement_mode="strict",
    )
    assert result.status == "ok"


def test_strict_mode_multiple_pending_oids_all_listed():
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min_count": 1, "completion_required": True},
            "ART11-OBL-1": {"evidence_min_count": 2, "completion_required": True},
            "ART15-OBL-1": {"evidence_min_count": 1, "completion_required": True},
        },
        evidence_counts={},
        enforcement_mode="strict",
    )
    assert result.status == "pending_evidence_needs_sync"
    pending_ids = sorted(p["obligation_id"] for p in result.pending)
    assert pending_ids == ["ART11-OBL-1", "ART15-OBL-1", "ART9-OBL-1"]
    # Each pending row must carry the gap data for AI client renderable UI.
    for row in result.pending:
        assert "expected" in row and "actual" in row


# ──────────────────────────────────────────────────────────────────────
# 3. Safe fallbacks (legal asymmetry rules)
# ──────────────────────────────────────────────────────────────────────


def test_questionnaire_none_returns_ok_in_strict_mode():
    """Free tier or SaaS down: questionnaire=None means no narrowing,
    so there's nothing to enforce against. MUST NOT block scan."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire=None,
        evidence_counts={},
        enforcement_mode="strict",
    )
    assert result.status == "ok"
    assert result.pending == []


def test_questionnaire_empty_dict_returns_ok():
    """Empty dict (no narrowed OIDs) is functionally equivalent to None."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={},
        evidence_counts={},
        enforcement_mode="strict",
    )
    assert result.status == "ok"


def test_oid_missing_completion_required_treated_as_false():
    """Spec §C0 — `completion_required` absent on a row means optional.
    NEVER block on absence (avoid over-reporting failure mode)."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min_count": 1},  # NO completion_required
        },
        evidence_counts={},
        enforcement_mode="strict",
    )
    assert result.status == "ok"


def test_oid_missing_evidence_min_count_treated_as_zero():
    """Schema gap — no evidence_min_count means structural prohibition
    (e.g. Art 5) → 0 required, status stays ok."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART5-PROH-1": {"completion_required": True},  # no evidence_min_count
        },
        evidence_counts={},
        enforcement_mode="strict",
    )
    assert result.status == "ok"


def test_evidence_min_count_zero_explicit_no_evidence_required():
    """Empty `evidence_types_allowed` + min=0 = prohibition pattern.
    Even completion_required=True must not block when min=0."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART5-PROH-1": {
                "evidence_min_count": 0,
                "completion_required": True,
                "evidence_types_allowed": [],
            },
        },
        evidence_counts={},
        enforcement_mode="strict",
    )
    assert result.status == "ok"


def test_evidence_count_above_min_is_satisfied():
    """Surplus evidence is fine (more is better). Match is `>=`, not `==`."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min_count": 1, "completion_required": True},
        },
        evidence_counts={"ART9-OBL-1": 17},
        enforcement_mode="strict",
    )
    assert result.status == "ok"


# ──────────────────────────────────────────────────────────────────────
# 4. Prompt formatting — AI client must be able to render structured
# ──────────────────────────────────────────────────────────────────────


def test_prompt_to_user_is_a_single_short_question():
    """AI clients render this verbatim to the human. MUST be a single
    short question, not a paragraph or markdown."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min_count": 1, "completion_required": True},
        },
        evidence_counts={},
        enforcement_mode="strict",
    )
    assert result.status == "pending_evidence_needs_sync"
    # Single line (no \n), reasonable length, ends with question mark.
    assert "\n" not in result.prompt_to_user
    assert len(result.prompt_to_user) < 300
    assert result.prompt_to_user.rstrip().endswith("?")


def test_prompt_lists_count_when_multiple_pending():
    """When multiple OIDs pending, prompt should reference the count
    (not enumerate all 50 OIDs verbatim)."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            f"ART{n}-OBL-1": {"evidence_min_count": 1, "completion_required": True}
            for n in (8, 9, 10, 11, 12)
        },
        evidence_counts={},
        enforcement_mode="strict",
    )
    assert result.status == "pending_evidence_needs_sync"
    assert "5" in result.prompt_to_user  # the count


# ──────────────────────────────────────────────────────────────────────
# 5. evidence_counts_from_state helper — flattens nested state.json
# ──────────────────────────────────────────────────────────────────────


def test_evidence_counts_from_state_flattens_nested_articles():
    from core.enforce_paid_completion import evidence_counts_from_state

    state = {
        "articles": {
            "art9": {
                "findings": {
                    "ART9-OBL-1": {"evidence": [{"id": "e1"}, {"id": "e2"}]},
                    "ART9-OBL-2": {"evidence": []},
                },
            },
            "art11": {
                "findings": {
                    "ART11-OBL-1": {"evidence": [{"id": "e3"}]},
                },
            },
        },
    }
    counts = evidence_counts_from_state(state)
    assert counts == {"ART9-OBL-1": 2, "ART9-OBL-2": 0, "ART11-OBL-1": 1}


def test_evidence_counts_from_state_handles_empty_state():
    from core.enforce_paid_completion import evidence_counts_from_state

    assert evidence_counts_from_state({}) == {}
    assert evidence_counts_from_state({"articles": {}}) == {}


def test_evidence_counts_from_state_skips_findings_without_evidence_key():
    """Older art{N}.json files may lack `evidence` (just `status`).
    Treat as 0 — never crash."""
    from core.enforce_paid_completion import evidence_counts_from_state

    state = {
        "articles": {
            "art9": {
                "findings": {
                    "ART9-OBL-1": {"status": "open"},  # no evidence key
                },
            },
        },
    }
    counts = evidence_counts_from_state(state)
    assert counts == {"ART9-OBL-1": 0}


def test_evidence_counts_from_state_skips_malformed_evidence():
    """Defensive: if `evidence` is a string or dict (data corruption),
    treat as 0. NEVER crash. NEVER claim evidence exists."""
    from core.enforce_paid_completion import evidence_counts_from_state

    state = {
        "articles": {
            "art9": {
                "findings": {
                    "ART9-OBL-1": {"evidence": "not-a-list"},
                    "ART9-OBL-2": {"evidence": None},
                },
            },
        },
    }
    counts = evidence_counts_from_state(state)
    assert counts == {"ART9-OBL-1": 0, "ART9-OBL-2": 0}
