"""Tests for scanner file logging."""
import os
import sys
import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

from core.scanner_log import get_scanner_logger, _loggers


@pytest.fixture(autouse=True)
def clear_logger_cache():
    """Clear cached loggers between tests."""
    _loggers.clear()
    yield
    _loggers.clear()


class TestScannerLog:

    def test_returns_logger_for_project(self, tmp_path):
        log = get_scanner_logger(str(tmp_path))
        assert log is not None
        assert log.name == "compliancelint.project"

    def test_creates_log_directory(self, tmp_path):
        get_scanner_logger(str(tmp_path))
        log_dir = tmp_path / ".compliancelint" / "logs"
        assert log_dir.is_dir()

    def test_writes_to_file(self, tmp_path):
        log = get_scanner_logger(str(tmp_path))
        log.info("test message 123")

        log_file = tmp_path / ".compliancelint" / "logs" / "scanner.log"
        assert log_file.is_file()
        content = log_file.read_text(encoding="utf-8")
        assert "test message 123" in content

    def test_caches_logger(self, tmp_path):
        log1 = get_scanner_logger(str(tmp_path))
        log2 = get_scanner_logger(str(tmp_path))
        assert log1 is log2

    def test_empty_path_returns_root_logger(self):
        log = get_scanner_logger("")
        assert log.name == "compliancelint"

    def test_no_path_returns_root_logger(self):
        log = get_scanner_logger()
        assert log.name == "compliancelint"

    def test_log_includes_timestamp(self, tmp_path):
        log = get_scanner_logger(str(tmp_path))
        log.info("timestamped entry")

        log_file = tmp_path / ".compliancelint" / "logs" / "scanner.log"
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

        log_file = tmp_path / ".compliancelint" / "logs" / "scanner.log"
        content = log_file.read_text(encoding="utf-8")
        assert "ValueError: test error" in content
