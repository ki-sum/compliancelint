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
 * Detect the best way to run the MCP server on this machine.
 * Priority: uvx > pip-installed > python module
 */
function detectServerConfig() {
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
  try {
    execSync("python -c \"import scanner.server\"", { stdio: "ignore", timeout: 3000 });
    return {
      command: "python",
      args: ["-m", "scanner.server"],
      method: "python -m",
    };
  } catch {}

  // Default: uvx (will prompt user to install uv if not available)
  return {
    command: "uvx",
    args: ["compliancelint-server"],
    method: "uvx (default)",
  };
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

  const action = existed ? "updated" : "created";

  console.log(`
${green("\u2713")} ComplianceLint MCP server added to ${MCP_CONFIG_FILE} ${dim(`(${action})`)}
  ${dim(`Using: ${serverConfig.method}`)}

${bold("Next steps:")}
  1. Restart your AI IDE (Claude Code, Cursor, Windsurf)
  2. Ask your AI: ${cyan('"Scan this project for EU AI Act compliance"')}
  3. ${dim("Optional:")} Run ${cyan("cl_connect()")} to link your dashboard
`);

  // If uvx is not available, suggest install
  if (serverConfig.method === "uvx (default)") {
    console.log(`${yellow("Note:")} If you don't have ${bold("uv")} installed, run:
  ${cyan("pip install compliancelint")}
  Then update ${MCP_CONFIG_FILE} to use: ${cyan('"command": "compliancelint-server"')}
`);
  }
}

main();
