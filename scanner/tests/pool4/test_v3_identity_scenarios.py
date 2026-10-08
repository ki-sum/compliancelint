"""Pool 4 — §16 v3 identity scenarios through the real MCP scanner + SaaS + DB (acceptance run E, 2026-10-07).

Automates the pre-launch manual QA scenarios §16.1-16.3 (previously manual). The dashboard's own tests pin the
scan-settings response for Anna / Bob / the invariant guard; this cell checks the three layers together: the wizard
answers on the repo profile → cl_scan_all fetches /scan-settings → cl_sync → the findings in DB.

Flow per scenario (test-pro persona, a throwaway repo):
  1. cl_scan_all (full answers template, high-risk scope) + cl_sync — creates the repo and caches its repo_id
  2. the wizard answers written to repo_profiles (what the Profiling Wizard's Save stores; the wizard UI itself is
     covered by the dashboard's tests)
  3. cl_scan_all + cl_sync again — the scanner applies the SaaS settings
  4. the latest scan's ART26 / ART27 / ART86 findings in DB

  Anna (§16.1): identity deployer, high-risk deployer No  → no applicable Art 26/27/86 finding
  Bob  (§16.2): identity deployer, high-risk deployer Yes → Art 26/27/86 findings present
  PM   (§16.3): product manufacturer, Annex I No, not Annex III → Chapter III (Art 8-22) still applicable (Art 25(3))
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest

from .cleanup import purge_repo
from .fixtures import PERSONAS
from .mcp_client import McpStdioClient, parse_first_json
from .saas_introspection import DB_PATH_ENV, open_readonly

SAAS_URL = "http://localhost:3000"

ANNA = {"roles": '["deployer"]', "is_deployer": 1, "is_high_risk_deployer": 0}
BOB = {"roles": '["deployer"]', "is_deployer": 1, "is_high_risk_deployer": 1, "annex_iii_category": "annex_iii_pt4_employment"}
PM = {"roles": '["provider"]', "is_product_manufacturer": 1, "is_deployer": 0, "is_importer": 0, "is_distributor": 0,
      "is_authorised_representative": 0, "is_annex_i_product": 0, "annex_iii_category": "not_annex_iii"}


def _context(client: McpStdioClient, project: Path) -> str:
    analyze = parse_first_json(client.call_tool("cl_analyze_project", {"project_path": str(project)}, timeout=120.0))
    answers = analyze["compliance_answers_template"]
    answers["_scope"].update({
        "is_ai_system": True, "risk_classification": "high-risk", "risk_classification_confidence": "high",
        "territorial_scope_applies": True, "is_open_source": False, "is_military_defense": False,
        "is_research_only": False,
    })
    return json.dumps({"framework": "python", "stack": ["python"], "compliance_answers": answers})


def _scan_and_sync(client: McpStdioClient, project: Path, context: str) -> dict:
    scan = parse_first_json(client.call_tool("cl_scan_all", {"project_path": str(project), "project_context": context,
                                                              "ai_provider": "pool4-v3-identity"}, timeout=900.0))
    assert "error" not in scan, scan
    sync = json.loads(client.call_tool("cl_sync", {"project_path": str(project)}, timeout=600.0))
    assert sync.get("status") == "synced", sync
    return sync


def _set_profile(db_path: str, repo_id: str, fields: dict) -> None:
    with sqlite3.connect(db_path) as conn:
        if not conn.execute("SELECT 1 FROM repo_profiles WHERE repo_id = ?", (repo_id,)).fetchone():
            conn.execute("INSERT INTO repo_profiles (id, repo_id) VALUES (?, ?)", (f"prof-{repo_id}", repo_id))
        sets = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE repo_profiles SET {sets} WHERE repo_id = ?", (*fields.values(), repo_id))
        conn.commit()


def _latest_findings(db_path: str, repo_id: str) -> dict[str, str]:
    with open_readonly(Path(db_path)) as conn:
        scan = conn.execute(
            "SELECT id FROM scans WHERE repo_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1", (repo_id,),
        ).fetchone()
        rows = conn.execute("SELECT obligation_id, status FROM findings WHERE scan_id = ?", (scan[0],)).fetchall()
        return {r[0]: str(r[1]).upper() for r in rows}


def _run(tmp_path: Path, profile: dict, scenario: str) -> tuple[str, dict[str, str], dict]:
    import os
    db_path = os.environ.get(DB_PATH_ENV)
    if not db_path:
        pytest.skip(f"{DB_PATH_ENV} not set")
    persona = PERSONAS["pro"]
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("def handler(request):\n    return model.predict(request)\n", encoding="utf-8")
    repo_name = f"test-pro/pool4-v3-{scenario}-{int(time.time() * 1000) % 1_000_000_000}"
    (project / ".compliancelintrc").write_text(json.dumps({
        "repo_name": repo_name, "saas_url": SAAS_URL, "saas_api_key": persona.api_key,
        "attester_name": "Pool 4 v3", "attester_email": "pool4-v3@test.invalid",
    }), encoding="utf-8")
    client = McpStdioClient.spawn(handshake_timeout=120.0)
    repo_id = ""
    try:
        context = _context(client, project)
        repo_id = _scan_and_sync(client, project, context).get("repo_id", "")
        assert repo_id, "first cl_sync did not resolve the repo id"
        _set_profile(db_path, repo_id, profile)
        _scan_and_sync(client, project, context)
        # The rescan must have used the dashboard settings — otherwise the assertions below read the first scan.
        saved = json.loads((project / ".compliancelint" / "local" / "last_context.json").read_text(encoding="utf-8"))
        assert saved["compliance_answers"]["_scope"].get("_saas_settings_active") is True, "rescan ignored the dashboard settings"
        settings = json.loads(
            __import__("urllib.request").request.urlopen(
                __import__("urllib.request").request.Request(
                    f"{SAAS_URL}/api/v1/repos/{repo_id}/scan-settings",
                    headers={"Authorization": f"Bearer {persona.api_key}"},
                ),
                timeout=10,
            ).read().decode("utf-8")
        )
        return repo_id, _latest_findings(db_path, repo_id), settings
    finally:
        client.close()
        if repo_id:
            purge_repo(SAAS_URL, persona.api_key, repo_id, confirm_name=repo_name)


def _articles(settings: dict) -> set[int]:
    """scan-settings lists applicable articles as "art26"-style keys."""
    return {int("".join(ch for ch in a if ch.isdigit())) for a in settings.get("applicable_articles") or []}


def _applicable(findings: dict[str, str], *prefixes: str) -> list[str]:
    return [o for o, s in findings.items()
            if o.startswith(prefixes) and "NOT-APPLICABLE" not in o and s != "NOT_APPLICABLE"]


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_anna_deployer_not_high_risk(tmp_path, server_reachable, seeded_users_present):
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")
    _, findings, settings = _run(tmp_path, ANNA, "anna")
    assert settings["is_deployer"] is False
    assert not {26, 27, 86} & _articles(settings)
    assert _applicable(findings, "ART26-", "ART27-", "ART86-") == []


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_bob_high_risk_deployer(tmp_path, server_reachable, seeded_users_present):
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")
    _, findings, settings = _run(tmp_path, BOB, "bob")
    assert settings["is_deployer"] is True
    assert {26, 27, 86} <= _articles(settings)
    assert _applicable(findings, "ART26-"), "Bob (high-risk deployer) must get Art 26 findings"


@pytest.mark.requires_dev_server
@pytest.mark.requires_seeded_users
def test_product_manufacturer_keeps_chapter_iii(tmp_path, server_reachable, seeded_users_present):
    if not server_reachable or not seeded_users_present:
        pytest.skip("server :3000 or seeded users not ready")
    _, findings, settings = _run(tmp_path, PM, "pm")
    assert settings.get("is_product_manufacturer") is True
    assert set(range(8, 23)) <= _articles(settings)
    assert _applicable(findings, "ART09-"), "a product manufacturer is a provider under Art 25(3): Art 9 applies"
