"""Q3 self-audit follow-up — pure-function lookup of an obligation
row from the per-article JSON files in `scanner/obligations/`.

Pre-fix gap: `cl_action_guide` returned only title + dashboard URL —
NO verbatim source quote, NO decomposed atoms, NO human-judgment
guidance. Customers got less from our paid tool than from ChatGPT.

This module is the ANTI-HALLUCINATION layer: every field returned
comes verbatim from a committed obligation JSON. Zero AI inference.

Cache strategy: load all 44 article JSONs lazily on first call and
hold a flat {OID: row} index in memory. Reload only on process
restart. The JSONs are committed to the repo (44 × ~10-50 KB each =
~1 MB total), so memory footprint is trivial.

Failure modes:
  - JSON missing on disk → log warning, return None
  - JSON parse error → log warning, skip that file
  - OID not in any indexed JSON → return None
  - Caller (cl_action_guide) handles None by returning the legacy
    "go to dashboard" redirect message
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger("compliancelint")

# Module-level cache (built on first call). None = not yet loaded;
# {} = loaded but empty (e.g. obligations dir missing).
_OID_INDEX: Optional[dict[str, dict]] = None


def _obligations_dir() -> str:
    """`scanner/obligations/` resolved from THIS module's location.

    Resolves through `scanner/core/obligation_lookup.py` → `scanner/`
    parent → `obligations/`. Doesn't depend on cwd.
    """
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "obligations")
    )


def _build_index() -> dict[str, dict]:
    """Walk all art*.json files in obligations/ and build a flat
    {obligation_id: row} index. Each row is the dict from the JSON
    array — preserves all fields (id, source, source_quote,
    deontic_type, modality, addressee, decomposed_atoms,
    automation_assessment, scope_limitation, etc.).

    Skips files that fail to parse (logs warning).
    Skips obligations missing `id` field (data corruption guard).
    """
    obligations_dir = _obligations_dir()
    index: dict[str, dict] = {}
    if not os.path.isdir(obligations_dir):
        logger.warning(
            "obligation_lookup: obligations dir not found at %s — "
            "cl_action_guide will degrade to legacy redirect",
            obligations_dir,
        )
        return index

    for fname in sorted(os.listdir(obligations_dir)):
        if not fname.endswith(".json") or not fname.startswith("art"):
            continue
        fpath = os.path.join(obligations_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(
                "obligation_lookup: skipping %s (parse error: %s)", fname, e
            )
            continue

        # Top-level shape: { "_metadata": {...}, "obligations": [...] }
        # Some early files may have used different top-level keys; be defensive.
        rows = data.get("obligations") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue
            oid = row.get("id")
            if not isinstance(oid, str) or not oid:
                continue
            # Don't blow up on duplicates — first-write wins. Log so
            # the team knows there's a duplicate to clean up.
            if oid in index:
                logger.warning(
                    "obligation_lookup: duplicate obligation id %s "
                    "(seen in earlier file, ignoring duplicate in %s)",
                    oid,
                    fname,
                )
                continue
            index[oid] = row

    return index


def lookup_obligation(obligation_id: str) -> Optional[dict]:
    """Return the obligation row for `obligation_id`, or None when
    not found.

    The returned dict is a SHALLOW reference to the cached row — do
    NOT mutate it; callers must read-only consume.

    Lookup is case-insensitive on the OID (e.g. "art26-obl-2" maps to
    "ART26-OBL-2") since obligation_id format normalisation lives in
    the calling tool.
    """
    global _OID_INDEX
    if _OID_INDEX is None:
        _OID_INDEX = _build_index()
    if not isinstance(obligation_id, str):
        return None
    return _OID_INDEX.get(obligation_id.upper())


def reset_cache() -> None:
    """Drop the in-memory index. Used by tests after disk mutations."""
    global _OID_INDEX
    _OID_INDEX = None


def loaded_oid_count() -> int:
    """Diagnostic — how many OIDs are indexed. Used by health checks
    and cl_version to surface 'I loaded N obligations'."""
    global _OID_INDEX
    if _OID_INDEX is None:
        _OID_INDEX = _build_index()
    return len(_OID_INDEX)


# ──────────────────────────────────────────────────────────────────────
# Field-extraction helpers — surface the subset cl_action_guide cares
# about, with safe defaults for missing fields.
# ──────────────────────────────────────────────────────────────────────


def extract_action_guide_fields(row: dict) -> dict:
    """Pull the cl_action_guide-relevant fields from an obligation
    row. Defensive against missing/malformed sub-fields — never throws.

    Returns a dict with these keys (always present, may be empty):
      - source             "Art. 26(2)" — section reference (str)
      - source_quote       verbatim EUR-Lex (str)
      - addressee          "provider" / "deployer" / etc. (str)
      - decomposed_atoms   list of {atom, description, requirement}
      - automation_level   "full" | "partial" | "manual" (str)
      - human_judgment_needed  what humans must judge (str)
    """
    if not isinstance(row, dict):
        return {
            "source": "",
            "source_quote": "",
            "addressee": "",
            "decomposed_atoms": [],
            "automation_level": "",
            "human_judgment_needed": "",
        }

    automation = row.get("automation_assessment")
    if not isinstance(automation, dict):
        automation = {}

    decomposed = row.get("decomposed_atoms")
    if not isinstance(decomposed, list):
        decomposed = []

    return {
        "source": str(row.get("source", "")),
        "source_quote": str(row.get("source_quote", "")),
        "addressee": str(row.get("addressee", "")),
        "decomposed_atoms": decomposed,
        "automation_level": str(automation.get("level", "")),
        "human_judgment_needed": str(automation.get("human_judgment_needed", "")),
    }
