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


class ObligationDriftError(RuntimeError):
    """Raised when the same OID appears in multiple obligation JSONs
    with conflicting source_quote values. Indicates the cross-reference
    has drifted from EUR-Lex and a human must reconcile before the
    engine can serve cl_action_guide for that OID."""


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

    §AA Option C (2026-05-02): public obligation JSONs only carry
    `automation_assessment.level`. The other 5 fields (detection_method,
    rationale, what_to_scan, confidence, human_judgment_needed) live
    in the SaaS dashboard and are fetched per-article by
    `classification_client.fetch_classifications`. We merge them in
    here so downstream consumers (obligation_engine, cl_action_guide)
    see one unified row whether the SaaS metadata was available or not.
    Degraded mode (no API key / network failure): rows have only
    `level` — existing consumers default to empty strings on missing
    keys, so behaviour is graceful but feature-degraded.
    """
    # Lazy import to avoid forcing the network module on callers that
    # don't actually load obligations (e.g. unit tests for unrelated
    # scanner modules).
    from scanner.core import classification_client

    obligations_dir = _obligations_dir()
    index: dict[str, dict] = {}
    # Track which articles we still need to fetch classifications for.
    # Filled as we walk public files; emptied as we merge.
    articles_seen: set[int] = set()
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

        meta = data.get("_metadata") or {}
        article_num = meta.get("article")
        if isinstance(article_num, int):
            articles_seen.add(article_num)

        for row in rows:
            if not isinstance(row, dict):
                continue
            oid = row.get("id")
            if not isinstance(oid, str) or not oid:
                continue
            # Normalise the index key to upper-case so lookup is
            # case-insensitive for the 80+ OIDs that use a lowercase
            # suffix letter (e.g. ART12-OBL-2a, ART19-OBL-1b). The row
            # itself preserves its original-case `id` field for
            # display purposes.
            key = oid.upper()
            # Cross-reference policy: an OID may appear in multiple
            # article JSONs (e.g. ART19-OBL-2 lives in art19 but is
            # mirrored into art12 because it directly extends Art. 12
            # logging requirements — see art12-consensus-lock-2026-03-20.md
            # for the design decision). When that happens, both copies
            # MUST share the same verbatim source_quote — otherwise the
            # cross-reference has drifted from EUR-Lex and we cannot
            # safely pick a winner without a human reconciling.
            #
            # 2026-04-30 incident: ART19-OBL-1 appeared in art12 (with
            # retention quote, from 2026-03-20) and art19 (with
            # kept-under-control quote, from 2026-04-04). Resolved by
            # renaming the art12 mirror to ART19-OBL-1b. This guard
            # ensures any future drift fails loud at load time.
            if key in index:
                existing_quote = (index[key] or {}).get("source_quote", "")
                new_quote = row.get("source_quote", "")
                if existing_quote != new_quote:
                    raise ObligationDriftError(
                        f"OID {oid} appears in multiple obligation JSONs "
                        f"with DIFFERENT source_quote values. The "
                        f"cross-reference has drifted from the canonical "
                        f"article. Reconcile the source_quote (or rename "
                        f"one OID — see art12 / art19 OBL-1b precedent) "
                        f"before this engine can answer cl_action_guide "
                        f"for {oid}. Conflicting file: {fname}."
                    )
                # Same source_quote → legitimate cross-reference.
                # First-write wins; canonical row stays in cache.
                continue
            index[key] = row

    # ── §AA Option C merge step ─────────────────────────────────
    # For each article we saw, fetch its 5-field classification map
    # and merge into matching rows' automation_assessment. None
    # response → degraded mode, leave rows with public-only fields.
    degraded_for_first_article = False
    for article_num in sorted(articles_seen):
        classifications = classification_client.fetch_classifications(article_num)
        if classifications is None:
            if not degraded_for_first_article:
                degraded_for_first_article = True
                classification_client.emit_degraded_notice_once()
            continue
        # Merge per-OID into the index. Missing OIDs in the
        # classification payload are silently skipped (private file
        # may legitimately omit obligations that need only public
        # `level`).
        for oid, fields in classifications.items():
            key = oid.upper()
            if key not in index:
                continue
            row = index[key]
            existing_aa = row.get("automation_assessment")
            if not isinstance(existing_aa, dict):
                existing_aa = {}
            # Public `level` wins over any private value if both exist
            # (defensive — they should never disagree, but if they do
            # the public file is the canonical taxonomy).
            merged = {**fields, **existing_aa}
            row["automation_assessment"] = merged

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


def obligations_for_article(article_number: int) -> list[dict]:
    """Return the list of obligation rows for a given article.

    Used by `cl_explain` to surface verbatim source_quote for every
    obligation in the article — anti-hallucination by reference. The
    consumer (AI agent) reads the verbatim text instead of trusting
    our paraphrased prose summary.

    Lookup walks ALL committed obligation JSONs and filters by
    `_metadata.article == article_number`. Cross-reference rows
    (e.g. ART19-OBL-1b mirrored into art12) appear under EVERY
    article that hosts them — we want this duplication when
    explaining art12 (because Art. 12 logging extends through
    Art. 19 retention) but cl_explain callers only ask for one
    article at a time.

    Returns [] when the article has no obligation JSON on disk.
    """
    obligations_dir = _obligations_dir()
    if not os.path.isdir(obligations_dir):
        return []

    out: list[dict] = []
    for fname in sorted(os.listdir(obligations_dir)):
        if not fname.endswith(".json") or not fname.startswith("art"):
            continue
        fpath = os.path.join(obligations_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        meta = data.get("_metadata") or {}
        if meta.get("article") != article_number:
            continue
        rows = data.get("obligations")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            oid = row.get("id")
            if not isinstance(oid, str) or not oid:
                continue
            out.append({
                "id": oid,
                "source": str(row.get("source", "")),
                "source_quote": str(row.get("source_quote", "")),
                "addressee": str(row.get("addressee", "")),
                "deontic_type": str(row.get("deontic_type", "")),
            })
    return out


def eur_lex_url_for_article(article_number: int) -> str:
    """Return the canonical EUR-Lex URL for the article — anchored at
    the article fragment so the AI consumer lands at the right
    paragraph.

    Format follows EUR-Lex's stable CELEX URL pattern for the EU AI
    Act consolidated text (Regulation 2024/1689). The fragment
    `#art_N` is the official anchor naming convention used by
    eur-lex.europa.eu.
    """
    return (
        f"https://eur-lex.europa.eu/legal-content/EN/TXT/"
        f"?uri=CELEX:32024R1689#art_{article_number}"
    )


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
