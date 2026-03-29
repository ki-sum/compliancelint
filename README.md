# ComplianceLint

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://modelcontextprotocol.io/)
[![EU AI Act](https://img.shields.io/badge/EU_AI_Act-94_obligations-emerald.svg)](https://compliancelint.dev)

**From non-compliant to audit-ready. Automatically.**

Scan your code and docs against 94 legal obligations from the EU AI Act. Find compliance gaps, fix them with AI-guided remediation, and track your journey to fully compliant. Your code never leaves your machine.

> **2026-08-02** — EU AI Act high-risk requirements become enforceable. ComplianceLint helps you prepare now.

> **Note:** ComplianceLint is a compliance engineering tool, not a law firm. It gives you a structured, evidence-based path toward compliance — but final legal decisions should always involve qualified legal counsel.

---

## Who Needs This

- **AI product teams** — building chatbots, recommendation engines, content generation, or any AI-powered feature
- **Solo developers & founders** — shipping AI products and need to know if they comply before enforcement begins
- **CTOs & engineering leads** — need compliance visibility without hiring a legal team
- **Compliance officers** — want code-level evidence, not just checkbox questionnaires

If your software uses AI and you serve EU customers, the EU AI Act applies to you.

---

## Quick Start

### Option A: One command (recommended)

```bash
npx compliancelint init
```

This adds ComplianceLint to your project's MCP config. Works with Claude Code, Cursor, Windsurf, and any MCP-compatible IDE.

### Option B: pip install

```bash
pip install compliancelint
```

Then add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "compliancelint": {
      "command": "compliancelint-server",
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

### Option C: Manual setup

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "compliancelint": {
      "type": "stdio",
      "command": "python",
      "args": ["/path/to/scanner/server.py"],
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

| IDE | Config location |
|-----|----------------|
| Claude Code | `.mcp.json` in project root |
| Cursor | Settings → MCP → Add Server |
| Windsurf | `.mcp.json` in project root |
| Codex | MCP settings |
| Zed | MCP settings |

### Then ask your AI

> "Scan my project for EU AI Act compliance."

That's it. No extra API key needed — uses your existing AI subscription.

### Track over time (optional)

> "Connect to ComplianceLint dashboard."

Opens browser, links your dashboard at [compliancelint.dev](https://compliancelint.dev). Code never leaves your machine — only compliance findings are synced.

---

## What You Get

```
Art. 12 — Record-keeping                            NON-COMPLIANT

┌──────────────┬────────────┬──────────────────────────────────────────┐
│ Obligation   │ Status     │ Description                              │
├──────────────┼────────────┼──────────────────────────────────────────┤
│ ART12-OBL-1  │ COMPLIANT      │ Logging detected (structlog)         │
│ ART12-OBL-2a │ NON_COMPLIANT  │ Risk event logging not found         │
│ ART12-OBL-4  │ NON_COMPLIANT  │ No retention policy documented       │
│ ART12-OBL-3a │ NOT_APPLICABLE │ Not a biometric system               │
└──────────────┴────────────┴──────────────────────────────────────────┘

Legal citation: Art. 12(1): "High-risk AI systems shall technically allow
for the automatic recording of events (logs)..."
```

Every finding includes:
- **Exact legal citation** — verbatim from EUR-Lex
- **Obligation ID** — traceable to our structured obligation database
- **AI evidence** — what the AI found (or didn't find) in your code
- **Remediation steps** — how to fix it

---

## From Non-Compliant to Compliant

ComplianceLint doesn't just find problems — it helps you fix them.

### 1. Get a remediation plan

> "Give me an action plan to fix my compliance issues."

The AI generates a prioritized plan with effort estimates — what to fix first, what code to change, and what documentation to add.

### 2. Fix and re-scan

Make the changes, then scan again. ComplianceLint tracks what improved and what's still open.

### 3. Record evidence

> "I've fixed the logging issue. Please re-check and update the finding."

The AI verifies your fix, updates the finding status, and records who made the change and when — ready for auditors.

### 4. Track your journey

Each scan is a snapshot. Over time, your dashboard shows the full compliance journey — from first scan to fully compliant. Export a PDF for your auditor or investor at any point.

---

## Dashboard

Track compliance over time at **[compliancelint.dev](https://compliancelint.dev)**:

- Compliance Journey — visualize progress from non-compliant to compliant
- Findings by article — bar chart of issues per EU AI Act article
- PDF reports — export audit-ready reports with legal citations
- Attestation — record human review decisions (cl_update_finding)

```
"Connect to ComplianceLint dashboard and sync my scan results."
```

---

## Why ComplianceLint

| | Other tools | ComplianceLint |
|-|------------|----------------|
| **Method** | Check if `RISK_MANAGEMENT.md` exists | AI reads entire codebase, checks against 94 decomposed legal obligations |
| **Citations** | "You need logging" | `Art. 12(1): "High-risk AI systems shall technically allow for the automatic recording of events..."` |
| **False positives** | Keyword matching → many | AI understands context → near zero |
| **Privacy** | Cloud upload | **100% local** — code never leaves your machine |
| **Cost** | Separate subscription | **Free + open source** — uses your existing AI IDE |

---

## "Can't I just ask Claude / ChatGPT to check my compliance?"

You can ask any AI to review your code. But here's the difference:

| | AI chat (Claude, ChatGPT, etc.) | ComplianceLint |
|-|--------------------------------|----------------|
| **Legal structure** | "You probably need logging" — vague, based on general knowledge | 94 specific obligations decomposed from actual EU AI Act articles |
| **Consistency** | Ask twice, get two different answers | Deterministic engine — same code, same result, every time |
| **Completeness** | AI decides what to check (and what to skip) | Every obligation is checked — nothing is missed |
| **Citations** | May hallucinate article numbers | Every finding traced to verbatim EUR-Lex source text |
| **Evidence trail** | Chat transcript (not audit-ready) | Per-obligation findings with timestamps and attestation records |
| **Progress tracking** | Start from scratch every conversation | Persistent history — scan today, compare with last month |
| **Team visibility** | Stuck in one person's chat window | Dashboard for your whole team (PMs, lawyers, auditors) |

**ComplianceLint uses your AI too** — Claude, GPT, or any AI reads the code. But instead of relying on the AI's general knowledge of the law, your answers go through a **verified obligation engine** built from the actual legal text. The AI is the eyes. The engine is the brain.

---

## Coverage

**EU AI Act** (Regulation (EU) 2024/1689) — 10 articles, 94 obligations:

| Article | Topic | Obligations |
|---------|-------|:-----------:|
| Art. 5 | Prohibited AI practices | 8 |
| Art. 6 | Risk classification | 8 |
| Art. 9 | Risk management system | 19 |
| Art. 10 | Data governance | 11 |
| Art. 11 | Technical documentation | 9 |
| Art. 12 | Record-keeping (logging) | 11 |
| Art. 13 | Transparency | 4 |
| Art. 14 | Human oversight | 6 |
| Art. 15 | Accuracy & robustness | 8 |
| Art. 50 | Transparency obligations | 10 |

All obligations verified against EUR-Lex source text via Three Locks methodology.

---

## MCP Tools

| Tool | Purpose |
|------|---------|
| `cl_scan` | Scan any article(s) — e.g. `cl_scan(article=12)` or `cl_scan(article="all")` |
| `cl_analyze_project` | Understand project structure before scanning |
| `cl_explain_article` | Plain-language explanation of any article |
| `cl_action_plan` | Prioritized remediation plan with effort estimates |
| `cl_update_finding` | Submit evidence, rebuttals, acknowledgements |
| `cl_verify_evidence` | Verify submitted evidence |
| `cl_export_report` | Export Markdown or JSON compliance report |
| `cl_connect` | Link to dashboard (browser OAuth) |
| `cl_sync` | Upload scan results to dashboard |
| `cl_check_updates` | Enforcement deadlines and regulation status |
| `cl_version` | Show ComplianceLint version |

Plus per-article shortcuts (`cl_scan_article_5`, `cl_scan_article_6`, etc.) for convenience.

---

## Compliance Badge

Add a real-time compliance badge to your README:

```markdown
![EU AI Act](https://compliancelint.dev/api/v1/badge/YOUR_REPO_ID)
```

---

## Project Structure

```
scanner/
├── server.py                 MCP Server entry point
├── core/
│   ├── obligation_engine.py  Obligation-driven analysis
│   ├── context.py            AI-to-scanner bridge
│   ├── config.py             Project configuration
│   └── state.py              Scan persistence + project identity
├── modules/                  Per-article scanning modules
├── obligations/              Obligation JSONs (from deontic decomposition)
└── tests/                    Unit + integration tests
```

---

## Pricing

The scanner is **free and open source** (Apache 2.0). The dashboard is freemium:

| | Free | Solo (€19/mo) | Pro (€49/mo) | Team (€149/mo) | Enterprise |
|-|------|---------------|--------------|----------------|------------|
| Developers | 1 | 1 | 5 | 25 | Unlimited |
| Projects | 1 | Unlimited | Unlimited | Unlimited | Unlimited |
| Scan history | 7 days | Unlimited | Unlimited | Unlimited | Unlimited |
| PDF reports | Watermarked | Full | Full | Full | Custom |
| Invite others | — | ✓ | ✓ | ✓ | ✓ |

---

## Roadmap

- [x] MCP Server
- [x] 10 EU AI Act articles, 94 obligations
- [x] SaaS Dashboard with Compliance Journey tracking
- [x] PDF exports (Scan Report, Journey, Declaration, Tasks)
- [x] Attestation system (evidence, rebuttals, acknowledgements)
- [x] Compliance Badge for README
- [x] Zero-friction project identity (git fingerprint)
- [x] `npx compliancelint init` — one-line setup
- [ ] Art. 4 AI Literacy (in force since Feb 2025)
- [ ] Art. 51-56 GPAI model obligations (in force since Aug 2025)
- [ ] Art. 26 Deployer obligations (enforceable Aug 2026)
- [ ] Art. 17 Quality Management System (enforceable Aug 2026)
- [ ] Additional regulations (GDPR, NIS2, DORA)
- [ ] PR Comment Bot (Codecov-style)
- [ ] GitHub Marketplace App

---

## Accuracy & Testing

| Metric | Value |
|--------|-------|
| Legal obligations covered | 94 (from 10 EU AI Act articles) |
| Unit tests | 800+ (scanner + dashboard) |
| Archetype test fixtures | Biometric systems to CRUD apps |
| Test pass rate | 100% |
| Obligation engine | Deterministic — same code, same result, every time |
| Source quote verification | All quotes verified verbatim against EUR-Lex |

All obligation logic is tested against 12 project archetypes covering the full spectrum from "fully compliant" to "all null answers". Mutation testing verifies that test assertions are meaningful.

---

## Limitations

- **Not a legal opinion.** ComplianceLint provides AI-assisted compliance assessments, not legal advice. All findings require review by qualified legal counsel.
- **AI-dependent scanning.** Scan quality depends on the AI model used (Claude, GPT, etc.). The scanner's obligation engine is deterministic, but the AI's code understanding may vary.
- **EU AI Act only (currently).** GDPR and other regulations are planned but not yet available.
- **High-risk focus.** Articles 9–15 apply primarily to high-risk AI systems. Non-high-risk systems may show NOT_APPLICABLE for many obligations.
- **No runtime monitoring.** ComplianceLint scans source code statically. It does not monitor running AI systems.
- **English only.** Legal citations and findings are in English. The EU AI Act source text is from the official English EUR-Lex publication.

---

## Human Oversight Design

ComplianceLint is designed with human oversight at every stage:

1. **Human initiates scans** — the AI never scans autonomously; the user explicitly requests each scan
2. **Human reviews findings** — all findings are presented for human judgment before any action
3. **Human submits evidence** — `cl_update_finding` allows users to acknowledge, rebut, defer, or provide evidence for any finding
4. **Human controls sync** — scan results are only uploaded to the dashboard when the user explicitly runs `cl_sync`
5. **No autonomous decisions** — ComplianceLint never makes compliance determinations without human review

The user can stop any MCP tool call at any time by pressing Stop in their IDE.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE)

---

## Contributing

Issues and PRs welcome. See the [GitHub Issues](https://github.com/ki-sum/compliancelint/issues) page to report bugs or request features.
