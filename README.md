# ComplianceLint

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://modelcontextprotocol.io/)
[![EU AI Act](https://img.shields.io/badge/EU_AI_Act-247_obligations-emerald.svg)](https://compliancelint.dev)

**From non-compliant to audit-ready. Automatically.**

Scan your code and docs against 247 legal obligations from the EU AI Act. Find compliance gaps, fix them with AI-guided remediation, and track your journey to fully compliant. Your code never leaves your machine.

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

**Prerequisites:** Python 3.10+ is required.

### Option A: npx (recommended)

```bash
npx compliancelint init
```

Auto-detects your environment, installs dependencies, and configures everything. Then reload your IDE window.

### Option B: pip install

```bash
pip install compliancelint
python -m scanner.cli init
```

After setup, reload your IDE window so it picks up the new MCP server, then ask:

> "Scan my project for EU AI Act compliance."

No extra API key needed — uses your existing AI subscription.

### Track over time (optional)

> "Connect to ComplianceLint dashboard."

Opens browser, links your dashboard at [compliancelint.dev](https://compliancelint.dev). Code never leaves your machine — only compliance findings, evidence submissions, remediation progress, and attestation records are synced. This builds an auditable compliance trail that demonstrates your ongoing compliance efforts to regulators and legal counsel.

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

- **Compliance Journey** — visualize progress from non-compliant to compliant over time
- **Findings by article** — bar chart of issues per EU AI Act article
- **Tasks** — prioritized remediation to-do list with severity and effort estimates
- **Scan History** — full audit trail of every scan, with diff between consecutive scans
- **PDF reports** — export audit-ready reports with legal citations
- **Attestation** — record human review decisions with evidence (cl_update_finding)

```
"Connect to ComplianceLint dashboard and sync my scan results."
```

---

## Why ComplianceLint

| | Other tools | ComplianceLint |
|-|------------|----------------|
| **Method** | Check if `RISK_MANAGEMENT.md` exists | AI reads entire codebase, checks against 247 decomposed legal obligations |
| **Citations** | "You need logging" | `Art. 12(1): "High-risk AI systems shall technically allow for the automatic recording of events..."` |
| **False positives** | Keyword matching → many | AI understands context → near zero |
| **Privacy** | Cloud upload | **100% local** — code never leaves your machine |
| **Cost** | Separate subscription | **Free + open source** — uses your existing AI IDE |

---

## "Can't I just ask Claude / ChatGPT to check my compliance?"

You can ask any AI to review your code. But here's the difference:

| | AI chat (Claude, ChatGPT, etc.) | ComplianceLint |
|-|--------------------------------|----------------|
| **Legal structure** | "You probably need logging" — vague, based on general knowledge | 247 specific obligations decomposed from actual EU AI Act articles |
| **Consistency** | Ask twice, get two different answers | Deterministic engine — same code, same result, every time |
| **Completeness** | AI decides what to check (and what to skip) | Every obligation is checked — nothing is missed |
| **Citations** | May hallucinate article numbers | Every finding traced to verbatim EUR-Lex source text |
| **Evidence trail** | Chat transcript (not audit-ready) | Per-obligation findings with timestamps and attestation records |
| **Progress tracking** | Start from scratch every conversation | Persistent history — scan today, compare with last month |
| **Team visibility** | Stuck in one person's chat window | Dashboard for your whole team (PMs, lawyers, auditors) |

**ComplianceLint uses your AI too** — Claude, GPT, or any AI reads the code. But instead of relying on the AI's general knowledge of the law, your answers go through a **verified obligation engine** built from the actual legal text. The AI is the eyes. The engine is the brain.

---

## Coverage

**EU AI Act** (Regulation (EU) 2024/1689) — 44 articles, 247 obligations:

| Article | Topic | Obligations |
|---------|-------|:-----------:|
| Art. 4 | AI literacy | 1 |
| Art. 5 | Prohibited AI practices | 8 |
| Art. 6 | Risk classification | 8 |
| Art. 8 | Compliance with requirements | 2 |
| Art. 9 | Risk management system | 19 |
| Art. 10 | Data governance | 11 |
| Art. 11 | Technical documentation | 9 |
| Art. 12 | Record-keeping (logging) | 11 |
| Art. 13 | Transparency | 4 |
| Art. 14 | Human oversight | 6 |
| Art. 15 | Accuracy & robustness | 8 |
| Art. 16 | Provider obligations | 12 |
| Art. 17 | Quality management system | 16 |
| Art. 18 | Documentation keeping | 2 |
| Art. 19 | Automatically generated logs | 3 |
| Art. 20 | Corrective actions | 3 |
| Art. 21 | Cooperation with authorities | 2 |
| Art. 22 | Authorised representatives | 4 |
| Art. 23 | Obligations of importers | 8 |
| Art. 24 | Obligations of distributors | 8 |
| Art. 25 | Value chain responsibilities | 7 |
| Art. 26 | Deployer obligations | 11 |
| Art. 27 | Fundamental rights impact assessment | 4 |
| Art. 41 | Common specifications | 1 |
| Art. 43 | Conformity assessment | 4 |
| Art. 47 | EU declaration of conformity | 4 |
| Art. 49 | Registration | 3 |
| Art. 50 | Transparency obligations | 10 |
| Art. 51 | GPAI classification (systemic risk) | 3 |
| Art. 52 | Classification notification procedure | 5 |
| Art. 53 | GPAI provider obligations | 8 |
| Art. 54 | GPAI authorised representatives | 6 |
| Art. 55 | GPAI systemic risk obligations | 6 |
| Art. 60 | Real-world testing | 4 |
| Art. 61 | Informed consent for testing | 2 |
| Art. 71 | EU database | 2 |
| Art. 72 | Post-market monitoring | 4 |
| Art. 73 | Serious incident reporting | 6 |
| Art. 80 | Non-high-risk misclassification | 3 |
| Art. 82 | Compliant AI presenting risk | 1 |
| Art. 86 | Right to explanation | 3 |
| Art. 91 | Documentation duty | 1 |
| Art. 92 | Cooperation with evaluations | 1 |
| Art. 111 | Transitional provisions | 3 |

All obligations verified against EUR-Lex source text.

**Why 44 of 113 articles?** The EU AI Act contains 113 articles. ComplianceLint covers the 44 that impose technical or organizational obligations on AI providers, deployers, and distributors. The remaining articles define terminology (Art. 1–3), establish governance bodies (Art. 28–40, 56–59, 64–70), set penalties (Art. 83–85, 99), and contain procedural/transitional provisions — none of which create scannable compliance requirements for software teams.

---

## MCP Tools

| Tool | Purpose |
|------|---------|
| `cl_scan` | Scan article(s) — `cl_scan(regulation="eu-ai-act", articles="12")` or `articles="all"` |
| `cl_scan_all` | Scan all articles in a regulation at once (summary report) |
| `cl_analyze_project` | Understand project structure before scanning |
| `cl_explain` | Plain-language explanation of any article |
| `cl_action_plan` | Prioritized remediation plan with effort estimates |
| `cl_update_finding` | Submit evidence, rebuttals, acknowledgements |
| `cl_update_finding_batch` | Batch-update multiple findings at once |
| `cl_verify_evidence` | Verify submitted evidence |
| `cl_interim_standard` | Generate interim compliance standard for an article |
| `cl_report` | Export Markdown or JSON compliance report |
| `cl_connect` | Link to dashboard (browser OAuth) |
| `cl_sync` | Upload scan results to dashboard |
| `cl_disconnect` | Remove dashboard connection (preserves local data) |
| `cl_delete` | Delete local or remote scan data |
| `cl_check_updates` | Enforcement deadlines and regulation status |
| `cl_version` | Show ComplianceLint version |

All scanning tools accept a `regulation` parameter (default: `"eu-ai-act"`), designed to support multiple regulations as they are added.

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
├── obligations/              Obligation JSONs (structured legal requirements)
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
- [x] 44 EU AI Act articles, 247 obligations
- [x] SaaS Dashboard with Compliance Journey tracking
- [x] PDF exports (Scan Report, Journey, Declaration, Tasks)
- [x] Attestation system (evidence, rebuttals, acknowledgements)
- [x] Zero-friction project identity (git fingerprint)
- [x] `npx compliancelint init` — one-line setup
- [ ] GitHub PR Bot (auto-scan PRs for compliance changes, like Codecov)
- [ ] GitHub Marketplace App
- [ ] Additional regulations (expanding beyond EU AI Act based on user demand)

---

## Accuracy & Testing

| Metric | Value |
|--------|-------|
| Legal obligations covered | 247 (from 44 EU AI Act articles) |
| Unit tests | 2500+ (scanner + dashboard) |
| Archetype test fixtures | Biometric systems to CRUD apps |
| Test pass rate | 100% |
| Obligation engine | Deterministic — same code, same result, every time |
| Source quote verification | All quotes verified verbatim against EUR-Lex |

All obligation logic is tested against 12 synthetic project archetypes — simulated compliance profiles covering diverse scenarios: open-source biometric libraries, commercial chatbots, medical device AI, military/defense systems, CRUD apps with no AI, research prototypes, deployers using third-party APIs, emotion recognition systems, deepfake generators, fully compliant systems, systems with no answers, and out-of-EU-scope systems. Mutation testing verifies that test assertions are meaningful.

---

## Limitations

- **Not a legal opinion.** ComplianceLint provides AI-assisted compliance assessments, not legal advice. All findings require review by qualified legal counsel.
- **AI-dependent scanning.** Scan quality depends on the AI model used (Claude, GPT, etc.). The scanner's obligation engine is deterministic, but the AI's code understanding may vary.
- **EU AI Act only (currently).** Additional regulations are on the roadmap.
- **High-risk focus.** Many obligations (Art. 9–27) apply primarily to high-risk AI systems. Non-high-risk systems may show NOT_APPLICABLE for those obligations.
- **No runtime monitoring.** ComplianceLint scans source code and documentation. It does not monitor running AI systems. For ongoing compliance assurance, schedule periodic scans via CI/CD and use `cl_sync` to maintain an auditable trail of compliance progress over time.
- **English legal citations.** Obligation definitions and source quotes are in English (from the official EUR-Lex publication). However, since ComplianceLint runs inside AI-powered IDEs, the AI will naturally converse, explain regulations, and generate reports in your preferred language.

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
