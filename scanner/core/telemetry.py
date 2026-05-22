"""
MCP scanner telemetry — opt-in Sentry error reporting (Phase 1).

Architecture (X2 design, 2026-05-14):
  - Scanner is BSL source-available → DSN cannot be hardcoded
  - SaaS endpoint /api/v1/telemetry/sentry-dsn delivers DSN to
    authenticated callers (anyone who's run cl_connect)
  - DSN persisted at ~/.compliancelint/sentry.json (per-user global,
    not per-project — server starts once across all projects)
  - This module reads that file at boot. No file → silent no-op
    (default opt-out). Phase 2 adds the cl_connect prompt that
    actually fetches the DSN + writes the file.

Phase 1 scope (this commit):
  - Read side: init_if_opted_in() reads ~/.compliancelint/sentry.json
  - If file exists and `opted_out` is true → silent no-op
  - If file exists and `dsn` is present → init sentry-sdk
  - Any exception in this module is swallowed — telemetry MUST NEVER
    break the MCP server. A broken Sentry SDK is preferable to a
    broken cl_scan.

Phase 2 (NOT in this commit):
  - cl_connect prompt asking user to opt in
  - Fetch DSN from SaaS, persist sentry.json
  - cl_disconnect wipes sentry.json

Phase 3 (NOT in this commit):
  - Scrub layer: normalize file paths to <workspace>/<file>, strip
    user home dir from stack traces
  - Tier 1 filter: drop known environment exceptions (git subprocess,
    FileNotFoundError, PermissionError, UnicodeDecodeError, SSL cert)
  - Fingerprint dedup

Data minimization already in place (matching dashboard pattern):
  - send_default_pii: False (no IP / machine name / username auto-attached)
  - sample_rate: 0.25 default (4 takes 1 — SaaS-controlled via DSN response)
  - traces_sample_rate: 0 (no performance spans, just exceptions)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger("compliancelint.telemetry")

# Global per-user config dir — same convention as scanner/core/scanner_log.py
# which uses ~/.compliancelint/logs/{hash}/. We use ~/.compliancelint/sentry.json
# (singular file, not subdir) because there is only one DSN per user across
# all projects.
_CONFIG_DIR = ".compliancelint"
_CONFIG_FILE = "sentry.json"


def _config_path() -> Path:
    """Where the per-user Sentry DSN config lives.

    Cross-platform via Path.home() — resolves to:
      - Windows: C:\\Users\\<user>\\.compliancelint\\sentry.json
      - Linux/Mac: /home/<user>/.compliancelint/sentry.json

    Override via COMPLIANCELINT_HOME env var (used in tests to point at
    a temp dir without polluting the real user home).
    """
    override = os.environ.get("COMPLIANCELINT_HOME")
    if override:
        return Path(override) / _CONFIG_FILE
    return Path.home() / _CONFIG_DIR / _CONFIG_FILE


def _read_config() -> dict[str, Any] | None:
    """Read the per-user Sentry config. Returns None if missing/invalid.

    Invalid JSON returns None (not raise) so a corrupted file from an
    earlier scanner version's bug doesn't kill subsequent server starts.
    """
    path = _config_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("telemetry config unreadable (%s) — treating as opted out", e)
        return None


def init_if_opted_in() -> bool:
    """Initialize Sentry SDK if the user has explicitly opted in.

    Returns True if init() was called (regardless of success), False if
    we skipped (default opt-out path). Never raises — wrapped in
    try/except so an SDK import failure or DSN format issue cannot
    prevent the MCP server from starting.

    Boot integration in scanner/server.py:
        from core.telemetry import init_if_opted_in
        init_if_opted_in()  # ← single line, near top of file

    Caller doesn't need to handle exceptions; this is the boundary.
    """
    try:
        config = _read_config()
        if config is None:
            return False  # no opt-in file → default opt-out, silent

        if config.get("opted_out") is True:
            # Explicit opt-out marker (cl_connect "no" answer writes this
            # so we don't re-prompt every server start).
            return False

        dsn = config.get("dsn")
        if not dsn or not isinstance(dsn, str):
            logger.debug("telemetry config has no usable dsn — skipping init")
            return False

        # Import sentry_sdk lazily so users who haven't installed the
        # optional dep don't fail at import time. (Phase 1 keeps it as
        # a regular dep in pyproject.toml, but lazy-import is defensive.)
        try:
            import sentry_sdk  # noqa: PLC0415 — defensive lazy import
        except ImportError:
            logger.debug("sentry_sdk not installed — telemetry disabled")
            return False

        sentry_sdk.init(
            dsn=dsn,
            environment=config.get("env", "production"),
            # Phase 1: scrubbing is a passthrough. Phase 3 will replace
            # this with the real scrub function that normalizes paths.
            before_send=_passthrough_before_send,
            send_default_pii=False,
            sample_rate=float(config.get("sample_rate", 0.25)),
            traces_sample_rate=0,  # no performance spans, errors only
            # Release tag helps Sentry group events across versions;
            # CL_VERSION lives in scanner/server.py. Read lazily here
            # to avoid a circular import — fall back to "unknown" if
            # the import path isn't available (unit-test contexts).
            release=_resolve_release(),
        )
        logger.info("telemetry initialised (sentry-sdk, sample_rate=%s)",
                    config.get("sample_rate", 0.25))
        return True

    except Exception as e:  # noqa: BLE001 — broad-except is intentional
        # Telemetry boot MUST NEVER break the server. Any failure here
        # (corrupted config, sentry-sdk API change, network at init,
        # whatever) is swallowed and logged at debug level.
        logger.debug("telemetry init failed silently: %s", e)
        return False


def _passthrough_before_send(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    """Phase 1 placeholder. Phase 3 will replace with real scrub logic.

    Real implementation will:
      - Normalize abs file paths in stack frames to <workspace>/<file>
      - Strip user home dir from any string field
      - Drop events whose exception type is in the Tier 1 filter list
        (FileNotFoundError, PermissionError, UnicodeDecodeError,
        subprocess.CalledProcessError from git invocations, etc.)
      - Return None to drop the event entirely when applicable
    """
    return event


def _resolve_release() -> str:
    """Best-effort version lookup for the Sentry release tag.

    Reads from installed package metadata (pyproject.toml version field)
    via importlib.metadata. We deliberately do NOT import scanner.server
    here — that would trigger server.py's boot wiring (which itself
    calls init_if_opted_in), causing a second init invocation on the
    first telemetry call and breaking test assertions on call_count.
    """
    try:
        from importlib.metadata import version  # noqa: PLC0415
        return f"compliancelint-mcp@{version('compliancelint')}"
    except Exception:  # noqa: BLE001 — metadata lookup is best-effort
        return "compliancelint-mcp@unknown"


# ─── Phase 2: opt-in / opt-out helpers used by cl_connect / cl_disconnect ──


def fetch_dsn_from_saas(saas_url: str, api_key: str, timeout: int = 8) -> dict[str, Any] | None:
    """Fetch the MCP scanner DSN from the authenticated SaaS endpoint.

    Returns the response dict on 200 ({dsn, env, sample_rate,
    send_default_pii}), or None on any failure (network, 401, 503,
    parse error). Caller decides whether to persist or treat as
    opted-out.

    Uses curl subprocess for consistency with cl_connect's existing
    approach (avoiding adding an httpx/requests dependency to the
    scanner just for one HTTP call). The CREATE_NO_WINDOW flag
    suppresses a console flash on Windows.
    """
    url = f"{saas_url.rstrip('/')}/api/v1/telemetry/sentry-dsn"
    flags: dict[str, Any] = {"capture_output": True, "text": True, "timeout": timeout}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(
            ["curl", "-s", "-w", "\n%{http_code}", "--max-time", str(timeout),
             "-H", f"Authorization: Bearer {api_key}", url],
            **flags,
        )
        if result.returncode != 0 or not result.stdout.strip():
            logger.debug("telemetry DSN fetch curl failed: rc=%s", result.returncode)
            return None
        # Split body and HTTP status (last line is the status code).
        lines = result.stdout.strip().split("\n")
        status_line = lines[-1].strip()
        body = "\n".join(lines[:-1])
        if status_line != "200":
            logger.debug("telemetry DSN endpoint returned %s — treating as not configured", status_line)
            return None
        data = json.loads(body)
        if not data.get("dsn"):
            return None
        return data
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as e:
        logger.debug("telemetry DSN fetch failed silently: %s", e)
        return None


def write_dsn_config(payload: dict[str, Any]) -> Path:
    """Persist the opt-in DSN config to ~/.compliancelint/sentry.json.

    Caller is expected to pass the dict returned by fetch_dsn_from_saas
    (which already has the required `dsn` key). We add no business
    logic here — this is a pure I/O helper so opt-in flows remain
    auditable in one place (cl_connect's call site).

    Creates parent directory if missing. Overwrites any existing file
    (opt-in is idempotent and may also be used to refresh the DSN
    after rotation).
    """
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def delete_dsn_config() -> bool:
    """Remove ~/.compliancelint/sentry.json (clean opt-out).

    Returns True if a file was deleted, False if nothing was there to
    delete (idempotent — no error on missing file). Called by
    cl_disconnect for clean uninstall, and by the cl_connect opt-out
    path (enable_telemetry=False) to reset to default no-op state.
    """
    path = _config_path()
    if not path.exists():
        return False
    try:
        path.unlink()
        return True
    except OSError as e:
        logger.debug("telemetry config delete failed: %s", e)
        return False


def is_opted_in() -> bool:
    """True iff a usable DSN config is currently persisted.

    Used by cl_connect to decide whether to surface the opt-in hint
    (don't nag a user who has already opted in). Mirrors the gate
    inside init_if_opted_in() but without the side effect.
    """
    config = _read_config()
    if config is None:
        return False
    if config.get("opted_out") is True:
        return False
    dsn = config.get("dsn")
    return bool(dsn and isinstance(dsn, str))
