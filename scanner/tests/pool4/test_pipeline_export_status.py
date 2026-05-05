"""Pool 4 — pipeline-export-status via real MCP cl_sync + dashboard /export.

End-to-end coverage for the Compliance All-in-One Pack export endpoint
(POST /api/v1/repos/<id>/export). Today's existing coverage:
  - The internal dashboard e2e-time-capsule Playwright spec uses
    PRE-SEEDED data from seed-demo. It doesn't trigger cl_sync to
    create the data; if cl_sync's payload format ever drifts from
    what seed-demo writes, that test stays green but real exports
    break silently.

What this cell adds (audit-first, true 3-layer):
  - cl_sync (real MCP) creates the repo + scan + findings via
    real /api/v1/scans payload — same shape a customer would send
  - Direct POST /api/v1/repos/<id>/export → application/zip
  - Python zipfile parses the response, asserts:
      * the zip is well-formed
      * contains at least one PDF (the actual report)
      * the PDF bytes start with the PDF magic header (`%PDF-`)
      * the manifest entry exists for cross-checking the contents
    These pin the export-bundle contract end-to-end so a future
    refactor that breaks zip assembly (missing PDF, wrong file order,
    truncated bytes) surfaces here.

Setup nuances:
  - Export gate requires the repo_profile to declare role=provider
    (per Art 47 Declaration of Conformity). seed-demo's repos have
    this preset; for our fresh tmp_path-derived repo we INSERT a
    repo_profiles row directly with roles=["provider"] before POSTing
    /export. Mirrors what dashboard wizard onboarding would write.
  - Tier gate: export is Business+ only. Cell uses test-business
    persona which seed-demo provisions with plan='business'.
  - Format defaults to "pdf-zip"; we send it explicitly to pin the
    request contract.

Per Pool 4 hard constraints:
  - C1: real MCP subprocess (default cwd=REPO_ROOT)
  - C2: live :3000 prod server
  - C3: real seeded test-business persona
  - C7: tmp_path Pattern B (no manual-fixture drift)
  - C8: purge_repo + tmp_path; pre-seeded repo_profile cascades

Verified-via: scanner/server.py cl_sync POST /api/v1/scans + the SaaS
POST /api/v1/repos/<id>/export route handler's pdf-zip assembly
pipeline + the lib/export-manifest-builder.
"""
from __future__ import annotations

import io
import json
import os
import sqlite3
import subprocess
import time
import urllib.request
import uuid
import zipfile
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


def _git_init(project_dir: Path) -> str:
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
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], **flags,
    ).stdout.strip()


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


def _ensure_provider_repo_profile(db_path: str, repo_id: str) -> None:
    """The export endpoint requires the repo_profile to declare
    role=provider (Art 47 DoC duty). Seed an explicit row so the cell
    doesn't depend on whether cl_sync auto-creates the profile.
    Idempotent: replaces row if already present.
    """
    conn = sqlite3.connect(db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM repo_profiles WHERE repo_id = ?",
            (repo_id,),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE repo_profiles SET roles = ? WHERE repo_id = ?",
                (json.dumps(["provider"]), repo_id),
            )
        else:
            conn.execute(
                """INSERT INTO repo_profiles
                     (id, repo_id, roles, system_name, intended_purpose,
                      risk_classification)
                   VALUES (?, ?, ?, 'Pool 4 Test System',
                           'End-to-end test artifact for export cell',
                           'high-risk')""",
                (str(uuid.uuid4()), repo_id, json.dumps(["provider"])),
            )
        conn.commit()
    finally:
        conn.close()


def _post_export(repo_id: str, scan_id: str, api_key: str) -> tuple[int, bytes, dict]:
    """POST /api/v1/repos/<id>/export. Returns (status, body, headers).
    Body is raw bytes (zip on success, JSON on error).
    """
    payload = json.dumps({"scan_id": scan_id, "format": "pdf-zip"}).encode("utf-8")
    req = urllib.request.Request(
        f"{SAAS_URL}/api/v1/repos/{repo_id}/export",
        method="POST",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_pipeline_export_status_round_trip_via_real_mcp(
    tmp_path: Path,
    server_reachable: bool,
    seeded_users_present: bool,
) -> None:
    """End-to-end: cl_sync (real MCP) → dashboard scan rows → POST
    /export → application/zip → unzip → assert PDF + manifest."""
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")

    db_path = os.environ.get(DB_PATH_ENV)
    if not db_path:
        pytest.skip(f"{DB_PATH_ENV} not set")

    persona = PERSONAS["business"]
    suffix = str(int(time.time() * 1000) % 1_000_000_000)
    repo_name = f"test-business/pool4-export-{suffix}"

    project_dir = tmp_path / "fixture"
    project_dir.mkdir()
    _git_init(project_dir)

    (project_dir / ".compliancelintrc").write_text(
        json.dumps({
            "purpose": "Pool 4 export-status fixture",
            "repo_name": repo_name,
            "saas_url": SAAS_URL,
            "saas_api_key": persona.api_key,
            "scope": {
                "operator_role": ["provider"],
                "risk_classification": "high-risk",
            },
            "attester_name": "Pool 4 Export Test",
            "attester_email": "pool4-export@test.invalid",
        }, indent=2),
        encoding="utf-8",
    )

    repo_id_for_cleanup: str | None = None
    # IMPORTANT: omit cwd= so spawn() defaults to REPO_ROOT — same
    # lesson as the broken_link cell.
    client = McpStdioClient.spawn()
    try:
        project_context_json = _build_synthetic_context(client, project_dir)
        scan_resp = parse_first_json(client.call_tool("cl_scan", {
            "project_path": str(project_dir),
            "project_context": project_context_json,
            "articles": "9",
            "ai_provider": "Pool4 Export Synthetic",
        }))
        if "error" in scan_resp:
            pytest.skip(f"cl_scan rejected synthetic context: {scan_resp.get('error')}")

        sync_resp = parse_first_json(
            client.call_tool("cl_sync", {"project_path": str(project_dir)}),
        )
        assert "error" not in sync_resp, f"cl_sync errored: {sync_resp}"
    finally:
        client.close()

    # Resolve repo_id + scan_id via DB.
    with open_readonly() as conn:
        repo_row = fetch_repo_by_name(conn, repo_name)
        assert repo_row is not None, f"no repo row for {repo_name!r}"
        repo_id_for_cleanup = repo_row["id"]
        scan_row = conn.execute(
            "SELECT id FROM scans WHERE repo_id = ? "
            "ORDER BY scanned_at DESC LIMIT 1",
            (repo_id_for_cleanup,),
        ).fetchone()
        assert scan_row is not None, "no scan row after sync"
        dashboard_scan_id = scan_row["id"]

    # Pre-seed repo_profile with roles=["provider"] so the export gate
    # passes. Mirrors what dashboard wizard onboarding writes.
    _ensure_provider_repo_profile(db_path, repo_id_for_cleanup)

    # POST /export.
    status, body, headers = _post_export(
        repo_id=repo_id_for_cleanup,
        scan_id=dashboard_scan_id,
        api_key=persona.api_key,
    )

    try:
        assert status == 200, (
            f"POST /export expected 200; got {status}. Body head: "
            f"{body[:300]!r}"
        )

        # Content-Type must be zip.
        ctype = headers.get("Content-Type") or headers.get("content-type") or ""
        assert "application/zip" in ctype.lower() or "zip" in ctype.lower(), (
            f"Content-Type should indicate zip; got {ctype!r}"
        )

        # The body should be a valid zip.
        try:
            zf = zipfile.ZipFile(io.BytesIO(body))
        except zipfile.BadZipFile as e:
            pytest.fail(
                f"export body is not a valid zip: {e}. "
                f"Body head: {body[:200]!r}"
            )

        names = zf.namelist()
        assert names, "zip is empty"

        # At least one PDF inside (the report).
        pdfs = [n for n in names if n.lower().endswith(".pdf")]
        assert pdfs, (
            f"export zip should contain at least 1 PDF report; "
            f"got entries: {names}"
        )

        # Verify the PDF bytes start with the PDF magic header.
        # If the assembly pipeline ever truncates or wraps the PDF in
        # plain text, this catches it before the user opens a 0-byte
        # report in Acrobat.
        pdf_bytes = zf.read(pdfs[0])
        assert pdf_bytes.startswith(b"%PDF-"), (
            f"first 8 bytes of {pdfs[0]!r} should be %PDF-... ; "
            f"got {pdf_bytes[:8]!r}"
        )
        assert len(pdf_bytes) > 1000, (
            f"PDF {pdfs[0]!r} is suspiciously small ({len(pdf_bytes)} "
            f"bytes); probably a placeholder, not a real export"
        )

        # Verify the zip carries something resembling a manifest. The
        # exact filename varies (manifest.json / EXPORT_MANIFEST.json
        # / similar); accept any *.json with 'manifest' in the name.
        manifests = [
            n for n in names
            if n.lower().endswith(".json") and "manifest" in n.lower()
        ]
        assert manifests, (
            f"export zip should contain a manifest .json; got entries: {names}"
        )

        # Manifest must carry the load-bearing fields that downstream
        # consumers (audit reviewer / signing pipeline / EU regulator
        # PDF cross-check) rely on. Audit-first observation 2026-05-05:
        # the actual manifest schema (per lib/export-manifest-builder)
        # uses these keys:
        #   articles / generated_at / version / snapshot / format /
        #   bundle_format_version / phase / disclaimer / signing /
        #   watermark / generator / include_*
        # Pinning a small subset here so a future refactor that drops
        # one of these surfaces immediately.
        manifest_data = json.loads(zf.read(manifests[0]).decode("utf-8"))
        manifest_keys = set(manifest_data.keys())
        required_keys = {
            "version",            # bundle compat marker
            "generated_at",       # audit timestamp
            "articles",           # the actual scan content
            "format",             # pdf-zip / oscal / etc.
            "bundle_format_version",  # contract version
        }
        missing = required_keys - manifest_keys
        assert not missing, (
            f"manifest missing load-bearing fields: {sorted(missing)}. "
            f"Got keys: {sorted(manifest_keys)}"
        )

        # The articles array must be a non-empty list.
        articles = manifest_data.get("articles")
        assert isinstance(articles, list) and len(articles) > 0, (
            f"manifest.articles should be a non-empty list; "
            f"got {type(articles).__name__}: {articles!r}"
        )

        # Format should be the one we requested.
        assert manifest_data.get("format") == "pdf-zip", (
            f"manifest.format should echo the request format pdf-zip; "
            f"got {manifest_data.get('format')!r}"
        )

        zf.close()
    finally:
        # ── Cleanup ──
        if repo_id_for_cleanup is not None:
            try:
                purge_repo(
                    SAAS_URL, persona.api_key, repo_id_for_cleanup,
                    confirm_name=repo_name,
                )
            except CleanupError as e:
                pytest.fail(
                    f"export cleanup purge failed: {e}; orphan repo "
                    f"id={repo_id_for_cleanup}"
                )
