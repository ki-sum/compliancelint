# Changelog

All notable changes to ComplianceLint will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-04-11 (unreleased)

### Changed — Role coverage 4 → 5 (2026-04-26)
- **Authorised Representative** added as the 5th selectable role, completing
  the EU AI Act Art. 3 operator set (provider 3(3), deployer 3(4), authorised
  representative 3(5), importer 3(6), distributor 3(7)).
- **`isActionableForUser` is now role-aware** — accepts an optional `userRoles`
  argument so AR-addressed obligations are visible to AR users only and
  hidden from provider/deployer/importer/distributor users.
- **Art 54 OBL-3 + OBL-5 addressee fixed**: were previously misclassified as
  `provider`; corrected to `authorised_representative` to match the
  source-text "the authorised representative shall…".
- **Backward compatible**: existing users with `roles: ["provider"]` etc.
  see no change in behavior. AR-addressed oids were globally hidden before
  (because the addressee was excluded from `USER_ADDRESSEES`); they now
  surface only for users who explicitly select AR.
- **Note on README article table**: the per-article role mapping is paid
  content (Starter+ tier feature) and was removed from the public README.

### Changed — marketing copy + SEO metadata (2026-04-18)
- Primary tagline: **"Compliance in your IDE. Not in a meeting."** (was "From non-compliant to audit-ready. Automatically.")
- Landing page H1 now reads as two lines. Old tagline retained as sub-text in README.
- SEO `<title>` and OpenGraph / Twitter card metadata updated to match new tagline.
- **Fix**: `description` no longer claims "Open source" — corrected to "Source-available (BSL 1.1)" to match actual licensing.

### Changed — risk_classification schema aligned with EU AI Act canonical categories (2026-04-17)
- AI prompt now requests one of 4 canonical values: `prohibited` / `high-risk` / `limited-risk` / `minimal-risk` (or empty when undetermined). Previously the prompt accepted free-form values like `"likely high-risk"`, `"not high-risk"`, `"unclear"`, which mixed "the classification" with "uncertainty about it" in a single field.
- AI uncertainty now goes solely in the existing `risk_classification_confidence` field (`high` | `medium` | `low`).
- This eliminates a known false-positive in the SaaS dashboard's settings-mismatch banner: previously, an AI-emitted `"likely high-risk"` never matched the user-set `"high-risk"` despite semantic equivalence, triggering an amber warning. With canonical values both sides compare identically.
- **Backward compatibility**: legacy values (`"not high-risk"`, `"likely high-risk"`, `"limited risk"`, `"minimal risk"`, etc.) are still accepted by `_NOT_HIGH_RISK_VALUES` in `protocol.py` for the article-skip path. Existing `.compliancelintrc` files with `risk_classification_override` set to legacy strings continue to work.
- **Recommended action for users**: when next editing your `.compliancelintrc`, switch `risk_classification_override` to a canonical value (`minimal-risk` / `limited-risk` / `high-risk` / `prohibited`) to match the SaaS dashboard.

### Added — Human Gates
- **Human Gates system** — guided questionnaires for manual compliance obligations (DPIA, FRIA, human oversight, worker notification, log retention, and 66 more)
- **QuestionnaireRenderer** — schema-driven form component renders any questionnaire from JSON definition
- **Golden template script** — systematic generation of 71 questionnaire schemas from obligation JSONs
- **Human Gates hub page** — `/dashboard/human-gates` with progress bars, per-repo grouping, and inline questionnaire modal
- **`cl_action_guide` MCP tool** — signpost for Human Gate obligations, directs users to dashboard (tool count: 16)
- **`human_gate_hint`** field on manual obligation findings — scanner output includes dashboard link

### Added — Role Selection & Score Isolation
- **Role selection** in repo settings — Provider, Deployer, Importer, Distributor checkboxes
- **Score isolation** — compliance score calculated only for selected roles' obligations
- **Role filtering** applied consistently across: dashboard overview, repo dashboard, PDF reports, declaration PDF, badge, dashboard API, trend charts, article breakdown
- **`roles.ts`** — role-to-article mapping with `filterByRoles()`, `parseRoles()` utilities
- **`_saas_settings_active`** flag in validation gate — article filtering only when SaaS-confirmed settings exist
- **`scan-settings` API** — scanner fetches role/risk settings from SaaS at scan start
- **Post-scan hint** — prompts users to configure roles when no SaaS settings active

### Added — Compliance Infrastructure
- **Settings audit trail** — `settings_audit_log` table tracks who changed roles, risk classification, and export settings
- **Audit trail UI** — collapsible change history in repo settings page
- **`finding_responses.answers`** column — structured JSON storage for questionnaire responses

### Changed — License
- **BSL 1.1** replaces Apache 2.0 — free to use for your own projects, cannot build competing hosted scanning service. Auto-converts to Apache 2.0 on 2030-04-11.

### Changed — PDF
- **Human Gate CTA** in PDF — UNABLE_TO_DETERMINE findings show "Complete this Human Gate at compliancelint.dev" block
- **Role note** in PDF header — "This report covers Provider and Deployer obligations"
- **Role filtering** in PDF — only selected roles' findings appear in exported PDFs

### Changed — Navigation
- Sidebar: "Guidance" renamed to **"Human Gates"**
- Old `/dashboard/guidance` URL redirects to `/dashboard/human-gates`
- ProviderCheckWizard preserved inside Human Gates page as role determination tool

### Removed
- `cl_report` MCP tool — compliance reports are now exclusively generated as PDF from the dashboard. This prevents free-tier feature leakage. Tool count: 16 → 15.

### Changed — PDF Redesign
- **Declaration PDF**: redesigned System Identification as structured card; scope as color-coded grid; appendix now groups by article with per-obligation table; added Place field to signature; removed ambiguous percentage score
- **Scan Findings PDF** (renamed from "Compliance Report"): removed "How to Fix" remediation (belongs in Tasks PDF); removed overall status badge; added per-finding source quotes
- **Journey PDF**: resolved/regressed changes now in table format (Obligation | Before | After); added Not Applicable line to chart; removed status badge; added "Scanned by" user info; removed truncation limits
- **Tasks PDF**: all tasks shown in full detail (removed top-15 limit and "Remaining Tasks" appendix); article names are now clickable EUR-Lex links; added guidance text after each remediation
- **Technical Documentation PDF**: status badges unified to standard 4-status system (COMPLIANT / NON-COMPLIANT / NEEDS REVIEW / NOT APPLICABLE); removed "...and X more" truncation; placeholder text now actionable with yellow highlight
- **All PDFs**: removed all italic text; filenames now include seconds-precision timestamp; AI Provider shown in all 5 types; "Scanned by" shows who triggered scan; EUR-Lex links on article titles; all links point to compliancelint.dev; NotoSans font files corrected (was accidentally swapped with italic variant)

### Changed — Status Calculation
- Unified `computeOverallStatus()` as single source of truth (was duplicated in two routes)
- Status matrix: 7 test cases covering all state combinations

### Changed — UI
- Removed PDF variant picker (executive variant cancelled) — all PDFs now direct download
- Landing page: "Compliance Report" → "Scan Findings", Declaration naming updated

### Changed — Seed Data
- Demo scans now include NEEDS_REVIEW findings (~15% of non-compliant)
- `overallStatus` computed from actual counts (was hardcoded)
- `aiProvider` and `submittedBy` fields populated
- `createdAt` set to `scannedAt` for correct ordering
- Art. 5 obligations have per-prohibition evidence text

## [1.0.5] — 2026-04-07

### Added
- Validation gate: scope enforcement, template coercion, auto-fix for common scan issues
- `cl_update_finding_batch` — batch-update multiple findings at once
- Python CLI: `python -m scanner.cli init` as alternative to `npx`
- Regulation registry: dynamic article discovery from obligation JSONs
- Scanner logging module for structured debug output
- Device flow for `cl_connect` (replaces local HTTP callback — more reliable across OSes)

### Changed
- Error responses standardized to `{error, fix, details}` structure
- `cl_scan` result compression: smaller payloads, faster sync
- README simplified: removed manual `.mcp.json` option, added Python 3.10+ prerequisite

### Fixed
- Obligation ID zero-padding matching (ART9-OBL-1 now matches ART9-OBL-01)
- `ai_provider` field now correctly synced from metadata.json
- `cl_connect` no longer hangs on Windows (removed git subprocess calls)

## [1.0.1] — 2026-04-06

### Changed
- Version bump for PyPI/npm distribution sync

## [1.0.0] — 2026-03-29

### Added
- MCP Server with 16 tools for EU AI Act compliance scanning
- 44 EU AI Act articles covered (247 legal obligations)
- All obligations verified against EUR-Lex source text
- 2500+ unit tests with 12 archetype test fixtures
- Obligation Engine: maps AI-provided answers to legal findings (<100ms, deterministic)
- Per-obligation findings with exact EUR-Lex legal citations
- `cl_connect` — link to ComplianceLint dashboard
- `cl_sync` — upload scan results to dashboard
- `cl_update_finding` — submit evidence, rebuttals, acknowledgements
- `cl_action_plan` — prioritized remediation with effort estimates
- Dashboard at compliancelint.dev
- PDF exports: Scan Report, Compliance Journey, Tasks
- Zero-friction project identity (git fingerprint, no config needed)
- `pip install compliancelint` — PyPI distribution
- `npx compliancelint init` — one-line MCP setup via npm

### Security
- No source code leaves the user's machine — only findings JSON is synced

## [Unreleased]

### Planned
- Additional regulations (based on user demand)
- PR Comment Bot (Codecov-style)
- GitHub Marketplace App
