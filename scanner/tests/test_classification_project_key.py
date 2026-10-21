"""The classification metadata is fetched with the project's API key; cl_connect caches the plan.

Found on the production site (2026-10-21): classification_client read the API key only from
~/.compliancelint/config.json, which nothing writes — cl_connect stores the key in the project's .compliancelintrc.
So every connected scan ran in degraded mode since the classification metadata moved to the SaaS (May 2026):
cl_analyze_project said "No detection hints available … once this project is connected" for a connected project,
and findings read "Detection method: " with nothing after it. And the first cl_analyze_project after cl_connect said
tier "unconnected" / "Connect to Starter+" for a Business account: the plan was cached only from the first scan.
"""
import asyncio
import importlib.util
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core import classification_client, obligation_lookup  # noqa: E402
from core.config import ProjectConfig  # noqa: E402


@pytest.fixture
def no_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(classification_client, "CONFIG_PATH", tmp_path / "home" / "config.json")
    monkeypatch.setattr(classification_client, "CACHE_DIR", tmp_path / "home" / "classification-cache")
    classification_client.use_api_key(None)
    yield
    classification_client.use_api_key(None)


def _project(tmp_path, key="cl_project_key"):
    p = tmp_path / "proj"
    p.mkdir()
    (p / ".compliancelintrc").write_text(json.dumps({"saas_api_key": key, "repo_name": "proj"}), encoding="utf-8")
    return str(p)


def test_without_any_key_the_client_degrades(no_user_config):
    assert classification_client._load_api_key() is None


def test_loading_a_connected_project_gives_the_client_its_key(no_user_config, tmp_path):
    ProjectConfig.load(_project(tmp_path))
    assert classification_client._load_api_key() == "cl_project_key"


def test_the_user_config_key_still_wins(no_user_config, tmp_path):
    classification_client.CONFIG_PATH.parent.mkdir(parents=True)
    classification_client.CONFIG_PATH.write_text(json.dumps({"api_key": "cl_user_key"}), encoding="utf-8")
    ProjectConfig.load(_project(tmp_path))
    assert classification_client._load_api_key() == "cl_user_key"


def test_the_request_carries_the_project_key(no_user_config, tmp_path):
    ProjectConfig.load(_project(tmp_path))
    seen = {}

    class _Resp:
        status = 200
        headers = {"ETag": '"e1"'}

        def read(self):
            return json.dumps({"obligations": {"ART50-OBL-1": {"detection_method": "grep for a disclosure"}}}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        seen["auth"] = req.get_header("Authorization")
        return _Resp()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        got = classification_client.fetch_classifications(50)
    assert seen["auth"] == "Bearer cl_project_key"
    assert got == {"ART50-OBL-1": {"detection_method": "grep for a disclosure"}}


def test_an_index_built_without_a_key_is_rebuilt_once_a_key_arrives(no_user_config, tmp_path):
    obligation_lookup._OID_INDEX = {"ART50-OBL-1": {"_classification_unavailable": True}}
    ProjectConfig.load(_project(tmp_path))
    assert obligation_lookup._OID_INDEX is None  # rebuilt on next use, now with the key
    # the same key again does not throw the index away
    obligation_lookup._OID_INDEX = {"ART50-OBL-1": {"detection_method": "x"}}
    ProjectConfig.load(str(tmp_path / "proj"))
    assert obligation_lookup._OID_INDEX == {"ART50-OBL-1": {"detection_method": "x"}}
    obligation_lookup.reset_cache()


# ── cl_connect caches the plan from the register answer ───────────────

_spec = importlib.util.spec_from_file_location(
    "_server_test_project_key", os.path.join(SCANNER_ROOT, "server.py"), submodule_search_locations=[],
)
_server = importlib.util.module_from_spec(_spec)
try:
    from mcp.server.fastmcp import FastMCP
    _orig_tool, _orig_run = FastMCP.tool, getattr(FastMCP, "run", None)
    FastMCP.tool = lambda self, *a, **kw: lambda f: f
    FastMCP.run = lambda self, *a, **kw: None
except ImportError:
    _orig_tool = _orig_run = None
_spec.loader.exec_module(_server)
if _orig_tool:
    FastMCP.tool = _orig_tool
if _orig_run:
    FastMCP.run = _orig_run


def _resp(data):
    m = MagicMock()
    m.returncode = 0
    m.stdout = json.dumps(data) if data is not None else ""
    m.stderr = ""
    return m


def _curl(register_response):
    def run(args, **_kw):
        url = next((a for a in args if isinstance(a, str) and a.startswith("http")), "")
        if "/auth/connect/poll" in url:
            return _resp({"status": "complete", "api_key": "cl_key_1", "email": "user@example.com"})
        if "/repos/register" in url:
            return _resp(register_response)
        return _resp(None)
    return run


@patch("webbrowser.open")
@patch("asyncio.sleep", return_value=None)
def test_cl_connect_caches_the_plan(_sleep, _browser, tmp_path):
    from core.upgrade_hint import get_cached_tier
    p = tmp_path / "proj2"
    (p / ".git").mkdir(parents=True)
    register = {"repo_id": "r-1", "dashboard_url": "https://compliancelint.dev/dashboard/repos/r-1", "was_new": True,
                "tier_at_scan": "business"}
    with patch("subprocess.run", side_effect=_curl(register)):
        result = json.loads(asyncio.run(_server.cl_connect(str(p))))
    assert result["status"] == "connected"
    assert get_cached_tier(str(p)) == "business"


@patch("webbrowser.open")
@patch("asyncio.sleep", return_value=None)
def test_cl_connect_with_an_older_dashboard_caches_nothing(_sleep, _browser, tmp_path):
    from core.upgrade_hint import get_cached_tier
    p = tmp_path / "proj3"
    (p / ".git").mkdir(parents=True)
    register = {"repo_id": "r-2", "dashboard_url": "https://compliancelint.dev/dashboard/repos/r-2", "was_new": True}
    with patch("subprocess.run", side_effect=_curl(register)):
        asyncio.run(_server.cl_connect(str(p)))
    assert get_cached_tier(str(p)) == "unconnected"  # no tier in the answer: unchanged behaviour


def test_analyze_builds_the_strategy_with_the_project_key(no_user_config, tmp_path):
    """cl_analyze_project loaded the project settings (and so the key) only after building the strategy."""
    from core.context import analyze_project_metadata

    proj = _project(tmp_path)
    obligation_lookup.reset_cache()
    calls = []

    def fake_fetch(article):
        calls.append(classification_client._load_api_key())
        return {"ART50-OBL-1": {"detection_method": "look for an AI notice shown before the first message",
                                "what_to_scan": ["chat UI"]}} if article == 50 else {}

    from scanner.core import classification_client as pkg_client
    with patch.object(pkg_client, "fetch_classifications", side_effect=fake_fetch):
        result = analyze_project_metadata(proj)
    obligation_lookup.reset_cache()
    assert calls and set(calls) == {"cl_project_key"}
    hints = result["scanning_strategy"]["articles"]["art50"]["detection_hints"]
    assert hints == ["look for an AI notice shown before the first message"]
