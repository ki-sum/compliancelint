"""Q3 follow-up — invariants for the obligation index.

Pre-fix: obligation_lookup silently dropped duplicate OIDs and warned.
This let `ART19-OBL-1` ship in two states (art12: retention quote /
art19: kept-under-control quote) without anyone noticing.

Post-fix:
  - same OID + same source_quote across files = legitimate
    cross-reference, silently accepted (first-write wins)
  - same OID + DIFFERENT source_quote = ObligationDriftError raised at
    load time

These tests guard the invariant by:
  1. running the real index build against the committed obligations
     dir and asserting no drift exists today
  2. round-tripping a synthetic obligations dir to prove the guard
     fires when source_quote diverges
  3. round-tripping a synthetic obligations dir to prove the guard
     does NOT fire when source_quote is identical (cross-reference
     case)
"""

import json
import os
import sys
from pathlib import Path

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


# ──────────────────────────────────────────────────────────────────────
# 1. Live obligations dir must load cleanly (no drift today)
# ──────────────────────────────────────────────────────────────────────


def test_committed_obligations_load_without_drift():
    """The 44 committed obligation JSONs must produce a clean index.

    If this test fails with ObligationDriftError, a cross-referenced
    OID has drifted from its canonical article. Reconcile the
    source_quote before merging — see art12 / art19 ART19-OBL-1b
    precedent (2026-04-30 fix)."""
    from core.obligation_lookup import _build_index, reset_cache

    reset_cache()
    index = _build_index()

    # Sanity — index should have hundreds of entries
    assert len(index) > 200, (
        f"Expected >200 indexed OIDs, got {len(index)}. "
        "Did the obligations dir change location?"
    )


# ──────────────────────────────────────────────────────────────────────
# 2. Drift case — different source_quote MUST raise
# ──────────────────────────────────────────────────────────────────────


def test_drift_raises_obligation_drift_error(tmp_path, monkeypatch):
    """Two files claim the same OID with different source_quote →
    ObligationDriftError at load time, NOT silent first-write-wins."""
    from core import obligation_lookup
    from core.obligation_lookup import (
        ObligationDriftError,
        _build_index,
        reset_cache,
    )

    obl_dir = tmp_path / "obligations"
    obl_dir.mkdir()
    (obl_dir / "art01-foo.json").write_text(
        json.dumps({
            "obligations": [
                {"id": "TEST-OBL-1", "source_quote": "Quote A.", "addressee": "p"},
            ]
        }),
        encoding="utf-8",
    )
    (obl_dir / "art02-bar.json").write_text(
        json.dumps({
            "obligations": [
                {"id": "TEST-OBL-1", "source_quote": "Quote B (different).", "addressee": "p"},
            ]
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        obligation_lookup, "_obligations_dir", lambda: str(obl_dir)
    )
    reset_cache()

    with pytest.raises(ObligationDriftError) as exc_info:
        _build_index()

    msg = str(exc_info.value)
    assert "TEST-OBL-1" in msg
    assert "DIFFERENT source_quote" in msg
    assert "art02-bar.json" in msg


# ──────────────────────────────────────────────────────────────────────
# 3. Cross-reference case — identical source_quote MUST silently pass
# ──────────────────────────────────────────────────────────────────────


def test_cross_reference_same_quote_silently_passes(tmp_path, monkeypatch):
    """Two files claim the same OID with the SAME verbatim
    source_quote → legitimate cross-reference. First-write wins, no
    error. This is the ART19-OBL-2 / ART26-OBL-6 pattern (mirrored
    in art12 because they extend Art. 12 logging requirements)."""
    from core import obligation_lookup
    from core.obligation_lookup import _build_index, reset_cache

    obl_dir = tmp_path / "obligations"
    obl_dir.mkdir()
    shared_quote = "Verbatim text shared by both files."
    (obl_dir / "art01-canonical.json").write_text(
        json.dumps({
            "obligations": [
                {"id": "XREF-OBL-1", "source_quote": shared_quote, "addressee": "p"},
            ]
        }),
        encoding="utf-8",
    )
    (obl_dir / "art02-mirror.json").write_text(
        json.dumps({
            "obligations": [
                {"id": "XREF-OBL-1", "source_quote": shared_quote, "addressee": "p"},
            ]
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        obligation_lookup, "_obligations_dir", lambda: str(obl_dir)
    )
    reset_cache()

    # Should NOT raise — both copies agree on the canonical text
    index = _build_index()
    assert "XREF-OBL-1" in index
    assert index["XREF-OBL-1"]["source_quote"] == shared_quote


# ──────────────────────────────────────────────────────────────────────
# 4. Specific regression — the ART19-OBL-1 ↔ ART19-OBL-1b alignment
# ──────────────────────────────────────────────────────────────────────


def test_art19_obl1_canonical_is_kept_under_control_not_retention():
    """Regression for the 2026-04-30 OID drift fix.

    Before the fix, ART19-OBL-1 had two meanings:
      - art12 JSON: retention (6 months) — placeholder pre-2026-04-04
      - art19 JSON: kept under control — canonical post-2026-04-04

    After the fix, art12's mirror is renamed ART19-OBL-1b (matching
    art19's split for the retention clause). ART19-OBL-1 now has
    one canonical meaning across all files: 'kept under control'.

    This test pins that contract — if it fails, someone reverted the
    rename or re-introduced the drift."""
    from core.obligation_lookup import lookup_obligation, reset_cache

    reset_cache()
    obl1 = lookup_obligation("ART19-OBL-1")
    assert obl1 is not None, "ART19-OBL-1 missing from index"
    quote = obl1.get("source_quote", "")
    assert "kept" in quote.lower() or "keep" in quote.lower(), (
        f"ART19-OBL-1 source_quote should be the 'kept under control' "
        f"clause from art19. Got: {quote[:100]!r}"
    )
    assert "six months" not in quote, (
        f"ART19-OBL-1 source_quote should NOT be the retention clause "
        f"(that is now ART19-OBL-1b). Got: {quote[:100]!r}"
    )

    obl1b = lookup_obligation("ART19-OBL-1b")
    assert obl1b is not None, "ART19-OBL-1b missing from index"
    quote_1b = obl1b.get("source_quote", "")
    assert "six months" in quote_1b.lower(), (
        f"ART19-OBL-1b source_quote should be the 6-month retention "
        f"clause. Got: {quote_1b[:100]!r}"
    )
