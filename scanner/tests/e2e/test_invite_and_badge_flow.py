"""Cross-system flows 3 + 4.

From project_cross_system_test_design.md:
  3. "SaaS invite member → member runs cl_scan on shared repo → findings
      visible to both"
  4. "SaaS badge toggle → cl_sync updates badge status"

Flow 3 verifies the DATA-visibility cross-system contract: after owner
syncs a scan, a user with `member` role on that specific repo sees the
same findings, while a non-member gets 403/404. We grant member role
via repo_access INSERT (not via the invite UI — that's a web flow
already covered by dashboard e2e).

Flow 4 toggles public_badge on the repos row and verifies the public
badge endpoint /api/v1/badge/{id} respects it. No auth on the badge
route — that's the public-embed design point. The cross-system claim
is that owner action on SaaS propagates to the anonymous badge consumer.

Isolation (v6 reviewer B4, 2026-04-23): uses `isolated_project` fixture
so each test creates a brand-new repo via cl_sync. Canonical test-pro
repo is never touched. Test 1 adds a repo_access row for the test-pro-
invited member on the isolated repo (cleaned up by the fixture's
cascade-delete on repos.id).
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import uuid
from pathlib import Path

import pytest

from _e2e_consts import API_KEY, DB_PATH, PROJECT, SAAS

pytestmark = pytest.mark.live_dashboard

MEMBER_API_KEY = "cl_test_pro_invited_key_for_development"
MEMBER_EMAIL = "test-pro-invited@compliancelint.dev"


def _curl(
    method: str,
    url: str,
    *,
    api_key: str | None = None,
    body: dict | None = None,
    timeout: int = 15,
) -> tuple[int, str]:
    """Run curl, return (http_code, body_str)."""
    cmd = [
        "curl",
        "-sS",
        "-X",
        method,
        url,
        "--max-time",
        str(timeout),
        "-o",
        "-",
        "-w",
        "\n%{http_code}",
    ]
    if api_key:
        cmd += ["-H", f"Authorization: Bearer {api_key}"]
    if body is not None:
        cmd += [
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps(body),
        ]
    r = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout + 5
    )
    if r.returncode != 0:
        raise AssertionError(f"curl {method} {url} rc={r.returncode}: {r.stderr[:200]!r}")
    out = r.stdout.rstrip()
    lines = out.rsplit("\n", 1)
    body_str = lines[0] if len(lines) > 1 else ""
    code = int(lines[-1]) if lines[-1].isdigit() else 0
    return code, body_str


def _grant_member_access(repo_id: str, member_email: str) -> None:
    """INSERT a repo_access row granting `member_email` member role on repo.

    Cleanup piggybacks on isolated_project's cascade (DELETE FROM repo_access
    WHERE repo_id = ?) — no explicit revoke needed here.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        user_row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (member_email,)
        ).fetchone()
        if not user_row:
            raise AssertionError(
                f"seed-demo should provide {member_email}; re-run seed-demo.ts"
            )
        conn.execute(
            "INSERT INTO repo_access (id, repo_id, user_id, role) "
            "VALUES (?, ?, ?, 'member')",
            (str(uuid.uuid4()), repo_id, user_row[0]),
        )
        conn.commit()
    finally:
        conn.close()


def _set_public_badge(repo_id: str, enabled: bool) -> None:
    """Toggle public_badge directly in DB.

    PUT /api/v1/repos/{id} is the dashboard-UI path but enforces cookie
    CSRF on a cookie-session (bearer is accepted too). Direct DB write
    is sufficient to prove the badge route consumes the flag — we're
    testing propagation, not the toggle UI itself.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE repos SET public_badge = ? WHERE id = ?",
            (1 if enabled else 0, repo_id),
        )
        conn.commit()
    finally:
        conn.close()


def _write_synthetic_art9(project_path: str, findings: list[dict]) -> None:
    art_dir = os.path.join(project_path, ".compliancelint", "articles")
    Path(art_dir).mkdir(parents=True, exist_ok=True)
    findings_dict = {
        f["obligation_id"]: {
            "obligation_id": f["obligation_id"],
            "level": f["level"],
            "description": f["description"],
            "source_quote": f.get("source_quote", ""),
            "status": "open",
            "history": [],
            "evidence": [],
        }
        for f in findings
    }
    with open(os.path.join(art_dir, "art9.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "article": 9,
                "last_scan": "2026-04-22T12:00:00+00:00",
                "findings": findings_dict,
                "regulation": "eu-ai-act",
            },
            fh,
            indent=2,
        )


# ═════════════════════════════════════════════════════════════════════
# Flow 3 — member sees the same scan + findings the owner synced
# ═════════════════════════════════════════════════════════════════════


def test_invited_member_sees_same_scan_findings_as_owner(
    server_module, isolated_project, with_remote, log
):
    """Owner cl_syncs a scan on isolated repo; granted member GET /scans/{id}
    sees identical findings."""
    # Owner pushes a synthetic scan onto the isolated repo.
    marker = uuid.uuid4().hex[:8]
    _write_synthetic_art9(
        PROJECT,
        [
            {
                "obligation_id": f"ART09-SHARED-{marker}",
                "level": "non_compliant",
                "description": f"shared-visibility test {marker}",
                "source_quote": "stub",
            }
        ],
    )
    sync_result = json.loads(server_module.cl_sync(PROJECT, regulation=""))
    assert "error" not in sync_result, sync_result
    scan_id = sync_result.get("scan_id") or sync_result.get("scanId")
    assert scan_id

    repo_id = isolated_project["repo_id_getter"]()
    assert repo_id

    # Grant member role on this isolated repo to test-pro-invited. Fixture
    # teardown's cascade-delete on repo_access WHERE repo_id = ? cleans up.
    _grant_member_access(repo_id, MEMBER_EMAIL)

    # Owner view.
    owner_code, owner_body = _curl(
        "GET",
        f"{SAAS}/api/v1/repos/{repo_id}/scans/{scan_id}",
        api_key=API_KEY,
    )
    assert owner_code == 200, f"owner GET /scans/{scan_id} → {owner_code}"
    owner_findings = (json.loads(owner_body).get("findings") or [])
    owner_oids = {
        f.get("obligationId") for f in owner_findings if marker in (f.get("obligationId") or "")
    }
    assert owner_oids == {f"ART09-SHARED-{marker}"}

    # Member view — same repo_id, same scan_id, different API key.
    member_code, member_body = _curl(
        "GET",
        f"{SAAS}/api/v1/repos/{repo_id}/scans/{scan_id}",
        api_key=MEMBER_API_KEY,
    )
    assert member_code == 200, (
        f"member GET /scans/{scan_id} → {member_code} (expected 200 — "
        f"test-pro-invited is a member of this repo). body={member_body[:200]!r}"
    )
    member_findings = (json.loads(member_body).get("findings") or [])
    member_oids = {
        f.get("obligationId") for f in member_findings if marker in (f.get("obligationId") or "")
    }
    # Strict contract: member MUST see the owner's synced findings.
    assert member_oids == owner_oids, (
        f"member view diverges from owner: {member_oids} != {owner_oids}"
    )

    # Non-member (free user key) MUST NOT see the scan.
    non_member_code, _ = _curl(
        "GET",
        f"{SAAS}/api/v1/repos/{repo_id}/scans/{scan_id}",
        api_key="cl_test_free_key_for_development",
    )
    assert non_member_code in (403, 404), (
        f"non-member got {non_member_code} — should be 403/404"
    )

    log.info(
        "invited member flow OK: owner=%d, member=%d, non-member=%d on isolated repo %s",
        owner_code, member_code, non_member_code, repo_id,
    )
    # isolated_project teardown cascades repo + repo_access + scans + findings.


# ═════════════════════════════════════════════════════════════════════
# Flow 4 — public_badge toggle propagates to anonymous /badge GET
# ═════════════════════════════════════════════════════════════════════


def test_badge_endpoint_respects_public_badge_toggle_after_cl_sync(
    server_module, isolated_project, with_remote, log
):
    """public_badge off → 404 'not found'; on + scan → 200 SVG;
    back to off → 404 again."""
    # Create the isolated repo by syncing an all-compliant scan first.
    marker = uuid.uuid4().hex[:8]
    _write_synthetic_art9(
        PROJECT,
        [
            {
                "obligation_id": f"ART09-BADGE-{marker}",
                "level": "compliant",
                "description": f"badge-flow test {marker}",
                "source_quote": "stub",
            }
        ],
    )
    sync_result = json.loads(server_module.cl_sync(PROJECT, regulation=""))
    assert "error" not in sync_result, sync_result
    scan_id = sync_result.get("scan_id") or sync_result.get("scanId")
    assert scan_id
    repo_id = isolated_project["repo_id_getter"]()
    assert repo_id

    badge_url = f"{SAAS}/api/v1/badge/{repo_id}"

    # Default (just-created): public_badge defaults to 0 per schema.
    # Verify 404 "not found" SVG before any toggle.
    _set_public_badge(repo_id, enabled=False)
    code_off, svg_off = _curl("GET", badge_url)
    assert code_off == 404, f"expected 404 when badge disabled, got {code_off}"
    assert "not found" in svg_off, (
        f"disabled-badge SVG should contain 'not found' literal, got {svg_off[:300]!r}"
    )

    # Enable → 200 SVG reflecting the synced scan.
    _set_public_badge(repo_id, enabled=True)
    code_on, svg_on = _curl("GET", badge_url)
    assert code_on == 200, (
        f"expected 200 when badge enabled + repo has scans, got {code_on}: {svg_on[:200]!r}"
    )
    assert "<svg" in svg_on, "enabled-badge payload should be an SVG"
    assert "not found" not in svg_on, (
        "enabled-badge must not render the 'not found' fallback"
    )

    # Disable again → back to 404 — proves the toggle truly gates.
    _set_public_badge(repo_id, enabled=False)
    code_off_2, svg_off_2 = _curl("GET", badge_url)
    assert code_off_2 == 404, (
        f"expected 404 after disabling, got {code_off_2}"
    )
    assert "not found" in svg_off_2

    log.info(
        "badge toggle flow OK on isolated repo %s: off=%d → on=%d → off=%d",
        repo_id, code_off, code_on, code_off_2,
    )
    # isolated_project teardown cascades.
