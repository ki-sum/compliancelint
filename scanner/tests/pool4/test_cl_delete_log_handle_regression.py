"""Pool 4 — cl_delete BUG-1 regression via real MCP transport.

The original BUG-1 (commit ``02cb86b``, 2026-04-24): a long-running MCP
process called ``cl_scan`` (or any tool that hits
``get_scanner_logger(project_path)``), attaching a
``RotatingFileHandler`` to ``scanner.log`` inside the project's
``.compliancelint/logs/``. A subsequent ``cl_delete`` target=local in
the same MCP process tried to ``shutil.rmtree`` that very directory and
crashed with ``PermissionError: [WinError 32] sharing violation`` on
Windows because the handler still owned the file.

The fix had two parts:

  1. ``scanner_log._resolve_log_dir`` was relocated outside the project
     tree to ``~/.compliancelint/logs/{sha256(abs_path)[:16]}/`` so an
     ``rmtree`` on the project ``.compliancelint/`` can never reach an
     open log handle.
  2. ``cl_delete`` calls ``close_scanner_logger(project_path)`` BEFORE
     ``rmtree`` so the home-side log directory can also be removed.

Existing in-process unit coverage (``scanner/tests/test_cl_delete.py``
``test_delete_works_after_real_cl_scan_without_monkeypatch`` +
``test_scanner_log_lives_outside_project_tree``) exercises the fix from
inside the same Python process. The gap this Pool 4 cell closes:
**real MCP stdio subprocess transport**. Same scanner version, same
logger module, but the calls go through JSON-RPC over stdio — exactly
the path a Claude Code session takes. If a future refactor breaks the
subprocess-side logger lifecycle (e.g. spawn-time global hooks that
short-circuit ``close_scanner_logger``), the unit tests stay green and
only this cell fails RED.

Setup:
  1. tmp_path with a fresh project (rc + a minimal evidence file so
     cl_scan has something to scan).
  2. Single ``McpStdioClient`` reused across the cell — both cl_scan
     AND cl_delete must run in the SAME subprocess so the logger state
     persists between them. ``mcp_client_session`` (session-scope) is
     intentionally NOT used: cl_delete is destructive and could leak
     state into sibling cells.
  3. Step 1: ``cl_scan`` with a synthetic context — triggers
     ``get_scanner_logger(project_path)`` server-side, attaches the
     ``RotatingFileHandler`` to the home-side log file.
  4. Sanity-check: home log dir exists and ``scanner.log`` is non-empty.
     Pre-fix this would already be a project-tree path; post-fix it's
     under ``Path.home()/.compliancelint/logs/{hash}/``.
  5. Step 2: ``cl_delete`` target=local, confirm=True. Server-side
     calls ``close_scanner_logger`` and ``rmtree``s both the project's
     ``.compliancelint/local/`` and the home-side log dir.
  6. Assertions:
       - response status is ``deleted`` (no error envelope)
       - response.results.local == ``deleted``
       - response.results.logs == ``deleted`` (post-fix the log dir
         was created and then removed)
       - project ``.compliancelint/local/`` is gone on disk
       - home log dir is gone on disk
       - ``.compliancelint/evidence/`` and ``.compliancelintrc`` are
         preserved (target=local contract)

Per Pool 4 hard constraints:
  - C1: real MCP subprocess (default ``cwd=REPO_ROOT``)
  - C2: NOT required — cl_delete target=local is scanner-side only,
    no SaaS dependency. No ``requires_dev_server`` marker.
  - C3: persona moot for target=local (no SaaS calls). No
    ``requires_seeded_users`` marker.
  - C7: tmp_path Pattern B
  - C8: tmp_path auto-cleanup; the home log dir is removed by
    cl_delete itself (the load-bearing assertion of this cell)

Verified-via: scanner/server.py:cl_delete (target=local branch) +
scanner/core/scanner_log.py:close_scanner_logger + the logger-attach
side effect inside ``cl_scan``.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from .mcp_client import McpStdioClient, parse_first_json


def _project_hash(project_path: str) -> str:
    """Mirror scanner_log._project_hash so the cell can locate the
    expected home log dir without importing scanner internals."""
    abs_path = os.path.abspath(project_path)
    return hashlib.sha256(abs_path.encode("utf-8")).hexdigest()[:16]


def _expected_home_log_dir(project_path: str) -> Path:
    return Path.home() / ".compliancelint" / "logs" / _project_hash(project_path)


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


def test_cl_delete_target_local_after_real_scan_via_real_mcp(
    tmp_path: Path,
) -> None:
    """End-to-end BUG-1 regression: real MCP cl_scan attaches the file
    logger, real MCP cl_delete target=local must succeed without a
    Windows file-handle-busy error.
    """
    project_dir = tmp_path / "fixture"
    project_dir.mkdir()

    # Minimal evidence file so cl_scan has something to find.
    evidence_dir = project_dir / "controls"
    evidence_dir.mkdir()
    (evidence_dir / "risk-mgmt.md").write_text(
        "# Risk Management\n\nPlaceholder evidence for cl_scan to discover.\n",
        encoding="utf-8",
    )
    (project_dir / "README.md").write_text(
        "# Pool 4 BUG-1 fixture\n", encoding="utf-8",
    )

    # Pre-seed an evidence dir so we can verify target=local preserves it.
    audit_evidence_dir = project_dir / ".compliancelint" / "evidence"
    audit_evidence_dir.mkdir(parents=True)
    audit_marker = audit_evidence_dir / "audit-trail-marker.json"
    audit_marker.write_text(
        '{"committed_at": "2026-05-06"}', encoding="utf-8",
    )

    # rc with no SaaS binding so cl_scan stays local-only.
    (project_dir / ".compliancelintrc").write_text(
        json.dumps({
            "purpose": "Pool 4 BUG-1 regression fixture",
            "repo_name": "test/bug1-log-handle",
            "scope": {
                "operator_role": ["provider"],
                "risk_classification": "high-risk",
            },
        }, indent=2),
        encoding="utf-8",
    )

    expected_home_log_dir = _expected_home_log_dir(str(project_dir))
    # Pre-state: home log dir for this project should NOT exist yet
    # (tmp_path is unique per test invocation, so the hash is unique).
    assert not expected_home_log_dir.exists(), (
        f"unexpected pre-existing home log dir {expected_home_log_dir} — "
        f"hash collision or stale state from a prior run"
    )

    # IMPORTANT: do NOT pass cwd=project_dir — see sister cell rationale.
    # Default REPO_ROOT cwd loads the editable scanner with the BUG-1
    # fix (commit 02cb86b). A stale pip-installed copy might still have
    # the old in-tree log path and would silently REGRESS via the same
    # PermissionError the fix addressed.
    client = McpStdioClient.spawn()
    try:
        # ── Step 1: cl_scan triggers the server-side
        #    get_scanner_logger(project_path) — attaches a
        #    RotatingFileHandler on scanner.log inside the home log
        #    dir. Pre-fix this attached inside .compliancelint/logs/
        #    in the project tree, which made Step 2 fail.
        project_context_json = _build_synthetic_context(client, project_dir)
        scan_resp = parse_first_json(client.call_tool("cl_scan", {
            "project_path": str(project_dir),
            "project_context": project_context_json,
            "articles": "9",
            "ai_provider": "Pool4 BUG-1 Regression Synthetic",
        }))
        if "error" in scan_resp:
            pytest.skip(f"cl_scan rejected synthetic context: {scan_resp.get('error')}")

        # Sanity: post-scan, the home log dir exists and scanner.log
        # has at least one byte. Pre-fix this lived in the project
        # tree; post-fix it lives under Path.home(). Either way we
        # need a real, non-empty file before the rmtree test.
        assert expected_home_log_dir.is_dir(), (
            f"BUG-1 post-fix invariant: cl_scan must have created the "
            f"home log dir at {expected_home_log_dir}. Got nothing — "
            f"either the logger was not attached OR the fix regressed "
            f"and the log went back into the project tree."
        )
        scanner_log_path = expected_home_log_dir / "scanner.log"
        assert scanner_log_path.is_file(), (
            f"BUG-1 post-fix invariant: scanner.log must be at "
            f"{scanner_log_path} after cl_scan; got nothing"
        )
        assert scanner_log_path.stat().st_size > 0, (
            f"scanner.log at {scanner_log_path} is empty — cl_scan "
            f"completed but no log entries were written. Either the "
            f"handler attached at WARNING+ only, or cl_scan went silent."
        )

        # Sanity: log MUST NOT have leaked back into the project tree.
        # This is the load-bearing post-fix invariant from
        # test_scanner_log_lives_outside_project_tree.
        project_log_dir = project_dir / ".compliancelint" / "logs"
        assert not project_log_dir.exists(), (
            f"BUG-1 REGRESSED: scanner.log leaked into project tree at "
            f"{project_log_dir}. The relocate-to-home fix is broken."
        )

        # ── Step 2: cl_delete target=local in the SAME subprocess.
        # Pre-fix this raised WinError 32 sharing violation because the
        # RotatingFileHandler from Step 1 still owned the file inside
        # the rmtree target. Post-fix the log lives under home (fix 1)
        # and close_scanner_logger releases the handle (fix 2) before
        # rmtree. Either way the rmtree must succeed.
        delete_resp = parse_first_json(client.call_tool("cl_delete", {
            "project_path": str(project_dir),
            "target": "local",
            "confirm": True,
        }))
    finally:
        client.close()

    assert "error" not in delete_resp, (
        f"cl_delete target=local failed after a real cl_scan in the "
        f"same MCP subprocess — that's the BUG-1 signature. Response: "
        f"{delete_resp}"
    )
    assert delete_resp.get("status") == "deleted", (
        f"cl_delete should report status='deleted'; got "
        f"{delete_resp.get('status')!r}. Full response: {delete_resp}"
    )
    results = delete_resp.get("results") or {}
    assert results.get("local") == "deleted", (
        f"cl_delete results.local should be 'deleted'; got "
        f"{results.get('local')!r}. Full results: {results}"
    )
    # Logs key reflects the home-side log dir wipe. Post-fix this is
    # always populated (the dir was created in Step 1 above). Pre-fix
    # this key didn't exist (logs were in the project tree).
    assert results.get("logs") == "deleted", (
        f"cl_delete results.logs should be 'deleted' (home-side log "
        f"dir was wiped); got {results.get('logs')!r}. Full results: "
        f"{results}"
    )

    # ── Filesystem assertions ──
    local_dir = project_dir / ".compliancelint" / "local"
    assert not local_dir.exists(), (
        f"cl_delete claimed deletion but {local_dir} still exists with "
        f"files: {[p.name for p in local_dir.rglob('*') if p.is_file()][:5]}"
    )
    # Home log dir must also be gone (this is the assertion the fix
    # was specifically built to enable — pre-fix the rmtree would have
    # failed with WinError 32).
    assert not expected_home_log_dir.exists(), (
        f"home log dir {expected_home_log_dir} still exists after "
        f"cl_delete — the close_scanner_logger + rmtree path didn't "
        f"complete. On Windows this typically means the handle wasn't "
        f"released before the rmtree call (BUG-1 partial regression)."
    )

    # target=local contract: evidence dir + rc preserved.
    assert audit_evidence_dir.exists(), (
        f"target=local must preserve .compliancelint/evidence/ — "
        f"audit-trail data was lost"
    )
    assert audit_marker.exists(), (
        f"target=local removed audit-trail-marker.json from "
        f".compliancelint/evidence/; that violates the contract"
    )
    assert (project_dir / ".compliancelintrc").exists(), (
        ".compliancelintrc was deleted; target=local must preserve it"
    )
