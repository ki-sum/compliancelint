"""§AA Option C Step 3 — tests for scanner/core/classification_client.py.

Covers spec'd acceptance:
  - Success path (200 → cache write + return obligations dict)
  - 304 cache hit (re-uses cached obligations from disk)
  - 401 unauthed (returns None — degraded mode signal)
  - Network timeout (returns None — degraded mode)
  - Malformed cache file (ignored, fetched fresh)
  - No api_key in config.json (returns None — degraded mode)
  - Missing config.json (returns None — degraded mode)
  - emit_degraded_notice_once is idempotent

NOT covered here (lives in test_obligation_lookup_classification.py):
  - obligation_lookup._build_index merging fetched fields into rows
"""
from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scanner.core import classification_client


@pytest.fixture(autouse=True)
def _isolate_filesystem(tmp_path, monkeypatch):
    """Repoint CACHE_DIR + CONFIG_PATH at a tmp dir per test so no test
    pollutes the real ~/.compliancelint/ state."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(
        classification_client,
        "CACHE_DIR",
        fake_home / ".compliancelint" / "classification-cache",
    )
    monkeypatch.setattr(
        classification_client,
        "CONFIG_PATH",
        fake_home / ".compliancelint" / "config.json",
    )
    classification_client.reset_degraded_notice_flag()
    yield


def _write_config(api_key: str | None) -> None:
    """Write a config.json with the given api_key (or omit it if None)."""
    classification_client.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"api_key": api_key} if api_key else {}
    classification_client.CONFIG_PATH.write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _make_http_response(payload: dict, etag: str = '"sha256:fake_etag"') -> MagicMock:
    """Build a context-manager mock that mimics urllib's response."""
    mock = MagicMock()
    mock.read.return_value = json.dumps(payload).encode("utf-8")
    mock.headers = {"ETag": etag}
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def test_no_config_returns_none():
    """Fresh install — no ~/.compliancelint/config.json yet."""
    result = classification_client.fetch_classifications(4)
    assert result is None


def test_config_without_api_key_returns_none():
    _write_config(api_key=None)
    result = classification_client.fetch_classifications(4)
    assert result is None


def test_config_with_empty_api_key_returns_none():
    _write_config(api_key="")
    result = classification_client.fetch_classifications(4)
    assert result is None


def test_success_path_writes_cache_and_returns_obligations():
    _write_config(api_key="cl_test_key")
    payload = {
        "article": 4,
        "obligations": {
            "ART04-OBL-1": {
                "detection_method": "Check for AI training docs",
                "rationale": "Documentation artifacts only",
                "what_to_scan": ["documentation"],
                "confidence": "medium",
                "human_judgment_needed": "Whether training is adequate",
            }
        },
    }
    with patch(
        "urllib.request.urlopen",
        return_value=_make_http_response(payload, '"sha256:abc123"'),
    ):
        result = classification_client.fetch_classifications(4)

    assert result == payload["obligations"]
    cache_file = classification_client.CACHE_DIR / "art04.json"
    assert cache_file.exists()
    cached = json.loads(cache_file.read_text(encoding="utf-8"))
    assert cached["etag"] == '"sha256:abc123"'
    assert cached["obligations"] == payload["obligations"]


def test_304_returns_cached_obligations_without_redownload():
    _write_config(api_key="cl_test_key")
    # Pre-seed cache
    classification_client.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = classification_client.CACHE_DIR / "art04.json"
    seeded = {
        "etag": '"sha256:cached_etag"',
        "obligations": {
            "ART04-OBL-1": {"detection_method": "from cache"},
        },
    }
    cache_file.write_text(json.dumps(seeded), encoding="utf-8")

    # Mock 304 response
    err = urllib.error.HTTPError(
        url="http://test", code=304, msg="Not Modified", hdrs={}, fp=None
    )
    with patch("urllib.request.urlopen", side_effect=err):
        result = classification_client.fetch_classifications(4)

    assert result == seeded["obligations"]


def test_401_returns_none_degraded_mode():
    _write_config(api_key="cl_test_key")
    err = urllib.error.HTTPError(
        url="http://test", code=401, msg="Unauthorized", hdrs={}, fp=None
    )
    with patch("urllib.request.urlopen", side_effect=err):
        result = classification_client.fetch_classifications(4)
    assert result is None


def test_500_returns_none_degraded_mode():
    _write_config(api_key="cl_test_key")
    err = urllib.error.HTTPError(
        url="http://test", code=500, msg="Server Error", hdrs={}, fp=None
    )
    with patch("urllib.request.urlopen", side_effect=err):
        result = classification_client.fetch_classifications(4)
    assert result is None


def test_network_timeout_returns_none():
    _write_config(api_key="cl_test_key")
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        result = classification_client.fetch_classifications(4)
    assert result is None


def test_url_error_returns_none():
    _write_config(api_key="cl_test_key")
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        result = classification_client.fetch_classifications(4)
    assert result is None


def test_malformed_cache_file_falls_through_to_fresh_fetch():
    """Cache file exists but is corrupted JSON — should ignore cache and
    do a clean fetch (no If-None-Match header sent)."""
    _write_config(api_key="cl_test_key")
    classification_client.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = classification_client.CACHE_DIR / "art04.json"
    cache_file.write_text("{not valid json", encoding="utf-8")

    payload = {"article": 4, "obligations": {"ART04-OBL-1": {"detection_method": "fresh"}}}

    captured_request = {}

    def fake_urlopen(req, timeout):
        captured_request["headers"] = dict(req.header_items())
        return _make_http_response(payload)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = classification_client.fetch_classifications(4)

    assert result == payload["obligations"]
    # If cache was malformed, no If-None-Match should be sent
    headers_lower = {k.lower() for k in captured_request["headers"]}
    assert "if-none-match" not in headers_lower


def test_emit_degraded_notice_is_idempotent(capsys):
    """First call writes; subsequent calls are no-ops."""
    classification_client.emit_degraded_notice_once()
    first_capture = capsys.readouterr()
    assert "Offline mode" in first_capture.err

    # Second + third calls produce no further output.
    classification_client.emit_degraded_notice_once()
    classification_client.emit_degraded_notice_once()
    second_capture = capsys.readouterr()
    assert second_capture.err == ""


def test_reset_degraded_notice_flag_reenables_emission(capsys):
    """Test-only helper actually clears the flag so subsequent tests can
    exercise the notice path again."""
    classification_client.emit_degraded_notice_once()
    capsys.readouterr()
    classification_client.reset_degraded_notice_flag()
    classification_client.emit_degraded_notice_once()
    cap = capsys.readouterr()
    assert "Offline mode" in cap.err


def test_etag_round_trip_uses_if_none_match_header():
    """When cache exists with valid etag, fetch sends If-None-Match
    header so server can short-circuit to 304."""
    _write_config(api_key="cl_test_key")
    classification_client.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = classification_client.CACHE_DIR / "art04.json"
    seeded = {
        "etag": '"sha256:my_etag"',
        "obligations": {"ART04-OBL-1": {"detection_method": "x"}},
    }
    cache_file.write_text(json.dumps(seeded), encoding="utf-8")

    captured_headers = {}

    def fake_urlopen(req, timeout):
        captured_headers.update(dict(req.header_items()))
        return _make_http_response(
            {"article": 4, "obligations": {"ART04-OBL-2": {"detection_method": "y"}}},
            etag='"sha256:newer"',
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        classification_client.fetch_classifications(4)

    # urllib normalizes header keys; check both possible cases
    keys_lower = {k.lower(): v for k, v in captured_headers.items()}
    assert "if-none-match" in keys_lower
    assert keys_lower["if-none-match"] == '"sha256:my_etag"'
