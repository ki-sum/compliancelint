"""
Canonical error response envelope for ComplianceLint MCP tools.

Every tool that returns an error to the client should use `error_envelope()`
or `dump_error()` so that:

  1. The response includes a stable `request_id` (so bug reports are
     correlatable to scanner.log entries).
  2. The response includes a `report_url` pointing at a pre-filled GitHub
     issue template — users see this in their MCP client and can click
     through to file a bug.
  3. The error is logged to scanner.log alongside its request_id, which is
     what makes "the user pasted Error ID xyz" → "what actually happened
     server-side" lookup possible.

The shape is intentionally similar to the dashboard `/api/errors` payload
so we can correlate MCP-side and SaaS-side errors via request_id when
running cross-system scans (cl_sync round-trip).
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger("compliancelint")

REPORT_EMAIL = "support@compliancelint.dev"
ISSUE_TEMPLATE_URL = (
    "https://github.com/ki-sum/compliancelint/issues/new"
    "?template=bug_report.yml"
)


def new_request_id() -> str:
    """Generate a short, mostly-unique request id suitable for log correlation."""
    return f"req_{uuid.uuid4().hex[:16]}"


def error_envelope(
    message: str,
    *,
    request_id: str | None = None,
    log: bool = True,
    **extras: Any,
) -> dict[str, Any]:
    """Build a canonical error envelope.

    Args:
        message: human-readable error message (shown to the user).
        request_id: explicit request id; if None, a fresh one is generated.
        log: when True, write `error` level to scanner.log with request_id.
        **extras: additional fields (e.g. ``fix="..."``, ``article=10``,
                  ``validation_errors=[...]``). Caller-provided keys win
                  over the standard envelope keys.

    Returns:
        A dict ready to be passed to ``json.dumps`` or returned directly.
    """
    rid = request_id or new_request_id()
    payload: dict[str, Any] = {
        "error": message,
        "request_id": rid,
        "report_url": f"{ISSUE_TEMPLATE_URL}&error-id={rid}",
        "report_email": REPORT_EMAIL,
    }
    payload.update(extras)
    if log:
        logger.error("mcp_error request_id=%s message=%s", rid, message)
    return payload


def dump_error(message: str, **kwargs: Any) -> str:
    """Convenience: build envelope and JSON-serialize it.

    Mirrors the shape used by ``json.dumps({"error": ...})`` call sites,
    so migration is a near 1-to-1 replacement.
    """
    return json.dumps(error_envelope(message, **kwargs))
