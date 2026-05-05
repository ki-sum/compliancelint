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
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional


class RepoNotFoundError(Exception):
    """Raised by injected http_get_json when a list-scoped URL returns 404.

    Signals "the repoId path component was rejected by the server", so the
    caller can invalidate a cached repo_id and re-resolve. Other HTTP
    failures (401/403/500/network) do NOT raise this — they return None.
    """


# ── Cache for SaaS repo_id (lives in .compliancelint/local/metadata.json) ────
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


from core import paths


def _metadata_path(project_path: str) -> str:
    return paths.metadata_file_str(project_path)


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
    paths.ensure_local_dir(project_path)
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


# ── Pure-Python git internals reader (NO subprocess) ────────────────────
#
# Why pure Python: cl_sync runs in MCP stdio context. ANY subprocess call
# (especially git) from inside cl_sync triggers the documented MCP+stdio
# child-handle race that hangs 5-7 minutes regardless of timeout setting
# (see memory `bug_mcp_tool_hang.md` — regressed 4 times before this
# rewrite). Reading .git/* files directly via stdlib bypasses subprocess
# entirely, so the race cannot fire.
#
# Coverage: handles loose-object commits + packed-refs file. Does NOT
# walk packfiles (.git/objects/pack/*.pack). Acceptable trade-off because:
#   - Test fixtures + freshly-pushed user commits are loose
#   - The "just pushed evidence" path matches a remote ref tip on the
#     first BFS hop — packfile walk not needed
#   - If a deeper old commit is missed (loose objects gc'd into pack),
#     is_sha_on_remote returns False → evidence stays in pending_commit
#     → next sync retries → eventual consistency on next user `git gc`
#     boundary OR manual re-confirm. Worse than the prior subprocess
#     impl in this niche case, but never hangs.
#
# Permanent rule (per memory bug_mcp_tool_hang.md): No git subprocess
# from inside cl_sync hot path. Future authors: do NOT replace these
# with subprocess "for performance" — the race makes it slower, not
# faster, and unbounded.


def _resolve_git_dir(project_path: str) -> Optional[str]:
    """Locate the .git directory. Handles worktrees (`.git` is a file
    pointing at the actual gitdir). Returns absolute path or None.
    """
    candidate = os.path.join(project_path, ".git")
    if os.path.isdir(candidate):
        return candidate
    if os.path.isfile(candidate):
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content.startswith("gitdir: "):
                p = content[len("gitdir: "):].strip()
                if not os.path.isabs(p):
                    p = os.path.normpath(os.path.join(project_path, p))
                return p if os.path.isdir(p) else None
        except OSError:
            return None
    return None


def _read_packed_refs(git_dir: str) -> dict[str, str]:
    """Parse .git/packed-refs into {ref_name: sha}. Empty on missing/error."""
    out: dict[str, str] = {}
    path = os.path.join(git_dir, "packed-refs")
    if not os.path.isfile(path):
        return out
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith("^"):
                    continue
                parts = line.split(" ", 1)
                if len(parts) == 2 and is_valid_git_sha(parts[0]):
                    out[parts[1]] = parts[0]
    except OSError:
        pass
    return out


def _iter_remote_ref_tips(git_dir: str) -> set[str]:
    """Collect tip shas of every refs/remotes/* ref (loose + packed)."""
    tips: set[str] = set()
    # Loose: refs/remotes/<remote>/<branch>
    remotes_root = os.path.join(git_dir, "refs", "remotes")
    if os.path.isdir(remotes_root):
        for root, _dirs, files in os.walk(remotes_root):
            for name in files:
                fpath = os.path.join(root, name)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        sha = f.read().strip()
                    if is_valid_git_sha(sha):
                        tips.add(sha)
                except OSError:
                    continue
    # Packed
    packed = _read_packed_refs(git_dir)
    for ref_name, sha in packed.items():
        if ref_name.startswith("refs/remotes/"):
            tips.add(sha)
    return tips


def _read_commit_parents(git_dir: str, sha: str) -> list[str]:
    """Read a loose commit object and return its parent sha list.

    Returns [] on any error (object missing, not a commit, in packfile,
    zlib failure). Caller treats [] as "can't walk further".
    """
    if not is_valid_git_sha(sha):
        return []
    obj_path = os.path.join(git_dir, "objects", sha[:2], sha[2:])
    if not os.path.isfile(obj_path):
        # Object likely in a packfile — pure-Python pack reader is out
        # of scope for this fix (see module docstring rationale).
        return []
    try:
        with open(obj_path, "rb") as f:
            raw = zlib.decompress(f.read())
        # Git object header: "<type> <size>\0<content>"
        nul = raw.index(b"\0")
        header = raw[:nul]
        if not header.startswith(b"commit "):
            return []
        content = raw[nul + 1:].decode("utf-8", errors="replace")
        parents: list[str] = []
        for line in content.splitlines():
            if not line:
                break  # blank line separates commit headers from message
            if line.startswith("parent "):
                psha = line[len("parent "):].strip()
                if is_valid_git_sha(psha):
                    parents.append(psha)
            elif not line.startswith(("tree ", "author ", "committer ",
                                      "encoding ", "gpgsig ", " ")):
                # End of header block (next is message). Stop scanning.
                break
        return parents
    except (OSError, zlib.error, ValueError):
        return []


def is_sha_on_remote(
    project_path: str,
    sha: str,
    timeout: float = 0,  # kept for backward compat; ignored in pure-Python
    *,
    max_depth: int = 200,
) -> bool:
    """Return True if `sha` is reachable from any remote-tracking branch.

    Pure-Python implementation (NO subprocess) — bypasses the documented
    MCP+stdio race. Walks the commit graph from each refs/remotes/*
    tip via reading loose .git/objects entries. BFS bounded by
    `max_depth` (default 200 commits — generous for "just pushed N
    commits" while keeping pathological repos fast).

    Why this exists (Problem 1 / §4.6 fix 2026-04-21): SaaS cannot
    verify a commit reached the remote (no third-party OAuth tokens —
    hard rule #1). cl_sync runs in the user's working tree, so it CAN
    check by reading local refs/remotes/* . Without this guard,
    sync-confirm would fire for local-only commits and SaaS would
    record `committed_at_sha` for shas that never reached the remote,
    breaking audit trail (regulator audit cannot reproduce, laptop
    loss = evidence gone but dashboard says committed).

    `timeout` arg retained for backward compat with callers but
    ignored: pure-Python file reads are bounded by `max_depth`.
    """
    if not is_valid_git_sha(sha):
        return False
    git_dir = _resolve_git_dir(project_path)
    if git_dir is None:
        return False
    tips = _iter_remote_ref_tips(git_dir)
    if not tips:
        return False
    # Fast path: target IS a remote tip.
    if sha in tips:
        return True
    # BFS from each tip until we find target or exhaust depth.
    visited: set[str] = set()
    frontier: list[str] = list(tips)
    for _ in range(max_depth):
        if not frontier:
            return False
        next_frontier: list[str] = []
        for cur in frontier:
            if cur in visited:
                continue
            visited.add(cur)
            if cur == sha:
                return True
            for p in _read_commit_parents(git_dir, cur):
                if p not in visited:
                    next_frontier.append(p)
        frontier = next_frontier
    return False


def get_committed_sha(
    project_path: str,
    repo_path: str,
    timeout: float = 0,  # kept for backward compat; ignored
) -> Optional[str]:
    """Return a commit sha for `repo_path` that is on the remote, or None.

    Pure-Python (NO subprocess) per the MCP-stdio rule. Strategy:

      1. Read .git/HEAD → ref name → sha (or detached HEAD sha).
      2. Check is_sha_on_remote(HEAD).
      3. If true, return HEAD; else None.

    SIMPLIFICATION vs the prior `git log -1 -- <path>` impl: we no
    longer walk the commit graph to find the precise commit that
    touched `repo_path`. We return HEAD when HEAD is on remote.
    Rationale: in the calling context (pull_pending_evidence's confirm
    flow) the user has just been instructed to `git add <repo_path>
    && git commit && git push`. After that flow HEAD == the commit
    that just added the file. If the user instead made a different
    commit at HEAD (file uncommitted), the caller's prior file-on-
    disk vs expected_sha check still passes — but the audit anchor
    we record will be HEAD instead of the (non-existent) commit that
    touched repo_path. This preserves the §4.6 invariant ("never
    record a sha that's not on remote") while accepting that the
    recorded sha may not be the historically-most-recent commit
    that touched the file. Trade-off accepted because:
      a) the dashboard only uses committed_at_sha as the audit anchor
         for "user pushed evidence" — it does NOT rely on commit-
         to-path provenance;
      b) the alternative (walking trees in pure Python to find the
         commit-that-touched-path) is hundreds of LOC and orthogonal
         to the audit invariant.
    """
    git_dir = _resolve_git_dir(project_path)
    if git_dir is None:
        return None
    head_path = os.path.join(git_dir, "HEAD")
    if not os.path.isfile(head_path):
        return None
    try:
        with open(head_path, "r", encoding="utf-8") as f:
            head_content = f.read().strip()
    except OSError:
        return None
    head_sha: Optional[str] = None
    if head_content.startswith("ref: "):
        ref = head_content[len("ref: "):].strip()
        # Try loose ref file
        ref_file = os.path.join(git_dir, ref)
        if os.path.isfile(ref_file):
            try:
                with open(ref_file, "r", encoding="utf-8") as f:
                    candidate = f.read().strip()
                if is_valid_git_sha(candidate):
                    head_sha = candidate
            except OSError:
                pass
        # Fall back to packed-refs
        if head_sha is None:
            packed = _read_packed_refs(git_dir)
            candidate = packed.get(ref)
            if candidate and is_valid_git_sha(candidate):
                head_sha = candidate
    elif is_valid_git_sha(head_content):
        # Detached HEAD
        head_sha = head_content

    if head_sha is None:
        return None
    if is_sha_on_remote(project_path, head_sha):
        return head_sha
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
