"""The scanner's per-user directory (`~/.compliancelint`) and the test suite.

The scanner keeps one log directory per project under `~/.compliancelint/logs/<hash of the project path>`. Every
test that touched a tmp project created one in the REAL home directory: 216,816 directories had piled up on the
development machine by 2026-10-11. `COMPLIANCELINT_HOME` (already honoured by the telemetry config) now moves the
whole per-user directory, and the test session sets it to a temporary directory (conftest.py).
"""
import os
import sys
from pathlib import Path

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core import bug_report, paths, scanner_log  # noqa: E402

REAL_USER_DIR = Path.home() / ".compliancelint"


def test_default_is_the_home_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("COMPLIANCELINT_HOME", raising=False)
    assert paths.user_dir() == REAL_USER_DIR
    # Path arithmetic only — nothing is created.
    assert scanner_log._resolve_log_dir(str(tmp_path)) == REAL_USER_DIR / "logs" / scanner_log._project_hash(str(tmp_path))


def test_compliancelint_home_moves_the_log_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("COMPLIANCELINT_HOME", str(tmp_path / "elsewhere"))
    assert paths.user_dir() == tmp_path / "elsewhere"
    project = tmp_path / "project"
    project.mkdir()

    log = scanner_log.get_scanner_logger(str(project))
    log.info("hello")
    try:
        log_file = tmp_path / "elsewhere" / "logs" / scanner_log._project_hash(str(project)) / "scanner.log"
        assert log_file.is_file()
        # The bug-report bundle reads the same place.
        assert bug_report.log_dir_root() == tmp_path / "elsewhere" / "logs"
        assert [p.name for p in bug_report._list_log_dirs()] == [scanner_log._project_hash(str(project))]
    finally:
        scanner_log.close_scanner_logger(str(project))


def test_the_test_session_does_not_write_into_the_real_home(tmp_path):
    """Set by conftest.py for the whole session."""
    configured = os.environ.get("COMPLIANCELINT_HOME")
    assert configured, "conftest.py must point COMPLIANCELINT_HOME at a temporary directory"
    assert Path(configured).resolve() != REAL_USER_DIR.resolve()
    assert REAL_USER_DIR.resolve() not in scanner_log._resolve_log_dir(str(tmp_path)).resolve().parents
    assert REAL_USER_DIR.resolve() not in bug_report.log_dir_root().resolve().parents
