"""Coverage for MCP tool cl_version (server.py:3641).

§Y bootstrap pass 2026-05-03 — F-005 mechanical 1-liner test for
README claim C115 ("MCP tool: cl_version (show ComplianceLint
version)") + drift-prevention for the registered tool count.

Prior §Y Phase 2 sub-agent (gave_up_too_easy critique) confirmed
cl_version was NOT covered by a dedicated test. This file fills that
gap. Note: cl_version returns a JSON STRING (per MCP tool convention
— responses are always serialized) so tests parse it before
asserting.
"""
import json
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def _parse_cl_version() -> dict:
    raw = server.cl_version()
    assert isinstance(raw, str), "cl_version is expected to return a JSON string"
    return json.loads(raw)


def test_cl_version_returns_parseable_json_with_version_and_tools_keys():
    parsed = _parse_cl_version()
    assert isinstance(parsed, dict)
    assert "version" in parsed
    assert "tools" in parsed


def test_cl_version_version_is_non_empty_string():
    parsed = _parse_cl_version()
    assert isinstance(parsed["version"], str)
    assert len(parsed["version"]) > 0


def test_cl_version_tools_count_is_positive_integer():
    """README no longer hard-codes a tool count (founder policy
    2026-05-03: don't write specific quantities in docs since they
    drift). cl_version still reports the count for AI clients. This
    test just sanity-checks the field type + non-emptiness."""
    parsed = _parse_cl_version()
    assert isinstance(parsed["tools"], int)
    assert parsed["tools"] > 0


def test_cl_version_tools_count_matches_registered_decorators():
    """The number self-declared by cl_version MUST match the actual
    @mcp.tool() decorator count in server.py. If a new tool is added
    without updating cl_version's hardcoded count (or vice-versa),
    this fails and forces a sync."""
    server_path = os.path.join(SCANNER_ROOT, "server.py")
    with open(server_path, "r", encoding="utf-8") as f:
        source = f.read()
    decorator_count = source.count("@mcp.tool()")
    parsed = _parse_cl_version()
    reported = parsed["tools"]
    assert reported == decorator_count, (
        f"cl_version reports {reported} tools but server.py has "
        f"{decorator_count} @mcp.tool() decorators. Update the "
        f"cl_version count constant to match."
    )
