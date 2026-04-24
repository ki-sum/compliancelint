"""Thin coverage for MCP tool cl_interim_standard (server.py:1150).

Covers:
  - happy path: known article returns a structured checklist dict
  - error path: unknown article returns error with Available articles hint
"""
import json
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def test_interim_standard_known_article():
    server._ensure_module_loaded(12)
    raw = server.cl_interim_standard(article_number=12)
    parsed = json.loads(raw)

    assert "error" not in parsed, f"expected success, got error: {parsed}"
    assert "requirements" in parsed, f"checklist missing 'requirements' key: {list(parsed.keys())}"
    assert isinstance(parsed["requirements"], (list, dict)) and parsed["requirements"], (
        "requirements must be a non-empty list/dict"
    )


def test_interim_standard_unknown_article():
    raw = server.cl_interim_standard(article_number=999)
    parsed = json.loads(raw)

    assert "error" in parsed, f"expected error payload, got: {parsed}"
    assert "999" in parsed["error"]
    assert "fix" in parsed
    assert "Available articles" in parsed["fix"]
