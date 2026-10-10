"""cl_connect stores the dashboard's repo id, so the FIRST scan can read the dashboard settings (1.2.1).

cl_connect pre-registers the project on the dashboard and gets its repo id back, and its message invites the user to
"configure the profiling wizard before your first scan". The scanner reads the dashboard settings by repo id from
.compliancelint/local/metadata.json — which only cl_sync wrote. So the first scan of a new project could not read the
Profiling Wizard answers and reported dashboard_settings "unavailable" with a warning to re-run the scan (found on the
production site, 2026-10-10).
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

_spec = importlib.util.spec_from_file_location(
    "_server_test_repo_id", os.path.join(SCANNER_ROOT, "server.py"), submodule_search_locations=[],
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


def _resp(data) -> MagicMock:
    m = MagicMock()
    m.returncode = 0
    m.stdout = json.dumps(data) if data is not None else ""
    m.stderr = ""
    return m


def _curl(register_response):
    """subprocess.run stand-in for cl_connect's curl calls, keyed by the URL in the command line."""
    def run(args, **_kw):
        url = next((a for a in args if isinstance(a, str) and a.startswith("http")), "")
        if "/auth/connect/poll" in url:
            return _resp({"status": "complete", "api_key": "cl_key_1", "email": "user@example.com"})
        if "/repos/register" in url:
            return _resp(register_response)
        return _resp(None)
    return run


@pytest.fixture
def project(tmp_path):
    p = tmp_path / "proj"
    (p / ".git").mkdir(parents=True)
    return str(p)


def _metadata(project: str) -> dict:
    from core import paths
    path = paths.metadata_file_str(project)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@patch("webbrowser.open")
@patch("asyncio.sleep", return_value=None)
def test_cl_connect_stores_the_registered_repo_id(_sleep, _browser, project):
    register = {"repo_id": "repo-123", "dashboard_url": "https://compliancelint.dev/dashboard/repos/repo-123", "was_new": True}
    with patch("subprocess.run", side_effect=_curl(register)):
        result = json.loads(asyncio.run(_server.cl_connect(project)))
    assert result["status"] == "connected"
    assert _metadata(project).get("repo_id") == "repo-123"


@patch("webbrowser.open")
@patch("asyncio.sleep", return_value=None)
def test_first_scan_can_fetch_the_dashboard_settings_after_cl_connect(_sleep, _browser, project):
    register = {"repo_id": "repo-123", "dashboard_url": "https://compliancelint.dev/dashboard/repos/repo-123", "was_new": True}
    with patch("subprocess.run", side_effect=_curl(register)):
        asyncio.run(_server.cl_connect(project))

    from core.config import ProjectConfig
    config = ProjectConfig.load(project)
    seen = {}

    class _Resp:
        status = 200
        def read(self):
            return json.dumps({"roles": ["provider"], "risk_classification": "high-risk"}).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        seen["url"] = req.full_url
        return _Resp()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        settings = _server._fetch_saas_scan_settings(config, project)
    assert seen.get("url", "").endswith("/api/v1/repos/repo-123/scan-settings")
    assert settings == {"roles": ["provider"], "risk_classification": "high-risk"}


@patch("webbrowser.open")
@patch("asyncio.sleep", return_value=None)
def test_cl_connect_without_a_register_answer_still_connects(_sleep, _browser, project):
    # An older dashboard or a transient error: no repo id, no crash, nothing stored.
    with patch("subprocess.run", side_effect=_curl(None)):
        result = json.loads(asyncio.run(_server.cl_connect(project)))
    assert result["status"] == "connected"
    assert "repo_id" not in _metadata(project)
