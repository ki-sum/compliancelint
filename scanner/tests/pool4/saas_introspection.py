"""SaaS introspection helpers for Pool 4 Python asserters.

Python sibling of the internal TypeScript introspection module. Same
query primitives, same schema assumptions, same audit-log ↔ user-id
JOIN discipline. Lives on the Python side because pytest cells need
to verify SaaS DB state without going through the Node toolchain.

Connection mode: read-only by default. The pool4 pytest plugin opens
the db with ``mode=ro`` URI to avoid accidental writes during
verification queries. Fixture-seeding code that legitimately needs
write access opens its own connection with ``readonly=False``.

Schema reference: the internal dashboard's drizzle schema. Critical
fact (re-verified each session): ``audit_logs.user_id`` references
``users.id`` (a string), NOT ``users.email``. Asserters that want
"did this persona produce an audit row?" MUST resolve persona email
→ users.id first, then filter audit_logs.

Path resolution: the SaaS sqlite DB is located via ``POOL4_DB_PATH``.
Public repo test runs without the env var → ``open_readonly`` raises
``SaasIntrospectionError``; conftest skips dependent cells.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH_ENV = "POOL4_DB_PATH"


def _resolve_default_db_path() -> Path | None:
    raw = os.environ.get(DB_PATH_ENV)
    if not raw:
        return None
    candidate = Path(raw).expanduser().resolve()
    return candidate


class SaasIntrospectionError(RuntimeError):
    """Raised when a query precondition fails (missing user, malformed
    DB path, etc.). Distinct from sqlite3.Error so callers can
    distinguish "fixture is wrong" from "DB is corrupt".
    """


@contextmanager
def open_readonly(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open the dashboard SQLite DB read-only.

    SQLite's URI mode (``file:...?mode=ro``) blocks any INSERT/UPDATE/
    DELETE at the kernel level. The pool4 verification path uses this
    so a buggy asserter can't accidentally mutate dev DB state mid-run.
    """
    path = db_path if db_path is not None else _resolve_default_db_path()
    if path is None:
        raise SaasIntrospectionError(
            f"open_readonly: ${DB_PATH_ENV} env var not set. "
            f"Set it to the path of the dashboard's compliancelint.db, "
            f"or pass an explicit db_path."
        )
    if not path.is_file():
        raise SaasIntrospectionError(
            f"open_readonly: dashboard DB not found at {path}. "
            f"Re-run the dashboard seed script, or update ${DB_PATH_ENV} "
            f"to the actual db location."
        )
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def lookup_user_id_by_email(
    conn: sqlite3.Connection,
    email: str,
) -> str | None:
    """Look up users.id by email. Returns None if no row matches."""
    if not email or not isinstance(email, str):
        raise SaasIntrospectionError(
            f"lookup_user_id_by_email: email must be non-empty string "
            f"(got {email!r})"
        )
    cur = conn.execute(
        "SELECT id FROM users WHERE email = ? LIMIT 1", (email,),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def require_user_id_by_email(
    conn: sqlite3.Connection,
    email: str,
) -> str:
    """Resolve email → user_id; raise if missing. Use when a missing
    fixture row should fail the test loudly (e.g. an audit-row count
    that depends on the persona existing).
    """
    user_id = lookup_user_id_by_email(conn, email)
    if not user_id:
        raise SaasIntrospectionError(
            f"require_user_id_by_email: no users row for email "
            f"{email!r} — the dashboard seed must have created this "
            f"persona before pool4 cells run. Re-run the dashboard "
            f"seed script (see internal pool4 plan doc, Phase 1)."
        )
    return user_id


@dataclass(frozen=True)
class AuditLogQuery:
    """Filter parameters for ``count_audit_logs`` and
    ``fetch_latest_audit_log``. Fields:

    - actor_email (required): persona email, resolved to user_id
    - action: exact action match (e.g. "repo_fingerprint_set")
    - detail_contains: substring match against detail JSON text
    - resource: exact resource path match (e.g. "repos/<id>")
    - created_at_min: ISO timestamp; rows older are excluded — pass
      the invoke-start time so stale rows don't pollute the count
    """

    actor_email: str
    action: str | None = None
    detail_contains: str | None = None
    resource: str | None = None
    created_at_min: str | None = None


def count_audit_logs(
    conn: sqlite3.Connection,
    query: AuditLogQuery,
) -> int:
    """Count audit_logs rows matching the query."""
    user_id = require_user_id_by_email(conn, query.actor_email)
    clauses = ["user_id = ?"]
    params: list[Any] = [user_id]
    if query.action is not None:
        clauses.append("action = ?")
        params.append(query.action)
    if query.detail_contains is not None:
        clauses.append("detail LIKE ?")
        params.append(f"%{query.detail_contains}%")
    if query.resource is not None:
        clauses.append("resource = ?")
        params.append(query.resource)
    if query.created_at_min is not None:
        clauses.append("created_at >= ?")
        params.append(query.created_at_min)
    sql = f"SELECT COUNT(*) AS c FROM audit_logs WHERE {' AND '.join(clauses)}"
    row = conn.execute(sql, params).fetchone()
    return int(row["c"])


def fetch_latest_audit_log(
    conn: sqlite3.Connection,
    query: AuditLogQuery,
) -> dict[str, Any] | None:
    """Return the latest matching audit_logs row as a dict, or None."""
    user_id = require_user_id_by_email(conn, query.actor_email)
    clauses = ["user_id = ?"]
    params: list[Any] = [user_id]
    if query.action is not None:
        clauses.append("action = ?")
        params.append(query.action)
    if query.detail_contains is not None:
        clauses.append("detail LIKE ?")
        params.append(f"%{query.detail_contains}%")
    if query.resource is not None:
        clauses.append("resource = ?")
        params.append(query.resource)
    sql = (
        "SELECT id, action, resource, detail, created_at AS createdAt "
        "FROM audit_logs "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY created_at DESC LIMIT 1"
    )
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def count_scans_for_repo(conn: sqlite3.Connection, repo_id: str) -> int:
    """Count rows in `scans` for a given repo_id."""
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM scans WHERE repo_id = ?", (repo_id,),
    ).fetchone()
    return int(row["c"])


def count_findings_for_scan(
    conn: sqlite3.Connection,
    scan_id: str,
    status: str | None = None,
) -> int:
    """Count findings rows for scan_id, optionally filtered by status."""
    if status is not None:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM findings WHERE scan_id = ? AND status = ?",
            (scan_id, status),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM findings WHERE scan_id = ?", (scan_id,),
        ).fetchone()
    return int(row["c"])


def fetch_latest_scan_for_repo(
    conn: sqlite3.Connection,
    repo_id: str,
) -> dict[str, Any] | None:
    """Latest scan row for repo, by scanned_at."""
    row = conn.execute(
        """SELECT id, scanned_at AS scannedAt, total_obligations AS totalObligations,
                  compliant_count AS compliantCount, non_compliant_count AS nonCompliantCount,
                  not_applicable_count AS notApplicableCount, overall_status AS overallStatus
           FROM scans
           WHERE repo_id = ?
           ORDER BY scanned_at DESC
           LIMIT 1""",
        (repo_id,),
    ).fetchone()
    return dict(row) if row else None


def fetch_repo_by_name(
    conn: sqlite3.Connection,
    repo_name: str,
) -> dict[str, Any] | None:
    """Look up a repo row by name. Used to resolve fixture project
    name → repo.id when no other handle is available.

    Schema note: repos.user_id (not owner_user_id) is the FK to users.id.
    Verified against current dev DB on 2026-05-04.
    """
    row = conn.execute(
        "SELECT id, name, user_id FROM repos WHERE name = ? LIMIT 1",
        (repo_name,),
    ).fetchone()
    return dict(row) if row else None


def fetch_repos_for_user(
    conn: sqlite3.Connection,
    user_id: str,
) -> list[dict[str, Any]]:
    """List all repos owned by a user. Used by cleanup paths to purge
    test-fixture repos at end of test.
    """
    rows = conn.execute(
        "SELECT id, name FROM repos WHERE user_id = ? ORDER BY created_at",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def now_iso() -> str:
    """ISO timestamp suitable for ``AuditLogQuery.created_at_min``.

    Asserters call this BEFORE invoking the MCP tool, then pass the
    result to ``count_audit_logs`` AFTER the tool returns, so the
    count covers only the invoke window.
    """
    from datetime import datetime, timezone
    return datetime.now(tz=timezone.utc).isoformat()
