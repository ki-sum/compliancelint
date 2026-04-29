"""Regression test: MCP tool function bodies must not directly call git
subprocess (or any helper that does) without _safely_derive_with_timeout.

Per memory bug_mcp_tool_hang.md:
    On Windows MCP stdio context, ANY git subprocess can hang 5-7 minutes
    because the subprocess child handle interacts badly with the asyncio
    event loop — `subprocess.run(timeout=N)` does NOT fire reliably.

    The bug regressed 3 times in cl_sync (each fix was supposed to be
    permanent) and once silently in cl_delete (`derive_git_identity` was
    called without protection). After the 4th-incident fix
    (commit TBD-2026-04-29), the rule is enforced mechanically by this
    test.

Approved pattern: any MCP tool body that needs git data must wrap the
helper call in `_safely_derive_with_timeout(helper_fn, *args)`. The
wrapper enforces a 3s hard timeout via threadpool — worst case the
orphaned subprocess thread keeps running but the tool returns.

This test fails fast in CI / pre-commit if a future author adds an
unwrapped git call to any MCP tool body. The test should NOT be
disabled / skipped without re-reading the memory note above.
"""

import ast
import re
from pathlib import Path

SCANNER_SERVER = Path(__file__).parent.parent / "server.py"

# Helpers in server.py that DIRECTLY call git subprocess. Any MCP tool
# body that calls these must wrap with _safely_derive_with_timeout.
DANGEROUS_HELPERS = {
    "_derive_head_commit_sha",
    "_derive_first_commit_sha",
    "derive_git_identity",  # called as config.derive_git_identity(...)
}

# The wrapper helper that makes git calls safe to invoke from MCP tools.
SAFE_WRAPPER = "_safely_derive_with_timeout"


def _find_mcp_tool_funcs():
    """Parse server.py and yield (name, body_source) for each @mcp.tool()
    function (top-level defs only; nested defs ignored)."""
    src = SCANNER_SERVER.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                # Match @mcp.tool() — call expression on attribute access.
                if (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr == "tool"
                ):
                    yield node.name, ast.unparse(node)
                    break


def test_no_unwrapped_dangerous_helper_in_mcp_tools():
    """For each @mcp.tool() function body, every call to a DANGEROUS_HELPERS
    must be inside a _safely_derive_with_timeout(...) call."""
    failures = []
    for tool_name, body in _find_mcp_tool_funcs():
        for helper in DANGEROUS_HELPERS:
            # Find every callsite of this helper in the body.
            # `\b{helper}\s*\(` — word-boundary then optional whitespace then `(`.
            for match in re.finditer(rf"\b{re.escape(helper)}\s*\(", body):
                # Look BACKWARD from the call to see if `_safely_derive_with_timeout(`
                # appears within ~120 chars (typical wrapping pattern). 120 chars
                # is enough for `_safely_derive_with_timeout(` + maybe a `config.`
                # prefix on the helper, but tight enough to avoid matching a
                # _safely_derive_with_timeout call earlier in the same function.
                start = max(0, match.start() - 120)
                preceding = body[start:match.start()]
                if SAFE_WRAPPER not in preceding:
                    failures.append((tool_name, helper, match.start()))

    if failures:
        msg_lines = [
            "MCP tool bodies must NOT call git subprocess helpers without",
            f"wrapping in {SAFE_WRAPPER}. Per memory bug_mcp_tool_hang.md,",
            "this WILL hang 5-7 minutes on Windows MCP stdio.",
            "",
            "Violations found:",
        ]
        for tool_name, helper, offset in failures:
            msg_lines.append(f"  - {tool_name} calls {helper}(...) at offset {offset}")
        msg_lines.append("")
        msg_lines.append("Fix: wrap each call as:")
        msg_lines.append(f"  result = {SAFE_WRAPPER}(<helper>, *args, slog=logger)")
        raise AssertionError("\n".join(msg_lines))


def test_safely_derive_with_timeout_helper_exists():
    """The wrapper itself must exist and be importable from server.py."""
    src = SCANNER_SERVER.read_text(encoding="utf-8")
    assert (
        f"def {SAFE_WRAPPER}(" in src
    ), f"Missing {SAFE_WRAPPER} helper in server.py — this test cannot enforce safety."


def test_dangerous_helpers_actually_call_subprocess():
    """Sanity check: the helpers we treat as dangerous actually do call
    git subprocess. If a helper stops calling subprocess (e.g. someone
    refactors to read from cache), it's no longer dangerous and should
    be removed from DANGEROUS_HELPERS to avoid false positives."""
    src = SCANNER_SERVER.read_text(encoding="utf-8")
    tree = ast.parse(src)
    helper_bodies = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in DANGEROUS_HELPERS:
            helper_bodies[node.name] = ast.unparse(node)
    # config.derive_git_identity is a method on a class — find it differently.
    # For now just verify the 2 _derive_* helpers we know are top-level.
    for name in ("_derive_head_commit_sha", "_derive_first_commit_sha"):
        body = helper_bodies.get(name)
        assert body is not None, f"Helper {name} not found in server.py"
        assert "subprocess" in body, (
            f"{name} no longer calls subprocess — remove from DANGEROUS_HELPERS "
            f"or rename if behavior changed"
        )
