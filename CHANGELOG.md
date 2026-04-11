# Changelog

All notable changes to ComplianceLint will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-04-10

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
