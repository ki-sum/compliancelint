"""Pool 4 fixture project builders — Patterns A and B.

Pattern A — reuse the canonical manual fixture (provider × high-risk
× Annex III §5) used by the manual snapshot pipeline. Tests overlay
a transient ``.compliancelintrc`` with ``saas_url`` + ``saas_api_key``
for the duration of the cell, then strip them before commit (per C8
cleanup discipline). Path comes from ``POOL4_MANUAL_FIXTURE_DIR``.

Pattern B — scenario-specific: each cell that needs a different scope
shape (GPAI, distributor, prohibited-system, empty repo, etc.) gets
its own subdir under ``POOL4_SCENARIO_FIXTURES_DIR/<scenario>/``.
Builders here create the dir + minimal files on first use; the
fixture tree owns the long-lived seed.

Why builders instead of static fixture dirs:

- Cell yaml stays language-neutral (no dir paths embedded)
- Pattern A's saas_url overlay is per-cell (repo_name varies by
  scenario, e.g. "test-business/cl_sync_happy" vs
  "test-business/cl_sync_repo_limit")
- Pattern B fixtures may need framework files (Next.js page, Django
  settings.py, etc.) the builder generates deterministically from
  the scenario string — keeps the on-disk fixture tree small

Cleanup is the caller's responsibility (the ``conftest.py`` plugin
owns the symmetric cleanup: post-test rc strip + throwaway dir
removal). These builders are setup-only.
"""
from __future__ import annotations

import json
import os
import shutil
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[3]
MANUAL_FIXTURE_DIR_ENV = "POOL4_MANUAL_FIXTURE_DIR"
SCENARIO_FIXTURES_DIR_ENV = "POOL4_SCENARIO_FIXTURES_DIR"
DEFAULT_SAAS_URL = "http://localhost:3000"


def _resolve_dir(env_var: str) -> Path | None:
    raw = os.environ.get(env_var)
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def manual_fixture_dir() -> Path | None:
    """Resolve the canonical manual-fixture dir from env. None if unset."""
    return _resolve_dir(MANUAL_FIXTURE_DIR_ENV)


def scenario_fixtures_root() -> Path | None:
    """Resolve the scenario-fixtures parent dir from env. None if unset."""
    return _resolve_dir(SCENARIO_FIXTURES_DIR_ENV)


@dataclass(frozen=True)
class PersonaCreds:
    """Resolved persona row used for fixture overlays. Populated by
    the conftest plugin after asserting the persona exists in the dev
    DB. Cells reference these by ``$persona.email`` etc. — fixture
    builder injects them into ``.compliancelintrc`` writes.
    """

    key: str
    email: str
    api_key: str
    session_token: str


PERSONAS: dict[str, PersonaCreds] = {
    "free": PersonaCreds(
        key="free",
        email="test-free@compliancelint.dev",
        api_key="cl_test_free_key_for_development",
        session_token="cls_free_session_for_testing",
    ),
    "starter": PersonaCreds(
        key="starter",
        email="test-starter@compliancelint.dev",
        api_key="cl_test_starter_key_for_development",
        session_token="cls_starter_session_for_testing",
    ),
    "pro": PersonaCreds(
        key="pro",
        email="test-pro@compliancelint.dev",
        api_key="cl_test_pro_key_for_development",
        session_token="cls_pro_session_for_testing",
    ),
    "business": PersonaCreds(
        key="business",
        email="test-business@compliancelint.dev",
        api_key="cl_test_business_key_for_development",
        session_token="cls_business_session_for_testing",
    ),
    "pro_invited": PersonaCreds(
        key="pro_invited",
        email="test-pro-invited@compliancelint.dev",
        api_key="cl_test_pro_invited_key_for_development",
        session_token="cls_pro_invited_session_for_testing",
    ),
    "business_invited": PersonaCreds(
        key="business_invited",
        email="test-business-invited@compliancelint.dev",
        api_key="cl_test_business_invited_key_for_development",
        session_token="cls_business_invited_session_for_testing",
    ),
}


@dataclass
class FixtureHandle:
    """What a builder returns. The cell runner reads ``project_path``
    when resolving ``$pytest.tmp_path``; ``cleanup_callbacks`` runs
    post-test (rc strip + dir removal as appropriate).
    """

    project_path: Path
    repo_name: str
    pattern: str  # "A" or "B"
    cleanup_callbacks: list[Any] = field(default_factory=list)


class FixtureError(RuntimeError):
    """Builder precondition failure (missing manual-fixture dir, bad
    scenario name, etc.). Distinct from the cell schema validator's
    errors so the conftest plugin can label them differently in the
    skip / fail decision.
    """


def get_persona(persona_key: str) -> PersonaCreds:
    """Resolve persona key → creds. Raises ``FixtureError`` for
    unknown keys (cells with malformed persona shouldn't pass the
    cell loader, but raise loudly here as a defense-in-depth).
    """
    creds = PERSONAS.get(persona_key)
    if creds is None:
        raise FixtureError(
            f"get_persona: unknown persona key {persona_key!r}. "
            f"Valid: {sorted(PERSONAS.keys())}"
        )
    return creds


@contextmanager
def pattern_a(
    persona_key: str,
    *,
    repo_name_override: str | None = None,
    saas_url: str = DEFAULT_SAAS_URL,
    extra_rc_fields: dict[str, Any] | None = None,
) -> Iterator[FixtureHandle]:
    """Use the canonical manual fixture with a transient saas overlay.

    On enter:
      1. Resolves the fixture dir from ``POOL4_MANUAL_FIXTURE_DIR``;
         verifies it + its .compliancelintrc exist.
      2. Snapshots the original rc bytes.
      3. Writes a new rc with ``saas_url`` + ``saas_api_key`` +
         (optional) ``repo_name`` override + caller-supplied extras
         merged on top of the original.

    On exit:
      Restores the original rc bytes verbatim. Asserts the post-test
      rc has no ``saas_url`` / ``saas_api_key`` (defense-in-depth
      against partial writes).

    Why context-manager: guarantees the rc is restored even if the
    test raises. Per C8 the committed rc must never carry dev fields.
    """
    fixture_dir = manual_fixture_dir()
    if fixture_dir is None or not fixture_dir.is_dir():
        raise FixtureError(
            f"pattern_a: ${MANUAL_FIXTURE_DIR_ENV} env var unset or path "
            f"missing. Pool 4 cross-system cells require an internal "
            f"fixture dir; set ${MANUAL_FIXTURE_DIR_ENV} to its location."
        )
    rc_path = fixture_dir / ".compliancelintrc"
    if not rc_path.is_file():
        raise FixtureError(
            f"pattern_a: rc file missing at {rc_path}. The fixture dir "
            f"is corrupt — restore from the canonical seed."
        )
    original_bytes = rc_path.read_bytes()
    original = json.loads(original_bytes.decode("utf-8"))

    creds = get_persona(persona_key)
    overlay = dict(original)
    overlay["saas_url"] = saas_url
    overlay["saas_api_key"] = creds.api_key
    if repo_name_override is not None:
        overlay["repo_name"] = repo_name_override
    if extra_rc_fields:
        overlay.update(extra_rc_fields)

    rc_path.write_text(json.dumps(overlay, indent=2) + "\n", encoding="utf-8")

    handle = FixtureHandle(
        project_path=fixture_dir,
        repo_name=overlay.get("repo_name", original.get("repo_name", "")),
        pattern="A",
    )
    try:
        yield handle
    finally:
        rc_path.write_bytes(original_bytes)
        verify = json.loads(rc_path.read_text(encoding="utf-8"))
        if "saas_url" in verify or "saas_api_key" in verify:
            raise FixtureError(
                f"pattern_a cleanup: rc still contains dev fields after "
                f"restore — committed bytes drifted? rc={verify}"
            )


def pattern_b_path(scenario: str) -> Path:
    """Path for a Pattern-B scenario fixture. Does NOT create."""
    if not scenario or "/" in scenario or scenario.startswith("."):
        raise FixtureError(
            f"pattern_b_path: invalid scenario {scenario!r} — must be "
            f"a non-empty single-segment slug"
        )
    root = scenario_fixtures_root()
    if root is None:
        raise FixtureError(
            f"pattern_b_path: ${SCENARIO_FIXTURES_DIR_ENV} env var unset. "
            f"Set it to the parent dir for scenario-specific fixtures."
        )
    return root / scenario


def ensure_pattern_b(
    scenario: str,
    *,
    rc_scope: dict[str, Any],
    persona_key: str,
    repo_name: str,
    extra_files: dict[str, str] | None = None,
    saas_url: str = DEFAULT_SAAS_URL,
) -> FixtureHandle:
    """Create or reuse a Pattern-B scenario fixture.

    Idempotent: if the dir already exists with a matching rc, returns
    a handle without touching it. Otherwise creates the dir, writes
    ``.compliancelintrc`` with the scope + saas overlay, and writes
    any ``extra_files`` (path → content) the scenario needs (e.g.
    ``src/biometric_identify.py`` for high-risk-detection cells).

    Cleanup is NOT automatic — Pattern B fixtures are intended to be
    long-lived for repeat scenarios. Use ``cleanup_pattern_b`` to
    remove a throwaway scenario manually.
    """
    creds = get_persona(persona_key)
    fixture_dir = pattern_b_path(scenario)
    fixture_dir.mkdir(parents=True, exist_ok=True)

    rc = dict(rc_scope)
    rc["repo_name"] = repo_name
    rc["saas_url"] = saas_url
    rc["saas_api_key"] = creds.api_key
    rc_path = fixture_dir / ".compliancelintrc"
    rc_path.write_text(json.dumps(rc, indent=2) + "\n", encoding="utf-8")

    if extra_files:
        for relpath, content in extra_files.items():
            target = fixture_dir / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    return FixtureHandle(
        project_path=fixture_dir,
        repo_name=repo_name,
        pattern="B",
    )


def cleanup_pattern_b(scenario: str) -> None:
    """Remove a throwaway Pattern-B fixture dir. Caller chooses when
    to call (typically post-cell or post-session for short-lived scenarios)."""
    fixture_dir = pattern_b_path(scenario)
    if fixture_dir.is_dir():
        shutil.rmtree(fixture_dir)


def assert_no_committed_dev_fields(rc_path: Path) -> None:
    """Defense-in-depth check used by the conftest plugin's
    ``pytest_sessionfinish``: verify no fixture rc on disk carries
    ``saas_url`` / ``saas_api_key`` after the run completed. Catches
    a builder that forgot to restore in an exception path.
    """
    if not rc_path.is_file():
        return
    try:
        rc = json.loads(rc_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    leaks = [k for k in ("saas_url", "saas_api_key") if k in rc]
    if leaks:
        raise FixtureError(
            f"assert_no_committed_dev_fields: {rc_path} contains "
            f"{leaks} — a builder failed to restore. Strip manually "
            f"before commit."
        )


def _is_truthy_env(name: str) -> bool:
    """Helper for env-flag-driven branches (e.g. autospawn server)."""
    val = os.environ.get(name, "").strip().lower()
    return val in {"1", "true", "yes", "on"}
