"""Coverage for README claim C124 'Git-host neutral — works with
GitHub, GitLab, Bitbucket, Gitea, Azure DevOps, self-hosted, or a
purely local repo'.

§Y bootstrap pass 2026-05-03 — F-005 mechanical 1-liner test.

Strategy: structural absence assertion. The git-host neutrality
claim is true if scanner code has zero host-conditional branches
(if hostname == 'github.com' do X else do Y). This test scans
scanner/ source for forbidden host-conditional patterns and
hardcoded host references outside the allowed allowlist (CI-config
detection list + bug-report URL).

If a future PR introduces github.com / gitlab.com / bitbucket.org
hardcoded behavior, this test fails — preserving the public
neutrality claim.
"""
import os
import re

SCANNER_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def _python_sources_in_scanner():
    """Walk scanner/ for .py files, excluding tests/ and __pycache__."""
    for root, dirs, files in os.walk(SCANNER_ROOT):
        # Skip cache + tests + virtual envs
        dirs[:] = [d for d in dirs if d not in {"__pycache__", "tests", ".venv", "venv", ".pytest_cache"}]
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


# Files / lines explicitly allowed to reference host names.
# Each entry = (file relative to SCANNER_ROOT, reason).
ALLOWED_HOST_REFERENCES = {
    "cli.py": "bug-report URL link to ki-sum/compliancelint Issues",
    "server.py": "bug-report URL link",
    "core/bug_report.py": "bug-report URL constant",
    "core/error_response.py": "bug-report URL hint",
    # art50 transparency module mentions external SDK doc URLs in
    # obligation detection hints (string content, not behavior
    # gating)
    "modules/art50-transparency-obligations/module.py":
        "external SDK doc URLs in obligation detection hints",
}


HOST_PATTERNS = [
    r"github\.com",
    r"gitlab\.com",
    r"bitbucket\.org",
    r"dev\.azure\.com",
    r"gitea\.io",
]


def test_no_host_conditional_branches_in_scanner_core():
    """Look for `if ... github.com ...` style host-conditional logic
    that would falsify the host-neutral claim."""
    found = []
    for path in _python_sources_in_scanner():
        rel = os.path.relpath(path, SCANNER_ROOT).replace("\\", "/")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        for pattern in HOST_PATTERNS:
            # Only flag when the host appears WITHIN a conditional —
            # crude but catches the obvious shape.
            for m in re.finditer(rf"\bif\b[^\n]*{pattern}", content):
                found.append((rel, m.group(0)[:80]))
    assert not found, (
        f"Found {len(found)} host-conditional branch(es) in scanner/. "
        f"This falsifies README:312 'Git-host neutral' claim. "
        f"First 3: {found[:3]}"
    )


def test_host_name_references_are_allowlisted():
    """Any hardcoded host string in scanner/ must be in
    ALLOWED_HOST_REFERENCES with a documented reason. New unallowed
    hosts → fix the source OR update the allowlist (with PR
    justification)."""
    unexpected = []
    for path in _python_sources_in_scanner():
        rel = os.path.relpath(path, SCANNER_ROOT).replace("\\", "/")
        if rel in ALLOWED_HOST_REFERENCES:
            continue
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        for pattern in HOST_PATTERNS:
            if re.search(pattern, content):
                unexpected.append((rel, pattern))
    assert not unexpected, (
        f"Found {len(unexpected)} unexpected host reference(s) outside "
        f"the allowlist. If legitimate (e.g. another bug-report URL), "
        f"add to ALLOWED_HOST_REFERENCES with a documented reason. "
        f"Otherwise this falsifies the host-neutral claim. First 3: "
        f"{unexpected[:3]}"
    )
