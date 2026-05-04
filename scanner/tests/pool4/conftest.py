"""Pool 4 cross-system real-flow conftest (H2 pytest plugin).

Auto-loaded by pytest only for tests collected under
``scanner/tests/pool4/``. Other pytest invocations (the existing
~2700 scanner tests under ``scanner/tests/test_art*``) don't import
this conftest.

Phase 1 scope (this file):

  - Register Pool 4 custom markers (``mcp_subprocess``,
    ``requires_dev_server``, ``requires_seeded_users``,
    ``git_required``, ``evidence_committed``)
  - Probe ``http://localhost:3000/`` once at session start, cache the
    result on ``session.config.stash``
  - Probe the dev DB for the 6 seeded users (per C3) once
  - Provide three fixtures used by every cell:
      * ``mcp_client`` (function-scoped) — fresh subprocess per test
        for hard isolation; closed in teardown
      * ``mcp_client_session`` (session-scoped) — shared subprocess
        for matrix tests that opt into amortized startup cost
      * ``persona_creds`` (function-scoped, parametrized) — the
        :class:`PersonaCreds` row matching the cell's persona
  - Skip cells gated by ``requires_dev_server`` marker when :3000 is
    unreachable, with a clear remediation message
  - Skip cells gated by ``requires_seeded_users`` marker when the dev
    DB doesn't have the 6 personas
  - At session finish: assert no committed-rc leakage (defense vs C8),
    print a one-line summary

Phase 2+ extensions documented inline (lock acquisition, per-cell
fixture-builder hooks, persona orphan-row teardown).
"""
from __future__ import annotations

import socket
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

import pytest

from .fixtures import (
    PERSONAS,
    FixtureError,
    PersonaCreds,
    assert_no_committed_dev_fields,
    manual_fixture_dir,
)
from .mcp_client import McpStdioClient
from .saas_introspection import (
    SaasIntrospectionError,
    _resolve_default_db_path,
    lookup_user_id_by_email,
    open_readonly,
)


if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.fixtures import FixtureRequest
    from _pytest.nodes import Item


DEV_SERVER_URL_DEFAULT = "http://localhost:3000"
SERVER_PROBE_TIMEOUT_SECONDS = 2.0
SEEDED_PERSONA_KEYS = ("free", "starter", "pro", "business")


# ---------------------------------------------------------------------------
# Marker registration + collection-time probes
# ---------------------------------------------------------------------------


def pytest_configure(config: "Config") -> None:
    """Register Pool 4 custom markers."""
    config.addinivalue_line(
        "markers",
        "mcp_subprocess: cell uses real MCP stdio subprocess (every "
        "Pool 4 cell — informational marker only)",
    )
    config.addinivalue_line(
        "markers",
        "requires_dev_server: cell needs prod server :3000 to be up "
        "(cl_sync / cl_connect / cl_delete + tier-A pipelines)",
    )
    config.addinivalue_line(
        "markers",
        "requires_seeded_users: cell needs the 6 seeded test users in "
        "dev DB (cross-system + most local-only mutating tools)",
    )
    config.addinivalue_line(
        "markers",
        "git_required: cell exercises real git commit inside the "
        "fixture project (evidence pending→committed transitions)",
    )
    config.addinivalue_line(
        "markers",
        "evidence_committed: cell verifies evidence_items.commit_sha "
        "is captured post-sync (subset of git_required)",
    )


# Sentinel keys on session.stash; pytest >= 7 has stash, fall back to a
# module-level dict for older versions.
_PROBE_RESULTS: dict[str, Any] = {}


def pytest_collection_modifyitems(
    config: "Config",
    items: list["Item"],
) -> None:
    """Run server + DB probes once at the start of collection.

    Results stored on ``_PROBE_RESULTS`` and inspected by
    ``pytest_runtest_setup`` to skip-or-run individual cells.

    Phase 2 will extend this with lock acquisition (dev-server-3000 +
    db locks per C9). Lock acquisition is intentionally deferred until
    the test set actually depends on :3000 — the Phase 1 cl_version
    cell doesn't, so claiming locks would block sibling sessions for
    no reason.
    """
    _PROBE_RESULTS["server_reachable"] = _probe_dev_server()
    _PROBE_RESULTS["seeded_users_present"] = _probe_seeded_users()
    _PROBE_RESULTS["item_count"] = len(items)


def _probe_dev_server() -> bool:
    """HEAD-equivalent against ``DEV_SERVER_URL_DEFAULT``. Returns
    True only when a 2xx/3xx response comes back within timeout.
    """
    try:
        req = urllib.request.Request(DEV_SERVER_URL_DEFAULT, method="GET")
        with urllib.request.urlopen(req, timeout=SERVER_PROBE_TIMEOUT_SECONDS) as resp:
            return 200 <= resp.status < 400
    except (urllib.error.URLError, socket.timeout, ConnectionRefusedError, OSError):
        return False


def _probe_seeded_users() -> bool:
    """Check all 4 core personas exist in the dev DB.

    pro_invited / business_invited are members of pro / business
    teams; their absence in this probe is acceptable for Phase 1
    (relevant only for cl_connect member-vs-owner cells in Phase 2).
    """
    db_path = _resolve_default_db_path()
    if db_path is None or not db_path.is_file():
        return False
    try:
        with open_readonly() as conn:
            for key in SEEDED_PERSONA_KEYS:
                creds = PERSONAS[key]
                if lookup_user_id_by_email(conn, creds.email) is None:
                    return False
        return True
    except SaasIntrospectionError:
        return False
    except Exception:  # pragma: no cover - best-effort probe
        return False


# ---------------------------------------------------------------------------
# Per-cell skip-or-run gates (run before the test fixture chain)
# ---------------------------------------------------------------------------


def pytest_runtest_setup(item: "Item") -> None:
    """Skip cells whose markers can't be satisfied right now."""
    if item.get_closest_marker("requires_dev_server") and not _PROBE_RESULTS.get(
        "server_reachable", False,
    ):
        pytest.skip(
            "Pool 4 cell needs the dashboard prod server at "
            f"{DEV_SERVER_URL_DEFAULT}. Start it (npm run build && "
            "PORT=3000 npm start) in another terminal, then retry."
        )
    if item.get_closest_marker("requires_seeded_users") and not _PROBE_RESULTS.get(
        "seeded_users_present", False,
    ):
        pytest.skip(
            "Pool 4 cell needs the 4 core seeded test users. Run the "
            "dashboard seed script to populate the dev DB."
        )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """End-of-run defense + one-line summary.

    Defense vs C8: if the manual-fixture rc is reachable (env var set),
    assert it has no leftover ``saas_url`` / ``saas_api_key`` — a
    builder failing in an exception path could leave them; subsequent
    commits would leak credentials. Read-only check; surfaces leaks
    via stderr but doesn't try to clean.
    """
    leak_warning: str | None = None
    fixture_dir = manual_fixture_dir()
    if fixture_dir is not None and fixture_dir.is_dir():
        rc_path = fixture_dir / ".compliancelintrc"
        try:
            assert_no_committed_dev_fields(rc_path)
        except FixtureError as e:
            leak_warning = str(e)
    summary_parts = [
        f"pool4 collected={_PROBE_RESULTS.get('item_count', '?')}",
        f"server_reachable={_PROBE_RESULTS.get('server_reachable')}",
        f"seeded_users={_PROBE_RESULTS.get('seeded_users_present')}",
    ]
    if leak_warning:
        summary_parts.append(f"DEV_FIELD_LEAK_DETECTED: {leak_warning}")
    print("\n[pool4] " + " | ".join(summary_parts))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def mcp_client() -> Any:
    """Fresh MCP subprocess per test. Closed in teardown.

    Use when the cell needs hard isolation between cells (e.g. a cell
    that mutates scanner-side state where leakage between same-process
    runs would mask bugs).
    """
    client = McpStdioClient.spawn()
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="session")
def mcp_client_session() -> Any:
    """Shared MCP subprocess for the whole pytest session.

    Use for read-only / pure-function tools (cl_version, cl_explain,
    cl_action_guide, cl_action_plan with shared fixture, etc.) where
    state leakage is impossible because the tools don't write any
    state. Saves ~0.5-1s startup per cell on Windows.
    """
    client = McpStdioClient.spawn()
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="function")
def persona_creds(request: "FixtureRequest") -> PersonaCreds:
    """Resolve the cell's persona to the matching :class:`PersonaCreds`.

    The cell's persona key is conventionally available via either
    ``request.param`` (when parametrized over personas) or the
    ``persona`` marker. Falls back to ``test-business`` for tests
    that don't declare a persona — business persona has no tier
    limits, so it's the safest default for non-tier cells.
    """
    requested: str | None = None
    param = getattr(request, "param", None)
    if isinstance(param, str):
        requested = param
    elif param is not None:
        requested = getattr(param, "key", None)
    if requested is None:
        marker = request.node.get_closest_marker("persona")
        if marker and marker.args:
            requested = marker.args[0]
    key = requested or "business"
    return PERSONAS[key]


@pytest.fixture(scope="session")
def server_reachable() -> bool:
    """Expose the cached :3000 probe result. Useful for tests that
    branch on availability rather than skipping wholesale.
    """
    return bool(_PROBE_RESULTS.get("server_reachable", False))


@pytest.fixture(scope="session")
def seeded_users_present() -> bool:
    """Expose the cached seeded-users probe result."""
    return bool(_PROBE_RESULTS.get("seeded_users_present", False))


# ---------------------------------------------------------------------------
# Server-stability helper (used by Phase 2+; harmless here)
# ---------------------------------------------------------------------------


def wait_for_server(
    url: str = DEV_SERVER_URL_DEFAULT,
    timeout: float = 30.0,
) -> bool:
    """Poll ``url`` every 0.5s until 2xx/3xx or timeout. Returns True
    on success. Phase 2's autospawn-server flow uses this after
    ``npm start`` to wait for the prod server to be ready.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if 200 <= resp.status < 400:
                    return True
        except (urllib.error.URLError, socket.timeout, OSError):
            pass
        time.sleep(0.5)
    return False
