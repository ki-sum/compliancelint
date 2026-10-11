"""The update notice appears only when PyPI has a NEWER version than the installed one.

`_check_latest_version` compared with `!=`: a real session running 1.2.2 before it was published was told "an update
is available: 1.2.1" (2026-10-11) — the same would happen to a user during the minutes in which a mirror still
serves the previous version.
"""
import io
import json
import os
import sys
import urllib.request

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def _pypi_says(monkeypatch, latest, installed):
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Response(json.dumps({"info": {"version": latest}}).encode()))
    monkeypatch.setattr(server, "CL_VERSION", installed)
    return server._check_latest_version()


@pytest.mark.parametrize("latest,installed", [
    ("1.2.1", "1.2.2"),    # installed is newer
    ("1.2.2", "1.2.2"),    # same
    ("1.9.0", "1.10.0"),   # numeric, not alphabetical
    ("1.2.2", "1.2.2.dev1"),
])
def test_no_notice_when_pypi_is_not_newer(monkeypatch, latest, installed):
    assert _pypi_says(monkeypatch, latest, installed) == {"update_available": False}


@pytest.mark.parametrize("latest,installed", [
    ("1.2.3", "1.2.2"),
    ("1.10.0", "1.9.9"),
    ("2.0.0", "1.99.99"),
])
def test_notice_when_pypi_is_newer(monkeypatch, latest, installed):
    assert _pypi_says(monkeypatch, latest, installed) == {
        "update_available": True,
        "current_version": installed,
        "latest_version": latest,
        "upgrade_command": "pip install --upgrade compliancelint",
    }
