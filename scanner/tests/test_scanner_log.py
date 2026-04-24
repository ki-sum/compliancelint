"""Tests for scanner file logging.

BUG-1 fix: logs live under ~/.compliancelint/logs/{project_hash}/ instead of
inside the project tree. Each project gets its own logger name
(compliancelint.project.{hash}) to avoid cross-project handler leaks in
long-running MCP processes.
"""
import os
import shutil
import sys
import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.scanner_log import (
    _loggers,
    _project_hash,
    _resolve_log_dir,
    close_scanner_logger,
    get_scanner_logger,
)


@pytest.fixture(autouse=True)
def clear_logger_cache(tmp_path):
    """Release handlers + clear cache + remove home-side log dir between tests.

    Post-BUG-1 the log lives in Path.home() / .compliancelint/logs/{hash},
    so the test cleans up the real home-side dir it created (keyed on the
    per-test tmp_path, so there is no cross-test collision).
    """
    _loggers.clear()
    yield
    for project_path in list(_loggers.keys()):
        close_scanner_logger(project_path)
    _loggers.clear()
    home_log_dir = _resolve_log_dir(str(tmp_path))
    if home_log_dir.exists():
        shutil.rmtree(home_log_dir, ignore_errors=True)


class TestScannerLog:

    def test_returns_logger_for_project(self, tmp_path):
        log = get_scanner_logger(str(tmp_path))
        expected_hash = _project_hash(str(tmp_path))
        assert log.name == f"compliancelint.project.{expected_hash}", (
            "each project must get its own logger name suffix for isolation"
        )

    def test_creates_log_directory_under_home(self, tmp_path):
        get_scanner_logger(str(tmp_path))
        home_log_dir = _resolve_log_dir(str(tmp_path))
        assert home_log_dir.is_dir(), (
            f"log dir must be created at {home_log_dir} (outside project tree)"
        )
        project_log_dir = tmp_path / ".compliancelint" / "logs"
        assert not project_log_dir.exists(), (
            "BUG-1: log dir must NOT be inside the project tree"
        )

    def test_writes_to_file(self, tmp_path):
        log = get_scanner_logger(str(tmp_path))
        log.info("test message 123")

        log_file = _resolve_log_dir(str(tmp_path)) / "scanner.log"
        assert log_file.is_file(), f"expected scanner.log at {log_file}"
        content = log_file.read_text(encoding="utf-8")
        assert "test message 123" in content

    def test_caches_logger(self, tmp_path):
        log1 = get_scanner_logger(str(tmp_path))
        log2 = get_scanner_logger(str(tmp_path))
        assert log1 is log2, "same project_path must return cached logger instance"

    def test_empty_path_returns_root_logger(self):
        log = get_scanner_logger("")
        assert log.name == "compliancelint"

    def test_no_path_returns_root_logger(self):
        log = get_scanner_logger()
        assert log.name == "compliancelint"

    def test_log_includes_timestamp(self, tmp_path):
        log = get_scanner_logger(str(tmp_path))
        log.info("timestamped entry")

        log_file = _resolve_log_dir(str(tmp_path)) / "scanner.log"
        content = log_file.read_text(encoding="utf-8")
        # Format: 2026-04-06 19:00:00 INFO timestamped entry
        assert "INFO" in content
        assert "timestamped entry" in content

    def test_logs_error_with_traceback(self, tmp_path):
        log = get_scanner_logger(str(tmp_path))
        try:
            raise ValueError("test error")
        except ValueError:
            log.error("caught exception", exc_info=True)

        log_file = _resolve_log_dir(str(tmp_path)) / "scanner.log"
        content = log_file.read_text(encoding="utf-8")
        assert "ValueError: test error" in content

    def test_distinct_projects_get_distinct_loggers(self, tmp_path):
        proj_a = tmp_path / "project-a"
        proj_b = tmp_path / "project-b"
        proj_a.mkdir()
        proj_b.mkdir()

        log_a = get_scanner_logger(str(proj_a))
        log_b = get_scanner_logger(str(proj_b))

        assert log_a.name != log_b.name, (
            "two different projects must not share the same logger (cross-project leak)"
        )
        assert _resolve_log_dir(str(proj_a)) != _resolve_log_dir(str(proj_b))
        # Clean up the extra home-side dirs this test created (the autouse
        # fixture only cleans tmp_path's hash; these are tmp_path/project-*).
        for p in (proj_a, proj_b):
            d = _resolve_log_dir(str(p))
            close_scanner_logger(str(p))
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)

    def test_close_scanner_logger_releases_handler(self, tmp_path):
        get_scanner_logger(str(tmp_path))
        close_scanner_logger(str(tmp_path))
        assert str(tmp_path) not in _loggers, (
            "close_scanner_logger must evict the entry from the cache"
        )
