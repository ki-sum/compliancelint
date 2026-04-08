"""Tests for the regulation registry — dynamic article discovery."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from scanner.core.regulation_registry import (
    _build_registry,
    _article_sort_key,
    get_articles,
    get_regulations,
    get_article_metadata,
    reload,
)


# ---------------------------------------------------------------------------
# Unit tests using temp directories (isolated from real obligation files)
# ---------------------------------------------------------------------------


def _write_obligation(directory: Path, filename: str, article: int, title: str,
                      regulation: str | None = None) -> None:
    """Helper: write a minimal obligation JSON."""
    metadata = {"article": article, "title": title}
    if regulation is not None:
        metadata["regulation"] = regulation
    data = {"_metadata": metadata, "obligations": []}
    (directory / filename).write_text(json.dumps(data), encoding="utf-8")


class TestBuildRegistry:
    """Tests for _build_registry with synthetic obligation files."""

    def test_discovers_articles_from_files(self, tmp_path):
        _write_obligation(tmp_path, "art04-literacy.json", 4, "AI Literacy")
        _write_obligation(tmp_path, "art09-risk.json", 9, "Risk Management")
        registry = _build_registry(tmp_path)
        assert "eu-ai-act" in registry
        assert registry["eu-ai-act"] == ["art4", "art9"]

    def test_articles_sorted_numerically(self, tmp_path):
        # Write in non-sorted order
        _write_obligation(tmp_path, "art111-transitional.json", 111, "Transitional")
        _write_obligation(tmp_path, "art05-prohibited.json", 5, "Prohibited")
        _write_obligation(tmp_path, "art50-transparency.json", 50, "Transparency")
        registry = _build_registry(tmp_path)
        assert registry["eu-ai-act"] == ["art5", "art50", "art111"]

    def test_regulation_field_groups_correctly(self, tmp_path):
        _write_obligation(tmp_path, "art04-literacy.json", 4, "AI Literacy")
        _write_obligation(tmp_path, "art01-scope.json", 1, "Scope", regulation="gdpr")
        _write_obligation(tmp_path, "art05-principles.json", 5, "Principles", regulation="gdpr")
        registry = _build_registry(tmp_path)
        assert "eu-ai-act" in registry
        assert "gdpr" in registry
        assert registry["eu-ai-act"] == ["art4"]
        assert registry["gdpr"] == ["art1", "art5"]

    def test_unknown_regulation_returns_empty(self, tmp_path):
        _write_obligation(tmp_path, "art04-literacy.json", 4, "AI Literacy")
        registry = _build_registry(tmp_path)
        assert registry.get("nis2", []) == []

    def test_empty_directory(self, tmp_path):
        registry = _build_registry(tmp_path)
        assert registry == {}

    def test_nonexistent_directory(self, tmp_path):
        registry = _build_registry(tmp_path / "nonexistent")
        assert registry == {}

    def test_malformed_json_skipped(self, tmp_path):
        (tmp_path / "art99-bad.json").write_text("{bad json", encoding="utf-8")
        _write_obligation(tmp_path, "art04-literacy.json", 4, "AI Literacy")
        registry = _build_registry(tmp_path)
        assert registry["eu-ai-act"] == ["art4"]

    def test_missing_metadata_skipped(self, tmp_path):
        (tmp_path / "art99-nometadata.json").write_text(
            json.dumps({"obligations": []}), encoding="utf-8"
        )
        _write_obligation(tmp_path, "art04-literacy.json", 4, "AI Literacy")
        registry = _build_registry(tmp_path)
        assert registry["eu-ai-act"] == ["art4"]

    def test_explicit_regulation_field(self, tmp_path):
        """Explicit regulation field in _metadata is respected."""
        _write_obligation(tmp_path, "art09-risk.json", 9, "Risk", regulation="eu-ai-act")
        registry = _build_registry(tmp_path)
        assert registry["eu-ai-act"] == ["art9"]


class TestArticleSortKey:

    def test_simple(self):
        assert _article_sort_key("art4") == 4
        assert _article_sort_key("art111") == 111

    def test_no_digits(self):
        assert _article_sort_key("nodigits") == 0


# ---------------------------------------------------------------------------
# Integration tests against real obligation files
# ---------------------------------------------------------------------------


class TestRealObligations:
    """Tests that run against the actual scanner/obligations/ directory."""

    def test_discovers_all_44_articles(self):
        reload()  # Force fresh scan
        articles = get_articles("eu-ai-act")
        assert len(articles) == 44, f"Expected 44 articles, got {len(articles)}: {articles}"

    def test_articles_sorted_numerically(self):
        reload()
        articles = get_articles("eu-ai-act")
        nums = [int(a.replace("art", "")) for a in articles]
        assert nums == sorted(nums), f"Articles not sorted: {articles}"

    def test_first_and_last_article(self):
        reload()
        articles = get_articles("eu-ai-act")
        assert articles[0] == "art4", f"First article should be art4, got {articles[0]}"
        assert articles[-1] == "art111", f"Last article should be art111, got {articles[-1]}"

    def test_unknown_regulation_returns_empty(self):
        reload()
        assert get_articles("nonexistent-regulation") == []

    def test_get_regulations_includes_eu_ai_act(self):
        reload()
        regs = get_regulations()
        assert "eu-ai-act" in regs

    def test_regulation_field_in_art09_metadata(self):
        reload()
        meta = get_article_metadata("eu-ai-act")
        assert "art9" in meta
        assert meta["art9"]["regulation"] == "eu-ai-act"
        assert meta["art9"]["title"] == "Risk Management System"

    def test_get_articles_returns_copy(self):
        """Mutating the returned list must not affect the registry."""
        reload()
        a = get_articles("eu-ai-act")
        a.clear()
        b = get_articles("eu-ai-act")
        assert len(b) == 44
