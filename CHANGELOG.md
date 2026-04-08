# Changelog

All notable changes to ComplianceLint will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/).

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
- `cl_report` — Markdown or JSON compliance report
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
