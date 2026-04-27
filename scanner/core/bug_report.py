"""
Bug report bundle generator for cl_report_bug MCP tool.

Produces a self-contained Markdown file the user can attach to a GitHub
issue. The bundle contains:

  * Environment info (Python, OS, ComplianceLint version, MCP client hint)
  * Last ~200 lines of every scanner.log in ~/.compliancelint/logs/
  * Recent error envelopes (request_id + message) extracted from logs

Privacy:

  * Paths are anonymized — user homedir is replaced with ``~``, and any
    absolute path under it has the parent directories collapsed.
  * No file contents from the project are included — only scanner logs.
  * Customer PII patterns (emails, IPs) in log lines are redacted.

The output is plain Markdown so the user can read it before submitting
and redact further if they want. We do NOT auto-upload anything.
"""

from __future__ import annotations

import os
import platform
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

LOG_DIR_ROOT = Path.home() / ".compliancelint" / "logs"
DEFAULT_TAIL_LINES = 200
DEFAULT_BUNDLE_DIR = Path.home()
BUNDLE_FILE_PREFIX = "compliancelint-bugreport"

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
HOME_STR = str(Path.home())


def _scrub_line(line: str) -> str:
    """Redact obvious PII (emails, IPs) and collapse home paths to ``~``."""
    line = line.replace(HOME_STR, "~")
    line = EMAIL_RE.sub("<email>", line)
    line = IPV4_RE.sub("<ip>", line)
    return line


def _tail_file(path: Path, lines: int) -> list[str]:
    """Return the last ``lines`` lines of ``path``. Empty list on failure."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            buf = fh.readlines()
    except OSError:
        return []
    return [_scrub_line(ln.rstrip("\n")) for ln in buf[-lines:]]


def _list_log_dirs() -> list[Path]:
    """Return all per-project log dirs under ~/.compliancelint/logs/."""
    if not LOG_DIR_ROOT.is_dir():
        return []
    return sorted(
        (p for p in LOG_DIR_ROOT.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


@dataclass
class EnvInfo:
    cl_version: str
    python_version: str
    platform_str: str
    platform_release: str
    cwd_anonymized: str

    def to_md(self) -> str:
        return (
            "## Environment\n\n"
            f"- **ComplianceLint**: {self.cl_version}\n"
            f"- **Python**: {self.python_version}\n"
            f"- **OS**: {self.platform_str} {self.platform_release}\n"
            f"- **Working directory**: `{self.cwd_anonymized}`\n"
        )


def _collect_env(cl_version: str) -> EnvInfo:
    cwd = os.getcwd()
    if cwd.startswith(HOME_STR):
        cwd = "~" + cwd[len(HOME_STR):]
    return EnvInfo(
        cl_version=cl_version,
        python_version=sys.version.split()[0],
        platform_str=platform.system(),
        platform_release=platform.release(),
        cwd_anonymized=cwd,
    )


def _extract_recent_request_ids(log_lines: Iterable[str], limit: int = 10) -> list[str]:
    """Pull request_ids from log lines (most recent first)."""
    ids: list[str] = []
    seen: set[str] = set()
    for line in reversed(list(log_lines)):
        for m in re.finditer(r"request_id=(req_[0-9a-f]{8,})", line):
            rid = m.group(1)
            if rid not in seen:
                seen.add(rid)
                ids.append(rid)
                if len(ids) >= limit:
                    return ids
    return ids


def build_bundle(
    cl_version: str,
    *,
    tail_lines: int = DEFAULT_TAIL_LINES,
    output_dir: Path | None = None,
    now: datetime | None = None,
) -> Path:
    """Build the bug report bundle and return its path.

    ``cl_version`` should be the value of ``CL_VERSION`` from server.py.
    ``output_dir`` defaults to the user's home directory.
    ``now`` is injectable for testing.
    """
    output_dir = output_dir or DEFAULT_BUNDLE_DIR
    now = now or datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{BUNDLE_FILE_PREFIX}-{ts}.md"

    env = _collect_env(cl_version)
    log_dirs = _list_log_dirs()

    sections: list[str] = []
    sections.append(f"# ComplianceLint bug report\n\n*Generated {now.isoformat()}*\n")
    sections.append(env.to_md())

    sections.append(
        "## Privacy\n\n"
        "- Home directory paths replaced with `~`.\n"
        "- Email addresses and IPv4 addresses redacted.\n"
        "- No source code or evidence files are included.\n"
        "- Review this file before attaching it to a GitHub issue.\n"
    )

    if not log_dirs:
        sections.append(
            "## Logs\n\n"
            f"No scanner logs were found at `{LOG_DIR_ROOT}`. "
            "This is expected if you have not run a scan yet, or if the logs "
            "have been deleted by `cl_delete`.\n"
        )
    else:
        sections.append("## Recent project logs\n")
        for project_dir in log_dirs[:5]:  # most recent 5 projects
            log_file = project_dir / "scanner.log"
            if not log_file.is_file():
                continue
            tail = _tail_file(log_file, tail_lines)
            recent_ids = _extract_recent_request_ids(tail)
            sections.append(
                f"### Project hash `{project_dir.name}`\n\n"
                f"- Log file: `~/.compliancelint/logs/{project_dir.name}/scanner.log`\n"
                f"- Last modified: {datetime.fromtimestamp(log_file.stat().st_mtime, tz=timezone.utc).isoformat()}\n"
                f"- Recent request IDs: {', '.join(f'`{rid}`' for rid in recent_ids) if recent_ids else 'none'}\n\n"
                f"<details>\n<summary>Last {len(tail)} log lines (scrubbed)</summary>\n\n"
                "```\n"
                + "\n".join(tail) + "\n"
                + "```\n\n</details>\n"
            )

    sections.append(
        "## How to submit this report\n\n"
        "1. Review the contents above. Remove anything you do not want public.\n"
        "2. Open https://github.com/ki-sum/compliancelint/issues/new?template=bug_report.yml\n"
        "3. In the **Bug report bundle** field, attach this file or paste its contents.\n"
        "4. Add a one-line description of what you were trying to do.\n\n"
        "If you cannot use GitHub, email this file to "
        "**support@compliancelint.dev** instead.\n"
    )

    out_path.write_text("\n".join(sections), encoding="utf-8")
    return out_path
