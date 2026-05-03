"""Pool 4 cross-system real-flow conftest — pytest plugin (H2 hooks).

Activated for `pytest scanner/tests/pool4/` runs only. Other pytest
invocations (the existing 2700+ scanner tests) don't import this
module.

Implements the 5 pytest hooks per the plan doc:
  - pytest_configure: register custom markers
  - pytest_collection_modifyitems: server-reachable + 6-user
    seeded checks; lock acquisition
  - pytest_runtest_setup: per-cell fixture clean state assertion
  - pytest_runtest_teardown: orphaned-rows assertion
  - pytest_sessionfinish: lock release + summary

STATUS: stub. Phase 1 of the plan replaces this with real
implementation. Filename suffix `_real_flow` so this stub doesn't
override the existing `conftest.py` in scanner/tests/.

Activation: at Phase 1 start, rename to `conftest.py` AND delete the
in-process `test_smoke_runner.py` parametrize-based tests (they get
replaced by real-MCP-subprocess test files generated from cell yamls).
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.nodes import Item


# Hard constraint references from the internal Pool 4 cross-system plan doc.
PLAN_DOC = "internal pool4 cross-system plan doc 2026-05-03"
DEV_SERVER_URL_DEFAULT = "http://localhost:3000"


def pytest_configure(config: "Config") -> None:
    """Register Pool 4 custom markers."""
    config.addinivalue_line("markers", "mcp_subprocess: cell uses real MCP stdio subprocess")
    config.addinivalue_line("markers", "requires_dev_server: cell needs prod server :3000")
    config.addinivalue_line("markers", "git_required: cell exercises git commit workflow")
    config.addinivalue_line("markers", "evidence_committed: cell tests evidence pending->committed transition")


def pytest_collection_modifyitems(config: "Config", items: list["Item"]) -> None:
    """Pre-flight checks per C2 + C3 + C9.

    PHASE-1 TODO: implement
      1. Probe localhost:3000/ — skip all if unreachable, message
         users to start the prod server
      2. Acquire dev-server-3000.lock + db.lock via cl-lock.sh
      3. Verify the 6 seeded users exist in dev DB (run
         seed-pool4-users.ts if missing)
      4. Set markers on collected items based on cell yaml metadata
         (mcp_subprocess / requires_dev_server / git_required /
         evidence_committed)
    """
    # Stub: no-op until Phase 1.


def pytest_runtest_setup(item: "Item") -> None:
    """Per-cell setup per C7 + C8.

    PHASE-1 TODO: implement
      1. Resolve cell yaml from item path
      2. Build fixture project per Pattern A or Pattern B
      3. If git_required: git init the fixture, configure user
      4. Assert no leftover .compliancelint/local/ from prior cell
      5. Assert no leftover saas_url/saas_api_key in fixture rc
    """
    # Stub: no-op until Phase 1.


def pytest_runtest_teardown(item: "Item", nextitem: "Item | None") -> None:
    """Per-cell teardown per C8.

    PHASE-1 TODO: implement
      1. Strip dev-only fields from fixture .compliancelintrc
      2. Purge throwaway repo via /api/v1/repos/<id>/purge
      3. Assert no orphaned scans/findings rows for persona's user_id
      4. Reset scanner.log if applicable
    """
    # Stub: no-op until Phase 1.


def pytest_sessionfinish(session, exitstatus: int) -> None:
    """Cleanup at the end of the matrix run.

    PHASE-1 TODO:
      1. Release dev-server-3000.lock + db.lock
      2. Print summary: cells passed / SaaS tables touched / git
         commits made / total runtime
      3. Append to mailbox at
         ~/.claude/coordination/messages/from-<session>.md
    """
    # Stub: no-op until Phase 1.
