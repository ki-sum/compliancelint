"""Scanner file logging — persistent logs for debugging customer issues.

Writes to .compliancelint/logs/scanner.log in the project directory.
Rotates at 2MB, keeps last 3 files. Also logs to stderr for MCP protocol.

Usage in MCP tools:
    from core.scanner_log import get_scanner_logger
    log = get_scanner_logger(project_path)
    log.info("Scanning article 9...")
    log.error("Failed to parse", exc_info=True)
"""
import logging
import os
from logging.handlers import RotatingFileHandler

_loggers: dict[str, logging.Logger] = {}


def get_scanner_logger(project_path: str = "") -> logging.Logger:
    """Get a file-backed logger for the given project.

    If project_path is empty, returns the root compliancelint logger (stderr only).
    """
    if not project_path:
        return logging.getLogger("compliancelint")

    # Return cached logger if already set up
    if project_path in _loggers:
        return _loggers[project_path]

    logger = logging.getLogger(f"compliancelint.project")

    # Only add file handler if not already present
    log_dir = os.path.join(project_path, ".compliancelint", "logs")
    log_file = os.path.join(log_dir, "scanner.log")

    # Check if we already have a handler for this file
    for h in logger.handlers:
        if isinstance(h, RotatingFileHandler) and h.baseFilename == os.path.abspath(log_file):
            _loggers[project_path] = logger
            return logger

    try:
        os.makedirs(log_dir, exist_ok=True)
        handler = RotatingFileHandler(
            log_file, maxBytes=2 * 1024 * 1024, backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    except Exception:
        pass  # Can't create log dir — fall back to stderr only

    _loggers[project_path] = logger
    return logger
