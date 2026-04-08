#!/usr/bin/env node
// npx compliancelint init — one-line MCP setup for ComplianceLint

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const MCP_CONFIG_FILE = ".mcp.json";

// ANSI color helpers
const green = (s) => `\x1b[32m${s}\x1b[0m`;
const cyan = (s) => `\x1b[36m${s}\x1b[0m`;
const bold = (s) => `\x1b[1m${s}\x1b[0m`;
const dim = (s) => `\x1b[2m${s}\x1b[0m`;
const yellow = (s) => `\x1b[33m${s}\x1b[0m`;

/**
 * Detect the correct python command ("python" or "python3").
 * Never returns a full path — full paths break in bash shells used by AI IDEs.
 */
function detectPythonCommand() {
  for (const cmd of ["python", "python3"]) {
    try {
      execSync(`${cmd} --version`, { stdio: "ignore", timeout: 3000 });
      return cmd;
    } catch {}
  }
  return "python"; // Best guess
}

/**
 * Detect the best way to run the MCP server on this machine.
 * Priority: uvx > pip-installed > python module
 */
function detectServerConfig() {
  const pythonCmd = detectPythonCommand();
  // Option 1: uvx (best — auto-downloads, no pre-install needed)
  try {
    execSync("uvx --version", { stdio: "ignore" });
    return {
      command: "uvx",
      args: ["compliancelint-server"],
      method: "uvx",
    };
  } catch {}

  // Option 2: pip-installed (compliancelint-server in PATH)
  try {
    execSync("compliancelint-server --help", { stdio: "ignore", timeout: 3000 });
    return {
      command: "compliancelint-server",
      args: [],
      method: "pip",
    };
  } catch {}

  // Option 3: python -m (if package is installed but script not in PATH)
  // Use `pip show` instead of `import` — import can succeed with stale .pyc files
  // even after pip uninstall, causing false positives.
  try {
    execSync("pip show compliancelint", { stdio: "ignore", timeout: 3000 });
    return {
      command: pythonCmd,
      args: ["-m", "scanner.server"],
      method: `${pythonCmd} -m`,
    };
  } catch {}

  // Default: pip install compliancelint, then find best way to run
  try {
    console.log(`${dim("Installing compliancelint via pip...")}`);
    execSync("pip install compliancelint", { stdio: "inherit", timeout: 60000 });

    // After install, check if compliancelint-server is now on PATH
    try {
      execSync("compliancelint-server --help", { stdio: "ignore", timeout: 3000 });
      return {
        command: "compliancelint-server",
        args: [],
        method: "pip (auto-installed)",
      };
    } catch {}

    // Script not on PATH (common on Windows user-install) — use python -m
    return {
      command: pythonCmd,
      args: ["-m", "scanner.server"],
      method: "pip (auto-installed)",
    };
  } catch {}

  // Last resort: tell user what to do
  console.error(
    `\x1b[31mError:\x1b[0m Could not find or install ComplianceLint.\n` +
    `Please install manually: ${cyan("pip install compliancelint")}\n` +
    `Then re-run: ${cyan("npx compliancelint init")}`
  );
  process.exit(1);
}

function main() {
  const args = process.argv.slice(2);

  if (args[0] !== "init") {
    console.log(`
${bold("ComplianceLint")} — EU AI Act compliance scanner for your codebase

${bold("Usage:")}
  npx compliancelint init    Set up MCP server in current project

${bold("Install methods:")}
  pip install compliancelint    Install via pip
  uvx compliancelint-server     Run via uvx (no install needed)

${dim("Learn more: https://github.com/ki-sum/compliancelint")}
`);
    process.exit(0);
  }

  const configPath = path.join(process.cwd(), MCP_CONFIG_FILE);

  // Read existing config or start fresh
  let config = { mcpServers: {} };
  let existed = false;

  if (fs.existsSync(configPath)) {
    existed = true;
    try {
      const raw = fs.readFileSync(configPath, "utf-8");
      config = JSON.parse(raw);
      if (!config.mcpServers) {
        config.mcpServers = {};
      }
    } catch (err) {
      console.error(
        `\x1b[31mError:\x1b[0m Could not parse existing ${MCP_CONFIG_FILE}: ${err.message}`
      );
      process.exit(1);
    }
  }

  // Check if already configured
  if (config.mcpServers.compliancelint) {
    console.log(`
${green("\u2713")} ComplianceLint is already configured in ${MCP_CONFIG_FILE}

${bold("Next steps:")}
  1. Restart your AI IDE (Claude Code, Cursor, Windsurf)
  2. Ask your AI: ${cyan('"Scan this project for EU AI Act compliance"')}
`);
    process.exit(0);
  }

  // Detect best server config
  const serverConfig = detectServerConfig();

  // Build MCP server entry
  const entry = {
    command: serverConfig.command,
    args: serverConfig.args,
    env: { PYTHONUNBUFFERED: "1" },
  };

  // Add ComplianceLint server entry (merge, don't overwrite)
  config.mcpServers.compliancelint = entry;

  // Write config
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2) + "\n", "utf-8");

  // Pre-derive git identity and save to .compliancelintrc
  // This runs in a normal terminal (not MCP), so git subprocess is safe.
  try {
    const rcPath = path.join(process.cwd(), ".compliancelintrc");
    let rc = {};
    if (fs.existsSync(rcPath)) {
      try { rc = JSON.parse(fs.readFileSync(rcPath, "utf-8")); } catch {}
    }
    if (!rc.repo_name || !rc.project_id) {
      // Get repo_name from git remote
      try {
        const url = execSync("git remote get-url origin", { stdio: ["pipe", "pipe", "pipe"], timeout: 3000 }).toString().trim();
        if (url) {
          if (url.includes(":") && url.includes("@")) {
            rc.repo_name = url.split(":").pop().replace(".git", "");
          } else if (url.includes("/")) {
            const parts = url.replace(/\/$/, "").replace(".git", "").split("/");
            if (parts.length >= 2) rc.repo_name = `${parts[parts.length - 2]}/${parts[parts.length - 1]}`;
          }
        }
      } catch {}
      if (!rc.repo_name) {
        rc.repo_name = path.basename(process.cwd());
      }
      // Get project_id from SHA256(remote_url:root_commit)
      try {
        const url = execSync("git remote get-url origin", { stdio: ["pipe", "pipe", "pipe"], timeout: 3000 }).toString().trim();
        const root = execSync("git rev-list --max-parents=0 HEAD", { stdio: ["pipe", "pipe", "pipe"], timeout: 3000 }).toString().trim().split("\n")[0];
        if (url && root) {
          const crypto = require("crypto");
          rc.project_id = `git-${crypto.createHash("sha256").update(`${url}:${root}`).digest("hex").slice(0, 16)}`;
        }
      } catch {}
      // Pre-derive attester from git config (name + email)
      if (!rc.attester_name || !rc.attester_email) {
        try {
          const name = execSync("git config user.name", { stdio: ["pipe", "pipe", "pipe"], timeout: 3000 }).toString().trim();
          const email = execSync("git config user.email", { stdio: ["pipe", "pipe", "pipe"], timeout: 3000 }).toString().trim();
          if (name) rc.attester_name = name;
          if (email) rc.attester_email = email;
        } catch {}
      }

      fs.writeFileSync(rcPath, JSON.stringify(rc, null, 2) + "\n", "utf-8");
    }
  } catch {}

  const action = existed ? "updated" : "created";

  console.log(`
${green("\u2713")} ComplianceLint MCP server added to ${MCP_CONFIG_FILE} ${dim(`(${action})`)}
  ${dim(`Using: ${serverConfig.method}`)}

${bold("Next steps:")}
  1. Restart your AI IDE (Claude Code, Cursor, Windsurf)
  2. Ask your AI: ${cyan('"Scan this project for EU AI Act compliance"')}
  3. ${dim("Optional:")} Run ${cyan("cl_connect()")} to link your dashboard
`);

}

main();
