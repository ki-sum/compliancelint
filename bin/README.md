# ComplianceLint CLI — `npx compliancelint init`

One-line setup to add ComplianceLint's MCP server to any project.

## Usage

```bash
npx compliancelint init
```

This will:
1. Create or update `.mcp.json` in the current directory
2. Detect the best way to run the server (uvx > pip > python)
3. Add the `compliancelint` MCP server entry
4. Print next steps

## Install methods

```bash
# Option 1: npx init (recommended — sets up MCP config automatically)
npx compliancelint init

# Option 2: pip install (then configure MCP manually)
pip install compliancelint
```

## What it configures

The command auto-detects your environment and adds one of these to `.mcp.json`:

```json
{
  "mcpServers": {
    "compliancelint": {
      "command": "uvx",
      "args": ["compliancelint-server"],
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

Or if pip-installed:

```json
{
  "mcpServers": {
    "compliancelint": {
      "command": "compliancelint-server",
      "args": [],
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

If `.mcp.json` already exists with other servers, ComplianceLint is merged in without affecting existing entries.

## After setup

1. Restart your AI IDE (Claude Code, Cursor, Windsurf)
2. Ask your AI: "Scan this project for EU AI Act compliance"
3. Run `cl_connect()` to link your dashboard at [compliancelint.dev](https://compliancelint.dev)
