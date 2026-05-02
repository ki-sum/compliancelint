"""§AA Option C — Fetch obligation classification metadata from compliancelint.dev SaaS.

The 5 SaaS-only `automation_assessment` fields (detection_method, rationale,
what_to_scan, confidence, human_judgment_needed) were stripped from the
public obligation JSONs in commit `ca31b2e`. They are now served by the
SaaS endpoint at:

    GET /api/v1/regulations/eu-ai-act/articles/<N>/classifications

This module fetches them per article, caches the response in
`~/.compliancelint/classification-cache/`, and uses ETag for HTTP-level
caching so re-runs only pay one round-trip per article (304 if file
unchanged) instead of re-downloading.

Falls back to **degraded mode** (returns None) when:
    - `~/.compliancelint/config.json` is missing or has no api_key
      (user hasn't run `cl_connect` yet)
    - SaaS endpoint is unreachable (network failure / timeout)
    - Endpoint returns 401 / 5xx

Caller (obligation_lookup._build_index) MUST handle None as
"classification metadata not available — automation_assessment will
only have `level`". This preserves the BSL "scanner usable offline"
promise: obligation list + level still browsable, deeper detection
metadata unlocks on free sign-up at compliancelint.dev.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger("compliancelint")

DEFAULT_BASE = "https://compliancelint.dev"
CACHE_DIR = Path.home() / ".compliancelint" / "classification-cache"
CONFIG_PATH = Path.home() / ".compliancelint" / "config.json"

# 10s is a reasonable upper bound for a single small JSON GET. Scanner is
# CLI-driven so a stuck request blocks user-visible work — fail fast.
HTTP_TIMEOUT_SEC = 10


class ClassificationFetchError(Exception):
    """Raised only by callers that explicitly want to fail-loud rather
    than degrade. Default fetch_classifications() catches all errors and
    returns None (degraded mode signal)."""


def _load_api_key() -> Optional[str]:
    """Read api_key from ~/.compliancelint/config.json. Returns None on
    any failure (file missing, JSON parse error, key missing).

    Caller treats None as "user hasn't run cl_connect yet → degraded
    mode". Logs at debug level only — config-missing is the expected
    state for fresh installs and we don't want to spam the CLI."""
    if not CONFIG_PATH.exists():
        return None
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("classification_client: config.json unreadable: %s", e)
        return None
    key = cfg.get("api_key")
    if not isinstance(key, str) or not key:
        return None
    return key


def _cache_file_for(article_number: int) -> Path:
    return CACHE_DIR / f"art{article_number:02d}.json"


def fetch_classifications(article_number: int) -> Optional[dict]:
    """Return {OID: {5_field_dict}} for the given article, or None on
    graceful failure.

    Caching:
      - First call: HTTP GET, store full response (etag + obligations)
        in ~/.compliancelint/classification-cache/artN.json
      - Subsequent calls: send If-None-Match with cached etag.
        - 304 → re-use cached obligations (instant, no payload)
        - 200 → overwrite cache with new payload + etag

    Caller must handle `None` as the "degraded mode" signal — the
    scanner falls back to public-only `automation_assessment.level`.
    """
    api_key = _load_api_key()
    if not api_key:
        return None

    base = os.environ.get("COMPLIANCELINT_BASE", DEFAULT_BASE)
    url = f"{base}/api/v1/regulations/eu-ai-act/articles/{article_number}/classifications"

    cache_file = _cache_file_for(article_number)
    cached_etag: Optional[str] = None
    cached_obligations: Optional[dict] = None
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            cached_etag = cached.get("etag")
            cached_obligations = cached.get("obligations")
        except (OSError, json.JSONDecodeError) as e:
            logger.debug(
                "classification_client: cache file %s unreadable, ignoring: %s",
                cache_file,
                e,
            )

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {api_key}")
    if cached_etag:
        req.add_header("If-None-Match", cached_etag)

    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            etag = resp.headers.get("ETag")
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps(
                    {
                        "etag": etag,
                        "obligations": payload.get("obligations", {}),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return payload.get("obligations") or {}
    except urllib.error.HTTPError as e:
        if e.code == 304 and cached_obligations is not None:
            return cached_obligations
        # 401 / 4xx / 5xx all degrade to None. Log at debug since
        # offline / unauthed is a normal state we want to support.
        logger.debug(
            "classification_client: HTTP %s for article %s, degrading",
            e.code,
            article_number,
        )
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        logger.debug(
            "classification_client: network error for article %s: %s",
            article_number,
            e,
        )
        return None


# One-time CLI notice flag — set on first degraded-mode detection per
# process so we don't spam the user with the same warning N times when
# build_index loads 44 articles.
_DEGRADED_NOTICE_SHOWN = False


def emit_degraded_notice_once() -> None:
    """Print a one-time degraded-mode notice to stderr. Idempotent —
    subsequent calls within the same process are no-ops.

    Called by obligation_lookup when classification_client returns
    None for the first article it tries to enrich."""
    global _DEGRADED_NOTICE_SHOWN
    if _DEGRADED_NOTICE_SHOWN:
        return
    _DEGRADED_NOTICE_SHOWN = True
    import sys

    sys.stderr.write(
        "⚠ Offline mode: 247 obligations loaded, but classification "
        "metadata\n"
        "  (detection_method, rationale, etc.) unavailable.\n"
        "  Run `cl_connect` to enable scanning. "
        "Free at compliancelint.dev.\n"
    )


def reset_degraded_notice_flag() -> None:
    """Test-only helper. Resets the one-time-notice flag so subsequent
    tests can re-trigger the notice path."""
    global _DEGRADED_NOTICE_SHOWN
    _DEGRADED_NOTICE_SHOWN = False
