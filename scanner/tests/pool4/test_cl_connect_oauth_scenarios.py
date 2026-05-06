"""Pool 4 — cl_connect device-flow OAuth scenarios.

Closes the gap left by ``test_cl_connect_round_trip.py``, which only
covers the ``already_connected`` branch (rc has a valid api_key, a
single ``GET /api/v1/auth/check`` returns the user). This file
exercises the full device-flow path:

  scanner -> webbrowser-launched curl -> ``GET /api/v1/auth/connect``
    -> dashboard inserts pending row in ``connect_tokens``
    -> [user signs in via OAuth in a real browser; here a simulator
        stand-in flips the row's api_key + email]
    -> scanner polls ``/api/v1/auth/connect/poll`` -> sees complete
    -> writes api_key to .compliancelintrc -> returns connected.

Three scenarios:

  * ``test_oauth_callback_success`` — simulator completes the row
    with a synthetic api_key + email; cl_connect returns connected
    and writes them to rc.
  * ``test_oauth_canceled`` — simulator deletes the pending row
    (mirrors user closing the browser tab); the next poll observes
    ``status: expired`` and cl_connect returns the canonical error
    envelope.
  * ``test_repo_binding_race`` — two parallel cl_connect invocations
    in distinct MCP subprocesses with distinct project paths each
    create their own pending row; the simulator completes both with
    DIFFERENT api_keys; assert each subprocess sees only its own
    api_key and the rcs don't cross-contaminate.

Per Pool 4 hard constraints:
  - C1: real MCP subprocess(es)
  - C2: live :3000 prod server (the only consumer of curl's GET +
    the source of poll responses)
  - C3: not required — cl_connect creates a fresh api_key, doesn't
    care which seeded persona owns the dashboard. We use a synthetic
    fake email/api_key string so we don't accidentally minted a real
    persona.
  - C7: tmp_path Pattern B
  - C8: per-test cleanup of any leftover connect_tokens rows;
    scanner-side rc is in tmp_path so auto-cleaned

The "browser" the scanner launches is a curl binary (resolved via
``oauth_simulator.resolve_curl_path``); curl GETs the URL and exits,
so the test doesn't pop up a real browser tab. If curl can't be
located on the host, the cells skip with a remediation message.

Verified-via: scanner/server.py:cl_connect device-flow branch + the
SaaS dashboard's auth/connect + auth/connect/poll routes + the
connect-tokens lib (DB-backed device-flow token store).
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

import pytest

from .fixtures import PERSONAS
from .mcp_client import McpStdioClient, parse_first_json
from .oauth_simulator import (
    OAuthSimulator,
    OAuthSimulatorError,
    resolve_curl_path,
)
from .saas_introspection import DB_PATH_ENV


SAAS_URL = "http://localhost:3000"
SIM_API_KEY = "cl_test_simulated_oauth_key_pool4"
SIM_EMAIL = "pool4-oauth-sim@test.invalid"


def _write_rc_no_api_key(project_dir: Path, repo_name: str) -> Path:
    """rc that has saas_url but NO saas_api_key — forces cl_connect
    onto the device-flow path. Returns the rc path."""
    rc_path = project_dir / ".compliancelintrc"
    rc_path.write_text(
        json.dumps({
            "purpose": "Pool 4 cl_connect OAuth-scenario fixture",
            "repo_name": repo_name,
            "saas_url": SAAS_URL,
            "scope": {
                "operator_role": ["provider"],
                "risk_classification": "high-risk",
            },
        }, indent=2),
        encoding="utf-8",
    )
    return rc_path


def _purge_connect_token(db_path: str, token: str) -> None:
    """Best-effort delete of a stray connect_tokens row at teardown."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "DELETE FROM connect_tokens WHERE token = ?", (token,),
            )
            conn.commit()
    except Exception:  # pragma: no cover - cleanup best-effort
        pass


def _resolve_db_path() -> Optional[str]:
    """Return the dev DB path from env or skip the test."""
    return os.environ.get(DB_PATH_ENV)


def _resolve_connect_tokens_db_path() -> Optional[str]:
    """Return the DB path that the dev server's connect-tokens lib
    actually writes to.

    Discovered drift (2026-05-06): the SaaS dashboard's connect-tokens
    module hardcodes ``path.join(process.cwd(), "data",
    "compliancelint.db")`` and does NOT honor ``DATABASE_URL``, while
    the rest of the dashboard (db/index.ts) does. The dev server is
    typically launched from a standalone build dir, so its
    ``connect_tokens`` rows go to
    ``<standalone>/data/compliancelint.db``, NOT the ``DATABASE_URL``
    DB that ``POOL4_DB_PATH`` points at.

    The drift is a real dashboard bug (the lib's docstring promises
    "same DB as the rest of the app" but the code diverges). Fixing
    it requires a dashboard rebuild + server restart, which is too
    big a blast radius for this Pool 4 cell. Tracked separately;
    this helper encodes the observed behavior:

      <repo>/<dashboard>/data/compliancelint.db
        ->  <repo>/<dashboard>/.next/standalone/data/compliancelint.db
    """
    db_url = os.environ.get("POOL4_CONNECT_TOKENS_DB_PATH")
    if db_url:
        return db_url
    base = _resolve_db_path()
    if not base:
        return None
    base_path = Path(base)
    if base_path.parent.name == "data":
        candidate = (
            base_path.parent.parent / ".next" / "standalone" / "data"
            / base_path.name
        )
        if candidate.is_file():
            return str(candidate)
    return base


def _resolve_browser_env() -> dict[str, str]:
    """Build the env-var override dict for McpStdioClient.spawn so the
    scanner's ``webbrowser.open(connect_url)`` call spawns a curl that
    GETs the URL silently instead of popping a real browser tab.
    """
    curl = resolve_curl_path()
    if not curl:
        pytest.skip("curl binary not found — required to stand in for the browser")
    return {"BROWSER": curl}


@pytest.mark.requires_dev_server
def test_oauth_callback_success(
    tmp_path: Path,
    server_reachable: bool,
) -> None:
    """End-to-end: simulator completes the pending row -> scanner
    poll returns complete -> cl_connect writes api_key/email to rc
    and returns ``status: connected``."""
    if not server_reachable:
        pytest.skip("server :3000 not ready")

    db_path = _resolve_connect_tokens_db_path()
    if not db_path:
        pytest.skip(f"{DB_PATH_ENV} not set or connect_tokens DB unresolvable")

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    suffix = str(int(time.time() * 1000) % 1_000_000_000)
    rc_path = _write_rc_no_api_key(
        project_dir, repo_name=f"test/pool4-oauth-success-{suffix}",
    )

    simulator = OAuthSimulator(db_path)

    seen_token: dict[str, Any] = {}
    sim_error: dict[str, Any] = {}

    def run_simulator() -> None:
        try:
            token = simulator.wait_for_pending_token(timeout=20.0)
            seen_token["t"] = token
            simulator.complete(token, SIM_API_KEY, SIM_EMAIL)
        except OAuthSimulatorError as e:  # pragma: no cover - surfaced via assert
            sim_error["e"] = str(e)

    sim_thread = threading.Thread(target=run_simulator, daemon=True)
    sim_thread.start()

    response: dict[str, Any] = {}
    client = McpStdioClient.spawn(env=_resolve_browser_env())
    try:
        raw = client.call_tool("cl_connect", {
            "project_path": str(project_dir),
        }, timeout=120.0)
        response = parse_first_json(raw)
    finally:
        client.close()

    sim_thread.join(timeout=10.0)
    if sim_error:
        pytest.fail(f"OAuth simulator: {sim_error['e']}")
    assert "t" in seen_token, (
        "simulator never observed a pending connect_tokens row — "
        "did the scanner's webbrowser-launched curl fail to GET "
        "/api/v1/auth/connect? Check that BROWSER env was inherited "
        "into the subprocess."
    )

    try:
        assert "error" not in response, (
            f"cl_connect returned error envelope: {response}"
        )
        assert response.get("status") == "connected", (
            f"cl_connect should return status='connected'; got "
            f"status={response.get('status')!r}, full keys="
            f"{list(response.keys())}"
        )
        assert response.get("email") == SIM_EMAIL, (
            f"cl_connect email mismatch: expected {SIM_EMAIL!r}, "
            f"got {response.get('email')!r}"
        )

        # Layer 3: api_key + email persisted to rc.
        rc_data = json.loads(rc_path.read_text(encoding="utf-8"))
        assert rc_data.get("saas_api_key") == SIM_API_KEY, (
            f"rc did not pick up the simulated api_key; "
            f"saas_api_key in rc={rc_data.get('saas_api_key')!r}"
        )
        # cl_connect pre-populates attester_email from OAuth email.
        assert rc_data.get("attester_email") == SIM_EMAIL, (
            f"rc.attester_email should have been pre-populated from "
            f"OAuth email; got {rc_data.get('attester_email')!r}"
        )
    finally:
        _purge_connect_token(db_path, seen_token.get("t", ""))


@pytest.mark.requires_dev_server
def test_oauth_canceled(
    tmp_path: Path,
    server_reachable: bool,
) -> None:
    """User closes the browser without finishing OAuth → simulator
    deletes the pending row → poll returns ``status: expired`` →
    cl_connect returns the ``Connect token expired`` error envelope.
    """
    if not server_reachable:
        pytest.skip("server :3000 not ready")

    db_path = _resolve_connect_tokens_db_path()
    if not db_path:
        pytest.skip(f"{DB_PATH_ENV} not set or connect_tokens DB unresolvable")

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    suffix = str(int(time.time() * 1000) % 1_000_000_000)
    rc_path = _write_rc_no_api_key(
        project_dir, repo_name=f"test/pool4-oauth-cancel-{suffix}",
    )
    rc_bytes_before = rc_path.read_bytes()

    simulator = OAuthSimulator(db_path)
    seen_token: dict[str, Any] = {}
    sim_error: dict[str, Any] = {}

    def run_simulator() -> None:
        try:
            token = simulator.wait_for_pending_token(timeout=20.0)
            seen_token["t"] = token
            simulator.cancel(token)
        except OAuthSimulatorError as e:  # pragma: no cover - assert below
            sim_error["e"] = str(e)

    sim_thread = threading.Thread(target=run_simulator, daemon=True)
    sim_thread.start()

    response: dict[str, Any] = {}
    client = McpStdioClient.spawn(env=_resolve_browser_env())
    try:
        raw = client.call_tool("cl_connect", {
            "project_path": str(project_dir),
        }, timeout=120.0)
        response = parse_first_json(raw)
    finally:
        client.close()

    sim_thread.join(timeout=10.0)
    if sim_error:
        pytest.fail(f"OAuth simulator: {sim_error['e']}")

    try:
        assert "error" in response, (
            f"cl_connect after a canceled OAuth should return an "
            f"error envelope; got {response}"
        )
        # The scanner code returns the canonical "Connect token
        # expired" error. Also accept "Timed out waiting for
        # authentication" as a tolerable alternate, because if the
        # simulator's DELETE happens AFTER the scanner's first poll
        # but before the next poll, the scanner sees pending forever
        # until the 90s timeout. The 20s simulator timeout makes the
        # expired path overwhelmingly likely; document the alt path
        # so a flake isn't misread as a feature regression.
        err = response.get("error", "")
        assert "expired" in err.lower() or "timed out" in err.lower(), (
            f"cl_connect canceled scenario should mention 'expired' "
            f"or 'timed out'; got error={err!r}"
        )

        # rc must not have been written (no api_key was minted).
        assert rc_path.read_bytes() == rc_bytes_before, (
            "cl_connect canceled-flow must not mutate rc — but rc "
            "bytes drifted post-call. Did cl_connect persist a "
            "partial api_key after the expired response?"
        )
    finally:
        _purge_connect_token(db_path, seen_token.get("t", ""))


@pytest.mark.requires_dev_server
def test_repo_binding_race(
    tmp_path: Path,
    server_reachable: bool,
) -> None:
    """Two cl_connect invocations in parallel (different MCP subprocesses,
    different project paths) each create their own pending row. The
    simulator completes BOTH with DIFFERENT api_keys. Assert each
    invocation reads only its own api_key — no cross-contamination
    via shared connect_tokens rows / cookie state / etc.

    This is the audit pin for the dashboard's per-token isolation:
    INSERT OR REPLACE on the ``token`` PRIMARY KEY guarantees no two
    sessions can collide as long as scanner-side uuid generation is
    unique. If a future refactor introduces a shared-state bug
    (e.g. globally-cached token/in-flight key), this cell goes RED.
    """
    if not server_reachable:
        pytest.skip("server :3000 not ready")

    db_path = _resolve_connect_tokens_db_path()
    if not db_path:
        pytest.skip(f"{DB_PATH_ENV} not set or connect_tokens DB unresolvable")

    suffix = str(int(time.time() * 1000) % 1_000_000_000)

    proj_a = tmp_path / "project-a"
    proj_b = tmp_path / "project-b"
    proj_a.mkdir()
    proj_b.mkdir()
    rc_a = _write_rc_no_api_key(proj_a, f"test/pool4-oauth-race-a-{suffix}")
    rc_b = _write_rc_no_api_key(proj_b, f"test/pool4-oauth-race-b-{suffix}")

    api_key_a = f"{SIM_API_KEY}_RACE_A_{suffix}"
    api_key_b = f"{SIM_API_KEY}_RACE_B_{suffix}"
    email_a = f"pool4-race-a-{suffix}@test.invalid"
    email_b = f"pool4-race-b-{suffix}@test.invalid"

    simulator = OAuthSimulator(db_path)
    sim_state: dict[str, Any] = {}
    sim_error: dict[str, Any] = {}

    def run_simulator() -> None:
        try:
            tokens = simulator.wait_for_n_pending_tokens(2, timeout=25.0)
            sim_state["tokens"] = tokens
            # Pair tokens to invocations by created_at order isn't
            # reliable (proj_a may not lock first). Instead: complete
            # one with key A and the other with key B; the test
            # below maps each subprocess's response back via the
            # api_key it received.
            simulator.complete(tokens[0], api_key_a, email_a)
            simulator.complete(tokens[1], api_key_b, email_b)
        except OAuthSimulatorError as e:  # pragma: no cover - assert below
            sim_error["e"] = str(e)

    sim_thread = threading.Thread(target=run_simulator, daemon=True)
    sim_thread.start()

    # Two cl_connects in parallel via two MCP subprocesses, each in
    # its own thread so call_tool's blocking wait doesn't serialize.
    response_a: dict[str, Any] = {}
    response_b: dict[str, Any] = {}
    err_a: dict[str, Any] = {}
    err_b: dict[str, Any] = {}

    def run_connect(
        project_dir: Path,
        out: dict[str, Any],
        err: dict[str, Any],
    ) -> None:
        try:
            client = McpStdioClient.spawn(env=_resolve_browser_env())
            try:
                raw = client.call_tool("cl_connect", {
                    "project_path": str(project_dir),
                }, timeout=120.0)
                out.update(parse_first_json(raw))
            finally:
                client.close()
        except Exception as e:  # pragma: no cover - surfaced below
            err["e"] = str(e)

    t_a = threading.Thread(target=run_connect, args=(proj_a, response_a, err_a))
    t_b = threading.Thread(target=run_connect, args=(proj_b, response_b, err_b))
    t_a.start()
    t_b.start()
    t_a.join(timeout=120.0)
    t_b.join(timeout=120.0)

    sim_thread.join(timeout=10.0)
    tokens = sim_state.get("tokens", [])

    try:
        if err_a:
            pytest.fail(f"cl_connect A subprocess error: {err_a['e']}")
        if err_b:
            pytest.fail(f"cl_connect B subprocess error: {err_b['e']}")
        if sim_error:
            pytest.fail(f"OAuth simulator: {sim_error['e']}")

        for label, resp in (("A", response_a), ("B", response_b)):
            assert "error" not in resp, (
                f"cl_connect {label} returned error envelope: {resp}"
            )
            assert resp.get("status") == "connected", (
                f"cl_connect {label} should return status='connected'; "
                f"got {resp}"
            )

        # Crucial: each subprocess saw exactly one of the two
        # simulator-minted api keys, and the two subprocesses got
        # DIFFERENT keys. If both saw the same key the race produced
        # cross-contamination.
        rc_data_a = json.loads(rc_a.read_text(encoding="utf-8"))
        rc_data_b = json.loads(rc_b.read_text(encoding="utf-8"))
        key_a_observed = rc_data_a.get("saas_api_key", "")
        key_b_observed = rc_data_b.get("saas_api_key", "")

        assert key_a_observed in (api_key_a, api_key_b), (
            f"rc_a.saas_api_key={key_a_observed!r} not in "
            f"{{api_key_a, api_key_b}} — simulator never set this row"
        )
        assert key_b_observed in (api_key_a, api_key_b), (
            f"rc_b.saas_api_key={key_b_observed!r} not in "
            f"{{api_key_a, api_key_b}} — simulator never set this row"
        )
        assert key_a_observed != key_b_observed, (
            f"BOTH subprocesses received the same api_key — "
            f"connect_tokens isolation is broken. "
            f"key_a={key_a_observed!r} key_b={key_b_observed!r}"
        )

        # The OAuth email must match the api_key's pair as the
        # simulator set them together.
        expected_pair = {
            api_key_a: email_a,
            api_key_b: email_b,
        }
        assert rc_data_a.get("attester_email") == expected_pair[key_a_observed], (
            f"rc_a attester_email pair mismatch: api_key={key_a_observed!r} "
            f"-> expected email={expected_pair[key_a_observed]!r}, got "
            f"{rc_data_a.get('attester_email')!r}"
        )
        assert rc_data_b.get("attester_email") == expected_pair[key_b_observed], (
            f"rc_b attester_email pair mismatch: api_key={key_b_observed!r} "
            f"-> expected email={expected_pair[key_b_observed]!r}, got "
            f"{rc_data_b.get('attester_email')!r}"
        )
    finally:
        for tok in tokens:
            _purge_connect_token(db_path, tok)
