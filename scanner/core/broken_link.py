"""Broken-link health check for git_path evidence (Evidence v4 Track 4c-2).

Scanner-side logic that runs at the end of every cl_sync loop: asks the
dashboard which `git_path` evidence rows exist for this repo, checks
whether each one's `repo_path` still resolves to a real file inside the
customer's working tree, and POSTs the results back as a batch to the
/evidence-health endpoint (contract frozen in 4d).

Hard rules observed:
  - Runs client-side only (hard rule #1: SaaS cannot access git repo);
    SaaS has no working tree to check.
  - NO auto-fix: never creates a missing file, never relocates, never
    renames, never triggers a re-scan. Only reports status.
  - Symlink that escapes the repo root is treated as broken_link
    (security: a symlink to /etc/passwd must not be reported as ok
    just because the target exists on disk).
  - Submodule uninitialized → file absent → broken_link (correct; the
    user needs to know the evidence isn't actually present).

HTTP transport is injected so unit tests run without a dashboard.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional


# ── File-existence check with security ──────────────────────────────────


def check_file_exists_secure(project_path: str, repo_path: str) -> bool:
    """Return True iff repo_path resolves to a regular file inside project_path.

    Security-focused: rejects symlinks that escape the project root.
    Rejects non-file targets (directories, special files). Handles
    relative path traversal like `../../etc/passwd` cleanly — realpath
    resolution catches them.

    The evidence_items.repo_path stored server-side is always relative
    to the project root (populated by cl_scan_all), so we always
    anchor at project_path. We do NOT honor absolute repo_path values
    even if they appear — same security concern.
    """
    if not repo_path or not isinstance(repo_path, str):
        return False

    # Reject absolute paths outright — evidence paths are repo-relative.
    # Windows check for drive letters + POSIX for leading slash.
    if os.path.isabs(repo_path):
        return False
    # Also reject paths starting with `..` — a stored repo_path should
    # never walk up out of the repo root.
    normalised = repo_path.replace("\\", "/").lstrip("/")
    if normalised.startswith("../") or normalised == "..":
        return False

    joined = os.path.join(project_path, repo_path)
    try:
        real_project = os.path.realpath(project_path)
        real_target = os.path.realpath(joined)
    except (OSError, ValueError):
        return False

    # Security: resolved target MUST remain inside the project root.
    # os.path.commonpath raises ValueError if paths are on different
    # drives (Windows) — treat that as "outside" = broken_link.
    try:
        common = os.path.commonpath([real_project, real_target])
    except ValueError:
        return False
    if common != real_project:
        return False

    # Only regular files count as "present" — directories, FIFOs, etc.
    # don't qualify as evidence artifacts.
    return os.path.isfile(real_target)


# ── Report construction ─────────────────────────────────────────────────


@dataclass
class EvidenceRow:
    """One git_path row returned from GET /api/v1/repos/{id}/evidence."""

    evidence_item_id: str
    finding_id: str
    repo_path: str
    health_status: str = "ok"          # current value server-side, for logging
    content_sha256: str = ""


@dataclass
class HealthReport:
    """One entry in the POST /evidence-health body.reports[]."""

    evidence_item_id: str
    repo_path: str
    health_status: str                 # 'ok' | 'broken_link'
    checked_at_sha: Optional[str]
    checked_at: str                    # ISO8601


@dataclass
class CheckSummary:
    """Aggregate outcome for cl_sync to surface."""

    checked: int = 0
    ok: int = 0
    broken: int = 0
    skipped_by_server: int = 0          # server said evidence_item not in repo
    errors: list[str] = field(default_factory=list)
    # Transitions observed server-side
    transitioned: int = 0
    unchanged: int = 0

    def to_dict(self) -> dict:
        return {
            "checked": self.checked,
            "ok": self.ok,
            "broken": self.broken,
            "skipped_by_server": self.skipped_by_server,
            "transitioned": self.transitioned,
            "unchanged": self.unchanged,
            "errors": self.errors,
        }


def build_reports(
    project_path: str,
    rows: list[EvidenceRow],
    checked_at_sha: Optional[str],
    checked_at: Optional[str] = None,
) -> list[HealthReport]:
    """Check file existence per row, return reports. Pure function."""
    ts = checked_at or datetime.now(timezone.utc).isoformat()
    out: list[HealthReport] = []
    for row in rows:
        exists = check_file_exists_secure(project_path, row.repo_path)
        out.append(
            HealthReport(
                evidence_item_id=row.evidence_item_id,
                repo_path=row.repo_path,
                health_status="ok" if exists else "broken_link",
                checked_at_sha=checked_at_sha,
                checked_at=ts,
            )
        )
    return out


# ── Orchestrator with injected HTTP ────────────────────────────────────


HttpGetJson = Callable[[str], Optional[dict]]
HttpPostJson = Callable[[str, dict], Optional[dict]]


def run_broken_link_check(
    project_path: str,
    saas_url: str,
    repo_id: str,
    http_get_json: HttpGetJson,
    http_post_json: HttpPostJson,
    checked_at_sha: Optional[str],
    checked_at: Optional[str] = None,
    max_pages: int = 50,
    logger=None,
) -> CheckSummary:
    """End-to-end broken_link sweep. Pure orchestration — HTTP injected.

    1. Page through GET /api/v1/repos/{repoId}/evidence?storage_kind=git_path
    2. Check file existence for each row
    3. Single batch POST to /evidence-health with all reports
    4. Return summary counting ok/broken/transitioned/unchanged

    `max_pages` is a safety ceiling; at limit=500 rows/page that's 25,000
    rows cap, far above any realistic repo.
    """
    summary = CheckSummary()

    def _log(level: str, msg: str) -> None:
        if logger is None:
            return
        fn = getattr(logger, level, None)
        if callable(fn):
            fn(msg)

    # Pass 1: page through evidence rows.
    rows: list[EvidenceRow] = []
    cursor: Optional[str] = None
    for page in range(max_pages):
        query = "storage_kind=git_path&limit=500"
        if cursor:
            query += f"&cursor={cursor}"
        url = f"{saas_url.rstrip('/')}/api/v1/repos/{repo_id}/evidence?{query}"
        try:
            payload = http_get_json(url)
        except Exception as e:
            _log("error", f"broken_link: list fetch failed page={page}: {e}")
            summary.errors.append(f"list fetch page {page}: {e}")
            break
        if not payload:
            break

        evidence_list = payload.get("evidence") or []
        for row in evidence_list:
            eid = row.get("evidence_item_id")
            fid = row.get("finding_id")
            rp = row.get("repo_path")
            if not eid or not fid or not rp:
                # Skip malformed — the server guarantees these but
                # defensive code never hurts.
                _log("warn", f"broken_link: skipping row with missing fields: {row}")
                continue
            rows.append(EvidenceRow(
                evidence_item_id=eid,
                finding_id=fid,
                repo_path=rp,
                health_status=row.get("health_status") or "ok",
                content_sha256=row.get("content_sha256") or "",
            ))
        cursor = payload.get("next_cursor")
        if not cursor:
            break

    if not rows:
        _log("info", "broken_link: no git_path evidence to check")
        return summary

    # Pass 2: file-existence check per row.
    reports = build_reports(project_path, rows, checked_at_sha, checked_at)
    summary.checked = len(reports)
    summary.ok = sum(1 for r in reports if r.health_status == "ok")
    summary.broken = sum(1 for r in reports if r.health_status == "broken_link")

    # Pass 3: batch POST reports to /evidence-health.
    if not reports:
        return summary

    confirm_url = f"{saas_url.rstrip('/')}/api/v1/repos/{repo_id}/evidence-health"
    payload = {
        "reports": [
            {
                "evidence_item_id": r.evidence_item_id,
                "repo_path": r.repo_path,
                "health_status": r.health_status,
                "checked_at_sha": r.checked_at_sha,
                "checked_at": r.checked_at,
            }
            for r in reports
        ],
    }
    try:
        resp = http_post_json(confirm_url, payload)
    except Exception as e:
        _log("error", f"broken_link: evidence-health POST failed: {e}")
        summary.errors.append(f"evidence-health POST: {e}")
        return summary

    if not isinstance(resp, dict):
        _log("warn", "broken_link: evidence-health response not a dict")
        return summary

    summary.transitioned = int(resp.get("transitioned") or 0)
    summary.unchanged = int(resp.get("unchanged") or 0)
    summary.skipped_by_server = int(resp.get("skipped") or 0)

    skipped_details = resp.get("skipped_details") or []
    for item in skipped_details:
        # Log but don't treat as error — server skips are informational
        _log("warn",
             f"broken_link: server skipped {item.get('evidence_item_id')}: "
             f"{item.get('reason')}")

    _log("info",
         f"broken_link: checked={summary.checked} ok={summary.ok} "
         f"broken={summary.broken} transitioned={summary.transitioned} "
         f"unchanged={summary.unchanged} skipped={summary.skipped_by_server}")

    return summary
