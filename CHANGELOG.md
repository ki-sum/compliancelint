# Changelog

All notable changes to ComplianceLint will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-03-29

### Added
- MCP Server with 25 tools for EU AI Act compliance scanning
- 10 EU AI Act articles covered (Art. 5, 6, 9–15, 50)
- 94 legal obligations with exact EUR-Lex citations
- 674+ unit tests with 12 archetype test fixtures
- Obligation Engine: maps AI-provided answers to legal findings (<100ms, deterministic)
- Smart Scan: AI searches all files via Grep, reads only matches (typically 20–50 files)
- Per-obligation findings with exact EUR-Lex legal citations
- `cl_connect` — link to ComplianceLint dashboard
- `cl_sync` — upload scan results to dashboard
- `cl_update_finding` — submit evidence, rebuttals, acknowledgements
- `cl_export_report` — Markdown or JSON compliance report
- `cl_action_plan` — prioritized remediation with effort estimates
- Dashboard at compliancelint.dev
- PDF exports: Scan Report, Compliance Journey, Tasks
- Compliance Badge SVG for README embedding
- Zero-friction project identity (git fingerprint, no config needed)
- `pip install compliancelint` — PyPI distribution
- `npx compliancelint init` — one-line MCP setup via npm

### Security
- No source code leaves the user's machine — only findings JSON is synced

## [Unreleased]

### Planned
- Art. 4 AI Literacy (in force since Feb 2025)
- Art. 51-56 GPAI model obligations (in force since Aug 2025)
- Additional regulations (based on user demand)
- PR Comment Bot (Codecov-style)
- GitHub Marketplace App
