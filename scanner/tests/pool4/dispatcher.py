"""Cell-driven MCP tool dispatcher (real-MCP transport).

Phase 1 rewrite. Replaces the in-process Phase 0 dispatcher (which
imported scanner.server directly — violating Pool 4 hard constraint
C1) with a real subprocess JSON-RPC transport via
:class:`scanner.tests.pool4.mcp_client.McpStdioClient`.

Two responsibilities, same as before:

  1. **Resolve placeholders** in ``cell.invoke.args`` against a
     runtime ``ctx`` dict. The vocabulary mirrors the internal
     TypeScript runner's ``resolveOne``:

     - ``$pytest.tmp_path``     → ctx["tmp_path"]   (str/Path)
     - ``$persona.email``       → ctx["persona_email"]
     - ``$persona.api_key``     → ctx["api_key"]
     - ``$persona.session_token`` → ctx["session_token"]
     - ``$repo.id``             → ctx["repo_id"]
     - ``$repo.name``           → ctx["repo_name"]
     - ``$scan.id``             → ctx["scan_id"]
     - ``$finding.id``          → ctx["finding_id"]
     - ``$stepN.body.<dotpath>`` → ctx["chain_steps"][N]["body"][...]
       (Tier-A pipeline cells; runner populates after each step)

  2. **Invoke the named tool** by reusing a caller-supplied
     ``McpStdioClient`` (so the matrix runner can amortize subprocess
     startup across cells of the same persona). Returns the inner JSON
     string the @mcp.tool function emitted — same return shape as the
     legacy dispatcher so test code parses it identically.

What this dispatcher deliberately does NOT do:

  - Spawn the MCP subprocess itself. Caller owns lifecycle (the
    ``conftest.py`` plugin scopes it per cell or per session).
  - SaaS DB introspection. Use
    :mod:`scanner.tests.pool4.saas_introspection` for that.
  - Asserter dispatch. Per-tool asserters (TypeScript side) own that.

Why client injection: subprocess startup on Windows is ~0.5-1 s; for
a 330-cell daily run that's 2-5 minutes of pure startup overhead.
Letting the runner reuse one client across same-persona cells (with
per-cell isolation enforced by the SaaS / git layer, not the MCP
layer) keeps the smoke fast. Per-cell isolation can be opted into by
spawning a fresh client when a cell opts in.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .cell_loader import ToolCell
from .mcp_client import McpStdioClient


class DispatchError(RuntimeError):
    """Raised when a cell can't be dispatched (unresolved placeholder,
    bad ctx shape, etc.)."""


_STEP_REF_RE = re.compile(r"^\$step(\d+)\.body(?:\.(.+))?$")


def resolve_args(cell: ToolCell, ctx: dict[str, Any]) -> dict[str, Any]:
    """Return cell.invoke.args with placeholder strings substituted.

    Unrecognized ``$``-prefixed strings raise ``DispatchError`` so
    drift between the cell tree and dispatcher vocabulary surfaces
    loudly instead of silently passing the literal placeholder
    through to the tool.
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
    return {
        key: _resolve_one(value, ctx, cell.cell_id, key)
        for key, value in raw.items()
    }


def _resolve_one(value: Any, ctx: dict[str, Any], cell_id: str, key: str) -> Any:
    if isinstance(value, list):
        return [_resolve_one(v, ctx, cell_id, f"{key}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, dict):
        return {k: _resolve_one(v, ctx, cell_id, f"{key}.{k}") for k, v in value.items()}
    if not isinstance(value, str) or not value.startswith("$"):
        return value

    if value == "$pytest.tmp_path":
        tmp = ctx.get("tmp_path")
        if tmp is None:
            raise DispatchError(
                f"resolve_args({cell_id}): args.{key} references "
                f"$pytest.tmp_path but ctx['tmp_path'] is missing"
            )
        return str(tmp) if isinstance(tmp, Path) else tmp

    if value == "$persona.email":
        email = ctx.get("persona_email")
        if email is None:
            raise DispatchError(
                f"resolve_args({cell_id}): args.{key} references "
                f"$persona.email but ctx['persona_email'] is missing"
            )
        return email

    if value == "$persona.api_key":
        api_key = ctx.get("api_key")
        if api_key is None:
            raise DispatchError(
                f"resolve_args({cell_id}): args.{key} references "
                f"$persona.api_key but ctx['api_key'] is missing"
            )
        return api_key

    if value == "$persona.session_token":
        token = ctx.get("session_token")
        if token is None:
            raise DispatchError(
                f"resolve_args({cell_id}): args.{key} references "
                f"$persona.session_token but ctx['session_token'] is missing"
            )
        return token

    if value == "$repo.id":
        repo_id = ctx.get("repo_id")
        if repo_id is None:
            raise DispatchError(
                f"resolve_args({cell_id}): args.{key} references "
                f"$repo.id but ctx['repo_id'] is missing — runner must "
                f"populate after the create-repo step"
            )
        return repo_id

    if value == "$repo.name":
        repo_name = ctx.get("repo_name")
        if repo_name is None:
            raise DispatchError(
                f"resolve_args({cell_id}): args.{key} references "
                f"$repo.name but ctx['repo_name'] is missing"
            )
        return repo_name

    if value == "$scan.id":
        scan_id = ctx.get("scan_id")
        if scan_id is None:
            raise DispatchError(
                f"resolve_args({cell_id}): args.{key} references "
                f"$scan.id but ctx['scan_id'] is missing — runner must "
                f"populate after the cl_sync step"
            )
        return scan_id

    if value == "$finding.id":
        finding_id = ctx.get("finding_id")
        if finding_id is None:
            raise DispatchError(
                f"resolve_args({cell_id}): args.{key} references "
                f"$finding.id but ctx['finding_id'] is missing"
            )
        return finding_id

    step_match = _STEP_REF_RE.match(value)
    if step_match:
        step_idx = int(step_match.group(1))
        dotpath = step_match.group(2) or ""
        steps = ctx.get("chain_steps") or []
        if step_idx >= len(steps):
            raise DispatchError(
                f"resolve_args({cell_id}): args.{key} references "
                f"$step{step_idx} but only {len(steps)} chain step(s) "
                f"have run — runner must execute steps in order"
            )
        step_ctx = steps[step_idx]
        body = step_ctx.get("body") if isinstance(step_ctx, dict) else None
        if body is None:
            raise DispatchError(
                f"resolve_args({cell_id}): args.{key} references "
                f"$step{step_idx}.body but step has no body"
            )
        if not dotpath:
            return body
        cursor: Any = body
        for segment in dotpath.split("."):
            if not isinstance(cursor, dict) or segment not in cursor:
                raise DispatchError(
                    f"resolve_args({cell_id}): args.{key} dotpath "
                    f"{dotpath!r} not resolvable on $step{step_idx}.body "
                    f"(stuck at segment {segment!r})"
                )
            cursor = cursor[segment]
        return cursor

    raise DispatchError(
        f"resolve_args({cell_id}): args.{key} = {value!r} — unrecognized "
        f"placeholder. Extend dispatcher._resolve_one (and the TS sibling "
        f"in the TS sibling) when introducing new placeholder vocabulary."
    )


def invoke_tool(
    cell: ToolCell,
    ctx: dict[str, Any],
    *,
    client: McpStdioClient,
) -> str:
    """Send tools/call over MCP and return the inner JSON string.

    Caller-supplied client lets the matrix runner reuse one
    subprocess for many cells (or open a fresh one per cell when
    isolation matters). The dispatcher itself is stateless.

    Raises ``DispatchError`` for cell-level problems (unknown tool,
    unresolved placeholder); raises
    :class:`McpClientError` for transport-level problems (subprocess
    dead, JSON-RPC error envelope).
    """
    args = resolve_args(cell, ctx)
    return client.call_tool(cell.tool, args)
