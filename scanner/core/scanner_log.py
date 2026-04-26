"""Scanner file logging — persistent logs for debugging customer issues.

Writes to ~/.compliancelint/logs/{project_hash}/scanner.log. The log dir
lives OUTSIDE the project tree so cl_delete's shutil.rmtree on the project's
.compliancelint/ directory can never hit an open log handle (on Windows,
an open RotatingFileHandler inside the rmtree target raises WinError 32
sharing violation; see test_scanner_log_lives_outside_project_tree).

Rotates at 2MB, keeps last 3 files. Also logs to stderr for MCP protocol.

Usage in MCP tools:
    from core.scanner_log import get_scanner_logger
    log = get_scanner_logger(project_path)
    log.info("Scanning article 9...")
    log.error("Failed to parse", exc_info=True)

cl_delete should call close_scanner_logger(project_path) before removing
the home-side log directory so the file handle is released first.
"""
import hashlib
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_loggers: dict[str, logging.Logger] = {}


def _project_hash(project_path: str) -> str:
    """Stable 16-hex fingerprint of a project's absolute path.

    Used so every unique project gets its own log directory and its own
    logger name, avoiding cross-project handler leaks in long-running MCP
    processes that touch many projects.
    """
    abs_path = os.path.abspath(project_path)
    return hashlib.sha256(abs_path.encode("utf-8")).hexdigest()[:16]


def _resolve_log_dir(project_path: str) -> Path:
    """Return the log directory for a project: ~/.compliancelint/logs/{hash}.

    Lives outside the project tree so rmtree on the project is safe.
    """
    return Path.home() / ".compliancelint" / "logs" / _project_hash(project_path)


def get_scanner_logger(project_path: str = "") -> logging.Logger:
    """Get a file-backed logger for the given project.

    If project_path is empty, returns the root compliancelint logger (stderr only).
    """
    if not project_path:
        return logging.getLogger("compliancelint")

    # Return cached logger if already set up
    if project_path in _loggers:
        return _loggers[project_path]

    h = _project_hash(project_path)
    logger = logging.getLogger(f"compliancelint.project.{h}")

    log_dir = _resolve_log_dir(project_path)
    log_file = log_dir / "scanner.log"

    # Check if we already have a handler for this file (idempotent re-attach)
    for existing in logger.handlers:
        if isinstance(existing, RotatingFileHandler) and existing.baseFilename == os.path.abspath(str(log_file)):
            _loggers[project_path] = logger
            return logger

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            str(log_file), maxBytes=2 * 1024 * 1024, backupCount=3,
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


def close_scanner_logger(project_path: str) -> None:
    """Close and detach the file handler for a given project.

    Call this when the project is being deleted (e.g. cl_delete target=local)
    before removing the home-side log directory. Releases the scanner.log
    handle so the log directory can be removed on Windows. Safe to call even
    if no logger was created for this project.
    """
    if not project_path or project_path not in _loggers:
        return
    logger = _loggers[project_path]
    for h in list(logger.handlers):
        if isinstance(h, RotatingFileHandler):
            try:
                h.close()
            except Exception:
                pass
            logger.removeHandler(h)
    del _loggers[project_path]
