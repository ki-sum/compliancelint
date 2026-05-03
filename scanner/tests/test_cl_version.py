"""Coverage for MCP tool cl_version (server.py:3641).

§Y bootstrap pass 2026-05-03 — F-005 mechanical 1-liner test for
README claims C115 ("MCP tool: cl_version (show ComplianceLint
version)") + C158 ("MCP Server (17 tools)").

Prior §Y Phase 2 sub-agent (gave_up_too_easy critique) confirmed
cl_version was NOT covered by a dedicated test. This file fills that
gap and pins the 17-tool count claim to a runtime assertion.
"""
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def test_cl_version_returns_dict_with_version_and_tools_keys():
    result = server.cl_version()
    assert isinstance(result, dict)
    assert "version" in result
    assert "tools" in result


def test_cl_version_version_is_non_empty_string():
    result = server.cl_version()
    assert isinstance(result["version"], str)
    assert len(result["version"]) > 0


def test_cl_version_tools_count_matches_readme_claim_17():
    """Pins README:375 'MCP Server (17 tools)' claim to runtime.
    If the registered tool count drifts away from 17 (either README
    becomes stale OR a new tool ships without README update), this
    test fails and forces a sync."""
    result = server.cl_version()
    assert result["tools"] == 17, (
        f"cl_version reports {result['tools']} tools but README.md:375 "
        f"claims 17. Either update README or update the cl_version "
        f"hardcoded constant + register the matching @mcp.tool decorator."
    )
