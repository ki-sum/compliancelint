"""Static AST contract test — every paywall-wrapped MCP tool calls
`append_upgrade_hint` somewhere in its body.

Spec: 2026-04-29-pre-launch-paid-engine-spec §H + Phase 5 Task 15.

Why static AST and not runtime e2e:
  - 4 of the 9 wrapped tools (cl_scan, cl_scan_all, cl_action_plan,
    cl_verify_evidence) need a full project fixture (compliance_answers,
    44 modules loaded, scan results on disk) to reach the success path
    where the wrap fires. That's heavy fixture infra.
  - The 5 lighter tools are already covered by runtime e2e in
    test_upgrade_hint_e2e.py (cl_explain, cl_action_guide,
    cl_check_updates, cl_interim_standard, cl_analyze_project).
  - The wrap pattern itself is what we want to regress-guard. AST
    inspection catches "did someone forget to wrap on a new return
    path?" bugs without booting the scanner.

This test fails when:
  - A wrapped tool's source no longer contains a call to
    `append_upgrade_hint`. Likely cause: a new `return` path was added
    without wrapping, OR the wrap was deleted by accident.
  - A utility tool (intentionally NOT wrapped) suddenly contains a
    call to `append_upgrade_hint`. Likely cause: someone confused
    "no paywall nudge on writes" with "always wrap".

The 9 wrapped tools and 8 unwrapped utility tools are the contract.
Update the registries below if a new tool is added.
"""

import ast
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


# ──────────────────────────────────────────────────────────────────────
# Contract registries — single source of truth for which tools wrap
# ──────────────────────────────────────────────────────────────────────


# Tools that MUST call append_upgrade_hint somewhere in their body.
# The free-tier user gets a paywall hint on these paid-feature outputs.
WRAPPED_TOOLS = frozenset({
    "cl_explain",
    "cl_analyze_project",
    "cl_scan",
    "cl_scan_all",
    "cl_action_guide",
    "cl_action_plan",
    "cl_check_updates",
    "cl_interim_standard",
    "cl_verify_evidence",
})


# Tools that MUST NOT call append_upgrade_hint — utility/write ops where
# a paywall nudge would be intrusive (per Spec §H comment + scanner
# tests/test_upgrade_hint_e2e.py docstring).
UNWRAPPED_TOOLS = frozenset({
    "cl_version",
    "cl_report_bug",
    "cl_connect",
    "cl_disconnect",
    "cl_sync",
    "cl_delete",
    "cl_update_finding",
    "cl_update_finding_batch",
})


# ──────────────────────────────────────────────────────────────────────
# AST helpers
# ──────────────────────────────────────────────────────────────────────


def _server_source() -> str:
    server_py = os.path.join(SCANNER_ROOT, "server.py")
    with open(server_py, "r", encoding="utf-8") as f:
        return f.read()


def _is_mcp_tool_decorator(decorator: ast.expr) -> bool:
    """Match `@mcp.tool()` — the FastMCP tool decorator."""
    if not isinstance(decorator, ast.Call):
        return False
    func = decorator.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "tool"
        and isinstance(func.value, ast.Name)
        and func.value.id == "mcp"
    )


def _calls_append_upgrade_hint_anywhere(node: ast.AST) -> bool:
    """Walk `node` looking for any Call whose function name is
    `append_upgrade_hint`. Catches both direct calls and any
    aliased forms (defensive — ideally there are no aliases now)."""
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        # Direct: append_upgrade_hint(...)
        if isinstance(func, ast.Name) and func.id == "append_upgrade_hint":
            return True
        # Aliased: _append_hint(...) — would mean a remaining inline
        # `from core.upgrade_hint import append_upgrade_hint as _append_hint`
        # which is the exact debt this hoist removed. Guard against
        # regression.
        if isinstance(func, ast.Name) and func.id in {
            "_append_hint",
            "_append_hint_v",
        }:
            return True
        # Module-attr: core.upgrade_hint.append_upgrade_hint(...)
        if isinstance(func, ast.Attribute) and func.attr == "append_upgrade_hint":
            return True
    return False


def _collect_mcp_tools() -> dict[str, ast.AST]:
    """Parse server.py and return {tool_name: FunctionDef-or-Async} for
    each @mcp.tool()-decorated function. Matches both sync `def` and
    `async def` (cl_connect is async)."""
    tree = ast.parse(_server_source())
    tools: dict[str, ast.AST] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(_is_mcp_tool_decorator(d) for d in node.decorator_list):
            tools[node.name] = node
    return tools


# ──────────────────────────────────────────────────────────────────────
# Cached parse — every test re-uses the same AST snapshot
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def mcp_tools() -> dict[str, ast.AST]:
    return _collect_mcp_tools()


# ──────────────────────────────────────────────────────────────────────
# 1. Coverage — every tool in the registry exists in server.py
# ──────────────────────────────────────────────────────────────────────


def test_all_wrapped_tools_exist_in_server(mcp_tools):
    missing = [t for t in WRAPPED_TOOLS if t not in mcp_tools]
    assert missing == [], f"WRAPPED_TOOLS registry has stale entries: {missing}"


def test_all_unwrapped_tools_exist_in_server(mcp_tools):
    missing = [t for t in UNWRAPPED_TOOLS if t not in mcp_tools]
    assert missing == [], f"UNWRAPPED_TOOLS registry has stale entries: {missing}"


def test_no_unaccounted_mcp_tools(mcp_tools):
    """Every @mcp.tool() function must be classified as either
    WRAPPED or UNWRAPPED. Catches new tools added without contract
    classification."""
    classified = WRAPPED_TOOLS | UNWRAPPED_TOOLS
    unclassified = [t for t in mcp_tools.keys() if t not in classified]
    assert unclassified == [], (
        f"New @mcp.tool() functions added without contract: {unclassified}. "
        f"Add each to either WRAPPED_TOOLS or UNWRAPPED_TOOLS in this file."
    )


# ──────────────────────────────────────────────────────────────────────
# 2. WRAPPED tools — body MUST call append_upgrade_hint
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("tool_name", sorted(WRAPPED_TOOLS))
def test_wrapped_tool_calls_append_upgrade_hint(tool_name, mcp_tools):
    func = mcp_tools[tool_name]
    assert _calls_append_upgrade_hint_anywhere(func), (
        f"{tool_name} is registered as WRAPPED but its body never calls "
        f"append_upgrade_hint(). Either someone forgot to wrap a return "
        f"path, or the wrap was deleted. Spec §H + Phase 5 Task 15."
    )


# ──────────────────────────────────────────────────────────────────────
# 3. UNWRAPPED tools — body MUST NOT call append_upgrade_hint
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("tool_name", sorted(UNWRAPPED_TOOLS))
def test_unwrapped_tool_does_not_call_append_upgrade_hint(tool_name, mcp_tools):
    func = mcp_tools[tool_name]
    assert not _calls_append_upgrade_hint_anywhere(func), (
        f"{tool_name} is a utility/write tool (paywall nudge would be "
        f"intrusive) but its body calls append_upgrade_hint(). Move it "
        f"to WRAPPED_TOOLS if the classification has changed, or remove "
        f"the wrap call."
    )


# ──────────────────────────────────────────────────────────────────────
# 4. Hoist-regression guard — no inline imports of upgrade_hint should
#    remain in server.py (we hoisted to module top on 2026-04-30)
# ──────────────────────────────────────────────────────────────────────


def test_no_inline_upgrade_hint_imports_inside_functions():
    """After the 2026-04-30 hoist, the only `from core.upgrade_hint
    import` statement should be at module level. Any inline import
    inside a function is regression — re-introduces the same style
    debt that was just cleaned."""
    tree = ast.parse(_server_source())
    inline_imports = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.ImportFrom) and child.module == "core.upgrade_hint":
                inline_imports.append(node.name)
                break
    assert inline_imports == [], (
        f"Functions with inline `from core.upgrade_hint import` (regression "
        f"of the 2026-04-30 hoist): {sorted(set(inline_imports))}"
    )
