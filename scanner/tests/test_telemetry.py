"""
Unit tests for scanner/core/telemetry.py — opt-in semantics + safe-fail.

Critical invariants under test:
  1. Default = opt-out (no config file → init_if_opted_in returns False)
  2. Explicit opt-out marker is honoured (so re-prompts don't happen)
  3. Valid DSN config → init is attempted (sentry_sdk.init is called)
  4. Corrupted config → silent skip (returns False, never raises)
  5. Module-level call NEVER raises (server boot must be unblockable)
  6. Missing sentry_sdk → silent skip (returns False)

The tests use COMPLIANCELINT_HOME env var to redirect ~/.compliancelint
to a tmp dir, so the real user-home config (if any) is never touched.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture
def tmp_compliancelint_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ~/.compliancelint/ to a tmp dir for the duration of one test.

    Returns the tmp_path so the test can write a sentry.json into it.
    """
    monkeypatch.setenv("COMPLIANCELINT_HOME", str(tmp_path))
    return tmp_path


def _write_config(home: Path, payload: dict) -> Path:
    """Helper: write a sentry.json into the tmp home dir."""
    config_path = home / "sentry.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return config_path


# ─── Default opt-out ─────────────────────────────────────────────────


def test_no_config_returns_false(tmp_compliancelint_home: Path) -> None:
    """No sentry.json file at all → silent opt-out, no init."""
    from scanner.core.telemetry import init_if_opted_in
    assert init_if_opted_in() is False


def test_explicit_opted_out_returns_false(tmp_compliancelint_home: Path) -> None:
    """sentry.json with `opted_out: true` → no init even if dsn present."""
    _write_config(
        tmp_compliancelint_home,
        {"opted_out": True, "dsn": "https://x@y.ingest.de.sentry.io/1"},
    )
    from scanner.core.telemetry import init_if_opted_in
    assert init_if_opted_in() is False


def test_missing_dsn_returns_false(tmp_compliancelint_home: Path) -> None:
    """sentry.json without dsn field → silent skip."""
    _write_config(tmp_compliancelint_home, {"env": "production"})
    from scanner.core.telemetry import init_if_opted_in
    assert init_if_opted_in() is False


def test_empty_dsn_returns_false(tmp_compliancelint_home: Path) -> None:
    """sentry.json with empty-string dsn → silent skip (defensive)."""
    _write_config(tmp_compliancelint_home, {"dsn": ""})
    from scanner.core.telemetry import init_if_opted_in
    assert init_if_opted_in() is False


def test_non_string_dsn_returns_false(tmp_compliancelint_home: Path) -> None:
    """Corrupted dsn field (number / list / etc.) → silent skip."""
    _write_config(tmp_compliancelint_home, {"dsn": 12345})
    from scanner.core.telemetry import init_if_opted_in
    assert init_if_opted_in() is False


# ─── Init on valid config ────────────────────────────────────────────


def test_valid_dsn_calls_sentry_init(tmp_compliancelint_home: Path) -> None:
    """sentry.json with valid dsn → sentry_sdk.init is invoked exactly once."""
    _write_config(
        tmp_compliancelint_home,
        {"dsn": "https://test_key@o123.ingest.de.sentry.io/456"},
    )
    with mock.patch("sentry_sdk.init") as mock_init:
        from scanner.core.telemetry import init_if_opted_in
        result = init_if_opted_in()
        assert result is True
        assert mock_init.call_count == 1
        # Verify critical safety kwargs are set
        call_kwargs = mock_init.call_args.kwargs
        assert call_kwargs["send_default_pii"] is False
        assert call_kwargs["traces_sample_rate"] == 0
        assert call_kwargs["dsn"] == "https://test_key@o123.ingest.de.sentry.io/456"


def test_sample_rate_is_passed_through(tmp_compliancelint_home: Path) -> None:
    """SaaS-controlled sample_rate (from /telemetry/sentry-dsn response) honoured."""
    _write_config(
        tmp_compliancelint_home,
        {
            "dsn": "https://test_key@o123.ingest.de.sentry.io/456",
            "sample_rate": 0.1,
        },
    )
    with mock.patch("sentry_sdk.init") as mock_init:
        from scanner.core.telemetry import init_if_opted_in
        init_if_opted_in()
        assert mock_init.call_args.kwargs["sample_rate"] == 0.1


def test_default_sample_rate_is_025(tmp_compliancelint_home: Path) -> None:
    """When config omits sample_rate, fall back to 0.25 (the X2 design default)."""
    _write_config(
        tmp_compliancelint_home,
        {"dsn": "https://test_key@o123.ingest.de.sentry.io/456"},
    )
    with mock.patch("sentry_sdk.init") as mock_init:
        from scanner.core.telemetry import init_if_opted_in
        init_if_opted_in()
        assert mock_init.call_args.kwargs["sample_rate"] == 0.25


def test_env_defaults_to_production(tmp_compliancelint_home: Path) -> None:
    """When env not set in config, default to 'production' for safety
    (better to over-tag prod events than under-tag and lose grouping)."""
    _write_config(
        tmp_compliancelint_home,
        {"dsn": "https://test_key@o123.ingest.de.sentry.io/456"},
    )
    with mock.patch("sentry_sdk.init") as mock_init:
        from scanner.core.telemetry import init_if_opted_in
        init_if_opted_in()
        assert mock_init.call_args.kwargs["environment"] == "production"


# ─── Safe-fail invariants ────────────────────────────────────────────


def test_corrupted_json_does_not_raise(tmp_compliancelint_home: Path) -> None:
    """Malformed sentry.json from a prior scanner version bug → silent skip."""
    (tmp_compliancelint_home / "sentry.json").write_text(
        "{this-is-not: valid json", encoding="utf-8"
    )
    from scanner.core.telemetry import init_if_opted_in
    # MUST NOT raise. MUST return False.
    assert init_if_opted_in() is False


def test_sentry_sdk_import_error_silent(
    tmp_compliancelint_home: Path,
) -> None:
    """If sentry_sdk somehow isn't installed (extras / partial install),
    init_if_opted_in must NOT crash — return False silently."""
    _write_config(
        tmp_compliancelint_home,
        {"dsn": "https://test_key@o123.ingest.de.sentry.io/456"},
    )
    import sys

    # Block sentry_sdk import by inserting a sentinel that raises ImportError
    # when the telemetry module tries to import it.
    real_sentry_sdk = sys.modules.pop("sentry_sdk", None)
    sys.modules["sentry_sdk"] = None  # type: ignore[assignment]
    try:
        # Force re-import of telemetry so the lazy import inside fires
        # against our None-blocked sys.modules entry.
        sys.modules.pop("scanner.core.telemetry", None)
        from scanner.core.telemetry import init_if_opted_in
        assert init_if_opted_in() is False
    finally:
        if real_sentry_sdk is not None:
            sys.modules["sentry_sdk"] = real_sentry_sdk
        else:
            sys.modules.pop("sentry_sdk", None)


def test_sentry_init_exception_swallowed(tmp_compliancelint_home: Path) -> None:
    """If sentry_sdk.init itself raises (network / DSN parse / SDK bug),
    init_if_opted_in must catch it — server.py boot MUST NEVER break."""
    _write_config(
        tmp_compliancelint_home,
        {"dsn": "https://test_key@o123.ingest.de.sentry.io/456"},
    )
    with mock.patch(
        "sentry_sdk.init", side_effect=RuntimeError("simulated SDK failure")
    ):
        from scanner.core.telemetry import init_if_opted_in
        # MUST NOT raise. Returns False because init failed.
        assert init_if_opted_in() is False


# ─── Boot integration invariant ──────────────────────────────────────


def test_module_import_does_not_init(tmp_compliancelint_home: Path) -> None:
    """Importing the module must NOT auto-init Sentry. Init is explicit
    via init_if_opted_in() called from server.py — this guarantees test
    suites that import scanner.core.* don't accidentally turn on
    telemetry, and that the boot wiring is observable + reviewable."""
    _write_config(
        tmp_compliancelint_home,
        {"dsn": "https://test_key@o123.ingest.de.sentry.io/456"},
    )
    with mock.patch("sentry_sdk.init") as mock_init:
        # Force a fresh import by clearing the cached module entry.
        # We avoid importlib.reload() because it requires the module to
        # still be in sys.modules (which we want to remove to simulate
        # a fresh process boot).
        import sys
        sys.modules.pop("scanner.core.telemetry", None)
        import scanner.core.telemetry  # noqa: F401 — import-side-effect under test
        # Init must NOT have been called just by importing the module.
        assert mock_init.call_count == 0


def test_override_home_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """COMPLIANCELINT_HOME overrides ~/.compliancelint resolution.
    Critical for these tests (so we don't touch the real user home)
    AND for any deployment that wants to relocate the config dir."""
    monkeypatch.setenv("COMPLIANCELINT_HOME", str(tmp_path))
    from scanner.core.telemetry import _config_path  # noqa: PLC2701
    assert _config_path() == tmp_path / "sentry.json"


def test_no_override_uses_home_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """When COMPLIANCELINT_HOME is unset, resolve to ~/.compliancelint."""
    monkeypatch.delenv("COMPLIANCELINT_HOME", raising=False)
    from scanner.core.telemetry import _config_path  # noqa: PLC2701
    expected = Path.home() / ".compliancelint" / "sentry.json"
    assert _config_path() == expected


# ─── Phase 2: opt-in / opt-out helpers ───────────────────────────────


def test_write_dsn_config_persists_payload(tmp_compliancelint_home: Path) -> None:
    """write_dsn_config persists the SaaS response dict verbatim."""
    from scanner.core.telemetry import write_dsn_config
    payload = {
        "dsn": "https://test_key@o999.ingest.de.sentry.io/123",
        "env": "production",
        "sample_rate": 0.25,
        "send_default_pii": False,
    }
    path = write_dsn_config(payload)
    assert path.exists()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == payload


def test_write_dsn_config_creates_parent_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """write_dsn_config mkdir -p the home dir if missing.
    Critical for first-time opt-in on a fresh machine."""
    nested = tmp_path / "fresh_machine_home"
    monkeypatch.setenv("COMPLIANCELINT_HOME", str(nested))
    from scanner.core.telemetry import write_dsn_config
    write_dsn_config({"dsn": "https://x@y.ingest.de.sentry.io/1"})
    assert nested.exists()
    assert (nested / "sentry.json").exists()


def test_write_dsn_config_overwrites_existing(tmp_compliancelint_home: Path) -> None:
    """Idempotent — also used to refresh DSN after rotation."""
    _write_config(tmp_compliancelint_home, {"opted_out": True})
    from scanner.core.telemetry import write_dsn_config
    write_dsn_config({"dsn": "https://new@y.ingest.de.sentry.io/2"})
    saved = json.loads((tmp_compliancelint_home / "sentry.json").read_text())
    assert "opted_out" not in saved
    assert saved["dsn"].startswith("https://new@")


def test_delete_dsn_config_removes_file(tmp_compliancelint_home: Path) -> None:
    """delete_dsn_config removes sentry.json and reports True."""
    _write_config(tmp_compliancelint_home, {"dsn": "https://x@y.ingest.de.sentry.io/1"})
    from scanner.core.telemetry import delete_dsn_config
    assert delete_dsn_config() is True
    assert not (tmp_compliancelint_home / "sentry.json").exists()


def test_delete_dsn_config_when_missing_returns_false(tmp_compliancelint_home: Path) -> None:
    """delete_dsn_config is idempotent — no error if nothing to delete."""
    from scanner.core.telemetry import delete_dsn_config
    assert delete_dsn_config() is False


def test_is_opted_in_returns_true_with_valid_dsn(tmp_compliancelint_home: Path) -> None:
    """is_opted_in is the negation of init_if_opted_in's skip path."""
    _write_config(tmp_compliancelint_home, {"dsn": "https://x@y.ingest.de.sentry.io/1"})
    from scanner.core.telemetry import is_opted_in
    assert is_opted_in() is True


def test_is_opted_in_returns_false_when_opted_out(tmp_compliancelint_home: Path) -> None:
    """Explicit opt-out marker means is_opted_in() returns False."""
    _write_config(tmp_compliancelint_home, {"opted_out": True})
    from scanner.core.telemetry import is_opted_in
    assert is_opted_in() is False


def test_is_opted_in_returns_false_when_no_file(tmp_compliancelint_home: Path) -> None:
    """Default (no file) state."""
    from scanner.core.telemetry import is_opted_in
    assert is_opted_in() is False


# ─── fetch_dsn_from_saas: subprocess-mocked HTTP behaviour ────────────


def _mock_curl(stdout_body: str, http_status: str = "200", returncode: int = 0):
    """Helper: build a mock subprocess.run return that mimics curl
    output (body + status code on last line, per our -w flag)."""
    combined = f"{stdout_body}\n{http_status}"
    return mock.MagicMock(returncode=returncode, stdout=combined, stderr="")


def test_fetch_dsn_200_returns_parsed_payload() -> None:
    """fetch_dsn_from_saas parses 200 JSON response into dict."""
    body = json.dumps({
        "dsn": "https://k@o1.ingest.de.sentry.io/2",
        "env": "production",
        "sample_rate": 0.25,
    })
    with mock.patch("subprocess.run", return_value=_mock_curl(body, "200")):
        from scanner.core.telemetry import fetch_dsn_from_saas
        result = fetch_dsn_from_saas("https://test.saas", "cl_apikey123")
        assert result is not None
        assert result["dsn"] == "https://k@o1.ingest.de.sentry.io/2"


def test_fetch_dsn_503_returns_none() -> None:
    """SaaS host without MCP_SENTRY_DSN env var returns 503 → we return None."""
    body = json.dumps({"error": "telemetry-not-configured"})
    with mock.patch("subprocess.run", return_value=_mock_curl(body, "503")):
        from scanner.core.telemetry import fetch_dsn_from_saas
        assert fetch_dsn_from_saas("https://test.saas", "cl_apikey123") is None


def test_fetch_dsn_401_returns_none() -> None:
    """Invalid API key returns 401 → we return None (caller treats as skip)."""
    body = json.dumps({"error": "Unauthorized"})
    with mock.patch("subprocess.run", return_value=_mock_curl(body, "401")):
        from scanner.core.telemetry import fetch_dsn_from_saas
        assert fetch_dsn_from_saas("https://test.saas", "cl_bad_key") is None


def test_fetch_dsn_curl_failure_returns_none() -> None:
    """Network down / curl missing / DNS failure → curl non-zero exit
    → we return None (silent — telemetry MUST NEVER block cl_connect)."""
    with mock.patch("subprocess.run", return_value=_mock_curl("", "0", returncode=7)):
        from scanner.core.telemetry import fetch_dsn_from_saas
        assert fetch_dsn_from_saas("https://test.saas", "cl_apikey123") is None


def test_fetch_dsn_malformed_response_returns_none() -> None:
    """Server returns non-JSON despite 200 → silent skip."""
    with mock.patch("subprocess.run", return_value=_mock_curl("not json", "200")):
        from scanner.core.telemetry import fetch_dsn_from_saas
        assert fetch_dsn_from_saas("https://test.saas", "cl_apikey123") is None


def test_fetch_dsn_subprocess_exception_silent() -> None:
    """If subprocess itself raises (curl binary missing, etc.) → return None."""
    with mock.patch("subprocess.run", side_effect=FileNotFoundError("curl")):
        from scanner.core.telemetry import fetch_dsn_from_saas
        # MUST NOT raise FileNotFoundError up to cl_connect.
        assert fetch_dsn_from_saas("https://test.saas", "cl_apikey123") is None


def test_fetch_dsn_200_without_dsn_field_returns_none() -> None:
    """Defensive: 200 JSON missing the dsn field → skip (treat as invalid)."""
    body = json.dumps({"env": "production"})  # no dsn key
    with mock.patch("subprocess.run", return_value=_mock_curl(body, "200")):
        from scanner.core.telemetry import fetch_dsn_from_saas
        assert fetch_dsn_from_saas("https://test.saas", "cl_apikey123") is None


# ─── End-to-end opt-in/opt-out cycle ─────────────────────────────────


def test_opt_in_cycle_writes_then_init_succeeds(tmp_compliancelint_home: Path) -> None:
    """Full opt-in flow: fetch → write → init_if_opted_in returns True."""
    body = json.dumps({
        "dsn": "https://k@o1.ingest.de.sentry.io/2",
        "env": "production",
        "sample_rate": 0.25,
    })
    with mock.patch("subprocess.run", return_value=_mock_curl(body, "200")):
        from scanner.core.telemetry import fetch_dsn_from_saas, write_dsn_config
        payload = fetch_dsn_from_saas("https://test.saas", "cl_apikey123")
        assert payload is not None
        write_dsn_config(payload)

    with mock.patch("sentry_sdk.init") as mock_init:
        from scanner.core.telemetry import init_if_opted_in
        assert init_if_opted_in() is True
        assert mock_init.call_count == 1


def test_opt_out_cycle_deletes_then_init_skips(tmp_compliancelint_home: Path) -> None:
    """Full opt-out flow: write opt-in → delete → init_if_opted_in returns False."""
    from scanner.core.telemetry import (
        write_dsn_config,
        delete_dsn_config,
        init_if_opted_in,
    )
    write_dsn_config({"dsn": "https://k@o1.ingest.de.sentry.io/2"})
    assert delete_dsn_config() is True
    assert init_if_opted_in() is False
