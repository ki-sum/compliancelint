"""Pending evidence pull helpers (Evidence v4 MVP — cl_sync sub-3b).

cl_sync's deferred path pulls encrypted evidence bytes from SaaS into the
customer's working tree, then waits for the human to `git add/commit/push`.
On the next cl_sync, it reports back the committed_at_sha for each path so
the SaaS can transition commit_status='pending_commit' → 'committed'.

Hard rules (from claude-v6-prompt-answers-and-rules.md §5):
  - MCP NEVER executes git on anyone's behalf (no auto add/commit/push/revert).
  - `git log` (read-only) is allowed.
  - Hash mismatch on fetched bytes → refuse to write, do NOT pollute repo.
  - Network failure → fail gracefully, no partial file writes (atomic rename
    only after post-write hash re-verification).
  - File conflict (target exists + different hash) → write to
    `{target}.conflict-{ISO8601Z}` and surface to human. Never overwrite.

This module is split from server.py so the file-IO / conflict-resolution /
sha-verification logic can be unit-tested without spinning up an MCP server
or hitting the network. HTTP transport lives in server.py.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional


class RepoNotFoundError(Exception):
    """Raised by injected http_get_json when a list-scoped URL returns 404.

    Signals "the repoId path component was rejected by the server", so the
    caller can invalidate a cached repo_id and re-resolve. Other HTTP
    failures (401/403/500/network) do NOT raise this — they return None.
    """


# ── Cache for SaaS repo_id (lives in .compliancelint/metadata.json) ───────────
#
# Why here and not in core/config.py: this is a SaaS-derived identifier, not
# user configuration. metadata.json is already the file for SaaS-derived
# caches (ai_provider, last_sync_at), and `repo_id` is the same convention
# `_fetch_saas_scan_settings` already expects to read. By unifying on the
# same key, adopting this cache also activates scan-settings (which was
# orphaned — no writer existed until now).
#
# Key design: per-project. Cache is invalidated on 404 from a scoped
# endpoint. If the user changes `git remote` or dashboard deletes the repo,
# the next cl_sync detects 404 and re-matches by repo_name.


_METADATA_FILE = "metadata.json"
_METADATA_DIR = ".compliancelint"


def _metadata_path(project_path: str) -> str:
    return os.path.join(project_path, _METADATA_DIR, _METADATA_FILE)


def read_cached_repo_id(project_path: str) -> Optional[str]:
    """Return the cached SaaS repo_id for this project, or None.

    Malformed metadata.json returns None (not an exception). Callers treat
    None as "no cache, list SaaS" — safe fallback either way.
    """
    path = _metadata_path(project_path)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    rid = meta.get("repo_id")
    return rid if isinstance(rid, str) and rid else None


def write_cached_repo_id(project_path: str, repo_id: str) -> None:
    """Persist SaaS repo_id into metadata.json, preserving other keys.

    Merges with existing metadata (ai_provider, last_sync_at, etc). Creates
    the directory if needed. Silent on I/O errors — a failed cache write
    must never break cl_sync.
    """
    if not repo_id:
        return
    dir_path = os.path.join(project_path, _METADATA_DIR)
    os.makedirs(dir_path, exist_ok=True)
    path = _metadata_path(project_path)
    meta: dict = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                if not isinstance(meta, dict):
                    meta = {}
        except (OSError, json.JSONDecodeError):
            meta = {}
    meta["repo_id"] = repo_id
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def clear_cached_repo_id(project_path: str) -> None:
    """Remove the repo_id key from metadata.json (on cache invalidation).

    Preserves other keys. No-op if file/key absent.
    """
    path = _metadata_path(project_path)
    if not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(meta, dict) or "repo_id" not in meta:
        return
    meta.pop("repo_id", None)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def sha256_bytes(blob: bytes) -> str:
    """sha256(plaintext) hex — matches `content_sha256` stored in SaaS."""
    return hashlib.sha256(blob).hexdigest()


def sha256_file(path: str, chunk_size: int = 65536) -> str:
    """Stream-hash a file without loading it into memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def decode_bytes_b64(payload_b64: str) -> bytes:
    """base64 decode. Raises on invalid input (caller logs + skips)."""
    return base64.b64decode(payload_b64, validate=False)


def is_valid_git_sha(sha: str) -> bool:
    """40-char lowercase hex — matches SaaS sync-confirm regex."""
    if not isinstance(sha, str) or len(sha) != 40:
        return False
    try:
        int(sha, 16)
    except ValueError:
        return False
    return sha == sha.lower()


def get_committed_sha(project_path: str, repo_path: str, timeout: float = 3.0) -> Optional[str]:
    """Return the sha of the most recent commit that touched `repo_path`, or None.

    Uses `git log -1 --pretty=format:%H -- <path>`. Read-only git operation,
    safe in MCP context. Returns None on any error (no repo, path never
    committed, git timeout, etc).
    """
    try:
        flags: dict = {
            "capture_output": True,
            "text": True,
            "cwd": project_path,
            "timeout": timeout,
            "env": {**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        }
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags["creationflags"] = subprocess.CREATE_NO_WINDOW
        r = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%H", "--", repo_path],
            **flags,
        )
        if r.returncode != 0:
            return None
        sha = r.stdout.strip()
        return sha if is_valid_git_sha(sha) else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def atomic_write_bytes(target_path: str, blob: bytes, expected_sha: str) -> None:
    """Write blob to target_path atomically, verifying hash after disk write.

    Raises RuntimeError if post-write hash does not equal `expected_sha`.
    The temp file is cleaned up on any failure; target is only touched via
    atomic rename after verification passes.
    """
    os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
    tmp_path = f"{target_path}.{os.getpid()}.{int(datetime.now(timezone.utc).timestamp() * 1000)}.tmp"
    try:
        with open(tmp_path, "wb") as f:
            f.write(blob)
        actual = sha256_file(tmp_path)
        if actual != expected_sha:
            raise RuntimeError(
                f"post-write hash mismatch (expected {expected_sha[:12]}..., got {actual[:12]}...)"
            )
        os.replace(tmp_path, target_path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


def build_conflict_path(target_path: str, now_utc: Optional[datetime] = None) -> str:
    """`foo.pdf` → `foo.pdf.conflict-20260420T153012Z`. Deterministic per timestamp."""
    ts = (now_utc or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return f"{target_path}.conflict-{ts}"


def resolve_write_destination(
    project_path: str,
    repo_path: str,
    expected_sha: str,
    now_utc: Optional[datetime] = None,
) -> tuple[str, str]:
    """Decide where to write incoming bytes and why.

    Returns (absolute_write_path, action) where action is one of:
      - "write"    — target doesn't exist, write directly
      - "skip"     — target exists + matching hash (idempotent resume)
      - "conflict" — target exists + different hash, write to .conflict-{ts}
    """
    target = os.path.join(project_path, repo_path)
    if not os.path.exists(target):
        return target, "write"
    existing_hash = sha256_file(target)
    if existing_hash == expected_sha:
        return target, "skip"
    return build_conflict_path(target, now_utc=now_utc), "conflict"


@dataclass
class PullItemResult:
    """Outcome for a single pending_evidence row."""

    pending_id: str
    repo_path: str
    status: str  # "pulled" | "skipped_same_hash" | "conflict" | "confirmed" | "error"
    sha256: str = ""
    committed_at_sha: str = ""
    conflict_path: str = ""
    error: str = ""


@dataclass
class PullSummary:
    """Aggregate outcome — serialised into cl_sync result JSON."""

    pulled: int = 0
    skipped_same_hash: int = 0
    conflicts: int = 0
    confirmed: int = 0
    errors: int = 0
    items: list[PullItemResult] = field(default_factory=list)
    pulled_paths: list[str] = field(default_factory=list)
    conflict_paths: list[str] = field(default_factory=list)

    def add(self, item: PullItemResult) -> None:
        self.items.append(item)
        if item.status == "pulled":
            self.pulled += 1
            self.pulled_paths.append(item.repo_path)
        elif item.status == "skipped_same_hash":
            self.skipped_same_hash += 1
        elif item.status == "conflict":
            self.conflicts += 1
            if item.conflict_path:
                self.conflict_paths.append(item.conflict_path)
        elif item.status == "confirmed":
            self.confirmed += 1
        elif item.status == "error":
            self.errors += 1

    def to_dict(self) -> dict:
        return {
            "pulled": self.pulled,
            "skipped_same_hash": self.skipped_same_hash,
            "conflicts": self.conflicts,
            "confirmed": self.confirmed,
            "errors": self.errors,
            "pulled_paths": self.pulled_paths,
            "conflict_paths": self.conflict_paths,
            "item_details": [
                {
                    "pending_id": it.pending_id,
                    "repo_path": it.repo_path,
                    "status": it.status,
                    **({"error": it.error} if it.error else {}),
                    **({"conflict_path": it.conflict_path} if it.conflict_path else {}),
                    **({"committed_at_sha": it.committed_at_sha} if it.committed_at_sha else {}),
                }
                for it in self.items
            ],
        }


def build_human_prompt(summary: PullSummary) -> str:
    """Human-readable guidance appended to cl_sync output.

    NEVER includes an auto-executable command we run ourselves — the human
    must run git. This is the entire point of the deferred path.
    """
    lines: list[str] = []
    if summary.pulled_paths:
        n = len(summary.pulled_paths)
        lines.append(f"{n} evidence file(s) staged for commit:")
        for p in summary.pulled_paths:
            lines.append(f"  - {p}")
        lines.append("")
        lines.append(
            "Run: git add .compliancelint/evidence && "
            'git commit -m "[ComplianceLint] Evidence sync" && git push'
        )
    if summary.conflict_paths:
        if lines:
            lines.append("")
        lines.append(
            f"{len(summary.conflict_paths)} file(s) had different content already in the repo — "
            "the incoming copy was saved alongside, NOT overwritten:"
        )
        for p in summary.conflict_paths:
            lines.append(f"  - {p}")
        lines.append(
            "Review each pair, decide which to keep, and either re-upload via the dashboard "
            "or commit the conflict copy."
        )
    if summary.confirmed:
        if lines:
            lines.append("")
        lines.append(
            f"{summary.confirmed} previously-pulled file(s) detected as committed — "
            "transition recorded on dashboard."
        )
    return "\n".join(lines)


HttpGetJson = Callable[[str], Optional[dict]]
HttpPostJson = Callable[[str, dict], Optional[dict]]


def pull_pending_evidence(
    project_path: str,
    saas_url: str,
    repo_id: str,
    http_get_json: HttpGetJson,
    http_post_json: HttpPostJson,
    get_sha_for_path: Callable[[str, str], Optional[str]] = get_committed_sha,
    logger=None,
) -> PullSummary:
    """Orchestrate the full deferred-path round-trip.

    HTTP transport is injected so unit tests can mock it. `get_sha_for_path`
    is also injected so tests can run without git. This function does all
    the conflict resolution, hash verification, and sync-confirm reporting
    but does NOT do any git writes of its own.

    Returns a PullSummary. Never raises for per-item errors — they're
    recorded in summary.errors. Only raises for programmer errors (missing
    args etc).
    """
    if not repo_id:
        raise ValueError("repo_id is required")
    if not saas_url:
        raise ValueError("saas_url is required")

    summary = PullSummary()

    def _log(level: str, msg: str) -> None:
        if logger is None:
            return
        fn = getattr(logger, level, None)
        if callable(fn):
            fn(msg)

    list_url = f"{saas_url.rstrip('/')}/api/v1/repos/{repo_id}/pending-evidence"
    try:
        listing = http_get_json(list_url)
    except RepoNotFoundError:
        # Glue layer handles cache invalidation; let it through.
        raise
    except Exception as e:
        _log("error", f"pull_pending_evidence: list endpoint failed: {e}")
        return summary

    if not listing:
        _log("info", "pull_pending_evidence: list returned empty")
        return summary

    pending = listing.get("pending") or []
    if not pending:
        _log("info", "pull_pending_evidence: no pending items")
        return summary

    # Pass 1 — partition into already-committed vs to-pull.
    # "Already committed" means: the file exists in git HEAD matching the
    # pending row's repo_path AND its on-disk hash matches expected sha.
    # We do NOT trust mere presence of the file — hash verification
    # prevents reporting a stale unrelated file as committed evidence.
    confirm_batch: list[dict] = []
    confirm_items: list[PullItemResult] = []
    pull_queue: list[dict] = []

    for row in pending:
        pending_id = row.get("id") or ""
        repo_path = row.get("repo_path") or ""
        expected_sha = row.get("sha256") or ""
        if not pending_id or not repo_path or not expected_sha:
            summary.add(PullItemResult(
                pending_id=pending_id,
                repo_path=repo_path,
                status="error",
                error="pending row missing id/repo_path/sha256",
            ))
            continue

        abs_path = os.path.join(project_path, repo_path)
        if os.path.exists(abs_path):
            try:
                on_disk_sha = sha256_file(abs_path)
            except OSError as e:
                _log("warn", f"pull: cannot hash {repo_path}: {e}")
                on_disk_sha = ""

            if on_disk_sha == expected_sha:
                committed_sha = get_sha_for_path(project_path, repo_path)
                if committed_sha and is_valid_git_sha(committed_sha):
                    confirm_batch.append({
                        "repo_path": repo_path,
                        "committed_at_sha": committed_sha,
                    })
                    confirm_items.append(PullItemResult(
                        pending_id=pending_id,
                        repo_path=repo_path,
                        status="confirmed",
                        sha256=expected_sha,
                        committed_at_sha=committed_sha,
                    ))
                    continue
                # File present + hash matches, but not yet committed.
                # Skip re-pull (idempotent resume). Human hasn't committed
                # yet; next cl_sync will detect.
                summary.add(PullItemResult(
                    pending_id=pending_id,
                    repo_path=repo_path,
                    status="skipped_same_hash",
                    sha256=expected_sha,
                ))
                continue
        pull_queue.append(row)

    # Post the confirm batch BEFORE pulling new files. If this fails, we
    # still try to pull (the worst case is the server keeps the row
    # pending for one more cycle — next sync will retry the confirm).
    if confirm_batch:
        confirm_url = f"{saas_url.rstrip('/')}/api/v1/repos/{repo_id}/sync-confirm"
        try:
            resp = http_post_json(confirm_url, {"committed_paths": confirm_batch})
            confirmed_count = (resp or {}).get("confirmed", 0) if isinstance(resp, dict) else 0
            for item in confirm_items:
                summary.add(item)
            _log("info", f"sync-confirm: {confirmed_count} confirmed, "
                         f"{(resp or {}).get('skipped', 0)} skipped")
        except Exception as e:
            _log("error", f"sync-confirm: request failed: {e}")
            for item in confirm_items:
                summary.add(PullItemResult(
                    pending_id=item.pending_id,
                    repo_path=item.repo_path,
                    status="error",
                    error=f"sync-confirm failed: {e}",
                ))

    # Pass 2 — pull bytes for remaining items.
    for row in pull_queue:
        pending_id = row["id"]
        repo_path = row["repo_path"]
        expected_sha = row["sha256"]

        payload_url = f"{saas_url.rstrip('/')}/api/v1/pending-evidence/{pending_id}"
        try:
            payload = http_get_json(payload_url)
        except Exception as e:
            summary.add(PullItemResult(
                pending_id=pending_id,
                repo_path=repo_path,
                status="error",
                error=f"fetch failed: {e}",
            ))
            continue

        if not payload or not isinstance(payload, dict):
            summary.add(PullItemResult(
                pending_id=pending_id,
                repo_path=repo_path,
                status="error",
                error="empty or non-JSON response",
            ))
            continue

        b64 = payload.get("bytes_b64")
        server_sha = payload.get("sha256") or expected_sha
        if not b64:
            summary.add(PullItemResult(
                pending_id=pending_id,
                repo_path=repo_path,
                status="error",
                error="no bytes_b64 in response",
            ))
            continue

        try:
            blob = decode_bytes_b64(b64)
        except Exception as e:
            summary.add(PullItemResult(
                pending_id=pending_id,
                repo_path=repo_path,
                status="error",
                error=f"base64 decode: {e}",
            ))
            continue

        # Verify plaintext hash BEFORE writing to disk. The server returns
        # sha256(plaintext) — a mismatch means bytes were corrupted in
        # transit OR SaaS used the wrong key OR a MITM swapped blobs.
        # In all cases: do NOT pollute the working tree.
        actual_sha = sha256_bytes(blob)
        if actual_sha != server_sha or actual_sha != expected_sha:
            summary.add(PullItemResult(
                pending_id=pending_id,
                repo_path=repo_path,
                status="error",
                error=(
                    f"hash mismatch (list sha={expected_sha[:12]}..., "
                    f"server sha={server_sha[:12]}..., "
                    f"decoded sha={actual_sha[:12]}...)"
                ),
            ))
            _log("error", f"pull: refuse to write {repo_path} — hash mismatch")
            continue

        write_path, action = resolve_write_destination(project_path, repo_path, expected_sha)

        if action == "skip":
            # Very rare: file appeared between partitioning and here.
            summary.add(PullItemResult(
                pending_id=pending_id,
                repo_path=repo_path,
                status="skipped_same_hash",
                sha256=expected_sha,
            ))
            continue

        try:
            atomic_write_bytes(write_path, blob, expected_sha)
        except Exception as e:
            summary.add(PullItemResult(
                pending_id=pending_id,
                repo_path=repo_path,
                status="error",
                error=f"write failed: {e}",
            ))
            continue

        rel_write = os.path.relpath(write_path, project_path).replace("\\", "/")
        if action == "conflict":
            summary.add(PullItemResult(
                pending_id=pending_id,
                repo_path=repo_path,
                status="conflict",
                sha256=expected_sha,
                conflict_path=rel_write,
            ))
        else:
            summary.add(PullItemResult(
                pending_id=pending_id,
                repo_path=rel_write,
                status="pulled",
                sha256=expected_sha,
            ))

    return summary
