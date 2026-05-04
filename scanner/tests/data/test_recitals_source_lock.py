"""Source Lock test for the 180 Recital baseline (§AD.4).

Per `feedback_recital_text_no_retype.md` HARD RULE: no LLM ever retypes
Recital text. This test enforces that:

  1. scanner/data/recitals.json has exactly 180 entries (numbered 1-180)
  2. Each entry has a source_quote ≥ 30 chars (sanity)
  3. Each entry has source_quote_normalized_sha256 (integrity anchor)
  4. The PDF source file exists at docs/sources/eu-ai-act-2024-1689-en.pdf
  5. Re-extracting from PDF produces same canonical hash per Recital
     (full-PDF re-parse is heavy; we sample 5 random Recitals to keep
      test runtime under 30s)

If this test fails after manual edit to recitals.json: that edit
violated the HARD RULE. Re-run the canonical fetch_recitals.py audit
tool to regenerate from PDF + EC sources.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sys
import unicodedata
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RECITALS_JSON = REPO_ROOT / "scanner" / "data" / "recitals.json"
PDF_PATH = REPO_ROOT / "docs" / "sources" / "eu-ai-act-2024-1689-en.pdf"


def aggressive_norm(text: str) -> str:
    """Mirrors the canonical fetch_recitals.py normalization.
    DO NOT diverge — would break the hash chain.
    """
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", "", text)
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("—", "-").replace("–", "-").replace("‐", "-")
    text = text.replace(" ", "")
    return text.lower()


@pytest.fixture(scope="module")
def recitals():
    assert RECITALS_JSON.is_file(), f"missing baseline: {RECITALS_JSON}"
    with RECITALS_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_baseline_count_180(recitals):
    """Exactly 180 Recitals indexed by string '1' through '180'."""
    assert len(recitals) == 180
    keys = sorted(recitals.keys(), key=int)
    assert keys[0] == "1"
    assert keys[-1] == "180"
    # No gaps
    nums = sorted(int(k) for k in recitals.keys())
    assert nums == list(range(1, 181))


def test_each_has_source_quote(recitals):
    """Every Recital has non-trivial source_quote text (>= 30 chars)."""
    short = [n for n, r in recitals.items() if len(r.get("source_quote", "")) < 30]
    assert not short, f"Recitals with too-short source_quote: {short}"


def test_each_has_integrity_anchor(recitals):
    """Every Recital has source_quote_normalized_sha256 — the integrity anchor."""
    missing = [n for n, r in recitals.items() if not r.get("source_quote_normalized_sha256")]
    assert not missing, f"Recitals without sha256 anchor: {missing}"


def test_hash_matches_text(recitals):
    """Stored sha256 actually matches aggressive_norm(source_quote).

    This catches: someone manually edited source_quote without updating the
    hash, OR someone retyped Recital text breaking the hash chain.
    """
    drift = []
    for n, r in recitals.items():
        text = r.get("source_quote", "")
        stored_hash = r.get("source_quote_normalized_sha256", "")
        actual_hash = hashlib.sha256(aggressive_norm(text).encode("utf-8")).hexdigest()
        if stored_hash != actual_hash:
            drift.append(n)
    assert not drift, (
        f"Hash drift detected on Recitals {drift[:10]}{'...' if len(drift) > 10 else ''} — "
        f"manual edit without rehash, OR fetch_recitals.py changed normalization"
    )


def test_pdf_source_present():
    """PDF canonical source file must exist."""
    assert PDF_PATH.is_file(), f"missing canonical PDF: {PDF_PATH}"
    # Sanity: PDF should be ~2.5 MB (Regulation (EU) 2024/1689)
    assert PDF_PATH.stat().st_size > 1_000_000, "PDF suspiciously small — wrong file?"


def test_pdf_extraction_matches_baseline_sample(recitals):
    """Sample 5 random Recitals; re-extract from PDF; verify hash matches.

    This is the deepest integrity check: ensures baseline still tracks
    canonical PDF source. Heavy (PDF parse takes ~7s), so we sample.
    """
    pytest.importorskip("pypdf")
    audit_tools = os.environ.get("COMPLIANCELINT_AUDIT_TOOLS")
    if not audit_tools:
        pytest.skip(
            "Deep PDF re-extract requires COMPLIANCELINT_AUDIT_TOOLS env var "
            "pointing at the local audit-tools directory containing "
            "fetch_recitals.py (dev-only, internal). The 5 lighter tests "
            "above already cover the canonical hash invariant."
        )
    if not Path(audit_tools).is_dir():
        pytest.skip(f"COMPLIANCELINT_AUDIT_TOOLS={audit_tools} is not a directory")
    sys.path.insert(0, audit_tools)
    from fetch_recitals import parse_pdf_recitals  # type: ignore

    pdf_recitals = parse_pdf_recitals(PDF_PATH)
    assert len(pdf_recitals) == 180, f"PDF re-parse extracted only {len(pdf_recitals)}"

    # Use deterministic seed so failure is reproducible
    rng = random.Random(20260504)
    sample = rng.sample(range(1, 181), 5)
    drift = []
    for n in sample:
        pdf_text = pdf_recitals.get(n)
        baseline_hash = recitals[str(n)]["source_quote_normalized_sha256"]
        if pdf_text is None:
            drift.append((n, "missing in PDF re-parse"))
            continue
        pdf_hash = hashlib.sha256(aggressive_norm(pdf_text).encode("utf-8")).hexdigest()
        if pdf_hash != baseline_hash:
            drift.append((n, f"PDF hash {pdf_hash[:12]} != baseline {baseline_hash[:12]}"))

    assert not drift, f"PDF source drift: {drift}"
