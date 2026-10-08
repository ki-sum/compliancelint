"""Tests for _fetch_saas_scan_settings function.

Verifies the scanner correctly handles SaaS API responses,
timeouts, and network errors.
"""
import json
import os
import sys
import tempfile

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


class MockConfig:
    def __init__(self, api_key="", url="https://compliancelint.dev"):
        self.saas_api_key = api_key
        self.saas_url = url


class TestFetchSaasSettings:

    def test_returns_none_without_api_key(self):
        from server import _fetch_saas_scan_settings
        result = _fetch_saas_scan_settings(MockConfig(api_key=""), tempfile.gettempdir())
        assert result is None

    def test_returns_none_without_metadata(self):
        from server import _fetch_saas_scan_settings
        # No metadata.json → no repo_id → returns None
        config = MockConfig(api_key="cl_test_key")
        with tempfile.TemporaryDirectory() as tmp:
            result = _fetch_saas_scan_settings(config, tmp)
        assert result is None

    def test_returns_none_on_invalid_url(self):
        from server import _fetch_saas_scan_settings
        # Create a temp dir with metadata
        with tempfile.TemporaryDirectory() as tmp:
            cl_dir = os.path.join(tmp, ".compliancelint", "local")
            os.makedirs(cl_dir)
            with open(os.path.join(cl_dir, "metadata.json"), "w") as f:
                json.dump({"repo_id": "test-repo"}, f)

            config = MockConfig(api_key="cl_test_key", url="http://localhost:99999")
            result = _fetch_saas_scan_settings(config, tmp)
            assert result is None  # Connection refused → None (silent fallback)

    def test_returns_none_without_repo_id_in_metadata(self):
        from server import _fetch_saas_scan_settings
        with tempfile.TemporaryDirectory() as tmp:
            cl_dir = os.path.join(tmp, ".compliancelint", "local")
            os.makedirs(cl_dir)
            with open(os.path.join(cl_dir, "metadata.json"), "w") as f:
                json.dump({}, f)  # no repo_id

            config = MockConfig(api_key="cl_test_key")
            result = _fetch_saas_scan_settings(config, tmp)
            assert result is None


# Acceptance run E (2026-10-08, founder: fix before release): the fetch read metadata.json from
# `config._project_path if hasattr(config, '_project_path') else "."` — ProjectConfig never sets _project_path, so it
# read the MCP server's working directory. Claude Code opened at the project root happened to match; any other client
# (or a sub-directory / monorepo project) silently got no dashboard settings — wizard answers, applicability, tier.
# The tests above set config._project_path by hand and so hid it.

def _project_with_repo(tmp, repo_id="repo-xyz"):
    cl_dir = os.path.join(tmp, ".compliancelint", "local")
    os.makedirs(cl_dir)
    with open(os.path.join(cl_dir, "metadata.json"), "w") as f:
        json.dump({"repo_id": repo_id}, f)
    with open(os.path.join(tmp, ".compliancelintrc"), "w") as f:
        json.dump({"saas_url": "https://dash.test.local", "saas_api_key": "cl_test_key", "repo_name": "acme/x"}, f)


def test_reads_the_projects_metadata_not_the_working_directory(tmp_path, monkeypatch):
    import urllib.request
    from server import _fetch_saas_scan_settings
    project = tmp_path / "project"
    project.mkdir()
    _project_with_repo(str(project))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    seen = {}

    class _Resp:
        status = 200
        def read(self):
            return b'{"roles": ["provider"]}'
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = _fetch_saas_scan_settings(MockConfig(api_key="cl_test_key", url="https://dash.test.local"), str(project))
    assert result == {"roles": ["provider"]}
    assert seen["url"] == "https://dash.test.local/api/v1/repos/repo-xyz/scan-settings"


def _template_context():
    from core.context import _build_answers_template
    answers = _build_answers_template()
    answers["_scope"].update({"is_ai_system": True, "risk_classification": "high-risk", "risk_classification_confidence": "high"})
    return json.dumps({"framework": "python", "compliance_answers": answers})


def _saved_scope(project):
    with open(os.path.join(project, ".compliancelint", "local", "last_context.json"), encoding="utf-8") as f:
        return json.load(f)["compliance_answers"]["_scope"]


SETTINGS = {"roles": ["deployer"], "is_deployer": False, "is_provider": False, "riskClassification": "high-risk"}


def test_cl_scan_applies_the_dashboard_settings(tmp_path, monkeypatch):
    import server
    _project_with_repo(str(tmp_path))
    monkeypatch.setattr(server, "_fetch_saas_scan_settings", lambda config, project_path: dict(SETTINGS))
    server.cl_scan(str(tmp_path), project_context=_template_context(), articles="26")
    scope = _saved_scope(str(tmp_path))
    assert scope["_saas_settings_active"] is True
    assert scope["is_deployer"] is False


def test_cl_scan_all_applies_the_dashboard_settings(tmp_path, monkeypatch):
    import server
    _project_with_repo(str(tmp_path))
    monkeypatch.setattr(server, "_fetch_saas_scan_settings", lambda config, project_path: dict(SETTINGS))
    server.cl_scan_all(str(tmp_path), project_context=_template_context())
    scope = _saved_scope(str(tmp_path))
    assert scope["_saas_settings_active"] is True
    assert scope["is_deployer"] is False



def test_articles_the_dashboard_excludes_are_not_applicable_in_the_scan(tmp_path, monkeypatch):
    """§16.1 (Anna: deployer, not high-risk) — the dashboard's applicable_articles exclude Art 26. compute_applicable_
    articles listed it as skipped, but cl_scan_all scanned every module anyway, so Art 26 findings came back
    unable_to_determine and were synced. Now an excluded article is NOT_APPLICABLE without scanning (acceptance run
    E, 2026-10-08)."""
    import server
    _project_with_repo(str(tmp_path))
    settings = dict(SETTINGS)
    settings["applicable_articles"] = [f"art{n}" for n in (4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 50)]
    settings["applicable_obligations"] = None
    settings["questionnaire"] = None
    monkeypatch.setattr(server, "_fetch_saas_scan_settings", lambda config, project_path: dict(settings))
    server.cl_scan_all(str(tmp_path), project_context=_template_context())
    art_dir = tmp_path / ".compliancelint" / "local" / "articles"
    art26 = json.loads((art_dir / "art26.json").read_text(encoding="utf-8"))
    assert art26["overall_level"] == "not_applicable"
    assert list(art26["findings"]) == ["ART26-NOT-APPLICABLE"]
    assert "dashboard" in art26["findings"]["ART26-NOT-APPLICABLE"]["description"]
    art12 = json.loads((art_dir / "art12.json").read_text(encoding="utf-8"))
    assert art12["overall_level"] != "not_applicable"
    assert "ART12-OBL-1" in art12["findings"]


def test_obligations_the_dashboard_excludes_are_not_applicable(tmp_path, monkeypatch):
    """§16.1 Anna — Art 12's module also reports ART26-OBL-6 (Art. 26(6), deployer log keeping), which the dashboard's
    applicable_obligations exclude for a deployer that is not high-risk. Article-level narrowing left it
    unable_to_determine; findings outside the dashboard's applicable_obligations are now NOT_APPLICABLE (acceptance
    run E, 2026-10-08)."""
    import server
    _project_with_repo(str(tmp_path))
    settings = dict(SETTINGS)
    settings["applicable_articles"] = ["art4", "art5", "art6", "art12"]
    settings["applicable_obligations"] = ["ART12-OBL-1", "ART12-OBL-2a", "ART12-OBL-2b", "ART12-OBL-2c"]
    settings["questionnaire"] = None
    monkeypatch.setattr(server, "_fetch_saas_scan_settings", lambda config, project_path: dict(settings))
    server.cl_scan_all(str(tmp_path), project_context=_template_context())
    art12 = json.loads((tmp_path / ".compliancelint" / "local" / "articles" / "art12.json").read_text(encoding="utf-8"))
    assert art12["findings"]["ART26-OBL-6"]["level"] == "not_applicable"
    assert art12["findings"]["ART12-OBL-1"]["level"] != "not_applicable"
