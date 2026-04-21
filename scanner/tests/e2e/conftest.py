"""Pytest fixtures for Evidence v4 e2e suite.

These tests need a live dashboard dev server on http://localhost:3000 with
EVIDENCE_ENCRYPTION_KEY set, plus a pre-initialised git repo at
c:/tmp/cl-sub3b-e2e (with .compliancelintrc).

If either prereq is missing, every test in this directory skips with a
clear message — the suite is safe to include in the default pytest run.

Run only this suite:
    pytest scanner/tests/e2e -v
Run including these:
    pytest scanner/tests
Skip these explicitly:
    pytest scanner/tests -m "not live_dashboard"
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SCANNER_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
for _p in (HERE, SCANNER_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _e2e_consts import (  # noqa: E402  (after sys.path fix)
    API_KEY, DB_PATH, PROJECT, REPO_NAME, SAAS,
)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live_dashboard: requires dashboard at localhost:3000 + git project at "
        "c:/tmp/cl-sub3b-e2e (auto-skips if either is missing).",
    )


# ── Override parent conftest's autouse minimal_ai_context ─────────────────
# Parent fixture imports core.protocol and builds a ProjectContext on every
# test. e2e tests don't touch the article scanner, so we override with a
# no-op to skip that overhead and avoid any unintended coupling.

@pytest.fixture(autouse=True)
def minimal_ai_context():
    return None


# ── Live-env precondition (skips suite if dashboard or project missing) ───

def _server_reachable(url: str = SAAS, timeout_s: int = 3) -> bool:
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", os.devnull, "-w", "%{http_code}",
             "--max-time", str(timeout_s), url],
            capture_output=True, text=True, timeout=timeout_s + 2,
        )
        code = r.stdout.strip()
        return code.isdigit() and code != "000"
    except Exception:
        return False


def _project_ready(project: str = PROJECT) -> bool:
    p = Path(project)
    return p.is_dir() and (p / ".git").exists() and (p / ".compliancelintrc").is_file()


@pytest.fixture(scope="session", autouse=True)
def _live_env_check():
    """Confirm prereqs once per session and pre-warm the entry route.

    Next.js Turbopack JIT-compiles routes on first hit (5-10 s on cold
    start). A short-timeout reachability check races the compile and
    would falsely skip the first test. Two attempts at 15 s each gives
    the server up to 30 s; then we pre-hit `/api/v1/repos` (the route
    `discovered` fixture depends on) so the first real call is fast.
    """
    if not _project_ready():
        pytest.skip(
            f"Project dir not initialised at {PROJECT} "
            "(needs git + .compliancelintrc)"
        )
    if not _server_reachable(timeout_s=15) and not _server_reachable(timeout_s=15):
        pytest.skip(f"Dashboard dev server not reachable at {SAAS}")
    subprocess.run(
        [
            "curl", "-sS", "-o", os.devnull, "--max-time", "30",
            "-H", f"Authorization: Bearer {API_KEY}",
            f"{SAAS}/api/v1/repos",
        ],
        capture_output=True, timeout=35,
    )


# ── Module-scoped imports (after sys.path is set) ─────────────────────────

@pytest.fixture(scope="session")
def server_module():
    import server  # noqa: WPS433
    return server


# ── Runtime ID discovery (UUIDs are randomised on every re-seed) ──────────
# Per parallel-session sync 2026-04-21: scripts/seed-demo.ts uses uuid() for
# all repo / scan / finding IDs, so any hardcoded value goes stale on the
# next re-seed and surfaces as a 404 — NOT a skip. We discover them via the
# REST API at session start. Discovery failure → pytest.fail() (not skip),
# because a missing test-pro fixture is a setup bug, not an env precondition.

def _curl_json(method: str, url: str, *, timeout: int = 10):
    cmd = [
        "curl", "-sS", "-X", method, url,
        "-H", f"Authorization: Bearer {API_KEY}",
        "--max-time", str(timeout),
    ]
    r = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout + 5,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"curl {method} {url} failed (rc={r.returncode}): {r.stderr[:200]!r}"
        )
    out = r.stdout.strip()
    return json.loads(out) if out else None


@pytest.fixture(scope="session")
def discovered():
    """Discover repo_id / scan_id / finding_id via the live API.

    Returns dict with keys: repo_id, repo_name, scan_id, finding_id.
    Mirrors the Playwright-side fixture pattern from the parallel session.
    Errors specifically (not skip) so a misconfigured demo seed is loud.
    """
    repos_data = _curl_json("GET", f"{SAAS}/api/v1/repos")
    repos = repos_data if isinstance(repos_data, list) else (repos_data or {}).get("repos", [])
    repo = next(
        (x for x in repos if x.get("name") == REPO_NAME), None,
    )
    if not repo:
        names = [x.get("name") for x in repos]
        pytest.fail(
            f"discovery: no repo named {REPO_NAME!r} on {SAAS}. "
            f"Run `npx tsx scripts/seed-demo.ts` to seed test-pro fixtures. "
            f"Repos visible to test-pro API key: {names}"
        )
    repo_id = repo["id"]

    detail = _curl_json("GET", f"{SAAS}/api/v1/repos/{repo_id}") or {}
    scans = detail.get("scans") or []
    if not scans:
        pytest.fail(
            f"discovery: repo {repo_id} ({REPO_NAME}) has no scans. "
            f"seed-demo.ts should produce at least one scan. Re-seed."
        )

    # Walk scans newest-to-oldest and pick the first one that has an art09
    # finding. `scans[0]` alone is brittle — other sessions or tests may
    # have appended scans with no findings (or with a different article set)
    # which would fail discovery even when a usable scan exists elsewhere.
    checked_articles: dict[str, list[str]] = {}
    for s in scans:
        scan_id = s["id"]
        scan = _curl_json(
            "GET", f"{SAAS}/api/v1/repos/{repo_id}/scans/{scan_id}",
        ) or {}
        findings = scan.get("findings") or []
        finding = next(
            (x for x in findings if x.get("article") == "art09"), None,
        )
        if finding:
            return {
                "repo_id": repo_id,
                "repo_name": repo.get("name", REPO_NAME),
                "scan_id": scan_id,
                "finding_id": finding["id"],
            }
        checked_articles[scan_id] = sorted(
            {x.get("article") for x in findings if x.get("article")}
        )

    pytest.fail(
        f"discovery: none of {len(scans)} scan(s) on repo {repo_id} have "
        f"an art09 finding. Articles per scan: {checked_articles}. "
        f"Verify seed-demo.ts emits art09 findings for test-pro."
    )


@pytest.fixture
def log():
    return logging.getLogger("e2e_pytest")


# ── DB / file helpers exposed as fixtures ─────────────────────────────────

@pytest.fixture
def db_query():
    def _q(sql: str, params: tuple = ()) -> list[tuple]:
        conn = sqlite3.connect(DB_PATH)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()
    return _q


@pytest.fixture
def run_in_project():
    def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd, cwd=PROJECT, capture_output=True, text=True, timeout=timeout,
        )
    return _run


@pytest.fixture
def sha256_file_fn():
    def _hash(p: str) -> str:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    return _hash


@pytest.fixture
def curl_upload(run_in_project):
    """Returns f(finding_id, file_path) → JSON of upload response.

    Caller passes finding_id explicitly (use discovered['finding_id']).
    """
    def _upload(finding_id: str, file_path: str) -> dict:
        r = run_in_project([
            "curl", "-sS", "--max-time", "30", "-X", "POST",
            f"{SAAS}/api/v1/findings/{finding_id}/evidence/upload-file",
            "-H", f"Authorization: Bearer {API_KEY}",
            "-F", f"file=@{file_path}",
        ], timeout=45)
        if not r.stdout.strip():
            raise RuntimeError(
                f"upload returned empty stdout; stderr={r.stderr[:200]!r}"
            )
        return json.loads(r.stdout)
    return _upload


@pytest.fixture
def cleanup_pending(discovered):
    """Delete pending_evidence + evidence_items + finding_responses + audit
    rows scoped to the discovered repo / finding. Used at the start of tests
    that need a fresh DB state."""
    repo_id = discovered["repo_id"]
    finding_id = discovered["finding_id"]

    def _cleanup():
        conn = sqlite3.connect(DB_PATH)
        try:
            rows = conn.execute("""
                SELECT ei.id FROM evidence_items ei
                JOIN finding_responses fr ON fr.id = ei.finding_response_id
                JOIN findings f ON f.id = fr.finding_id
                JOIN scans s ON s.id = f.scan_id
                WHERE s.repo_id = ?
            """, (repo_id,)).fetchall()
            ids = [r[0] for r in rows]
            if ids:
                ph = ",".join("?" * len(ids))
                conn.execute(
                    f"DELETE FROM pending_evidence WHERE evidence_item_id IN ({ph})",
                    ids,
                )
                conn.execute(
                    f"DELETE FROM evidence_items WHERE id IN ({ph})", ids,
                )
                conn.execute(
                    "DELETE FROM finding_responses WHERE finding_id = ?",
                    (finding_id,),
                )
                conn.execute(
                    "DELETE FROM audit_logs WHERE resource LIKE 'evidence_items/%'"
                )
            conn.commit()
        finally:
            conn.close()
    return _cleanup


def _assert_safe_to_force_push(project: str) -> None:
    """Hard fail if PROJECT ever points at a real repo.

    The reset fixture runs `git reset --hard` + `git push --force origin`
    on whatever path PROJECT resolves to. If a future contributor
    accidentally repoints PROJECT at a real working tree (or someone's
    personal clone of compliancelint), force-push would silently destroy
    the remote. This guard makes the destruction impossible: the path
    must either be under the system tempdir, under c:/tmp, or contain
    "/tmp/" — all test-only conventions. The `or "tmp" in PROJECT`
    fallback exists because Windows `tempfile.gettempdir()` is typically
    `C:\\Users\\...\\AppData\\Local\\Temp` which doesn't match our
    historical test path `c:/tmp/cl-sub3b-e2e`.
    """
    tmp = tempfile.gettempdir().replace("\\", "/").lower()
    norm = project.replace("\\", "/").lower()
    if norm.startswith(tmp):
        return
    if "/tmp/" in norm or norm.startswith("/tmp/") or norm.startswith("c:/tmp/"):
        return
    raise RuntimeError(
        f"reset_working_tree refusing to force-push: PROJECT={project!r} "
        f"is not under a recognised temp dir. This fixture runs "
        f"`git push --force origin` — running it on a real repo would "
        f"destroy remote history. Point PROJECT at a dedicated test "
        f"worktree (e.g. c:/tmp/cl-sub3b-e2e) before running."
    )


@pytest.fixture
def reset_working_tree(run_in_project):
    """Remove pulled evidence files + metadata.json + git reset to root commit.

    If a remote is configured (see `with_remote` fixture), force-sync the
    remote back to the local root so subsequent tests that push start from
    a clean state. Force-push is safe here — the bare remote is a test
    fixture with no other readers, and `_assert_safe_to_force_push` hard-
    fails if PROJECT ever points outside a temp dir.
    """
    def _reset():
        _assert_safe_to_force_push(PROJECT)
        ev_dir = os.path.join(PROJECT, ".compliancelint", "evidence")
        if os.path.isdir(ev_dir):
            shutil.rmtree(ev_dir)
        meta = os.path.join(PROJECT, ".compliancelint", "metadata.json")
        if os.path.isfile(meta):
            os.unlink(meta)
        run_in_project(["git", "reset", "--hard", "HEAD"])
        log_out = run_in_project(["git", "log", "--oneline"]).stdout.strip()
        if log_out and log_out.count("\n") > 0:
            root = run_in_project(
                ["git", "rev-list", "--max-parents=0", "HEAD"]
            ).stdout.strip()
            run_in_project(["git", "reset", "--hard", root])
        if run_in_project(["git", "remote"]).stdout.strip():
            branch = run_in_project(
                ["git", "branch", "--show-current"]
            ).stdout.strip()
            if branch:
                run_in_project(["git", "push", "--force", "origin", branch])
    return _reset


@pytest.fixture(scope="session")
def with_remote():
    """Ensure the test project has an `origin` remote configured.

    Idempotent: returns early if origin already exists. Otherwise creates a
    sibling bare repo at PROJECT + '-remote.git', adds it as origin, and
    pushes the current branch so remote-tracking is established.

    Required by tests that depend on the §4.6 fix: cl_sync's get_committed_sha
    only returns a sha when `git branch -r --contains <sha>` is non-empty,
    which requires a remote that contains the commit. Session-scoped (so it
    cannot depend on function-scoped fixtures like run_in_project — uses
    bare subprocess.run with cwd=PROJECT instead).
    """
    def _git(*args):
        return subprocess.run(
            ["git", *args], cwd=PROJECT, capture_output=True, text=True, timeout=30,
        )

    if _git("remote").stdout.strip():
        return

    remote_path = PROJECT + "-remote.git"
    if not os.path.isdir(remote_path):
        subprocess.run(
            ["git", "init", "--bare", remote_path],
            check=True, capture_output=True,
        )
    _git("remote", "add", "origin", remote_path)
    branch = _git("branch", "--show-current").stdout.strip() or "master"
    _git("push", "-u", "origin", branch)


@pytest.fixture
def call_pull(server_module, log, discovered):
    repo_name = discovered["repo_name"]

    def _pull():
        return server_module._run_pending_evidence_pull(
            project_path=PROJECT,
            saas_url=SAAS,
            api_key=API_KEY,
            repo_name=repo_name,
            slog=log,
        )
    return _pull


# ── git_path evidence helpers (used by broken_link tests) ────────────────

@pytest.fixture
def seed_git_path_row(discovered):
    """Insert a finding_response + git_path evidence_items row directly under
    the discovered finding. Simulates a cl_scan_all result without running
    the full scanner pipeline. Returns evidence_item_id for inspection.
    """
    finding_id = discovered["finding_id"]

    def _seed(repo_path: str, content_sha: str = "a" * 64) -> str:
        conn = sqlite3.connect(DB_PATH)
        try:
            fr_id = str(uuid.uuid4())
            ei_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO finding_responses (id, finding_id, action, submitted_by) "
                "VALUES (?, ?, 'acknowledge', NULL)",
                (fr_id, finding_id),
            )
            conn.execute(
                "INSERT INTO evidence_items "
                "(id, finding_response_id, source, storage_kind, repo_path, "
                " content_sha256, commit_status, health_status, uploaded_at, created_at) "
                "VALUES (?, ?, 'scanner', 'git_path', ?, ?, 'committed', 'ok', "
                "       datetime('now'), datetime('now'))",
                (ei_id, fr_id, repo_path, content_sha),
            )
            conn.commit()
            return ei_id
        finally:
            conn.close()
    return _seed


@pytest.fixture
def clear_git_path_rows(discovered):
    finding_id = discovered["finding_id"]

    def _clear():
        conn = sqlite3.connect(DB_PATH)
        try:
            eids = [r[0] for r in conn.execute(
                "SELECT ei.id FROM evidence_items ei "
                "JOIN finding_responses fr ON fr.id = ei.finding_response_id "
                "WHERE fr.finding_id = ? AND ei.storage_kind = 'git_path'",
                (finding_id,),
            ).fetchall()]
            if eids:
                ph = ",".join("?" * len(eids))
                in_clause = ",".join(repr(f"evidence_items/{e}") for e in eids)
                conn.execute(
                    f"DELETE FROM audit_logs WHERE resource IN ({in_clause})"
                )
                conn.execute(
                    f"DELETE FROM evidence_items WHERE id IN ({ph})", eids,
                )
            conn.execute(
                "DELETE FROM finding_responses WHERE finding_id = ? "
                "AND submitted_by IS NULL",
                (finding_id,),
            )
            conn.commit()
        finally:
            conn.close()
    return _clear
