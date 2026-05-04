"""Pool 4 fixture cleanup helpers.

Cross-system tests create real SaaS repos under the test persona's
account; these helpers tear them down post-test so the dev DB doesn't
accumulate orphans. Wired into pytest fixture teardown via
``conftest.py``.

The purge endpoint is the same one the user-facing "Delete repo +
all data" UI button calls — single source of truth for cascade
behavior across scans/findings/finding_responses/evidence_items/
repo_access. We don't issue raw DELETE on each table because the
cascade order matters and is owned by the route handler.
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any


PURGE_TIMEOUT_SECONDS = 10.0


class CleanupError(RuntimeError):
    """Raised when teardown cleanup fails after a non-trivial number
    of retries. Distinguishable from in-test errors so the pytest
    teardown can decide whether to fail-RED or just warn.
    """


def purge_repo(
    saas_url: str,
    api_key: str,
    repo_id: str,
    *,
    confirm_name: str,
    timeout: float = PURGE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """DELETE /api/v1/repos/<repo_id>/purge with confirm body.

    The dashboard requires the body include a ``confirmName`` matching
    the repo name as a destructive-action safeguard (mirrors the UI's
    "type the repo name to confirm" pattern). Returns the parsed
    response on 2xx; raises ``CleanupError`` on any non-2xx.
    """
    url = f"{saas_url.rstrip('/')}/api/v1/repos/{repo_id}/purge"
    body = json.dumps({"confirmName": confirm_name}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="DELETE",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
            if 200 <= resp.status < 300:
                try:
                    return json.loads(payload) if payload else {}
                except json.JSONDecodeError:
                    return {"_raw": payload}
            raise CleanupError(
                f"purge_repo({repo_id}): unexpected status {resp.status} "
                f"body={payload[:200]}"
            )
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise CleanupError(
            f"purge_repo({repo_id}): HTTP {e.code} {e.reason} "
            f"body={body_text[:200]}"
        ) from e
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        raise CleanupError(
            f"purge_repo({repo_id}): transport failure: {e}"
        ) from e


def fetch_scan_via_api(
    saas_url: str,
    api_key: str,
    repo_id: str,
    scan_id: str,
    *,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """GET /api/v1/repos/<repo_id>/scans/<scan_id> — Layer 2 verification.

    Used by cross-system asserters to confirm the API view of the scan
    matches the DB view (Layer 1). Divergence indicates a normalize-
    layer bypass.
    """
    url = f"{saas_url.rstrip('/')}/api/v1/repos/{repo_id}/scans/{scan_id}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
            if 200 <= resp.status < 300:
                return json.loads(payload)
            raise CleanupError(
                f"fetch_scan_via_api({repo_id}/{scan_id}): unexpected "
                f"status {resp.status} body={payload[:200]}"
            )
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise CleanupError(
            f"fetch_scan_via_api({repo_id}/{scan_id}): HTTP {e.code} "
            f"body={body_text[:200]}"
        ) from e
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        raise CleanupError(
            f"fetch_scan_via_api: transport failure: {e}"
        ) from e
