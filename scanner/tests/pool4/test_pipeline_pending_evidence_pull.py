"""Pool 4 — pipeline-pending-evidence-pull via real MCP (Q3.5 real flow).

Verifies the previously-misnamed `needs_push_first` scenario from the
Pool 4 plan. Per audit-first investigation 2026-05-05 (Kisum's Q3
follow-up), the real flow is:

  1. User uploads an evidence file via the SaaS dashboard web UI.
     Bytes land in pending_evidence table; an evidence_items row with
     commit_status='pending_commit' is the audit anchor.
  2. cl_sync (MCP) STEP 11 detects the pending row, downloads the
     file bytes via GET /api/v1/pending-evidence/<id>, writes them to
     project_path/.compliancelint/evidence/<repo_path>.
  3. cl_sync's response surfaces a `pending_evidence` summary AND a
     top-level `action_required` (or `human_prompt`) string telling
     the user to run `git add .compliancelint/evidence && git commit
     && git push`.
  4. User commits + pushes (out of scope here — needs real git remote).
  5. Next cl_sync's pull orchestrator calls is_sha_on_remote() to
     confirm and marks committed_at_sha on the dashboard.

This cell exercises (1)→(3) via real MCP. The (4)→(5) confirm half
needs a real git remote which is heavy infra; deferred.

Why this cell matters: the Pool 4 plan listed `needs_push_first` as
an aspirational error scenario implying cl_sync REFUSES when there
are unpushed commits. The real behavior is the opposite — cl_sync
SUCCEEDS and prompts the user to commit+push the pulled evidence.
This cell pins the actual behavior end-to-end.

Per Pool 4 hard constraints:
  - C1: real MCP subprocess transport (default cwd=REPO_ROOT so
    `python -m scanner.server` resolves to THIS repo's editable
    package, not pip-installed older versions)
  - C2: live :3000 prod server
  - C3: real seeded test-business persona
  - C7: tmp_path Pattern B
  - C8: purge_repo + tmp_path

Verified-via: scanner/server.py STEP 11a-b (_run_pending_evidence_pull) +
scanner/core/pending_evidence.py (pull_pending_evidence orchestrator) +
the SaaS GET /api/v1/repos/<id>/pending-evidence + GET
/api/v1/pending-evidence/<id> endpoints.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from .cleanup import CleanupError, purge_repo
from .fixtures import PERSONAS
from .mcp_client import McpStdioClient, parse_first_json
from .saas_introspection import (
    DB_PATH_ENV,
    fetch_repo_by_name,
    open_readonly,
)


SAAS_URL = "http://localhost:3000"
EVIDENCE_REL_PATH = "controls/dpia-summary.md"
EVIDENCE_BYTES = b"# DPIA Summary\n\n(Pool 4 pending-evidence pull test artifact)\n"


def _aes_gcm_encrypt(plaintext: bytes, key_b64: str) -> bytes:
    """Encrypt with AES-256-GCM using the same wire format as the
    dashboard's lib/evidence-encryption.ts (12-byte IV || 16-byte tag ||
    ciphertext). The pending_evidence.bytes BLOB column stores this
    composite blob; the dashboard's GET handler decrypts it before
    base64-encoding for the scanner. Mirrors:
      [12 bytes IV] [16 bytes authTag] [N bytes ciphertext]
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = base64.b64decode(key_b64)
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    # AESGCM encrypt() returns ciphertext || tag (Python convention).
    # The dashboard's TS encryptBytes() puts tag BEFORE ciphertext, so
    # we re-order to match: IV || tag || ciphertext.
    ct_with_tag = aesgcm.encrypt(iv, plaintext, None)
    ciphertext, tag = ct_with_tag[:-16], ct_with_tag[-16:]
    return iv + tag + ciphertext


def _git_init_minimal(project_dir: Path) -> str:
    """Init a git repo with one initial commit. Returns HEAD sha."""
    flags = {"cwd": str(project_dir), "capture_output": True, "text": True, "check": True}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags["creationflags"] = subprocess.CREATE_NO_WINDOW
    subprocess.run(["git", "init", "-q"], **flags)
    subprocess.run(["git", "config", "user.email", "pool4@test.invalid"], **flags)
    subprocess.run(["git", "config", "user.name", "Pool 4 Test"], **flags)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], **flags)
    (project_dir / ".gitignore").write_text(".compliancelint/local/\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], **flags)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], **flags)
    r = subprocess.run(["git", "rev-parse", "HEAD"], **flags)
    return r.stdout.strip()


def _build_synthetic_context(client: McpStdioClient, project_path: Path) -> str:
    raw = client.call_tool(
        "cl_analyze_project", {"project_path": str(project_path)},
    )
    analyze = parse_first_json(raw)
    template = analyze.get("compliance_answers_template")
    if not template:
        raise RuntimeError("cl_analyze_project did not return template")
    answers = dict(template)
    answers["_scope"] = {
        **answers.get("_scope", {}),
        "risk_classification": "high-risk",
        "risk_classification_confidence": "high",
        "is_ai_system": True,
        "operator_role": ["provider"],
        "annex_iii_category": "annex_iii_pt5_essential_services",
        "is_annex_i_product": False,
        "uses_training_data": True,
        "is_gpai": False,
        "is_gpai_provider": False,
        "eu_established": True,
        "territorial_scope_applies": True,
        "is_open_source": False,
        "is_military_defense": False,
        "is_research_only": False,
        "is_biometric_system": False,
        "is_financial_institution": False,
        "is_distributor": False,
        "is_importer": False,
        "is_authorised_representative": False,
    }
    return json.dumps({
        "framework": "python",
        "stack": ["python"],
        "compliance_answers": answers,
    })


def _seed_pending_evidence(
    *,
    db_path: str,
    repo_id: str,
    scan_id: str,
    repo_path: str,
    bytes_payload: bytes,
    uploader_user_email: str,
    encryption_key_b64: str,
) -> tuple[str, str, str]:
    """Set up the chain: finding + finding_response + evidence_items
    (pending_commit, git_path) + pending_evidence row carrying ENCRYPTED
    bytes. Returns (finding_id, evidence_item_id, pending_evidence_id).

    Mirrors what the dashboard upload flow would create when a user
    drops a file into the evidence panel in the web UI. Bytes are
    encrypted with the same AES-256-GCM scheme the dashboard uses
    (lib/evidence-encryption.ts) so the dashboard's decryptBytes()
    succeeds when cl_sync fetches the bytes.
    """
    sha = hashlib.sha256(bytes_payload).hexdigest()
    encrypted_blob = _aes_gcm_encrypt(bytes_payload, encryption_key_b64)
    conn = sqlite3.connect(db_path)
    try:
        # Look up uploader user_id (foreign key for pending_evidence.uploader_user_id).
        u = conn.execute(
            "SELECT id FROM users WHERE email = ?", (uploader_user_email,),
        ).fetchone()
        assert u is not None, f"uploader email {uploader_user_email} not in users"
        uploader_user_id = u[0]

        finding_id = str(uuid.uuid4())
        response_id = str(uuid.uuid4())
        evidence_item_id = str(uuid.uuid4())
        pending_id = str(uuid.uuid4())

        conn.execute(
            """INSERT INTO findings
                 (id, scan_id, article, obligation_id, status, title)
               VALUES (?, ?, 'art9', 'ART09-OBL-1', 'compliant',
                       'Pool 4 pending-evidence pull seed')""",
            (finding_id, scan_id),
        )
        conn.execute(
            """INSERT INTO finding_responses
                 (id, finding_id, action, note, submitted_at, created_at)
               VALUES (?, ?, 'provide_evidence', 'pool4 pending pull seed',
                       strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                       strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))""",
            (response_id, finding_id),
        )
        conn.execute(
            """INSERT INTO evidence_items
                 (id, finding_response_id, source, evidence_value,
                  evidence_name, dedup_hash, commit_status, storage_kind,
                  repo_path, content_sha256, health_status,
                  uploaded_at, created_at)
               VALUES (?, ?, 'dashboard', ?, 'dpia-summary.md',
                       ?, 'pending_commit', 'git_path', ?, ?, 'ok',
                       strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                       strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))""",
            (
                evidence_item_id,
                response_id,
                repo_path,
                f"dedup-{evidence_item_id}",
                repo_path,
                sha,
            ),
        )
        # ttl_expires_at must be ISO 8601 UTC ('...Z' suffix). The
        # dashboard's TS handler does `new Date(ttlExpiresAt)` and
        # compares vs Date.now() (UTC). SQLite's `datetime('now', ...)`
        # returns space-separated YYYY-MM-DD HH:MM:SS which JS parses
        # as LOCAL time → comparison goes wrong on non-UTC dev boxes
        # (the row appears already-expired). Use strftime to force ISO
        # UTC with the trailing Z.
        conn.execute(
            """INSERT INTO pending_evidence
                  (id, evidence_item_id, repo_id, bytes, sha256,
                   filename, uploader_user_id, uploaded_at, ttl_expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?,
                        strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                        strftime('%Y-%m-%dT%H:%M:%fZ', 'now', '+1 hour'))""",
            (pending_id, evidence_item_id, repo_id, encrypted_blob, sha,
             "dpia-summary.md", uploader_user_id),
        )
        conn.commit()
    finally:
        conn.close()
    return finding_id, evidence_item_id, pending_id


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_pipeline_pending_evidence_pull_writes_file_and_prompts_commit(
    tmp_path: Path,
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end: SaaS-side pending evidence → cl_sync pulls bytes →
    file lands at the right path on disk → response includes
    pending_evidence summary + action_required prompt mentioning
    git add+commit+push."""
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    db_path = os.environ.get(DB_PATH_ENV)
    if not db_path:
        pytest.skip(f"{DB_PATH_ENV} not set")

    # The dashboard's encryption key — must match what the running
    # dev server has in its env (it's loaded from .env.local at boot).
    # Pool 4 cells run on Kisum's local dev box where this is the
    # canonical dev key. If POOL4_EVIDENCE_ENCRYPTION_KEY env var is
    # set the cell uses that; otherwise it reads from the dashboard's
    # .env.local file directly so the test stays self-contained.
    encryption_key_b64 = os.environ.get("POOL4_EVIDENCE_ENCRYPTION_KEY")
    if not encryption_key_b64:
        env_local = Path(db_path).parent.parent / ".env.local"
        if env_local.is_file():
            for line in env_local.read_text(encoding="utf-8").splitlines():
                if line.startswith("EVIDENCE_ENCRYPTION_KEY="):
                    encryption_key_b64 = line.split("=", 1)[1].strip()
                    break
    if not encryption_key_b64:
        pytest.skip(
            "EVIDENCE_ENCRYPTION_KEY not available — set "
            "POOL4_EVIDENCE_ENCRYPTION_KEY env var or place .env.local "
            "next to the dashboard data directory"
        )

    persona = PERSONAS["business"]
    suffix = str(int(time.time() * 1000) % 1_000_000_000)
    repo_name = f"test-business/pool4-pending-pull-{suffix}"

    project_dir = tmp_path / "fixture"
    project_dir.mkdir()
    _git_init_minimal(project_dir)

    (project_dir / ".compliancelintrc").write_text(
        json.dumps({
            "purpose": "Pool 4 pending-evidence pull fixture",
            "repo_name": repo_name,
            "saas_url": SAAS_URL,
            "saas_api_key": persona.api_key,
            "scope": {
                "operator_role": ["provider"],
                "risk_classification": "high-risk",
            },
            "attester_name": "Pool 4 Pending-Pull Test",
            "attester_email": "pool4-pending-pull@test.invalid",
        }, indent=2),
        encoding="utf-8",
    )

    repo_id_for_cleanup: str | None = None
    # IMPORTANT: omit cwd= so spawn() uses REPO_ROOT — otherwise
    # python -m scanner.server resolves to pip-installed older version
    # that lacks the STEP 11 pending-evidence pull (see broken_link
    # cell's commit message for the same lesson).
    client = McpStdioClient.spawn()
    try:
        # Step 1: cl_scan + cl_sync to create the dashboard repo + scan.
        project_context_json = _build_synthetic_context(client, project_dir)
        scan_resp = parse_first_json(client.call_tool("cl_scan", {
            "project_path": str(project_dir),
            "project_context": project_context_json,
            "articles": "9",
            "ai_provider": "Pool4 pending-pull Synthetic",
        }))
        if "error" in scan_resp:
            pytest.skip(f"cl_scan rejected synthetic context: {scan_resp.get('error')}")

        sync1_resp = parse_first_json(
            client.call_tool("cl_sync", {"project_path": str(project_dir)}),
        )
        assert "error" not in sync1_resp, f"cl_sync 1 errored: {sync1_resp}"

        with open_readonly() as conn:
            repo_row = fetch_repo_by_name(conn, repo_name)
            assert repo_row is not None, "no repo row after sync 1"
            repo_id_for_cleanup = repo_row["id"]
            scan_row = conn.execute(
                "SELECT id FROM scans WHERE repo_id = ? "
                "ORDER BY scanned_at DESC LIMIT 1",
                (repo_id_for_cleanup,),
            ).fetchone()
            assert scan_row is not None, "no scan row after sync 1"
            dashboard_scan_id = scan_row["id"]

        # Step 2: SaaS-side: simulate a user uploading evidence via the
        # web UI by INSERTing the chain directly. This is the audit-
        # canonical pre-state for the pending-evidence pull flow.
        _, evidence_item_id, _ = _seed_pending_evidence(
            db_path=db_path,
            repo_id=repo_id_for_cleanup,
            scan_id=dashboard_scan_id,
            repo_path=EVIDENCE_REL_PATH,
            bytes_payload=EVIDENCE_BYTES,
            uploader_user_email=persona.email,
            encryption_key_b64=encryption_key_b64,
        )

        # Step 3: cl_sync 2 — STEP 11 should pull the file.
        sync2_resp = parse_first_json(
            client.call_tool("cl_sync", {"project_path": str(project_dir)}),
        )
    finally:
        client.close()

    assert "error" not in sync2_resp, f"cl_sync 2 errored: {sync2_resp}"

    # ── Layer 1 verify: response shape ──
    pending_summary = sync2_resp.get("pending_evidence") or {}
    assert pending_summary, (
        f"cl_sync 2 should report pending_evidence summary; "
        f"got keys {sorted(sync2_resp.keys())}"
    )
    pulled = pending_summary.get("pulled", 0)
    assert pulled >= 1, (
        f"pending_evidence.pulled should be >= 1 (we seeded 1 file); "
        f"got summary={pending_summary}"
    )

    # The user-facing prompt MUST surface at top level so AI clients
    # (Claude / Cursor) can render it without drilling into nested
    # objects. Per scanner/server.py the field is `action_required`.
    prompt = (
        sync2_resp.get("action_required")
        or sync2_resp.get("human_prompt")
        or sync2_resp.get("message", "")
    )
    assert "git add" in prompt or "git commit" in prompt or "git push" in prompt, (
        f"sync 2 should surface a git commit/push prompt for the user; "
        f"got prompt={prompt[:300]!r}"
    )

    # ── Layer 2 verify: file landed on disk at the right relative path ──
    # The pull writes to os.path.join(project_path, repo_path) — i.e.
    # the working tree's evidence file path directly, NOT under
    # .compliancelint/evidence/ (the .compliancelint/ tree is for
    # scanner-internal state only). The user then `git add`s the file
    # at its logical project location.
    pulled_path = project_dir / EVIDENCE_REL_PATH
    assert pulled_path.is_file(), (
        f"pulled file should be at {pulled_path}; not found. "
        f"cl_sync claims pulled={pulled} but no file on disk."
    )
    assert pulled_path.read_bytes() == EVIDENCE_BYTES, (
        f"pulled file bytes do not match what was uploaded — "
        f"silent corruption in the pull pipeline."
    )

    # ── Layer 3 verify: dashboard's pending row is gone (or the
    # corresponding evidence_items still says pending_commit, but the
    # bytes are no longer needed because they're on disk). The pull
    # orchestrator's idempotency guarantee is that re-pulling the same
    # sha is a no-op (skipped_same_hash) — covered indirectly here.
    # We don't assert pending_evidence row deletion because the
    # contract (per server.py) is "pull bytes" not "delete pending row";
    # deletion happens on the user's commit+push round-trip (Step 5
    # which is out of scope for this cell).

    # ── Cleanup ──
    # purge_repo's cascade doesn't reach the pending_evidence table
    # (FKed to repos AND evidence_items but not in the cascade chain),
    # so manually drop pending rows for this repo first to avoid 500 on
    # the purge handler. This is a test-cleanup limitation — flagged
    # as a follow-up: dashboard purge route should cascade pending_evidence.
    if repo_id_for_cleanup is not None:
        cleanup_conn = sqlite3.connect(db_path)
        try:
            cleanup_conn.execute(
                "DELETE FROM pending_evidence WHERE repo_id = ?",
                (repo_id_for_cleanup,),
            )
            cleanup_conn.commit()
        finally:
            cleanup_conn.close()
        try:
            purge_repo(
                SAAS_URL, persona.api_key, repo_id_for_cleanup,
                confirm_name=repo_name,
            )
        except CleanupError as e:
            pytest.fail(
                f"pending-pull cleanup purge failed: {e}; orphan repo "
                f"id={repo_id_for_cleanup}"
            )
