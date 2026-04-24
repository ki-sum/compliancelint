"""Thin coverage for MCP tool cl_sync (server.py:1961).

cl_sync POSTs scan state to /api/v1/scans via subprocess curl. These tests
avoid the real dashboard by mocking subprocess.run with a dispatcher that:
  - treats any `git` invocation as a no-op (empty stdout, exit 0)
  - treats any `curl` invocation as a scripted fake (controlled status + body)

Per G1_HANDOFF §3.4 and §Tool 8: no real Anthropic API, no real dashboard.
No new pip deps — only stdlib unittest.mock-style monkeypatching.

Covers:
  - error: missing .compliancelintrc (no API key) returns typed error + fix
  - happy: POST payload contains project_id, repo, articles, first_commit_sha
  - error: dashboard 401 response surfaces invalid-key error, not a raise
"""
import json
import os
import subprocess
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def _seed_rc_with_saas(project_path, api_key="test-key-xyz"):
    rc = os.path.join(project_path, ".compliancelintrc")
    with open(rc, "w", encoding="utf-8") as f:
        json.dump({
            "saas_api_key": api_key,
            "saas_url": "https://dash.test.local",
            "project_id": "proj-fixture-abc",
            "repo_name": "acme/demo-repo",
            "attester_name": "Linus Torvalds",
            "attester_email": "linus@example.com",
        }, f)


def _seed_article_state(project_path, article_num=12, obligation_id="ART12-OBL-1"):
    art_dir = os.path.join(project_path, ".compliancelint", "articles")
    os.makedirs(art_dir, exist_ok=True)
    art_file = os.path.join(art_dir, f"art{article_num}.json")
    with open(art_file, "w", encoding="utf-8") as f:
        json.dump({
            "article": article_num,
            "last_scan": "2026-04-24T10:00:00+00:00",
            "findings": {
                obligation_id: {
                    "obligation_id": obligation_id,
                    "level": "non_compliant",
                    "description": "Seeded finding for cl_sync payload test",
                    "source_quote": "verbatim EUR-Lex stub",
                    "status": "open",
                    "history": [],
                    "evidence": [],
                },
            },
            "regulation": "eu-ai-act",
        }, f)


def _make_fake_run(scans_response, captured):
    """Build a subprocess.run stand-in.

    - `git` calls → exit 0 with empty stdout (real git may or may not exist;
      cl_sync treats None sha as acceptable).
    - `curl` calls → behaviour chosen by URL:
        * contains "/api/v1/scans" → `scans_response` dict controls status/body;
          captures the POSTed payload from the -d @<tmp> arg into `captured`.
        * contains "/api/v1/repos"  → status 200 with empty list (so the
          pending-evidence pull finds no matching repo and skips cleanly).
        * anything else             → 200 + empty body.
    """
    def fake_run(cmd, *args, **kwargs):
        if not isinstance(cmd, (list, tuple)) or not cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        head = cmd[0]

        if head == "git":
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        if head == "curl":
            url = next((c for c in cmd if isinstance(c, str) and c.startswith("http")), "")
            for i, arg in enumerate(cmd):
                if arg == "-d" and i + 1 < len(cmd):
                    raw = cmd[i + 1]
                    if isinstance(raw, str) and raw.startswith("@"):
                        with open(raw[1:], "r", encoding="utf-8") as fh:
                            captured["last_payload"] = json.load(fh)
                            captured["last_url"] = url
                    break

            if "/api/v1/scans" in url:
                body = scans_response["body"]
                status = scans_response["status"]
                return subprocess.CompletedProcess(
                    cmd, 0,
                    stdout=f"{body}\n{status}",
                    stderr="",
                )
            if "/api/v1/repos" in url:
                return subprocess.CompletedProcess(cmd, 0, stdout="[]\n200", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="\n200", stderr="")

        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    return fake_run


def test_sync_no_api_key_returns_typed_error(tmp_path):
    # No .compliancelintrc → config.saas_api_key is empty
    raw = server.cl_sync(str(tmp_path), regulation="")
    parsed = json.loads(raw)

    assert "error" in parsed, f"expected error, got: {parsed}"
    assert "No API key" in parsed["error"]
    assert "fix" in parsed
    assert "cl_connect" in parsed["fix"]


def test_sync_uploads_payload_with_expected_structure(tmp_path, monkeypatch):
    _seed_rc_with_saas(str(tmp_path))
    _seed_article_state(str(tmp_path))

    captured: dict = {}
    fake_scans = {
        "status": 200,
        "body": json.dumps({
            "scan_id": "scan-fake-42",
            "dashboard_url": "https://dash.test.local/dashboard/scans/scan-fake-42",
        }),
    }
    monkeypatch.setattr(subprocess, "run", _make_fake_run(fake_scans, captured))

    raw = server.cl_sync(str(tmp_path), regulation="")
    parsed = json.loads(raw)

    assert "error" not in parsed, f"cl_sync surfaced error: {parsed}"

    assert "last_payload" in captured, "fake curl never saw the /api/v1/scans POST"
    payload = captured["last_payload"]
    for key in ("project_id", "repo", "articles", "first_commit_sha", "scanner_version"):
        assert key in payload, f"payload missing {key}: keys={sorted(payload.keys())}"
    assert payload["project_id"] == "proj-fixture-abc"
    assert payload["repo"] == "acme/demo-repo"
    assert "art12" in payload["articles"], (
        f"seeded art12 not in payload articles: {list(payload['articles'].keys())}"
    )
    assert "ART12-OBL-1" in payload["articles"]["art12"]["findings"]
    assert "/api/v1/scans" in captured["last_url"]


def test_sync_handles_401_gracefully(tmp_path, monkeypatch):
    _seed_rc_with_saas(str(tmp_path), api_key="stale-key")
    _seed_article_state(str(tmp_path))

    captured: dict = {}
    fake_scans = {"status": 401, "body": ""}
    monkeypatch.setattr(subprocess, "run", _make_fake_run(fake_scans, captured))

    raw = server.cl_sync(str(tmp_path), regulation="")
    parsed = json.loads(raw)

    assert "error" in parsed, f"expected error on 401, got: {parsed}"
    assert "invalid or expired" in parsed["error"].lower()
    assert "cl_connect" in parsed["fix"]
