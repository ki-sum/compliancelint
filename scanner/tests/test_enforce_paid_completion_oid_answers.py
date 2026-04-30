"""B1 self-audit follow-up — `enforce_paid_completion` extension to
also verify per-OID answer presence (not just evidence count).

Pre-fix gap (Task 12b commit 136149f LEAST_CONFIDENT):
  > "Per-OID compliance_answers cross-check — wider work, deferred."

The bug class: SaaS narrows questionnaire to specific OIDs (paid
feature). Customer pays Pro, expects per-obligation guidance. Gate
checks evidence count per OID but NOT whether the OID has been
answered. So:
  - 0 evidence + 0 answer → gate fires (correct)
  - 1 evidence + 0 answer → gate passes silently (BUG)
                            → false-COMPLIANT signal in scan output

Fix: enforce_paid_completion takes a new optional `oid_answers` dict
mapping obligation_id → bool|None. When provided:
  - For each completion_required OID:
      - if oid_answers[oid] is None or missing → mark "answer" pending
      - AND check evidence_min as before → mark "evidence" pending
  - Pending row carries `missing` field: "answer" | "evidence" | "both"

Backward compat: oid_answers=None means "AI client didn't fill it"
→ skip answer check, only do evidence check (legacy behavior). NO
silent regression for callers that don't supply oid_answers.

Lenient + missing answer → warning
Strict + missing answer → block (same shape as evidence-pending)
"""

import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


# ──────────────────────────────────────────────────────────────────────
# 1. Backward compat — oid_answers=None means skip answer check
# ──────────────────────────────────────────────────────────────────────


def test_oid_answers_none_falls_back_to_legacy_evidence_only_check():
    """Legacy callers don't supply oid_answers. The evidence check
    must run identically to pre-B1 behavior — no silent change."""
    from core.enforce_paid_completion import enforce_paid_completion

    questionnaire = {
        "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
    }
    # No answer + 1 evidence → legacy says ok; B1 must also say ok
    # when oid_answers=None (no per-OID data to check)
    result = enforce_paid_completion(
        questionnaire=questionnaire,
        evidence_counts={"ART9-OBL-1": 1},
        enforcement_mode="strict",
        oid_answers=None,
    )
    assert result.status == "ok"


def test_oid_answers_omitted_kwarg_falls_back_to_legacy():
    """Same as above but the kwarg is omitted entirely (existing
    callers that pre-date the B1 extension)."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        evidence_counts={"ART9-OBL-1": 1},
        enforcement_mode="strict",
        # oid_answers NOT passed
    )
    assert result.status == "ok"


# ──────────────────────────────────────────────────────────────────────
# 2. Strict mode — answer-missing fires the gate
# ──────────────────────────────────────────────────────────────────────


def test_strict_with_evidence_but_no_answer_blocks():
    """The headline B1 scenario: customer has evidence file but never
    answered the per-OID question. Pre-B1 = silent pass. Post-B1 =
    block with `missing: answer`."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        evidence_counts={"ART9-OBL-1": 1},  # has evidence
        enforcement_mode="strict",
        oid_answers={"ART9-OBL-1": None},  # but answer not given
    )
    assert result.status == "pending_evidence_needs_sync"
    assert len(result.pending) == 1
    p = result.pending[0]
    assert p["obligation_id"] == "ART9-OBL-1"
    assert p["missing"] == "answer"


def test_strict_with_answer_but_no_evidence_blocks():
    """Symmetric: answered but no evidence → still block, missing=evidence."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        evidence_counts={},  # no evidence
        enforcement_mode="strict",
        oid_answers={"ART9-OBL-1": True},  # but answered
    )
    assert result.status == "pending_evidence_needs_sync"
    assert len(result.pending) == 1
    assert result.pending[0]["missing"] == "evidence"


def test_strict_missing_both_marks_both():
    """Neither answered nor evidenced → missing: both."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        evidence_counts={},
        enforcement_mode="strict",
        oid_answers={},  # OID absent from dict = no answer
    )
    assert result.status == "pending_evidence_needs_sync"
    assert result.pending[0]["missing"] == "both"


def test_strict_with_answer_and_evidence_passes():
    """Happy path: answered AND evidenced → ok."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        evidence_counts={"ART9-OBL-1": 1},
        enforcement_mode="strict",
        oid_answers={"ART9-OBL-1": True},
    )
    assert result.status == "ok"


def test_answer_false_counts_as_answered():
    """`answer = False` (user explicitly says No to the question) is a
    REAL answer, not "missing". Don't penalize negative answers."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        evidence_counts={"ART9-OBL-1": 1},
        enforcement_mode="strict",
        oid_answers={"ART9-OBL-1": False},  # answered: No
    )
    # Has answer + has evidence → ok
    assert result.status == "ok"


# ──────────────────────────────────────────────────────────────────────
# 3. Lenient mode — answer-missing surfaces as warning, not block
# ──────────────────────────────────────────────────────────────────────


def test_lenient_with_missing_answer_warns_but_proceeds():
    """Lenient never blocks. Missing answer surfaces in warnings list
    so customer/AI client can address it without halting the scan."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        evidence_counts={"ART9-OBL-1": 1},
        enforcement_mode="lenient",
        oid_answers={"ART9-OBL-1": None},
    )
    assert result.status == "ok"
    # Warning should mention the OID and reason
    assert len(result.warnings) == 1
    assert "ART9-OBL-1" in result.warnings[0]
    assert "answer" in result.warnings[0].lower()


# ──────────────────────────────────────────────────────────────────────
# 4. Multiple OIDs — fine-grained pending list
# ──────────────────────────────────────────────────────────────────────


def test_strict_multiple_oids_mix_of_missing_classes():
    """Realistic case: some OIDs missing answer, some missing evidence,
    some both, some fine. The pending list shows the right `missing`
    classification per OID."""
    from core.enforce_paid_completion import enforce_paid_completion

    questionnaire = {
        "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        "ART9-OBL-2": {"evidence_min": 1, "completion_required": True},
        "ART11-OBL-1": {"evidence_min": 2, "completion_required": True},
        "ART13-OBL-1": {"evidence_min": 1, "completion_required": True},  # ok
    }
    result = enforce_paid_completion(
        questionnaire=questionnaire,
        evidence_counts={
            "ART9-OBL-1": 1,        # has evidence
            "ART9-OBL-2": 0,        # no evidence
            "ART11-OBL-1": 0,       # no evidence
            "ART13-OBL-1": 1,       # has evidence
        },
        enforcement_mode="strict",
        oid_answers={
            "ART9-OBL-1": None,     # missing answer (has evidence)
            "ART9-OBL-2": True,     # answered (no evidence)
            "ART11-OBL-1": None,    # missing both
            "ART13-OBL-1": True,    # ok
        },
    )
    assert result.status == "pending_evidence_needs_sync"
    by_oid = {p["obligation_id"]: p for p in result.pending}
    assert by_oid["ART9-OBL-1"]["missing"] == "answer"
    assert by_oid["ART9-OBL-2"]["missing"] == "evidence"
    assert by_oid["ART11-OBL-1"]["missing"] == "both"
    assert "ART13-OBL-1" not in by_oid  # ok — not in pending


# ──────────────────────────────────────────────────────────────────────
# 5. Optional OIDs (completion_required=False) — answer never required
# ──────────────────────────────────────────────────────────────────────


def test_optional_oid_does_not_check_answer():
    """OID with completion_required=False is advisory. Even with
    missing answer + evidence in strict mode, never blocks."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART50-OBL-1": {"evidence_min": 1, "completion_required": False},
        },
        evidence_counts={},
        enforcement_mode="strict",
        oid_answers={},
    )
    assert result.status == "ok"


# ──────────────────────────────────────────────────────────────────────
# 6. Prompt wording covers the new "answer" missing class
# ──────────────────────────────────────────────────────────────────────


def test_prompt_for_answer_missing_uses_clear_wording():
    """When the only pending OID is missing an answer (not evidence),
    the AI-first prompt should mention 'answer' or 'questionnaire' —
    not 'cl_sync' which is the evidence-pull tool. Customer/AI client
    needs the right next action signal."""
    from core.enforce_paid_completion import enforce_paid_completion

    result = enforce_paid_completion(
        questionnaire={
            "ART9-OBL-1": {"evidence_min": 1, "completion_required": True},
        },
        evidence_counts={"ART9-OBL-1": 1},
        enforcement_mode="strict",
        oid_answers={"ART9-OBL-1": None},
    )
    assert result.status == "pending_evidence_needs_sync"
    # When missing answer, the action_on_yes still cl_sync (for now —
    # the user might fix via dashboard/cl_update_finding) but the
    # prompt copy should at least mention "answer" or "questionnaire"
    # so AI client surfaces the right intent.
    prompt_lower = result.prompt_to_user.lower()
    assert (
        "answer" in prompt_lower or "questionnaire" in prompt_lower
    ), f"prompt doesn't mention answer/questionnaire: {result.prompt_to_user}"
