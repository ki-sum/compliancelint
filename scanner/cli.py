#!/usr/bin/env python3
"""ComplianceLint CLI — project setup and MCP server management.

Usage:
  compliancelint init     Set up MCP server in current project
  compliancelint server   Start the MCP server (used by IDE)

`init` creates .mcp.json and .compliancelintrc with git identity + attester.
This runs in a normal terminal (not MCP), so git subprocess is safe here.
"""

import hashlib
import json
import os
import subprocess
import sys

MCP_CONFIG_FILE = ".mcp.json"

# ANSI colors (safe for all terminals)
def _green(s): return f"\033[32m{s}\033[0m"
def _cyan(s): return f"\033[36m{s}\033[0m"
def _bold(s): return f"\033[1m{s}\033[0m"
def _dim(s): return f"\033[2m{s}\033[0m"
_CHECK = "[OK]"  # ASCII-safe checkmark (no Unicode issues on Windows)


def _detect_python_command():
    """Detect the correct python command for this system.

    Returns "python" or "python3" — whichever works.
    Never returns a full path (e.g. C:\\Python313\\python.exe) because
    full paths break in bash shells used by Claude Code and other AI IDEs.
    """
    for cmd in ["python", "python3"]:
        try:
            r = subprocess.run(
                [cmd, "--version"], capture_output=True, timeout=3,
            )
            if r.returncode == 0:
                return cmd
        except Exception:
            pass
    return "python"  # Best guess


def _detect_server_command():
    """Detect the best way to run the MCP server.

    Priority: compliancelint-server (pip) > python -m scanner.server
    """
    python_cmd = _detect_python_command()

    # Option 1: pip-installed entry point
    try:
        subprocess.run(
            ["compliancelint-server", "--help"],
            capture_output=True, timeout=3,
        )
        return {"command": "compliancelint-server", "args": [], "method": "pip"}
    except Exception:
        pass

    # Option 2: python -m (package installed but script not on PATH)
    # Use `pip show` instead of `import` — import can succeed with stale .pyc
    # even after pip uninstall, causing false positives.
    try:
        r = subprocess.run(
            ["pip", "show", "compliancelint"],
            capture_output=True, timeout=3,
        )
        if r.returncode == 0:
            return {
                "command": python_cmd,
                "args": ["-m", "scanner.server"],
                "method": f"{python_cmd} -m",
            }
    except Exception:
        pass

    # Fallback
    return {
        "command": python_cmd,
        "args": ["-m", "scanner.server"],
        "method": f"{python_cmd} -m (default)",
    }


def _derive_git_identity(rc: dict) -> None:
    """Derive repo_name, project_id, and attester from git.

    Safe to call here — this runs in a normal terminal, NOT in MCP context.
    """
    def _git(args, timeout=3):
        try:
            r = subprocess.run(
                ["git"] + args,
                capture_output=True, text=True, timeout=timeout,
            )
            return r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            return ""

    # repo_name from git remote
    if not rc.get("repo_name"):
        url = _git(["remote", "get-url", "origin"])
        if url:
            if ":" in url and "@" in url:
                rc["repo_name"] = url.split(":")[-1].replace(".git", "")
            elif "/" in url:
                parts = url.rstrip("/").replace(".git", "").split("/")
                if len(parts) >= 2:
                    rc["repo_name"] = f"{parts[-2]}/{parts[-1]}"
        if not rc.get("repo_name"):
            rc["repo_name"] = os.path.basename(os.getcwd())

    # project_id from SHA256(remote_url:root_commit)
    if not rc.get("project_id"):
        url = _git(["remote", "get-url", "origin"])
        root = _git(["rev-list", "--max-parents=0", "HEAD"])
        if root:
            root = root.split("\n")[0]
        if url and root:
            h = hashlib.sha256(f"{url}:{root}".encode()).hexdigest()[:16]
            rc["project_id"] = f"git-{h}"

    # attester from git config
    if not rc.get("attester_name"):
        name = _git(["config", "user.name"])
        if name:
            rc["attester_name"] = name
    if not rc.get("attester_email"):
        email = _git(["config", "user.email"])
        if email:
            rc["attester_email"] = email


def cmd_init():
    """Set up ComplianceLint MCP server in the current project directory."""
    config_path = os.path.join(os.getcwd(), MCP_CONFIG_FILE)

    # Read existing .mcp.json or start fresh
    config = {"mcpServers": {}}
    existed = False

    if os.path.isfile(config_path):
        existed = True
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            if "mcpServers" not in config:
                config["mcpServers"] = {}
        except (json.JSONDecodeError, OSError) as e:
            print(f"\033[31mError:\033[0m Could not parse {MCP_CONFIG_FILE}: {e}")
            sys.exit(1)

    # Already configured?
    if "compliancelint" in config.get("mcpServers", {}):
        print(f"""
{_green(_CHECK)} ComplianceLint is already configured in {MCP_CONFIG_FILE}

{_bold("Next steps:")}
  1. Restart your AI IDE (Claude Code, Cursor, Windsurf)
  2. Ask your AI: {_cyan('"Scan this project for EU AI Act compliance"')}
""")
        return

    # Detect server command
    server = _detect_server_command()

    # Build MCP entry
    entry = {
        "command": server["command"],
        "args": server["args"],
        "env": {"PYTHONUNBUFFERED": "1"},
    }

    config["mcpServers"]["compliancelint"] = entry

    # Write .mcp.json
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    # Derive git identity → .compliancelintrc
    rc_path = os.path.join(os.getcwd(), ".compliancelintrc")
    rc = {}
    if os.path.isfile(rc_path):
        try:
            with open(rc_path, "r", encoding="utf-8") as f:
                rc = json.load(f)
        except Exception:
            rc = {}

    _derive_git_identity(rc)

    with open(rc_path, "w", encoding="utf-8") as f:
        json.dump(rc, f, indent=2)
        f.write("\n")

    action = "updated" if existed else "created"

    print(f"""
{_green(_CHECK)} ComplianceLint MCP server added to {MCP_CONFIG_FILE} {_dim(f"({action})")}
  {_dim(f"Using: {server['method']}")}

{_bold("Next steps:")}
  1. Restart your AI IDE (Claude Code, Cursor, Windsurf)
  2. Ask your AI: {_cyan('"Scan this project for EU AI Act compliance"')}
  3. {_dim("Optional:")} Run {_cyan("cl_connect()")} to link your dashboard
""")


def main():
    args = sys.argv[1:]

    if not args or args[0] == "--help" or args[0] == "-h":
        print(f"""
{_bold("ComplianceLint")} — EU AI Act compliance scanner for your codebase

{_bold("Usage:")}
  compliancelint init       Set up MCP server in current project
  compliancelint server     Start the MCP server (used by IDE)

{_bold("Install methods:")}
  pip install compliancelint    Install via pip
  npx compliancelint init       Run via npx (no install needed)

{_dim("Learn more: https://github.com/ki-sum/compliancelint")}
""")
        return

    if args[0] == "init":
        cmd_init()
    elif args[0] == "server":
        # Start MCP server directly
        from scanner.server import main as server_main
        server_main()
    else:
        print(f"Unknown command: {args[0]}")
        print(f"Run {_cyan('compliancelint --help')} for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
