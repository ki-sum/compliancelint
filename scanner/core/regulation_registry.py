"""
Regulation Registry — dynamic article discovery from obligation JSON files.

Instead of hardcoding article lists, this module scans the obligations/
directory at startup and builds a registry of regulation -> articles.

Each obligation JSON's _metadata may contain a "regulation" field.
If absent, defaults to "eu-ai-act".

Usage:
    from scanner.core.regulation_registry import get_articles, get_regulations

    articles = get_articles("eu-ai-act")   # ["art4", "art5", ..., "art111"]
    regs     = get_regulations()            # ["eu-ai-act"]
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

_DEFAULT_REGULATION = "eu-ai-act"

# Module-level cache: regulation_id -> sorted list of article keys
_registry: Optional[Dict[str, List[str]]] = None

# Path to obligation JSONs (sibling of core/)
_OBLIGATIONS_DIR = Path(__file__).resolve().parent.parent / "obligations"


def _article_sort_key(art_key: str) -> int:
    """Extract numeric value from article key for sorting (e.g., 'art09' -> 9)."""
    match = re.search(r"\d+", art_key)
    return int(match.group()) if match else 0


def _build_registry(obligations_dir: Optional[Path] = None) -> Dict[str, List[str]]:
    """Scan obligation JSONs and build regulation -> article list mapping."""
    directory = obligations_dir or _OBLIGATIONS_DIR
    registry: Dict[str, List[str]] = {}

    if not directory.is_dir():
        return registry

    for filepath in directory.glob("art*.json"):
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        metadata = data.get("_metadata")
        if not metadata or "article" not in metadata:
            continue

        regulation = metadata.get("regulation", _DEFAULT_REGULATION)
        article_num = metadata["article"]
        article_key = f"art{article_num}"

        if regulation not in registry:
            registry[regulation] = []

        if article_key not in registry[regulation]:
            registry[regulation].append(article_key)

    # Sort each regulation's articles numerically
    for reg in registry:
        registry[reg].sort(key=_article_sort_key)

    return registry


def _ensure_loaded() -> Dict[str, List[str]]:
    """Lazy-load the registry on first access."""
    global _registry
    if _registry is None:
        _registry = _build_registry()
    return _registry


def get_articles(regulation: str = _DEFAULT_REGULATION) -> List[str]:
    """Return sorted list of article keys for a regulation.

    Args:
        regulation: Regulation identifier (default: "eu-ai-act").

    Returns:
        List of article keys like ["art4", "art5", ...], or [] if unknown.
    """
    return list(_ensure_loaded().get(regulation, []))


def get_regulations() -> List[str]:
    """Return list of all discovered regulation identifiers."""
    return sorted(_ensure_loaded().keys())


def get_article_metadata(regulation: str = _DEFAULT_REGULATION) -> Dict[str, dict]:
    """Return {article_key: {article, title, regulation}} for a regulation.

    Useful for UIs that need article titles without loading full obligation data.
    """
    directory = _OBLIGATIONS_DIR
    result: Dict[str, dict] = {}

    if not directory.is_dir():
        return result

    for filepath in directory.glob("art*.json"):
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        metadata = data.get("_metadata")
        if not metadata or "article" not in metadata:
            continue

        reg = metadata.get("regulation", _DEFAULT_REGULATION)
        if reg != regulation:
            continue

        article_key = f"art{metadata['article']}"
        result[article_key] = {
            "article": metadata["article"],
            "title": metadata.get("title", ""),
            "regulation": reg,
        }

    return result


def reload() -> None:
    """Force re-scan of obligations directory. Useful after adding new articles."""
    global _registry
    _registry = _build_registry()
