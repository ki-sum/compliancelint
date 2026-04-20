"""Unit tests for core.pending_evidence — Evidence v4 sub-3b.

Covers:
  - Hash primitives (sha256_bytes, sha256_file, is_valid_git_sha)
  - Conflict-path generation (build_conflict_path, resolve_write_destination)
  - Atomic disk write with post-write hash verification
  - Full pull orchestration with mocked HTTP:
      * empty list → no-op
      * normal pull → bytes written + sha verified
      * hash mismatch → refuse to write
      * target exists same hash + committed → confirm batch
      * target exists same hash + NOT committed → skip (idempotent resume)
      * target exists different hash → .conflict-{ts}
      * list endpoint 404 → RepoNotFoundError bubbles up
      * sync-confirm HTTP failure → item marked error, pull continues
  - metadata.json cache helpers (read/write/clear, preserve other keys)
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# Ensure scanner/ is on path (conftest already does this, but be explicit).
SCANNER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SCANNER_ROOT not in sys.path:
    sys.path.insert(0, SCANNER_ROOT)

from core import pending_evidence as pe  # noqa: E402
from core.pending_evidence import (  # noqa: E402
    RepoNotFoundError,
    atomic_write_bytes,
    build_conflict_path,
    build_human_prompt,
    clear_cached_repo_id,
    is_valid_git_sha,
    pull_pending_evidence,
    read_cached_repo_id,
    resolve_write_destination,
    sha256_bytes,
    sha256_file,
    write_cached_repo_id,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_project(tmp_path):
    """Empty project dir — callers seed it as needed."""
    return str(tmp_path)


def _write_pending(project_path: str, repo_path: str, content: bytes) -> str:
    abs_path = os.path.join(project_path, repo_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(content)
    return abs_path


def _mk_pending_row(pid: str, repo_path: str, content: bytes) -> dict:
    return {
        "id": pid,
        "filename": os.path.basename(repo_path),
        "sha256": hashlib.sha256(content).hexdigest(),
        "repo_path": repo_path,
        "size": len(content),
        "finding_id": f"find-{pid}",
        "evidence_item_id": f"ei-{pid}",
        "uploaded_at": "2026-04-20T00:00:00Z",
        "ttl_expires_at": "2026-05-20T00:00:00Z",
        "encrypted_size": len(content) + 28,
        "commit_status": "pending_commit",
    }


def _bytes_payload(content: bytes, row: dict) -> dict:
    return {
        "bytes_b64": base64.b64encode(content).decode("ascii"),
        "sha256": row["sha256"],
        "filename": row["filename"],
        "repo_path": row["repo_path"],
        "finding_id": row["finding_id"],
        "evidence_item_id": row["evidence_item_id"],
        "size": len(content),
    }


class FakeHttp:
    """Recorder for injected HTTP callbacks; simulates responses by URL suffix."""

    def __init__(self):
        self.get_responses: dict[str, object] = {}  # url -> dict OR Exception
        self.post_responses: dict[str, object] = {}
        self.posted: list[tuple[str, dict]] = []
        self.gotten: list[str] = []

    def get(self, url: str):
        self.gotten.append(url)
        resp = self.get_responses.get(url)
        if isinstance(resp, Exception):
            raise resp
        return resp

    def post(self, url: str, payload: dict):
        self.posted.append((url, payload))
        resp = self.post_responses.get(url)
        if isinstance(resp, Exception):
            raise resp
        return resp


# ── Hash primitives ─────────────────────────────────────────────────────────


class TestHashPrimitives:
    def test_sha256_bytes_matches_hashlib(self):
        assert sha256_bytes(b"hello") == hashlib.sha256(b"hello").hexdigest()

    def test_sha256_file_streams_correctly(self, tmp_path):
        content = os.urandom(200_000)  # > single chunk
        p = tmp_path / "big.bin"
        p.write_bytes(content)
        assert sha256_file(str(p)) == hashlib.sha256(content).hexdigest()

    def test_is_valid_git_sha_accepts_lowercase_40_hex(self):
        assert is_valid_git_sha("a" * 40)
        assert is_valid_git_sha("0123456789abcdef0123456789abcdef01234567")

    def test_is_valid_git_sha_rejects_uppercase(self):
        assert not is_valid_git_sha("A" * 40)

    def test_is_valid_git_sha_rejects_wrong_length(self):
        assert not is_valid_git_sha("a" * 39)
        assert not is_valid_git_sha("a" * 41)
        assert not is_valid_git_sha("")

    def test_is_valid_git_sha_rejects_non_hex(self):
        assert not is_valid_git_sha("z" * 40)
        assert not is_valid_git_sha("g" + "a" * 39)

    def test_is_valid_git_sha_rejects_non_string(self):
        assert not is_valid_git_sha(None)  # type: ignore[arg-type]
        assert not is_valid_git_sha(123)  # type: ignore[arg-type]


# ── Conflict path + resolution ──────────────────────────────────────────────


class TestConflictPath:
    def test_build_conflict_path_format(self):
        fixed = datetime(2026, 4, 20, 15, 30, 12, tzinfo=timezone.utc)
        p = build_conflict_path("/tmp/foo.pdf", now_utc=fixed)
        assert p == "/tmp/foo.pdf.conflict-20260420T153012Z"

    def test_resolve_write_destination_new_file(self, tmp_project):
        dest, action = resolve_write_destination(tmp_project, "ev/a.txt", "abc")
        assert action == "write"
        # Server-sent repo_path uses forward slashes; os.path.join preserves them on Windows.
        assert dest.replace("\\", "/").endswith("ev/a.txt")

    def test_resolve_write_destination_same_hash(self, tmp_project):
        content = b"same content"
        _write_pending(tmp_project, "ev/a.txt", content)
        sha = hashlib.sha256(content).hexdigest()
        dest, action = resolve_write_destination(tmp_project, "ev/a.txt", sha)
        assert action == "skip"
        assert dest.replace("\\", "/").endswith("ev/a.txt")

    def test_resolve_write_destination_different_hash_goes_to_conflict(self, tmp_project):
        _write_pending(tmp_project, "ev/a.txt", b"original")
        incoming_sha = hashlib.sha256(b"incoming").hexdigest()
        fixed = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        dest, action = resolve_write_destination(
            tmp_project, "ev/a.txt", incoming_sha, now_utc=fixed,
        )
        assert action == "conflict"
        assert "conflict-20260420T120000Z" in dest


# ── Atomic write ────────────────────────────────────────────────────────────


class TestAtomicWrite:
    def test_writes_file_with_correct_hash(self, tmp_project):
        blob = b"evidence data"
        target = os.path.join(tmp_project, "ev", "out.bin")
        atomic_write_bytes(target, blob, sha256_bytes(blob))
        assert os.path.exists(target)
        assert open(target, "rb").read() == blob
        assert sha256_file(target) == sha256_bytes(blob)

    def test_refuses_on_hash_mismatch(self, tmp_project):
        blob = b"evidence data"
        target = os.path.join(tmp_project, "ev", "out.bin")
        with pytest.raises(RuntimeError, match="hash mismatch"):
            atomic_write_bytes(target, blob, "0" * 64)  # wrong expected sha
        assert not os.path.exists(target)
        # temp files must also be cleaned up — no leftover .tmp
        leftovers = [f for f in os.listdir(os.path.dirname(target)) if f.endswith(".tmp")]
        assert leftovers == []

    def test_overwrites_existing_target_only_after_hash_verified(self, tmp_project):
        target = os.path.join(tmp_project, "ev", "out.bin")
        os.makedirs(os.path.dirname(target))
        with open(target, "wb") as f:
            f.write(b"ORIGINAL")
        blob = b"new content"
        atomic_write_bytes(target, blob, sha256_bytes(blob))
        assert open(target, "rb").read() == blob

    def test_os_replace_failure_preserves_existing_target(self, tmp_project, monkeypatch):
        """Simulates mid-write interruption: os.replace raises (server crash /
        OOM kill / disk full at the atomic-rename step). Target must still
        hold its original content — the atomic guarantee. Tmp must be cleaned.

        Why this test matters: the design relies on os.replace being the
        only moment the target changes. A future refactor that writes in-
        place or renames before verify would silently break this guarantee.
        """
        target = os.path.join(tmp_project, "ev", "out.bin")
        os.makedirs(os.path.dirname(target))
        original = b"ORIGINAL - must survive crash"
        with open(target, "wb") as f:
            f.write(original)

        def boom(_src, _dst):
            raise OSError("simulated crash during atomic rename")

        monkeypatch.setattr(pe.os, "replace", boom)

        blob = b"incoming content"
        with pytest.raises(OSError, match="simulated crash"):
            atomic_write_bytes(target, blob, sha256_bytes(blob))

        # Invariant 1: target file unchanged (byte-identical to original)
        assert open(target, "rb").read() == original
        # Invariant 2: no .tmp leftover (cleanup handler ran)
        leftovers = [f for f in os.listdir(os.path.dirname(target))
                     if f.endswith(".tmp")]
        assert leftovers == []

    def test_os_replace_failure_leaves_no_file_when_target_absent(self, tmp_project, monkeypatch):
        """Same guarantee for the new-file case: target didn't exist before,
        os.replace fails, target still doesn't exist, tmp cleaned.
        """
        target = os.path.join(tmp_project, "ev", "new.bin")
        os.makedirs(os.path.dirname(target))

        def boom(_src, _dst):
            raise OSError("simulated crash during atomic rename")

        monkeypatch.setattr(pe.os, "replace", boom)

        blob = b"incoming content"
        with pytest.raises(OSError, match="simulated crash"):
            atomic_write_bytes(target, blob, sha256_bytes(blob))

        # Invariant 1: target never materialised
        assert not os.path.exists(target)
        # Invariant 2: tmp cleaned
        leftovers = [f for f in os.listdir(os.path.dirname(target))
                     if f.endswith(".tmp")]
        assert leftovers == []


# ── Cache helpers ───────────────────────────────────────────────────────────


class TestCacheHelpers:
    def test_read_returns_none_when_no_metadata(self, tmp_project):
        assert read_cached_repo_id(tmp_project) is None

    def test_read_returns_none_when_key_missing(self, tmp_project):
        meta_dir = os.path.join(tmp_project, ".compliancelint")
        os.makedirs(meta_dir)
        with open(os.path.join(meta_dir, "metadata.json"), "w") as f:
            json.dump({"ai_provider": "x"}, f)
        assert read_cached_repo_id(tmp_project) is None

    def test_read_returns_none_on_malformed_json(self, tmp_project):
        meta_dir = os.path.join(tmp_project, ".compliancelint")
        os.makedirs(meta_dir)
        with open(os.path.join(meta_dir, "metadata.json"), "w") as f:
            f.write("{ not json ")
        assert read_cached_repo_id(tmp_project) is None

    def test_write_preserves_existing_keys(self, tmp_project):
        meta_dir = os.path.join(tmp_project, ".compliancelint")
        os.makedirs(meta_dir)
        meta_path = os.path.join(meta_dir, "metadata.json")
        with open(meta_path, "w") as f:
            json.dump({"ai_provider": "Claude", "last_sync_at": "2026-04-20T00:00:00Z"}, f)

        write_cached_repo_id(tmp_project, "repo-uuid-42")

        with open(meta_path) as f:
            result = json.load(f)
        assert result == {
            "ai_provider": "Claude",
            "last_sync_at": "2026-04-20T00:00:00Z",
            "repo_id": "repo-uuid-42",
        }

    def test_write_creates_directory_and_file(self, tmp_project):
        assert read_cached_repo_id(tmp_project) is None
        write_cached_repo_id(tmp_project, "new-uuid")
        assert read_cached_repo_id(tmp_project) == "new-uuid"

    def test_write_noop_for_empty_repo_id(self, tmp_project):
        write_cached_repo_id(tmp_project, "")
        assert read_cached_repo_id(tmp_project) is None

    def test_clear_removes_only_repo_id(self, tmp_project):
        meta_dir = os.path.join(tmp_project, ".compliancelint")
        os.makedirs(meta_dir)
        meta_path = os.path.join(meta_dir, "metadata.json")
        with open(meta_path, "w") as f:
            json.dump({"repo_id": "stale", "ai_provider": "Claude"}, f)

        clear_cached_repo_id(tmp_project)

        with open(meta_path) as f:
            result = json.load(f)
        assert result == {"ai_provider": "Claude"}
        assert read_cached_repo_id(tmp_project) is None

    def test_clear_no_metadata_file(self, tmp_project):
        clear_cached_repo_id(tmp_project)  # must not raise

    def test_roundtrip(self, tmp_project):
        write_cached_repo_id(tmp_project, "uuid-1")
        assert read_cached_repo_id(tmp_project) == "uuid-1"
        # Overwrite
        write_cached_repo_id(tmp_project, "uuid-2")
        assert read_cached_repo_id(tmp_project) == "uuid-2"
        clear_cached_repo_id(tmp_project)
        assert read_cached_repo_id(tmp_project) is None


# ── Pull orchestration ─────────────────────────────────────────────────────


SAAS = "http://localhost:3000"
REPO_ID = "repo-uuid-fixture"


class TestPullOrchestration:

    def test_empty_pending_list_is_noop(self, tmp_project):
        http = FakeHttp()
        http.get_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/pending-evidence"] = {"pending": [], "count": 0}

        summary = pull_pending_evidence(
            project_path=tmp_project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            get_sha_for_path=lambda _p, _r: None,
        )
        assert summary.pulled == 0
        assert summary.confirmed == 0
        assert summary.items == []

    def test_raises_repo_not_found_when_list_404s(self, tmp_project):
        http = FakeHttp()
        http.get_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/pending-evidence"] = RepoNotFoundError(
            "simulated 404"
        )
        with pytest.raises(RepoNotFoundError):
            pull_pending_evidence(
                project_path=tmp_project,
                saas_url=SAAS,
                repo_id=REPO_ID,
                http_get_json=http.get,
                http_post_json=http.post,
                get_sha_for_path=lambda _p, _r: None,
            )

    def test_pulls_new_file_to_working_tree(self, tmp_project):
        content = b"risk assessment PDF content"
        row = _mk_pending_row("pid-1", ".compliancelint/evidence/find-1/risk.pdf", content)
        http = FakeHttp()
        http.get_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/pending-evidence"] = {"pending": [row]}
        http.get_responses[f"{SAAS}/api/v1/pending-evidence/pid-1"] = _bytes_payload(content, row)

        summary = pull_pending_evidence(
            project_path=tmp_project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            get_sha_for_path=lambda _p, _r: None,
        )

        target = os.path.join(tmp_project, row["repo_path"])
        assert os.path.exists(target)
        assert open(target, "rb").read() == content
        assert summary.pulled == 1
        assert summary.confirmed == 0
        assert summary.errors == 0

    def test_skips_when_target_exists_same_hash_not_committed(self, tmp_project):
        """Idempotent resume: human pulled last time, hasn't committed yet."""
        content = b"data"
        row = _mk_pending_row("pid-1", ".compliancelint/evidence/find-1/a.txt", content)
        _write_pending(tmp_project, row["repo_path"], content)
        http = FakeHttp()
        http.get_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/pending-evidence"] = {"pending": [row]}

        # get_sha_for_path returns None — file not yet committed
        summary = pull_pending_evidence(
            project_path=tmp_project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            get_sha_for_path=lambda _p, _r: None,
        )

        assert summary.skipped_same_hash == 1
        assert summary.pulled == 0
        assert summary.confirmed == 0
        # Must NOT have tried to fetch bytes
        assert f"{SAAS}/api/v1/pending-evidence/pid-1" not in http.gotten

    def test_confirms_when_target_exists_same_hash_and_committed(self, tmp_project):
        """§3.3: PM committed the file; next sync reports sync-confirm."""
        content = b"data"
        row = _mk_pending_row("pid-1", ".compliancelint/evidence/find-1/a.txt", content)
        _write_pending(tmp_project, row["repo_path"], content)
        http = FakeHttp()
        http.get_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/pending-evidence"] = {"pending": [row]}
        http.post_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/sync-confirm"] = {
            "confirmed": 1, "skipped": 0, "skipped_details": [],
        }

        fake_sha = "a" * 40
        summary = pull_pending_evidence(
            project_path=tmp_project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            get_sha_for_path=lambda _p, _r: fake_sha,
        )

        assert summary.confirmed == 1
        assert summary.pulled == 0
        # Confirm request was posted with correct payload
        assert len(http.posted) == 1
        url, payload = http.posted[0]
        assert url == f"{SAAS}/api/v1/repos/{REPO_ID}/sync-confirm"
        assert payload == {"committed_paths": [{
            "repo_path": row["repo_path"],
            "committed_at_sha": fake_sha,
        }]}

    def test_hash_mismatch_refuses_write(self, tmp_project):
        """§4.3: SaaS-returned bytes don't match expected sha → do not pollute tree."""
        content = b"correct content"
        row = _mk_pending_row("pid-1", ".compliancelint/evidence/find-1/a.txt", content)
        http = FakeHttp()
        http.get_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/pending-evidence"] = {"pending": [row]}

        tampered = _bytes_payload(b"tampered bytes", row)
        # Claim server sha matches list sha but bytes are different
        tampered["sha256"] = row["sha256"]
        http.get_responses[f"{SAAS}/api/v1/pending-evidence/pid-1"] = tampered

        summary = pull_pending_evidence(
            project_path=tmp_project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            get_sha_for_path=lambda _p, _r: None,
        )

        target = os.path.join(tmp_project, row["repo_path"])
        assert not os.path.exists(target)
        assert summary.errors == 1
        assert summary.pulled == 0
        assert "hash mismatch" in summary.items[0].error

    def test_conflict_writes_to_timestamped_path(self, tmp_project):
        """§4.5: target exists + different hash → .conflict-{ts}, original preserved."""
        original = b"original file in repo"
        _write_pending(tmp_project, ".compliancelint/evidence/find-1/a.txt", original)

        incoming = b"incoming file from dashboard"
        row = _mk_pending_row("pid-1", ".compliancelint/evidence/find-1/a.txt", incoming)
        http = FakeHttp()
        http.get_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/pending-evidence"] = {"pending": [row]}
        http.get_responses[f"{SAAS}/api/v1/pending-evidence/pid-1"] = _bytes_payload(incoming, row)

        summary = pull_pending_evidence(
            project_path=tmp_project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            get_sha_for_path=lambda _p, _r: None,
        )

        # Original untouched
        orig_path = os.path.join(tmp_project, ".compliancelint/evidence/find-1/a.txt")
        assert open(orig_path, "rb").read() == original
        # Conflict file written
        assert summary.conflicts == 1
        assert len(summary.conflict_paths) == 1
        conflict_name = summary.conflict_paths[0]
        assert "conflict-" in conflict_name
        abs_conflict = os.path.join(tmp_project, conflict_name.replace("/", os.sep))
        assert os.path.exists(abs_conflict)
        assert open(abs_conflict, "rb").read() == incoming

    def test_sync_confirm_http_failure_surfaces_error(self, tmp_project):
        """If sync-confirm fails, the confirm items become errors, pull continues."""
        content = b"data"
        row = _mk_pending_row("pid-1", ".compliancelint/evidence/find-1/a.txt", content)
        _write_pending(tmp_project, row["repo_path"], content)
        http = FakeHttp()
        http.get_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/pending-evidence"] = {"pending": [row]}
        http.post_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/sync-confirm"] = RuntimeError("boom")

        fake_sha = "b" * 40
        summary = pull_pending_evidence(
            project_path=tmp_project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            get_sha_for_path=lambda _p, _r: fake_sha,
        )
        assert summary.confirmed == 0
        assert summary.errors == 1
        assert "sync-confirm failed" in summary.items[0].error

    def test_invalid_sha_from_git_is_not_reported(self, tmp_project):
        """If git log returns non-40-hex garbage, do NOT include in confirm batch."""
        content = b"data"
        row = _mk_pending_row("pid-1", ".compliancelint/evidence/find-1/a.txt", content)
        _write_pending(tmp_project, row["repo_path"], content)
        http = FakeHttp()
        http.get_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/pending-evidence"] = {"pending": [row]}

        summary = pull_pending_evidence(
            project_path=tmp_project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            get_sha_for_path=lambda _p, _r: "not-a-sha",
        )
        # No confirm, no pull (file exists + same hash, but invalid sha → skipped_same_hash)
        assert summary.confirmed == 0
        assert summary.skipped_same_hash == 1
        assert len(http.posted) == 0

    def test_missing_pending_id_in_row_becomes_error(self, tmp_project):
        row = _mk_pending_row("pid-1", "a.txt", b"x")
        row["id"] = ""
        http = FakeHttp()
        http.get_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/pending-evidence"] = {"pending": [row]}

        summary = pull_pending_evidence(
            project_path=tmp_project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            get_sha_for_path=lambda _p, _r: None,
        )
        assert summary.errors == 1
        assert "missing" in summary.items[0].error

    def test_multiple_files_mixed_outcomes(self, tmp_project):
        """One new pull + one already-committed confirm + one conflict — all together."""
        # File A: new (will be pulled)
        a_content = b"file A new"
        a = _mk_pending_row("pid-A", ".compliancelint/evidence/find-1/a.txt", a_content)

        # File B: already on disk + hash match + committed → confirm
        b_content = b"file B already committed"
        b = _mk_pending_row("pid-B", ".compliancelint/evidence/find-2/b.txt", b_content)
        _write_pending(tmp_project, b["repo_path"], b_content)

        # File C: different hash on disk → conflict
        c_incoming = b"C incoming"
        _write_pending(tmp_project, ".compliancelint/evidence/find-3/c.txt", b"C original")
        c = _mk_pending_row("pid-C", ".compliancelint/evidence/find-3/c.txt", c_incoming)

        http = FakeHttp()
        http.get_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/pending-evidence"] = {
            "pending": [a, b, c],
        }
        http.get_responses[f"{SAAS}/api/v1/pending-evidence/pid-A"] = _bytes_payload(a_content, a)
        http.get_responses[f"{SAAS}/api/v1/pending-evidence/pid-C"] = _bytes_payload(c_incoming, c)
        http.post_responses[f"{SAAS}/api/v1/repos/{REPO_ID}/sync-confirm"] = {
            "confirmed": 1, "skipped": 0, "skipped_details": [],
        }

        committed_sha = "c" * 40
        def sha_lookup(_proj, rp):
            # Only B is committed
            return committed_sha if rp == b["repo_path"] else None

        summary = pull_pending_evidence(
            project_path=tmp_project,
            saas_url=SAAS,
            repo_id=REPO_ID,
            http_get_json=http.get,
            http_post_json=http.post,
            get_sha_for_path=sha_lookup,
        )
        assert summary.pulled == 1       # A
        assert summary.confirmed == 1    # B
        assert summary.conflicts == 1    # C
        assert summary.errors == 0


# ── Human prompt ───────────────────────────────────────────────────────────


class TestHumanPrompt:
    def test_empty_summary_returns_empty_prompt(self):
        from core.pending_evidence import PullSummary
        assert build_human_prompt(PullSummary()) == ""

    def test_prompt_includes_pulled_paths_and_git_command(self):
        from core.pending_evidence import PullItemResult, PullSummary
        s = PullSummary()
        s.add(PullItemResult(pending_id="x", repo_path=".compliancelint/evidence/find-1/risk.pdf",
                             status="pulled"))
        out = build_human_prompt(s)
        assert "1 evidence file(s) staged for commit" in out
        assert ".compliancelint/evidence/find-1/risk.pdf" in out
        assert "git add .compliancelint/evidence" in out
        assert "git commit" in out
        # MUST NOT include anything auto-executable beyond the suggestion
        assert "git push" in out

    def test_prompt_flags_conflicts_separately(self):
        from core.pending_evidence import PullItemResult, PullSummary
        s = PullSummary()
        s.add(PullItemResult(pending_id="x", repo_path=".compliancelint/evidence/find-1/a.txt",
                             status="conflict",
                             conflict_path=".compliancelint/evidence/find-1/a.txt.conflict-20260420T120000Z"))
        out = build_human_prompt(s)
        assert "different content" in out
        assert "conflict-20260420T120000Z" in out
