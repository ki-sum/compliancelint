# ComplianceLint

[![License](https://img.shields.io/badge/License-BSL_1.1-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://modelcontextprotocol.io/)
[![EU AI Act](https://img.shields.io/badge/EU_AI_Act-247_obligations-emerald.svg)](https://compliancelint.dev)

**Compliance in your IDE. Not in a meeting.**

From EU AI Act code to audit-ready evidence — in one workflow, inside the tools you already use.

Scan, attest, and document EU AI Act compliance without leaving your IDE. The scanner catches code-verifiable violations; Human Gates capture human attestations (with AI-assisted evidence collection along the way) — all with audit trail. Your code never leaves your machine.

> **EU AI Act enforcement timeline**:
> - **2025-02-02** — Art. 5 prohibited practices + Art. 99 penalty regime in force
> - **2025-08-02** — Art. 51-55 GPAI obligations in force
> - **2026-08-02** *(original)* — Art. 6-27 high-risk obligations were due to become enforceable
> - **2026-05-07** — Council + Parliament reached political agreement on the Digital Omnibus delaying high-risk obligations to **2027-12-02** (standalone Annex III systems) and **2028-08-02** (embedded in Annex I products). Provisional pending formal adoption; if not adopted before 2026-08-02, the original timeline applies. GenAI watermarking for pre-Aug-2026 models delayed to 2026-12-02.
>
> Track current status in-app: [compliancelint.dev/dashboard/regulations/eu-ai-act](https://compliancelint.dev/dashboard/regulations/eu-ai-act).

> **Note:** ComplianceLint is a compliance engineering tool, not a law firm. It gives you a structured, evidence-based path toward compliance — but final legal decisions should always involve qualified legal counsel.

### See it in action

Try the live demo at **[compliancelint.dev/demo](https://compliancelint.dev/demo)** — pre-loaded with three AI systems (limited-risk chatbot, high-risk finance, high-risk medical) so you can browse a real scan, attestation flow, and Compliance Journey trend without setting up a project of your own.

### Dashboard

![ComplianceLint Dashboard](docs/media/dashboard.png)

Track compliance across all your AI systems. Export audit-ready PDF reports.

### Documentation

Full user manual at **[compliancelint.dev/docs](https://compliancelint.dev/docs/quick-start)** — 33 chapters covering setup, daily use, persona-specific reference (Provider / Product Manufacturer / Deployer / Importer / Distributor / Authorised Representative), and troubleshooting.

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

### Connect for full scanning (free)

> "Connect to ComplianceLint dashboard."

Opens browser, links your scanner to [compliancelint.dev](https://compliancelint.dev) with a free account. **Free sign-up enables full scanning** — the 5 detection-related fields (`detection_method`, `what_to_scan`, `confidence`, `human_judgment_needed`, `rationale`) live SaaS-side and are fetched per article at scan time. Until your scanner is connected to the dashboard, it runs in degraded mode: obligation list + automation `level` browsable, but no detection logic. The BSL source remains usable as an obligation browser; sign-up unlocks the methodology layer.

### Track over time (optional, paid tiers)

> "Sync my compliance results."

Uploads findings to your dashboard. Code never leaves your machine — only compliance findings, evidence submissions, remediation progress, and attestation records are synced. This builds an auditable compliance trail that demonstrates your ongoing compliance efforts to regulators and legal counsel.

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
- **Audit-ready PDF exports** — every PDF carries verbatim EUR-Lex citations + obligation IDs:
  - **Declaration of Conformity** (Art. 47, Annex V) — provider attestation document for high-risk AI systems
  - **Technical Documentation** (Art. 11, Annex IV §1–§8) — full system dossier covering data governance, risk management, accuracy / robustness, post-market monitoring
  - **Per-article Compliance PDF** — one per attested article, generated after Save with all findings + evidence + Human Gate answers for that article
  - **Compliance Journey PDF** — visual progress export for stakeholders, investors, or board reporting
  - **Compliance All-in-One Pack ZIP** (Business+) — audit-grade snapshot bundling all of the above plus an embedded offline HTML viewer that mirrors the live dashboard
- **Attestation** — record human review decisions with evidence directly in the dashboard, or ask your AI to submit evidence via natural-language conversation
- **Evidence stays in your repo** — upload files from the dashboard; bytes commit to `.compliancelint/evidence/` in your git repo. We relay transiently, never hold your files.
- **Profiling Wizard** — guided 3-section interview about your AI system + organisational role + Art. 2 scope carve-outs (territorial, military, research, open-source); filters the 247-obligation matrix down to the ones that actually apply to you
- **Human Gates** — guided questionnaires for obligations that need human judgment (FRIA, Art. 14 human oversight, Art. 26(7) worker notifications); each answer saved as attestation evidence with full audit trail
- **Penalty Exposure** — live € estimate per non-compliant finding using Art. 99 caps (€35M or 7% turnover for Art. 5 prohibitions; €15M or 3% for high-risk violations); applies the Art. 99(6) SME min-fine formula for microenterprise / small / medium organisations
- **Role-based filtering** — Provider / Product Manufacturer / Deployer / Importer / Distributor / Authorised Representative; combined with Art. 2 carve-outs auto-narrows the obligation set so you don't see noise from articles that don't apply

```
"Connect to ComplianceLint dashboard and sync my scan results."
```

---

## Human Oversight (design principle)

ComplianceLint is designed with human oversight at every stage:

1. **Human initiates scans** — the AI never scans autonomously; the user explicitly requests each scan
2. **Human reviews findings** — all findings are presented for human judgment before any action
3. **Human submits evidence** — users acknowledge, rebut, defer, or provide evidence for any finding via natural-language conversation with their AI (which invokes `cl_update_finding` on their behalf)
4. **Human controls sync** — scan results are only uploaded to the dashboard when the user explicitly asks the AI to sync
5. **No autonomous decisions** — ComplianceLint never makes compliance determinations without human review

The user can stop any MCP tool call at any time by pressing Stop in their IDE.

> This is the **architectural principle** — distinct from **Human Gates** in the Dashboard section above, which are guided questionnaires for specific EU AI Act obligations (FRIA, Art. 14 oversight, Art. 26(7) worker notifications). Human Oversight here means AI never acts compliance-decisively without your approval; Human Gates is the dashboard feature that captures your judgment for obligations the scanner can't determine from code alone.

---

## Why ComplianceLint

| | Other tools | ComplianceLint |
|-|------------|----------------|
| **Method** | Check if `RISK_MANAGEMENT.md` exists | AI reads entire codebase, checks against 247 decomposed legal obligations |
| **Citations** | "You need logging" | `Art. 12(1): "High-risk AI systems shall technically allow for the automatic recording of events..."` |
| **False positives** | Keyword matching → many | AI understands context → near zero |
| **Privacy** | Cloud upload | **Code stays local** — source never leaves your machine; only compliance verdicts sync to your dashboard |
| **Cost** | Separate subscription | **Free + source-available (BSL 1.1)** — uses your existing AI IDE |

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

Not all 44 articles apply to every project. The applicable obligations depend on your role (provider, product manufacturer, deployer, importer, distributor, authorised representative) and risk classification. Configure your role in the [dashboard](https://compliancelint.dev) for accurate scoring.

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
| `cl_get_ai_observation` | Fetch the AI's prior observation for an obligation (read-back of what your IDE AI told the dashboard last scan) |
| `cl_verify_evidence` | Verify submitted evidence |
| `cl_interim_standard` | Generate interim compliance standard for an article |
| `cl_connect` | Link to dashboard (browser OAuth) |
| `cl_sync` | Upload scan results to dashboard |
| `cl_disconnect` | Remove dashboard connection (preserves local data) |
| `cl_delete` | Delete with scope — `target="local"` (scan cache only, preserves evidence + rc), `target="all"` (local + evidence + rc), `target="dashboard"` (server-side purge) — all require explicit `confirm=true` |
| `cl_action_guide` | Get guidance for Human Gate obligations (directs to dashboard) |
| `cl_check_updates` | Enforcement deadlines and regulation status |
| `cl_version` | Show ComplianceLint version |
| `cl_report_bug` | Generate privacy-scrubbed bug-report bundle for GitHub issues |

All scanning tools accept a `regulation` parameter (default: `"eu-ai-act"`), designed to support multiple regulations as they are added.

### Auto-discoverable — zero-config setup

Point any MCP-compatible client at `compliancelint.dev` and it auto-detects our MCP server via the standard discovery endpoint:

```
https://compliancelint.dev/.well-known/mcp/server-card.json
```

Returns server metadata, tool catalogue, transport types, and auth flow — the same pattern OAuth uses (`/.well-known/oauth-authorization-server`). Implementation per [SEP-2127](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2127).

No manual JSON config required for clients that support discovery (Claude Desktop, Claude Code, Cursor, Windsurf, Cline, ChatGPT, Goose). Verify the endpoint yourself:

```sh
curl https://compliancelint.dev/.well-known/mcp/server-card.json | jq .
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
├── obligations/              Obligation JSONs (structured legal requirements)
└── tests/                    Unit + integration tests
```

---

## Git-native by design

ComplianceLint treats your git repository as the primary evidence store,
not our SaaS. Five architectural commitments:

1. **Evidence commits to your repo.** Bytes land at
   `.compliancelint/evidence/{finding_id}/{filename}` — you own them,
   you can grep them, they survive if we vanish. A sibling `manifest.json`
   under the same directory records who uploaded what, when, and at which
   sha — the audit-trail primary record. Scan cache (state.json, per-
   article results, baselines) lives in `.compliancelint/local/` and is
   gitignored; only evidence and the `.compliancelintrc` project binding
   are committed.

2. **MCP never runs git on your behalf.** No auto-commit, no auto-push,
   no auto-revert. Every commit is your decision. If you commit locally
   without pushing, the next sync waits until you push.

3. **Git-host neutral.** Works with GitHub, GitLab, Bitbucket, Gitea,
   Azure DevOps, self-hosted, or a purely local repo. MCP commits
   locally using your existing git config + SSH agent — no credentials
   shared with our SaaS. Planned OAuth integration for GitHub and
   GitLab (post-launch) will offer direct SaaS commits as an opt-in
   convenience; the MCP path always remains supported.

4. **Force-push aware.** If you rewrite history and erase an evidence
   commit, the next sync detects the missing file and flags it on
   the dashboard (`health_status='broken_link'`). The forensic record
   stays — who uploaded, when, at which sha — even after the bytes
   are gone from git.

5. **Snapshot ledger is your integrity anchor.** Every scan writes a
   deterministic hash (`sort_keys` + UTC ISO + fixed-precision floats)
   of findings + evidence state. Reproduce on any machine; compare to
   catch silent mutations. Git history is *not* the audit trail —
   the snapshot ledger is.

---

## Pricing

The scanner is **free and source-available** ([BSL 1.1](LICENSE)). The dashboard is freemium:

| | Free | Starter | Pro | Business | Enterprise |
|-|------|---------|-----|----------|------------|
| **Monthly** | €0 forever | €29/mo | €99/mo | €199/mo | Custom |
| **Annual (per-month rate · billed yearly)** | — | €25/mo · €300/yr (Save €48/yr) | €79/mo · €948/yr | €149/mo · €1,788/yr | — |
| Projects | 1 | 2 | 10 | Unlimited | Unlimited |
| Scan history | 7 days | Unlimited | Unlimited | Unlimited | Unlimited |
| PDF reports | Watermarked | Clean | Clean | Clean | Clean |
| All 247 obligations visible (worst-case) | ✓ | ✓ | ✓ | ✓ | ✓ |
| Penalty display (worst-case Art. 99 caps) | ✓ | ✓ | ✓ | ✓ | ✓ |
| Team members | Unlimited | Unlimited | Unlimited | Unlimited | Unlimited |
| **Scope narrowing** — see only obligations applicable to your AI system (typically saves ~70% review time) | — | ✓ | ✓ | ✓ | ✓ |
| **Risk classification picker** (Art. 5 / 6 / 50) | — | ✓ | ✓ | ✓ | ✓ |
| **SME relief** (Art. 11 simplified tech-doc per Recommendation 2003/361/EC) | — | ✓ | ✓ | ✓ | ✓ |
| **Per-obligation questionnaires** (anchor AI answers to verbatim legal text) | — | ✓ | ✓ | ✓ | ✓ |
| **Art. 2 carve-outs** (territorial / military / research / open-source — entire-Act exemption flags) | — | ✓ | ✓ | ✓ | ✓ |
| Penalty configuration (precise — based on your headcount + turnover + balance sheet) | — | ✓ | ✓ | ✓ | ✓ |
| Evidence — `text` declarations + `git_path` pointers (captured: content saved in DB or git) | — | ✓ | ✓ | ✓ | ✓ |
| Evidence — `url_reference` (external pointer — content not captured, may link-rot) | — | ✓ | ✓ | ✓ | ✓ |
| Evidence — `repo_file` upload from dashboard (bytes relayed to your git repo) | — | — | ✓ | ✓ | ✓ |
| Human Gates questionnaires (per-obligation Yes/No + Notes — the attestation surface) | — | ✓ | ✓ | ✓ | ✓ |
| Declaration of Conformity PDF (EU AI Act Art. 47 Annex V) | — | — | ✓ | ✓ | ✓ |
| Technical Documentation PDF (Annex IV §1–§8) | — | — | ✓ | ✓ | ✓ |
| Per-article Compliance PDF (one per attested article, post-Save) | — | — | ✓ | ✓ | ✓ |
| SARIF export — via [GitHub Action composite](https://compliancelint.dev/ci-cd) (no dashboard button; uploads to GitHub Code Scanning) | — | — | ✓ | ✓ | ✓ |
| CI/CD quality gate — runs in your CI runner; any AI driver via MCP, see [/ci-cd](https://compliancelint.dev/ci-cd) for the platform-agnostic prompt | — | — | ✓ | ✓ | ✓ |
| Multi-framework mapping (ISO 42001, NIST AI RMF) | — | — | — | ✓ | ✓ |
| Regulation updates timeline (in-app) — current EU AI Act milestones; email digest is Business+ roadmap | ✓ | ✓ | ✓ | ✓ | ✓ |
| Compliance All-in-One Pack (audit-grade snapshot zip) | — | — | — | ✓ | ✓ |
| OSCAL export — structured compliance data (NIST OSCAL JSON) for GRC / audit ingestion | — | — | — | — | ✓ |
| Cryptographically signed Compliance All-in-One Pack — tamper-evident audit chain | — | — | — | — | ✓ |
| SSO / SAML / on-prem | — | — | — | — | ✓ |
| Custom SaaS UI translation (your team's language) — bespoke build per engagement | — | — | — | — | ✓ |

**Evidence stays in your repo.** Upload files from the dashboard — bytes commit to `.compliancelint/evidence/` in your git repo. We relay transiently. We never hold your files.

**Team members are free + unlimited.** Invited members inherit the owner's tier — Pro members get Human Gates, Business members get Compliance All-in-One Pack exports. No per-seat billing. All actions are audit-logged with the actor's identity.

---

## Roadmap

### Shipped

- [x] **MCP Server** with full EU AI Act tool surface — 44 articles, 247 obligations
- [x] **SaaS Dashboard** with Compliance Journey tracking
- [x] **Audit-ready PDFs** — Compliance Journey, Declaration of Conformity (Art. 47), Technical Documentation (Art. 11), per-article evidence packs, and the Compliance All-in-One Pack ZIP
- [x] **`npx compliancelint init`** — one-line setup for Claude Code, Cursor, Windsurf, Claude Desktop, ChatGPT (zero-config auto-discovery via [SEP-2127](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2127))
- [x] **Role-based obligation filtering** — Provider, Product Manufacturer, Deployer, Importer, Distributor, Authorised Representative
- [x] **Profiling Wizard** — guided questions about your AI system + organisational role; filters the 247-obligation matrix down to what actually applies to you
- [x] **Human Gates** — guided questionnaires for obligations that need human judgment (FRIA, Art. 14 oversight, Art. 26(7) worker notifications)
- [x] **Evidence trail** — attestations, rebuttals, acknowledgements, deferrals with full audit history
- [x] **EU AI Act browser** at [`/dashboard/regulations/eu-ai-act`](https://compliancelint.dev/dashboard/regulations/eu-ai-act) — full text of 44 articles + 13 annexes + searchable across 247 obligations (free after sign-up, no credit card)
- [x] **Tamper-evident audit trail** — deterministic state hashing, evidence health sweeps, cross-OS CI tested (Ubuntu, macOS, Windows × Python 3.10–3.13)

### Up next

- [ ] **OAuth direct-commit** — dashboard commits evidence to your cloud git without MCP running (GitHub → GitLab)
- [ ] **GitHub Marketplace App** — discovery + one-click install
- [ ] **Multi-regulation expansion** — same scanner + Human Gates architecture, next regulations prioritised by customer demand. Likely candidates: GDPR, CRA, NIS2, DORA, ISO 27001
- [ ] **Incremental scanning** — only re-scan obligations whose underlying code changed since the last full scan
- [ ] **Human Gates evidence verifier** — AI cross-checks questionnaire answers against `source_quote` requirements before promoting evidence to COMPLIANT
- [ ] **Enterprise integrations** — OSCAL export, signed All-in-One Pack, SSO / SAML, on-prem (built per engagement)
- [ ] **MCP Apps** — interactive UI widgets inside Claude / Cursor / ChatGPT conversations, per the [MCP Apps spec](https://github.com/modelcontextprotocol/ext-apps)

---

## Accuracy & Testing

| Metric | Value |
|--------|-------|
| Legal obligations covered | 247 (from 44 EU AI Act articles) |
| Test coverage | Unit + integration + e2e (scanner pytest, dashboard Vitest, Playwright) |
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
- **No runtime monitoring.** ComplianceLint scans source code and documentation. It does not monitor running AI systems. For ongoing compliance assurance, schedule periodic scans via CI/CD and ask your AI to sync results after each scan to maintain an auditable trail of compliance progress over time.
- **English legal citations.** Obligation definitions and source quotes are in English (from the official EUR-Lex publication). However, since ComplianceLint runs inside AI-powered IDEs, the AI will naturally converse, explain regulations, and generate reports in your preferred language.

---

## License

[Business Source License 1.1](LICENSE) — free to use for your own projects. Cannot be used to build a competing hosted compliance scanning service. Converts to Apache 2.0 on 2030-04-11.

---

## Contributing

Issues and PRs welcome. See the [GitHub Issues](https://github.com/ki-sum/compliancelint/issues) page to report bugs or request features.
