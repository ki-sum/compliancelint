"""Q5 self-audit follow-up — cl_report_bug + build_bundle missing test
coverage. Pre-fix: only 1 test (upgrade_hint negative assertion).
This file covers the actual functionality:

  - bundle file is generated at expected path
  - PII redaction works (emails, IPs, home paths → ~)
  - empty log dir doesn't crash
  - bundle includes scanner version + env metadata
  - cl_report_bug returns proper JSON shape

Privacy contract: bundle MUST NOT contain raw home paths, raw emails,
raw IPs. Test enforces by writing log content with all 3 patterns
then verifying redaction.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)


# ──────────────────────────────────────────────────────────────────────
# 1. PII redaction (the privacy promise)
# ──────────────────────────────────────────────────────────────────────


def test_scrub_line_redacts_email():
    from core.bug_report import _scrub_line

    line = "user@example.com tried to login"
    out = _scrub_line(line)
    assert "@example.com" not in out
    assert "<email>" in out


def test_scrub_line_redacts_ipv4():
    from core.bug_report import _scrub_line

    line = "Connection from 192.168.1.42 refused"
    out = _scrub_line(line)
    assert "192.168.1.42" not in out
    assert "<ip>" in out


def test_scrub_line_collapses_home_path_to_tilde():
    from core.bug_report import _scrub_line, HOME_STR

    fake_path = HOME_STR + "/.compliancelint/logs/abc/scanner.log"
    line = f"Reading log at {fake_path}"
    out = _scrub_line(line)
    assert HOME_STR not in out
    assert "~" in out


def test_scrub_line_handles_all_three_patterns_at_once():
    from core.bug_report import _scrub_line, HOME_STR

    line = f"User alice@corp.io connected from 10.0.0.1 saw {HOME_STR}/.config"
    out = _scrub_line(line)
    assert "alice@corp.io" not in out
    assert "10.0.0.1" not in out
    assert HOME_STR not in out
    assert "<email>" in out
    assert "<ip>" in out
    assert "~" in out


# ──────────────────────────────────────────────────────────────────────
# 2. build_bundle — file generation + content
# ──────────────────────────────────────────────────────────────────────


def test_build_bundle_creates_file_with_expected_name(tmp_path):
    from core.bug_report import build_bundle

    out = build_bundle("1.1.0-test", output_dir=tmp_path)
    assert out.exists()
    assert out.is_file()
    assert "compliancelint-bugreport-" in out.name
    assert out.suffix == ".md"


def test_build_bundle_includes_cl_version():
    from core.bug_report import build_bundle

    with tempfile.TemporaryDirectory() as tmp:
        out = build_bundle("1.1.0-marker-test", output_dir=Path(tmp))
        content = out.read_text(encoding="utf-8")

    assert "1.1.0-marker-test" in content


def test_build_bundle_includes_env_metadata():
    """Bundle should have ## Environment section with Python version,
    OS, anonymized cwd."""
    from core.bug_report import build_bundle

    with tempfile.TemporaryDirectory() as tmp:
        out = build_bundle("1.1.0", output_dir=Path(tmp))
        content = out.read_text(encoding="utf-8")

    assert "## Environment" in content
    assert "Python" in content
    assert "ComplianceLint" in content


def test_build_bundle_handles_empty_log_dir(tmp_path):
    """When ~/.compliancelint/logs/ is empty or missing, bundle still
    generates — just with empty 'recent logs' section."""
    from core.bug_report import build_bundle

    # Default LOG_DIR_ROOT may not exist; build_bundle should not crash.
    out = build_bundle("1.1.0", output_dir=tmp_path)
    assert out.exists()
    # Bundle is valid markdown even with no log content
    content = out.read_text(encoding="utf-8")
    assert len(content) > 100  # at least the env + boilerplate


# ──────────────────────────────────────────────────────────────────────
# 3. PII redaction in bundle output (end-to-end)
# ──────────────────────────────────────────────────────────────────────


def test_bundle_redacts_pii_in_log_content(monkeypatch, tmp_path):
    """Plant a fake log with email + IP + home path. Bundle output
    MUST not contain the raw values — they must be redacted to
    <email> / <ip> / ~ before being included."""
    from core import bug_report

    fake_log_root = tmp_path / "fake_log_root"
    fake_log_dir = fake_log_root / "abc123"
    fake_log_dir.mkdir(parents=True)
    log_file = fake_log_dir / "scanner.log"
    log_file.write_text(
        f"alice@corp.io triggered scan from 192.168.50.42 in "
        f"{bug_report.HOME_STR}/projects/secret-app\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(bug_report, "LOG_DIR_ROOT", fake_log_root)

    out = bug_report.build_bundle("1.1.0", output_dir=tmp_path)
    content = out.read_text(encoding="utf-8")

    assert "alice@corp.io" not in content
    assert "192.168.50.42" not in content
    assert bug_report.HOME_STR not in content
    # AND the redaction markers should be present somewhere
    assert "<email>" in content
    assert "<ip>" in content


# ──────────────────────────────────────────────────────────────────────
# 4. cl_report_bug MCP tool — JSON contract
# ──────────────────────────────────────────────────────────────────────


def test_cl_report_bug_returns_ok_status_and_path(tmp_path, monkeypatch):
    """Tool returns JSON with status / bundle_path / size_bytes /
    next_steps fields."""
    from core import bug_report
    from server import cl_report_bug

    monkeypatch.setattr(bug_report, "DEFAULT_BUNDLE_DIR", tmp_path)

    raw = cl_report_bug()
    parsed = json.loads(raw)

    assert parsed["status"] == "ok"
    assert "bundle_path" in parsed
    assert isinstance(parsed["size_bytes"], int)
    assert parsed["size_bytes"] > 0
    assert "next_steps" in parsed
    assert "github.com" in parsed["next_steps"]


def test_cl_report_bug_explicitly_says_not_auto_uploaded():
    """Privacy contract: tool MUST tell user the bundle is local-only,
    NOT uploaded automatically. Customer trust depends on this clarity."""
    from core import bug_report
    from server import cl_report_bug

    with tempfile.TemporaryDirectory() as tmp:
        # Override default bundle dir for test isolation
        original_dir = bug_report.DEFAULT_BUNDLE_DIR
        bug_report.DEFAULT_BUNDLE_DIR = Path(tmp)
        try:
            raw = cl_report_bug()
        finally:
            bug_report.DEFAULT_BUNDLE_DIR = original_dir

    parsed = json.loads(raw)
    next_steps = parsed["next_steps"].lower()
    # Either "review", "attach", or "email" — words indicating
    # user-driven upload, not auto-upload
    assert "review" in next_steps or "attach" in next_steps or "email" in next_steps


# ──────────────────────────────────────────────────────────────────────
# 5. Defensive: write-permission failure → readable error
# ──────────────────────────────────────────────────────────────────────


def test_cl_report_bug_returns_error_on_write_failure(monkeypatch):
    """When build_bundle raises (e.g. disk full, permission denied),
    cl_report_bug returns a clean error JSON, not a Python traceback."""
    from server import cl_report_bug
    import core.bug_report

    def raising_build(*_args, **_kwargs):
        raise OSError("Permission denied")

    # Patch the import inside cl_report_bug
    monkeypatch.setattr(core.bug_report, "build_bundle", raising_build)

    raw = cl_report_bug()
    parsed = json.loads(raw)

    assert "error" in parsed
    assert "Permission denied" in parsed["error"] or "Failed to build" in parsed["error"]
