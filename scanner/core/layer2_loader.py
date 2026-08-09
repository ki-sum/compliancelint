"""Layer 2 loader — surface EU-authoritative interpretive materials
(EC Guidelines, Codes of Practice, EDPB Statements, etc.) alongside
Layer 1 obligation JSONs.

Public API:
  - get_interpretive_materials_for_article(article: int) -> list[dict]
  - get_atoms_for_obligation(obligation_id: str) -> list[dict]

Mirrors the TypeScript loader used by the compliancelint.dev dashboard
so scanner findings can cite Layer 2 atoms with byte-verbatim EC text
+ paragraph anchors + source PDF SHA256.

Pilot doc (2026-08-09): C(2026) 5054 final — EC Guidelines on Art 50
transparency obligations. 304 atoms attached to Art 50 obligations.

File lookup: `scanner/interpretive-materials/*.json` resolved from THIS
module's location (analog of `obligation_lookup._obligations_dir()`).

Cache: module-level, lazy-loaded on first call.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger("compliancelint")

# Module-level cache — None = not yet loaded, [] = loaded but empty.
_MATERIALS_CACHE: Optional[list[dict]] = None


def _interpretive_dir() -> str:
    """`scanner/interpretive-materials/` resolved from THIS module."""
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "interpretive-materials")
    )


def _load_all() -> list[dict]:
    """Walk all *.json files in interpretive-materials/ and return
    the parsed list. Skips files that fail to parse (logs warning).
    """
    dir_path = _interpretive_dir()
    if not os.path.isdir(dir_path):
        logger.info(
            "layer2_loader: interpretive-materials dir not found at %s — "
            "findings will not carry Layer 2 citations",
            dir_path,
        )
        return []

    out: list[dict] = []
    for fname in sorted(os.listdir(dir_path)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(dir_path, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(
                "layer2_loader: skipping %s (parse error: %s)", fname, e
            )
            continue
        if not isinstance(data, dict):
            continue
        out.append(data)
    return out


def _get_cache() -> list[dict]:
    global _MATERIALS_CACHE
    if _MATERIALS_CACHE is None:
        _MATERIALS_CACHE = _load_all()
    return _MATERIALS_CACHE


def reset_cache() -> None:
    """Drop the in-memory cache. Used by tests after disk mutations."""
    global _MATERIALS_CACHE
    _MATERIALS_CACHE = None


def get_interpretive_materials_for_article(article: int) -> list[dict]:
    """Return the list of Layer 2 documents that attach to any
    obligation of the given article.

    Each returned dict has:
      - doc_id            (e.g. "C(2026) 5054 final")
      - doc_type          (e.g. "guidelines")
      - title             full document title
      - issuing_body      (e.g. "European Commission")
      - publication_date  ISO date
      - source_url        canonical download URL
      - source_sha256     PDF integrity anchor
      - atoms             list of {id, attaches_to_obligation,
                                    paragraph_ref, section_ref,
                                    verbatim_text, atom_type}

    Filter: atoms whose `attaches_to_obligation` starts with
    `ART{article}-`. This is the same rule used by the TypeScript
    dashboard loader.
    """
    prefix = f"ART{article}-"
    out: list[dict] = []
    for doc in _get_cache():
        content = doc.get("content") or {}
        atoms = content.get("guidance_atoms") or []
        matching = [
            a for a in atoms
            if isinstance(a, dict)
            and isinstance(a.get("attaches_to_obligation"), str)
            and a["attaches_to_obligation"].startswith(prefix)
        ]
        if not matching:
            continue
        meta = doc.get("_meta") or {}
        out.append({
            "doc_id": meta.get("doc_id", ""),
            "doc_type": meta.get("doc_type", ""),
            "title": meta.get("title", ""),
            "issuing_body": meta.get("issuing_body", ""),
            "publication_date": meta.get("publication_date", ""),
            "source_url": meta.get("source_url", ""),
            "source_sha256": meta.get("source_sha256", ""),
            "binding_nature": meta.get("binding_nature", ""),
            "atoms": matching,
        })
    return out


def get_atoms_for_obligation(obligation_id: str) -> list[dict]:
    """Return all Layer 2 atoms that attach to `obligation_id`, across
    all documents. Each atom carries its parent doc's identifying
    metadata inline so findings can cite `doc_id + paragraph_ref +
    source_url` without a second lookup.

    Returns [] when no atoms attach to that obligation.
    """
    if not isinstance(obligation_id, str) or not obligation_id:
        return []
    key = obligation_id.upper()
    out: list[dict] = []
    for doc in _get_cache():
        meta = doc.get("_meta") or {}
        doc_id = meta.get("doc_id", "")
        doc_title = meta.get("title", "")
        source_url = meta.get("source_url", "")
        source_sha256 = meta.get("source_sha256", "")
        publication_date = meta.get("publication_date", "")
        content = doc.get("content") or {}
        for atom in content.get("guidance_atoms") or []:
            if not isinstance(atom, dict):
                continue
            attaches = atom.get("attaches_to_obligation", "")
            if not isinstance(attaches, str) or attaches.upper() != key:
                continue
            out.append({
                "id": atom.get("id", ""),
                "paragraph_ref": atom.get("paragraph_ref"),
                "section_ref": atom.get("section_ref", ""),
                "verbatim_text": atom.get("verbatim_text", ""),
                "atom_type": atom.get("atom_type", ""),
                "doc_id": doc_id,
                "doc_title": doc_title,
                "source_url": source_url,
                "source_sha256": source_sha256,
                "publication_date": publication_date,
            })
    return out


def loaded_doc_count() -> int:
    """Diagnostic — how many Layer 2 documents are loaded."""
    return len(_get_cache())


def loaded_atom_count() -> int:
    """Diagnostic — total atoms across all Layer 2 documents."""
    total = 0
    for doc in _get_cache():
        content = doc.get("content") or {}
        total += len(content.get("guidance_atoms") or [])
    return total
