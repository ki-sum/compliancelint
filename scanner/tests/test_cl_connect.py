"""Comprehensive tests for cl_connect device flow.

Tests the full cl_connect pipeline with mocked subprocess (curl), webbrowser,
and filesystem. Catches bugs like missing imports, polling logic errors,
config save failures, asyncio event loop blocking, etc.
"""
import asyncio
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

# Import cl_connect directly from server module
import importlib.util
_server_spec = importlib.util.spec_from_file_location(
    "_server_test", os.path.join(SCANNER_ROOT, "server.py"),
    submodule_search_locations=[],
)
_server_mod = importlib.util.module_from_spec(_server_spec)

# Prevent MCP server from actually starting
try:
    from mcp.server.fastmcp import FastMCP
    _orig_mcp_tool = FastMCP.tool
    _orig_mcp_run = getattr(FastMCP, 'run', None)
    FastMCP.tool = lambda self, *a, **kw: lambda f: f
    FastMCP.run = lambda self, *a, **kw: None
except ImportError:
    _orig_mcp_tool = _orig_mcp_run = None

_server_spec.loader.exec_module(_server_mod)

if _orig_mcp_tool:
    FastMCP.tool = _orig_mcp_tool
if _orig_mcp_run:
    FastMCP.run = _orig_mcp_run

cl_connect = _server_mod.cl_connect


def _run(coro):
    """Run an async function synchronously for tests."""
    return asyncio.run(coro)


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal project directory with git repo."""
    project = tmp_path / "test-project"
    project.mkdir()
    git_dir = project / ".git"
    git_dir.mkdir()
    return str(project)


def _make_poll_response(status, api_key="", email=""):
    if status == "pending":
        data = {"status": "pending"}
    elif status == "complete":
        data = {"status": "complete", "api_key": api_key, "email": email}
    elif status == "expired":
        data = {"status": "expired"}
    else:
        data = {"status": status}
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = json.dumps(data)
    mock.stderr = ""
    return mock


def _make_check_response(valid=True, email="test@example.com"):
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = json.dumps({"valid": valid, "email": email})
    mock.stderr = ""
    return mock


class TestClConnectBasicValidation:

    def test_invalid_project_path(self):
        result = json.loads(_run(cl_connect("C:/nonexistent_cl_test_path_12345")))
        assert "error" in result

    def test_empty_project_path(self):
        result = json.loads(_run(cl_connect("")))
        assert "error" in result


class TestClConnectAlreadyConnected:

    @patch("subprocess.run")
    def test_already_connected_returns_early(self, mock_run, tmp_project):
        config_path = os.path.join(tmp_project, ".compliancelintrc")
        with open(config_path, "w") as f:
            json.dump({"saas_api_key": "cl_test123", "saas_url": "https://example.com"}, f)
        mock_run.return_value = _make_check_response(valid=True, email="user@test.com")

        result = json.loads(_run(cl_connect(tmp_project)))
        assert result["status"] == "already_connected"
        assert result["email"] == "user@test.com"

    @patch("subprocess.run")
    def test_switch_account_skips_existing_key(self, mock_run, tmp_project):
        config_path = os.path.join(tmp_project, ".compliancelintrc")
        with open(config_path, "w") as f:
            json.dump({"saas_api_key": "cl_existing", "saas_url": "https://example.com"}, f)
        mock_run.return_value = _make_poll_response("complete", api_key="cl_new", email="new@test.com")

        with patch("webbrowser.open"):
            with patch("asyncio.sleep", return_value=None):
                result = json.loads(_run(cl_connect(tmp_project, switch_account=True)))
        assert result.get("status") != "already_connected"


class TestClConnectDeviceFlow:

    @patch("subprocess.run")
    @patch("webbrowser.open")
    @patch("asyncio.sleep", return_value=None)
    def test_successful_connect(self, mock_sleep, mock_browser, mock_run, tmp_project):
        mock_run.side_effect = [
            _make_poll_response("pending"),
            _make_poll_response("pending"),
            _make_poll_response("complete", api_key="cl_abc123", email="user@example.com"),
        ]

        result = json.loads(_run(cl_connect(tmp_project)))
        assert result["status"] == "connected"
        assert result["email"] == "user@example.com"

        mock_browser.assert_called_once()
        browser_url = mock_browser.call_args[0][0]
        assert "/api/v1/auth/connect?token=" in browser_url

        config_path = os.path.join(tmp_project, ".compliancelintrc")
        assert os.path.isfile(config_path)
        with open(config_path) as f:
            saved = json.load(f)
        assert saved["saas_api_key"] == "cl_abc123"

    @patch("subprocess.run")
    @patch("webbrowser.open")
    @patch("asyncio.sleep", return_value=None)
    def test_gitignore_updated(self, mock_sleep, mock_browser, mock_run, tmp_project):
        mock_run.return_value = _make_poll_response("complete", api_key="cl_key", email="a@b.com")
        _run(cl_connect(tmp_project))

        gitignore = os.path.join(tmp_project, ".gitignore")
        assert os.path.isfile(gitignore)
        with open(gitignore) as f:
            assert ".compliancelintrc" in f.read()

    @patch("subprocess.run")
    @patch("webbrowser.open")
    @patch("asyncio.sleep", return_value=None)
    def test_gitignore_not_duplicated(self, mock_sleep, mock_browser, mock_run, tmp_project):
        gitignore = os.path.join(tmp_project, ".gitignore")
        with open(gitignore, "w") as f:
            f.write(".compliancelintrc\n")

        mock_run.return_value = _make_poll_response("complete", api_key="cl_key", email="a@b.com")
        _run(cl_connect(tmp_project))

        with open(gitignore) as f:
            assert f.read().count(".compliancelintrc") == 1

    @patch("subprocess.run")
    @patch("webbrowser.open")
    @patch("asyncio.sleep", return_value=None)
    def test_poll_timeout(self, mock_sleep, mock_browser, mock_run, tmp_project):
        mock_run.return_value = _make_poll_response("pending")
        result = json.loads(_run(cl_connect(tmp_project)))
        assert "error" in result
        assert "timed out" in result["error"].lower() or "Timed out" in result["error"]

    @patch("subprocess.run")
    @patch("webbrowser.open")
    @patch("asyncio.sleep", return_value=None)
    def test_poll_expired(self, mock_sleep, mock_browser, mock_run, tmp_project):
        mock_run.return_value = _make_poll_response("expired")
        result = json.loads(_run(cl_connect(tmp_project)))
        assert "error" in result
        assert "expired" in result["error"].lower()

    @patch("subprocess.run")
    @patch("webbrowser.open")
    @patch("asyncio.sleep", return_value=None)
    def test_poll_network_error_retries(self, mock_sleep, mock_browser, mock_run, tmp_project):
        error_result = MagicMock()
        error_result.returncode = 7
        error_result.stdout = ""
        error_result.stderr = "Connection refused"

        mock_run.side_effect = [
            error_result,
            error_result,
            _make_poll_response("complete", api_key="cl_key", email="a@b.com"),
        ]
        result = json.loads(_run(cl_connect(tmp_project)))
        assert result["status"] == "connected"

    @patch("subprocess.run")
    @patch("webbrowser.open")
    @patch("asyncio.sleep", return_value=None)
    def test_poll_subprocess_exception_retries(self, mock_sleep, mock_browser, mock_run, tmp_project):
        mock_run.side_effect = [
            OSError("curl not found"),
            _make_poll_response("complete", api_key="cl_key", email="a@b.com"),
        ]
        result = json.loads(_run(cl_connect(tmp_project)))
        assert result["status"] == "connected"

    @patch("subprocess.run")
    @patch("webbrowser.open")
    @patch("asyncio.sleep", return_value=None)
    def test_saas_url_default(self, mock_sleep, mock_browser, mock_run, tmp_project):
        mock_run.return_value = _make_poll_response("complete", api_key="cl_k", email="a@b.com")
        _run(cl_connect(tmp_project))
        browser_url = mock_browser.call_args[0][0]
        assert browser_url.startswith("https://compliancelint.dev/")

    @patch("subprocess.run")
    @patch("webbrowser.open")
    @patch("asyncio.sleep", return_value=None)
    def test_custom_saas_url(self, mock_sleep, mock_browser, mock_run, tmp_project):
        config_path = os.path.join(tmp_project, ".compliancelintrc")
        with open(config_path, "w") as f:
            json.dump({"saas_url": "https://custom.example.com"}, f)

        mock_run.return_value = _make_poll_response("complete", api_key="cl_k", email="a@b.com")
        _run(cl_connect(tmp_project))
        browser_url = mock_browser.call_args[0][0]
        assert browser_url.startswith("https://custom.example.com/")


class TestClConnectBrowserFailure:

    @patch("subprocess.run")
    @patch("webbrowser.open", side_effect=Exception("No display"))
    def test_browser_open_fails(self, mock_browser, mock_run, tmp_project):
        result = json.loads(_run(cl_connect(tmp_project)))
        assert "error" in result
        assert "browser" in result["error"].lower()
        assert "fix" in result
        assert "cl_connect()" in result["fix"]


class TestClConnectIsAsync:
    """Verify cl_connect is async — critical for MCP event loop."""

    def test_cl_connect_is_coroutine_function(self):
        import inspect
        assert inspect.iscoroutinefunction(cl_connect), \
            "cl_connect MUST be async to avoid blocking MCP event loop"


class TestClConnectConfigSave:

    @patch("subprocess.run")
    @patch("webbrowser.open")
    @patch("asyncio.sleep", return_value=None)
    def test_api_key_saved_to_config(self, mock_sleep, mock_browser, mock_run, tmp_project):
        mock_run.return_value = _make_poll_response("complete", api_key="cl_saved_key_123", email="saved@test.com")
        _run(cl_connect(tmp_project))

        config_path = os.path.join(tmp_project, ".compliancelintrc")
        with open(config_path) as f:
            config = json.load(f)
        assert config["saas_api_key"] == "cl_saved_key_123"

    @patch("subprocess.run")
    @patch("webbrowser.open")
    @patch("asyncio.sleep", return_value=None)
    def test_config_preserves_existing_fields(self, mock_sleep, mock_browser, mock_run, tmp_project):
        config_path = os.path.join(tmp_project, ".compliancelintrc")
        with open(config_path, "w") as f:
            json.dump({"custom_field": "keep_me", "repo_name": "my/repo"}, f)

        mock_run.return_value = _make_poll_response("complete", api_key="cl_new", email="a@b.com")
        _run(cl_connect(tmp_project))

        with open(config_path) as f:
            config = json.load(f)
        assert config["saas_api_key"] == "cl_new"
        assert config.get("custom_field") == "keep_me"
