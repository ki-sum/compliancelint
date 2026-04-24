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
        result = _fetch_saas_scan_settings(MockConfig(api_key=""))
        assert result is None

    def test_returns_none_without_metadata(self):
        from server import _fetch_saas_scan_settings
        # No metadata.json → no repo_id → returns None
        config = MockConfig(api_key="cl_test_key")
        result = _fetch_saas_scan_settings(config)
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
            config._project_path = tmp
            result = _fetch_saas_scan_settings(config)
            assert result is None  # Connection refused → None (silent fallback)

    def test_returns_none_without_repo_id_in_metadata(self):
        from server import _fetch_saas_scan_settings
        with tempfile.TemporaryDirectory() as tmp:
            cl_dir = os.path.join(tmp, ".compliancelint", "local")
            os.makedirs(cl_dir)
            with open(os.path.join(cl_dir, "metadata.json"), "w") as f:
                json.dump({}, f)  # no repo_id

            config = MockConfig(api_key="cl_test_key")
            config._project_path = tmp
            result = _fetch_saas_scan_settings(config)
            assert result is None
