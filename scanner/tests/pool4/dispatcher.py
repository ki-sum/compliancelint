"""Cell-driven MCP tool dispatcher for the Pool 4 Python smoke runner.

Bridge from the language-neutral cell yaml format to the in-process
Python MCP tool functions exposed by `scanner.server`. Two responsibilities:

  1. Resolve placeholder strings in `cell.invoke.args` against a
     runtime context (e.g. `$pytest.tmp_path` → an actual `tmp_path`
     fixture path). The placeholder syntax mirrors the TypeScript
     runner's `$persona.email` / `$repo.id` resolver in
     `tool-cell-runner.ts`.

  2. Invoke the named MCP tool by importing it from `scanner.server`
     and calling with the resolved args. Returns the raw JSON string
     the tool returned (caller parses).

What this dispatcher deliberately does NOT do:
  - Network / SaaS calls. Cross-system tools (cl_sync / cl_connect /
    cl_delete with target=dashboard) need additional fixture setup
    (test-pro user seeded, dashboard DB writable) that lives outside
    this module.
  - SaaS DB introspection. That's the Python sibling of the internal
    Pool 4 SaaS-introspection helper, intentionally deferred until
    cross-system smoke ships.
  - Asserter dispatch. Cell-by-cell asserters live in the
    TypeScript runner; the Python smoke is response-shape-only for
    now.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from .cell_loader import ToolCell


class DispatchError(RuntimeError):
    """Raised when a cell can't be dispatched (unresolved placeholder,
    unknown tool, etc.)."""


def resolve_args(cell: ToolCell, ctx: dict[str, Any]) -> dict[str, Any]:
    """Return cell.invoke.args with placeholder strings substituted.

    Recognized placeholders (extend as new cells need them):
      - `$pytest.tmp_path` → str(ctx["tmp_path"]) — pytest's tmp_path
      - `$persona.email`  → ctx["persona_email"]
      - `$persona.api_key` → ctx["api_key"]
      - any string starting with `$` not in this list → raises
        DispatchError to surface unhandled placeholders loudly

    Non-string values (int, bool, None) pass through untouched.
    Args without placeholders also pass through untouched.
    """
    if not cell.invoke or "args" not in cell.invoke:
        raise DispatchError(
            f"resolve_args({cell.cell_id}): cell has no invoke.args block"
        )
    raw = cell.invoke["args"] or {}
    if not isinstance(raw, dict):
        raise DispatchError(
            f"resolve_args({cell.cell_id}): invoke.args must be a mapping, "
            f"got {type(raw).__name__}"
        )
    resolved: dict[str, Any] = {}
    for key, value in raw.items():
        resolved[key] = _resolve_one(value, ctx, cell.cell_id, key)
    return resolved


def _resolve_one(value: Any, ctx: dict[str, Any], cell_id: str, key: str) -> Any:
    if not isinstance(value, str):
        return value
    if not value.startswith("$"):
        return value
    if value == "$pytest.tmp_path":
        tmp = ctx.get("tmp_path")
        if tmp is None:
            raise DispatchError(
                f"resolve_args({cell_id}): cell args.{key} references "
                f"$pytest.tmp_path but ctx does not provide tmp_path"
            )
        return str(tmp) if isinstance(tmp, Path) else tmp
    if value == "$persona.email":
        email = ctx.get("persona_email")
        if email is None:
            raise DispatchError(
                f"resolve_args({cell_id}): args.{key} references "
                f"$persona.email but ctx does not provide persona_email"
            )
        return email
    if value == "$persona.api_key":
        api_key = ctx.get("api_key")
        if api_key is None:
            raise DispatchError(
                f"resolve_args({cell_id}): args.{key} references "
                f"$persona.api_key but ctx does not provide api_key"
            )
        return api_key
    raise DispatchError(
        f"resolve_args({cell_id}): args.{key} = {value!r} — "
        f"unrecognized placeholder. Extend dispatcher._resolve_one when "
        f"introducing new placeholder vocabulary."
    )


# Cached scanner.server module. Importing it once instantiates the
# FastMCP server (44 modules registered lazily). Subsequent calls are
# cheap.
_scanner_server: Any = None


def invoke_tool(cell: ToolCell, ctx: dict[str, Any]) -> str:
    """Import scanner.server, call the named MCP tool, return raw response.

    Raises DispatchError if the tool name doesn't resolve to a callable
    on scanner.server. The matrix runner uses this error to fail-RED
    cells with non-existent tool names — pre-launch this should never
    happen because validateCell rejects unknown tools, but the runtime
    check guards against drift if scanner.server is ever refactored.
    """
    global _scanner_server
    if _scanner_server is None:
        _scanner_server = importlib.import_module("scanner.server")

    fn = getattr(_scanner_server, cell.tool, None)
    if fn is None or not callable(fn):
        raise DispatchError(
            f"invoke_tool({cell.cell_id}): scanner.server has no callable "
            f"named {cell.tool!r}. Loader's VALID_TOOLS list out of sync?"
        )

    args = resolve_args(cell, ctx)
    return fn(**args)
