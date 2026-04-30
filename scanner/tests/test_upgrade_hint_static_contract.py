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


def _is_wrapped_return(return_node: ast.Return) -> bool | None:
    """Return True if the Return statement is `return append_upgrade_hint(...)`,
    False if it returns something else, None if it has no value (bare return).

    Only direct wrap counts — `return some_var` doesn't, even if `some_var`
    was assigned from append_upgrade_hint earlier (we can't statically prove
    that)."""
    if return_node.value is None:
        return None
    if not isinstance(return_node.value, ast.Call):
        return False
    func = return_node.value.func
    if isinstance(func, ast.Name) and func.id == "append_upgrade_hint":
        return True
    if isinstance(func, ast.Attribute) and func.attr == "append_upgrade_hint":
        return True
    return False


def _direct_returns_in_body(node: ast.AST) -> list[ast.Return]:
    """Collect Return statements that belong DIRECTLY to the given
    function — including those inside if/try/while/for blocks, but
    NOT inside nested function defs (which have their own wrap rules
    or are private helpers like cl_scan_all's _scan_one).

    Walks the body iteratively, descending into control-flow nodes
    but stopping at FunctionDef / AsyncFunctionDef boundaries."""
    returns: list[ast.Return] = []

    def _walk(n: ast.AST) -> None:
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Don't descend — nested helper has its own contract
                continue
            if isinstance(child, ast.Return):
                returns.append(child)
            _walk(child)

    _walk(node)
    return returns


def _vars_assigned_from_wrap(node: ast.AST) -> set[str]:
    """Find variable names assigned from append_upgrade_hint(...) calls
    in this function body (top-level, not nested defs). Used so
    `return some_var` is accepted when `some_var = append_upgrade_hint(...)`
    earlier in the function — common pattern for cl_scan_all that
    wraps then returns the variable later."""
    names: set[str] = set()

    def _walk(n: ast.AST) -> None:
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(child, ast.Assign):
                if (
                    isinstance(child.value, ast.Call)
                    and isinstance(child.value.func, ast.Name)
                    and child.value.func.id == "append_upgrade_hint"
                ):
                    for target in child.targets:
                        if isinstance(target, ast.Name):
                            names.add(target.id)
            elif isinstance(child, ast.AugAssign):
                # `output += ...` doesn't create a new wrap binding
                pass
            _walk(child)

    _walk(node)
    return names


def _is_delegating_return(return_node: ast.Return, mcp_tools: dict) -> bool:
    """`return some_other_mcp_tool(...)` is acceptable when the called
    function is itself in the WRAPPED_TOOLS set (which we verify
    independently). The delegated tool wraps internally."""
    val = return_node.value
    if not isinstance(val, ast.Call):
        return False
    func = val.func
    if isinstance(func, ast.Name) and func.id in mcp_tools and func.id in WRAPPED_TOOLS:
        return True
    return False


def _looks_like_error_path(return_node: ast.Return) -> bool:
    """Heuristic: a return whose value is a `dump_error(...)` call OR a
    `json.dumps({...})` containing one of these markers is an
    error/empty-state/AI-first-prompt path that should NOT wrap with
    upgrade_hint. Spec §H + Phase 5 Task 15:
      - error paths: no value in nudging users on errors
      - AI-first prompts: that JSON IS the prompt, double-wrapping
        would corrupt the AI client handler
      - empty-state guidance: "no evidence file found, here's what to
        create" — adding paywall nudge is annoying when user just
        hasn't set up yet

    Markers (any of):
      - `error` key (error response)
      - `status` key with value in {needs_analysis_first,
        pending_evidence_needs_sync, blocked_strict, ok_with_warning}
        (AI-first prompt shapes)
      - `found: False` (empty-state — convention from
        cl_verify_evidence "no compliance-evidence.json yet")
      - `fix` + `schema_example` keys (instructional empty-state)
    """
    val = return_node.value
    if val is None:
        return False
    if isinstance(val, ast.Call):
        func = val.func
        if isinstance(func, ast.Name) and func.id == "dump_error":
            return True
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "dumps"
            and isinstance(func.value, ast.Name)
            and func.value.id == "json"
        ):
            if val.args and isinstance(val.args[0], ast.Dict):
                d = val.args[0]
                key_names: set[str] = set()
                for k, v in zip(d.keys, d.values):
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        key_names.add(k.value)
                        if k.value == "error":
                            return True
                        if (
                            k.value == "status"
                            and isinstance(v, ast.Constant)
                            and isinstance(v.value, str)
                            and v.value
                            in {
                                "needs_analysis_first",
                                "pending_evidence_needs_sync",
                                "blocked_strict",
                                "ok_with_warning",
                            }
                        ):
                            return True
                        if (
                            k.value == "found"
                            and isinstance(v, ast.Constant)
                            and v.value is False
                        ):
                            return True
                # `fix` + `schema_example` = instructional empty-state
                if "fix" in key_names and "schema_example" in key_names:
                    return True
    return False


@pytest.mark.parametrize("tool_name", sorted(WRAPPED_TOOLS))
def test_wrapped_tool_every_non_error_return_path_is_wrapped(tool_name, mcp_tools):
    """Stronger contract than test_wrapped_tool_calls_append_upgrade_hint:
    verifies EVERY non-error return path in the function body wraps
    with append_upgrade_hint. Catches the cl_scan single-article
    regression class (2026-04-30 self-audit B3): one return path
    silently bypasses the wrap → paying customers don't see the
    paywall hint they should.

    Acceptable unwrapped returns:
      - Bare `return` (no value)
      - `return dump_error(...)` — error path
      - `return json.dumps({"error": ...})` — error JSON
      - `return json.dumps({"status": "needs_analysis_first"|...})` —
        AI-first prompt shape (Spec §H — that JSON IS the prompt,
        not a tool output to nudge on)
      - `return None`
      - `return some_var` where `some_var = append_upgrade_hint(...)`
        was assigned earlier in the body (common cl_scan_all pattern)
      - `return another_wrapped_mcp_tool(...)` — delegation; the
        delegate's own wrap fires
      - `return early_return_var` where the variable was assigned
        from a side-channel (e.g. `paid_gate = _check_...gate(...)`
        which itself returns wrapped JSON or None — accepted
        heuristically)

    Returns inside NESTED function definitions are skipped (they're
    helpers like cl_scan_all's _scan_one with their own contracts).
    """
    func = mcp_tools[tool_name]
    returns = _direct_returns_in_body(func)
    wrap_assigned_vars = _vars_assigned_from_wrap(func)

    # Side-channel vars: assigned from gate helpers that themselves
    # return either None (proceed) or wrapped JSON (early-return).
    # The early-return is itself the user-facing payload — wrapping
    # it again would double-inject _meta.
    GATE_HELPERS = frozenset({"_check_paid_completion_gate"})

    side_channel_vars: set[str] = set()

    def _collect_side_channel(n: ast.AST) -> None:
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(child, ast.Assign):
                if (
                    isinstance(child.value, ast.Call)
                    and isinstance(child.value.func, ast.Name)
                    and child.value.func.id in GATE_HELPERS
                ):
                    for target in child.targets:
                        if isinstance(target, ast.Name):
                            side_channel_vars.add(target.id)
            _collect_side_channel(child)

    _collect_side_channel(func)

    unwrapped: list[tuple[int, str]] = []
    for r in returns:
        wrapped = _is_wrapped_return(r)
        if wrapped is True:
            continue
        if wrapped is None:
            continue
        if _looks_like_error_path(r):
            continue
        if isinstance(r.value, ast.Constant) and r.value.value is None:
            continue
        # `return some_var` where some_var is assigned from a wrap call
        if isinstance(r.value, ast.Name):
            if r.value.id in wrap_assigned_vars:
                continue
            if r.value.id in side_channel_vars:
                continue
        # Delegation to another wrapped MCP tool
        if _is_delegating_return(r, mcp_tools):
            continue
        unwrapped.append(
            (r.lineno, ast.unparse(r) if hasattr(ast, "unparse") else str(r.lineno))
        )

    assert unwrapped == [], (
        f"{tool_name} has {len(unwrapped)} non-error return path(s) "
        f"that don't wrap with append_upgrade_hint:\n"
        + "\n".join(f"  line {ln}: {src}" for ln, src in unwrapped)
        + "\n\nEvery user-visible return MUST go through "
        "append_upgrade_hint(...) so paid-feature paywall hints fire "
        "for unconnected/free tier users. Spec §H + Phase 5 Task 15."
    )


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
