"""2026-06-15 D7 — cl_scan_all retry on transient AI failure +
partial-coverage report.

Pre-fix: a single `mod.scan(project_path)` exception (timeout, rate
limit, network blip) silently dropped that article's findings. Daily
auto-scan on a bad day would skip 5-6 high-content articles
(Chapter III provider, Art 9 / 11-15) → dashboard's Compliance Journey
chart showed mysterious dips on 6/5 + 6/14 for kisum's repo. The
scanner returned 200 / overall_compliance="compliant" with no
indication that ~5 articles never produced findings.

Post-fix:
  1. `mod.scan` is wrapped in `_scan_with_retry_module_level` — 3
     attempts with 0.5s / 1.0s / 2.0s exponential backoff
  2. Permanent failure (all 3 attempts exhausted) re-raises so
     cl_scan_all's outer except branch records the article in the
     report's `failed_articles` list AND overall_compliance is
     forced to "partial" — dashboard can flag partial-coverage scans
     visibly instead of treating them as clean runs

This file targets the module-level helper (unit-testable in isolation).
For the full request → response integration, see the Pool 4 fixture at
`pool4/test_cl_scan_all_real.py`.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


def test_retry_returns_immediately_on_first_success(monkeypatch):
    """Success on attempt 1 → returns without retrying or sleeping."""
    from server import _scan_with_retry_module_level

    mod = MagicMock()
    mod.scan.return_value = "scan-result-sentinel"

    # Sleep should never fire on first-attempt success — assert it.
    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

    result = _scan_with_retry_module_level(9, mod, "/tmp/proj")

    assert result == "scan-result-sentinel"
    assert mod.scan.call_count == 1, (
        f"Should have called scan exactly once, got {mod.scan.call_count}"
    )
    assert sleep_calls == [], f"Should not sleep on first success, got {sleep_calls}"


def test_retry_recovers_from_one_transient_failure(monkeypatch):
    """Failure on attempt 1, success on attempt 2 → returns success,
    sleeps once with the 0.5s backoff."""
    from server import _scan_with_retry_module_level

    mod = MagicMock()
    # First call raises, second returns success
    mod.scan.side_effect = [
        RuntimeError("simulated AI timeout"),
        "scan-result-recovered",
    ]

    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

    result = _scan_with_retry_module_level(9, mod, "/tmp/proj")

    assert result == "scan-result-recovered"
    assert mod.scan.call_count == 2
    assert sleep_calls == [0.5], (
        f"Should sleep 0.5s before retry, got {sleep_calls}"
    )


def test_retry_recovers_after_two_transient_failures(monkeypatch):
    """Failures on 1 + 2, success on 3 → returns success, sleeps
    twice (0.5s, 1.0s)."""
    from server import _scan_with_retry_module_level

    mod = MagicMock()
    mod.scan.side_effect = [
        RuntimeError("blip 1"),
        RuntimeError("blip 2"),
        "scan-result-finally",
    ]

    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

    result = _scan_with_retry_module_level(9, mod, "/tmp/proj")

    assert result == "scan-result-finally"
    assert mod.scan.call_count == 3
    assert sleep_calls == [0.5, 1.0]


def test_retry_raises_after_all_attempts_exhausted(monkeypatch):
    """3 attempts all fail → raises the LAST exception (cl_scan_all's
    outer except branch then records the article in failed_articles)."""
    from server import _scan_with_retry_module_level

    mod = MagicMock()
    err_third = RuntimeError("permanent failure on attempt 3")
    mod.scan.side_effect = [
        RuntimeError("blip 1"),
        RuntimeError("blip 2"),
        err_third,
    ]

    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

    with pytest.raises(RuntimeError, match="permanent failure on attempt 3"):
        _scan_with_retry_module_level(9, mod, "/tmp/proj")

    assert mod.scan.call_count == 3
    # Two sleeps between three attempts; no sleep after last failure
    assert sleep_calls == [0.5, 1.0]


def test_retry_passes_project_path_to_scan(monkeypatch):
    """Sanity: project_path is forwarded verbatim to mod.scan."""
    from server import _scan_with_retry_module_level

    mod = MagicMock()
    mod.scan.return_value = "ok"
    monkeypatch.setattr("time.sleep", lambda s: None)

    _scan_with_retry_module_level(15, mod, "/the/exact/project/path")

    mod.scan.assert_called_once_with("/the/exact/project/path")
