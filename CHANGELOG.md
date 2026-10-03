# Changelog

All notable changes to ComplianceLint will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/).

## [1.2.0] — unreleased

### Added — Regulation (EU) 2026/1744 (Digital Omnibus), Art. 5
- **ART05-PRO-1ba** (Art. 5(1)(ba), non-consensual intimate material) and **ART05-PRO-1bb**
  (Art. 5(1)(bb), child sexual abuse material). Both apply from **2026-12-02** (Art. 113, third
  paragraph, point (a), as amended); before that date their findings are informational
  `not_applicable` and do not change the Art. 5 result. Answers: `art5.has_ncii_generation`,
  `art5.has_csam_generation`.
- Obligations are now verified against the EUR-Lex consolidated text **02024R1689-20260727**.

### Added / changed — Regulation (EU) 2026/1744, Art. 11, 17, 50, 72, 111
- **ART111-OBL-4** (Art. 111(4)): providers of AI systems generating synthetic audio, image, video
  or text content placed on the market before 2 August 2026 must comply with Art. 50(2) by
  2 December 2026. Reported as an informational finding; Art. 50(2) itself is assessed under
  `ART50-OBL-2`.
- Art. 11(1) and 17(2): the SME provisions now also cover small mid-cap enterprises (SMCs).
- Art. 50(7): the Commission (formerly "the AI Office") encourages codes of practice and assesses
  whether adherence is adequate for Art. 50(2) and (4) (now an obligation, renamed `ART50-EMP-7a` → `ART50-OBL-7a`);
  such codes do not grant a presumption of conformity.
- Art. 72(3): the Commission adopts guidance including a template by 2 September 2027 (no
  implementing act).
- Art. 111(2): the cut-off for high-risk AI systems already on the market is the date Chapter III
  applies to them, no longer 2 August 2026.
- Superseded quotes and atom wording are kept internally (`_source_quote_history`, `_history`)
  and are not served.

### Added / changed — Regulation (EU) 2026/1744, Art. 4, 25, 27, 43
- Art. 4(1): providers and deployers must take measures to support the development of AI literacy;
  the obligation does not require them to guarantee any specific level of AI literacy of any
  individual (`ART04-OBL-1`).
- Art. 25(2): the initial provider's cooperation includes, where relevant, technical documentation
  sufficient to assess compliance with the requirements laid down in Art. 16, information on known
  limitations and failure modes, and targeted technical access, including for testing and
  validation. Fixed: an attested `ART25-EXC-2` (the initial provider's opt-out) now makes
  `ART25-OBL-2` not applicable; it wrongly derogated `ART25-OBL-4` before.
- Art. 25(4): third parties supplying an AI model are covered by the written-agreement duty.
- Art. 27(4): reusing a data protection impact assessment in the FRIA is a deployer permission;
  `ART27-OBL-4` is renamed `ART27-PERM-4` and no longer produces a finding.
- Art. 43(3): the conformity assessment of high-risk AI systems covered by Annex I Section A
  legislation also covers the Art. 17 quality management system, and points 3, 4.3, 4.4, 4.5, the
  fifth paragraph of point 4.6 and point 5 of Annex VII apply. A system covered by Annex I Section A
  legislation follows that legislation's procedure even if it also falls within Annex III, so
  `ART43-OBL-1` and `ART43-OBL-2` are not applicable when `is_annex_i_product` is true.

### Changed
- Application dates follow Art. 113 as amended (`scanner/data/application_dates.json`):
  `compliance_summary.applicable_from` (plus `applicable_from_annex_i` for Chapter III
  Sections 1-3 and `applicable_from_exceptions`), `cl_check_updates` (status computed against
  today) and `cl_explain` `enforcement_date`.
- `cl_version` reports the regulation text version(s) the obligations were verified against.
- EUR-Lex links point at the consolidated text.
- Obligation count in messages and docs is derived from the data: 247 unique obligations
  (three IDs are listed in two article files).

### Fixed
- Art. 5(1)(a)/(b)/(c)/(f)/(h) obligation atoms corrected after a two-model review
  against the primary text.
- `cl_action_guide` accepted only 163 of 246 obligation IDs (letter-suffixed IDs such as
  `ART05-PRO-1a` were rejected); it now also returns the ID in its shipped case and no longer
  serves superseded atom wording.
- The validation gate no longer renames fields modules read (Art. 5 `*_evidence` strings,
  Art. 9/10/12/15/19 legacy aliases) onto other answer fields.
- The paid strict gate no longer requires answers for obligations that do not apply yet.
- The wheel now ships `scanner/data/*.json` and `scanner/interpretive-materials/*.json`.
- Informational findings keep their `is_informational` flag and `human_gate_hint` when the
  obligation's source quote is added. As a result the Art. 25 classification findings
  (`ART25-CLS-1`, `ART25-CLS-3`) no longer change the Art. 25 overall level; the Art. 22/23/24
  "not in scope" findings still make those articles not applicable.

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

### Added — Bug reporting
- `cl_report_bug` MCP tool — generate a privacy-scrubbed bundle (recent scanner logs + environment info) for attaching to GitHub bug reports. Local-only, no auto-upload.

**v1.1.0 cumulative tool changes**: −1 `cl_report` (PDF-only via dashboard now), +1 `cl_action_guide` (Human Gates signpost), +1 `cl_report_bug` (this entry) ⇒ net **16 → 17 tools**.

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
