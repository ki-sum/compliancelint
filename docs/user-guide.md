# ComplianceLint — User Guide

## How to Run a Compliance Workflow

ComplianceLint runs inside any MCP-enabled AI client (Claude Code, Cursor,
VS Code, and others).
You ask your AI assistant in natural language — the assistant calls the
scanner tools.

---

## Two Scan Modes

### Mode 1 — Fast Scan (black box, may run silently for 10–20 minutes)

Ask your AI assistant:
```
Please scan my project at /path/to/project for EU AI Act compliance.
```

Your AI assistant will call `cl_scan_all` once and return a report.
**Downside**: No visible progress. You won't know if the scan is working or stuck.

---

### Mode 2 — Step-by-Step Scan (recommended, progress visible throughout)

Ask your AI assistant:
```
Please scan my project at /path/to/project for EU AI Act compliance, article by article.

Requirements:
- Before each article, tell me which files you are reading
- Describe what you found in natural language
- After each article, give me a brief summary (compliant/partial/non-compliant)
- After all 44 articles, use cl_sync to upload results to your ComplianceLint dashboard
```

**Why this works**: the AI reads files using Read/Grep tools (visible to you),
narrates its analysis (visible), then calls the scanner tool (brief silent moment).
You see activity at every step.

---

### Mode 3 — Attest Human Gates (after scanning, in the dashboard)

After scanning, many obligations still need structured attestation in the
dashboard. Ask your AI assistant:

```
Open the dashboard and guide me through Human Gates for this project.
```

Your AI client will:
1. Open the Human Gates page for your repo
2. Walk through each applicable article
3. Pre-fill attestation fields from code evidence where possible
4. Flag sections that need your written confirmation

All attestations are saved with timestamp, author, and source — the audit
trail regulators expect.

---

## What You'll See in Step-by-Step Mode

```
▶ Art. 5 — Prohibited Practices (1/44)
  📖 Reading: app/api/chat/route.ts
  📖 Reading: components/chat.tsx
  💬 "Found no emotional manipulation patterns. No social scoring features..."
  ⚙️ [scanner tool runs — ~5 seconds]
  ✅ Result: COMPLIANT — No prohibited practices detected

▶ Art. 6 — Risk Classification (2/44)
  💬 "This is a general-purpose chatbot. Not in Annex III high-risk categories..."
  ⚙️ [scanner tool runs — ~5 seconds]
  ✅ Result: COMPLIANT — Low-risk classification confirmed

... (continues for all 44 articles)

📋 [cl_sync uploads results to ComplianceLint dashboard for PDF export]
```

---

## Who Should Use Which Mode

| User | Mode | Reason |
|------|------|--------|
| Developer running quick check | Mode 1 (Fast) | Don't need to watch |
| Project manager reviewing results | Mode 2 (Step-by-Step) | Can see what's being checked |
| Preparing report for auditor | Mode 2 (Step-by-Step) | Need to verify scan was thorough |
| First time using ComplianceLint | Mode 2 (Step-by-Step) | Learn what each article checks |

---

## Exporting Reports

After scanning and syncing, export professional PDF reports from your ComplianceLint dashboard at [compliancelint.dev](https://compliancelint.dev):

- **Declaration of Conformity** — formal compliance declaration per EU AI Act
- **Scan Findings** — detailed per-obligation findings with evidence
- **Compliance Journey** — scan-over-scan progress timeline
- **Remediation Tasks** — prioritized fix list with legal references
- **Technical Documentation** — Annex IV structured document

> **Note:** ComplianceLint produces AI-assisted compliance assessments, not legal opinions.
> All findings require human review and legal counsel before use in regulatory submissions.

---

## Workflow Summary

```
1. Open Claude Code in VS Code (or Cursor/Windsurf)
2. Make sure ComplianceLint MCP server is connected
3. Paste the Step-by-Step prompt above with your project path
4. Watch Claude work through each article
5. Ask Claude to export the compliance report
```

---

## Technical Note for Developers

The silent period in Mode 1 is a fundamental MCP protocol constraint:
when Claude calls a tool, it cannot output text simultaneously.
Mode 2 minimizes silent periods by having Claude read files directly
(using Read/Grep tools, which show filenames) before calling scanner tools.

The unified `cl_scan` tool accepts an `articles` parameter for per-article scanning
(e.g. `cl_scan(articles="12")` or `cl_scan(articles="9,10,11")`).
Restart your IDE after updating the MCP server to load new tools.
