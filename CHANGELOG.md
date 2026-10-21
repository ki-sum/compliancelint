# Changelog

All notable changes to ComplianceLint will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- Connected projects were scanned without the detection metadata (detection method, what to scan, confidence,
  human judgment needed) that the dashboard serves: the scanner read the API key for it only from
  `~/.compliancelint/config.json`, which nothing writes — `cl_connect` stores the key in the project's
  `.compliancelintrc`. `cl_analyze_project` then said "No detection hints available … once this project is
  connected" for a connected project, findings showed an empty "Detection method", and the scanner printed the
  offline notice. The project's key is now used, and `cl_analyze_project` loads the project settings before it
  builds the scanning strategy.
- Right after `cl_connect`, `cl_analyze_project` reported the plan as "unconnected" and suggested connecting: the plan
  was learned only from the first scan. `cl_connect` now stores the plan the dashboard returns when it registers
  the project.
- After obligations were confirmed in Human Gates (dashboard: Compliant), a rescan still listed them under
  `pending_evidence` and gave no figure the dashboard shows. `cl_scan_all` now reads the dashboard's current statuses:
  pending items that are compliant there are dropped, and `totals.findings_on_dashboard_now` with `dashboard_overall`
  report what the dashboard shows as of the last sync.
- `cl_scan` for one article (`articles="50"`) asked for the answers of other articles too ("still need to check 4
  more": Art. 4, 5, 6, 111). It now needs the requested articles' answers only; `articles="all"` keeps the full check.
  The validation result also counts only the requested articles, so a single-article scan is no longer reported as
  blocked because of answers to articles it did not scan.
- Article 50: the scanner asked for one `disclosure_evidence` list and quoted it in the Article 50(1) finding, so
  evidence about the machine-readable marking (50(2)) or the public-interest text (50(4)) appeared under 50(1). The
  template now has one list per duty — `disclosure_evidence` (50(1)), `marking_evidence` (50(2)),
  `deep_fake_evidence` (50(4) first subparagraph), `public_interest_text_evidence` (50(4) second subparagraph) — each
  with its own description, and each finding quotes only its own list.

### Changed — harmonised standards and the instruments each article waits for (legal review)
- EN 18286:2026 (quality management system) is the first harmonised standard cited under the AI Act: Commission
  Implementing Decision (EU) 2026/2274 published its reference in the Official Journal of the European Union on
  14 October 2026. `cl_check_updates` reports it as cited, no longer as "prEN 18286 — Public Enquiry phase,
  expected Q4 2026". Article 17 (`cl_explain`, action plan, obligation file, `cl_interim_standard`) and Article 16
  name it; the European Commission states that providers implementing it benefit from a presumption of conformity
  with the Article 17 requirements covered by the standard, whose exact coverage is set out in its Annex ZA.
  `cl_interim_standard` has a new top-level `official_harmonised_standards` list (empty for articles without one).
- Every article's "waiting for" text, the interim checklists and the obligation files no longer promise a
  "CEN-CENELEC harmonized standard (expected Q4 2026)" or "(expected 2027)". They say whether a harmonised standard
  is being developed under the Commission's standardisation request C(2025) 3871 (Articles 9, 10, 12, 13, 14, 15
  and 43, no date announced), whether none is requested, and which instrument the Regulation provides instead
  (for example the Article 6(5) guidelines, the Article 50 guidelines and code of practice, the general-purpose AI
  code of practice under Article 56, the Article 72(3) guidance due by 2 September 2027).
- The action-plan disclaimer no longer says that standards "may modify these requirements": a ComplianceLint
  action plan gives no presumption of conformity, a cited harmonised standard gives it only for the requirements
  it covers, and harmonised standards do not amend the Regulation.
- Article 5: the Commission Guidelines on prohibited AI practices (C(2025) 884 final, 4 February 2025) are listed
  as published, no longer as expected.

## [1.3.2] — 2026-10-15

### Fixed
- The totals in the `cl_scan_all` response counted an obligation twice when two article modules report it (the
  Article 12 module also reports ART19-OBL-1b, ART19-OBL-2 and ART26-OBL-6). They now count one finding per
  obligation, the one of the obligation's own article, as the dashboard stores it: a scan that said 177 findings now
  says 175, the number the dashboard records. Article counts are unchanged.

## [1.3.1] — 2026-10-12

### Changed — texts follow the legal review and the role-first Profiling Wizard
- Article 48 (CE marking): finding sentences, notes, action-plan explanations and the article explanation in the
  wording of the legal review. Evidence found in a project is described as indicating that the CE marking may
  comply with the general principles of Article 30 of Regulation (EC) No 765/2008; the duties of Art. 48(4) keep
  their "where applicable" condition; the notes state what Article 16(h) and Article 48(4) each say.
- Scanner notice, rule 5: with dashboard settings, provider duties are reported as not applicable where the
  Profiling Wizard answers establish neither provider status under Article 3(3) nor deemed-provider status under
  Article 25(1) or (3); Article 25(2) is assessed separately.
- Setup and connection texts no longer describe the Profiling Wizard as a 30-second step of the free plan: it is
  part of the Starter plan and higher, it asks for your role(s), the scope and the use of the system, and the risk
  class is concluded from the answers.
- The AI client is told which label to show for each stored risk value: "Prohibited practice (Art. 5)",
  "High-risk", "Not high-risk — Article 50 transparency trigger identified", "Not high-risk — no Article 50
  transparency trigger identified". "Limited risk" and "minimal risk" are not classes of the Regulation.
- "Your code never leaves your machine" is replaced by what this project can state: ComplianceLint never receives
  your code. Source files are not uploaded; findings with their evidence notes are.
- The upgrade hint no longer quotes a review-time saving.

### Fixed
- `package.json` declared the licence as Apache-2.0. The project is under the Business Source License 1.1
  (SPDX `BUSL-1.1`), as `LICENSE` and `pyproject.toml` state.
- README: application dates follow Article 113 as amended by Regulation (EU) 2026/1744 (the block still described
  the amendment as a pending agreement); obligation counts for Article 5 (10) and Article 111 (4) in the table.

## [1.3.0] — 2026-10-12

### Added — Article 48 (CE marking)
- New scanned article, the 45th module: 7 obligation records (255 obligations in 46 articles, Art. 4a included).
  Art. 48(1) general principles of Article 30 of Regulation (EC) No 765/2008, 48(2) digital CE marking for systems
  provided digitally, 48(3) affixing, 48(4) the notified body's identification number in three records (after the
  CE marking, who affixes it, in promotional material), 48(5) other Union law that also provides for the CE
  marking. Source quotes are verbatim from the consolidated text of the Regulation.
- Eleven answer fields for `art48`: seven results and four conditions (`is_provided_digitally`,
  `has_notified_body_assessment`, `is_subject_to_other_ce_marking_law`, `has_ce_marking_promotional_material`).
  A condition answered false makes its record not applicable; an unanswered condition leaves it undetermined.
  Article 48 is assessed for providers of high-risk AI systems, like the other provider duties of Chapter III.
- The answer template asks the AI client for `art49.claims_art6_3_exception` and
  `art52.is_gpai_with_systemic_risk` as well; until now only dashboard settings could supply them.

### Changed
- Article 55 follows the systemic-risk answer in full: without systemic risk the paragraph 2 records
  (`ART55-PERM-2`, `ART55-OBL-2`) are not applicable, like the paragraph 1 records. The dashboard's systemic-risk
  answer is applied to `art55.has_systemic_risk` too.

### Fixed
- A condition field present with the value null — the shape of the answer template — was read as an answer and
  reported as "[APPLICABLE] … (field=None)". It is unanswered: the record stays undetermined.

## [1.2.3] — 2026-10-11

### Fixed
- The validation gate no longer reports an obligation's context field as an unknown field of its article. With
  dashboard settings applied, every scan told the AI client that its answers had format issues because of
  `art49.claims_art6_3_exception` — a field the scanner writes itself from the Profiling Wizard answer (the same
  applied to `art52.is_gpai_with_systemic_risk`). Scan results were not affected.
- The update notice (`cl_version`, `cl_check_updates`) appears only when PyPI has a newer version than the installed
  one; it used to appear whenever the two differed.

### Changed
- `COMPLIANCELINT_HOME` now moves the scanner's whole per-user directory (`~/.compliancelint`), the per-project
  log directories included; it already moved the telemetry config. The test suite sets it to a temporary directory,
  so running the tests no longer leaves a log directory per test project in the developer's home.

## [1.2.2] — 2026-10-11

### Changed — `cl_scan_all` and `cl_action_plan` responses: readable by the AI client in one piece
- `cl_scan_all` and `cl_action_plan` for all articles no longer carry the verbatim text of every related Recital
  (`related_recitals_by_article`). That text was about 254,000 characters — 78 % of a full scan response (325,000)
  and of a full action plan (329,000) — which is more than an AI client keeps in the conversation: Claude Code
  wrote the result to a file and handed the assistant the file path, so the assistant did not see the scan summary
  or the actions directly. Both now list the Recital numbers per article (`related_recital_numbers_by_article`).
  The text is returned, as before, by `cl_explain(article=N)`, by `cl_scan` for selected articles and by
  `cl_action_plan(article=N)`. A full scan response is now about 60,000 characters, a full action plan about 65,000.
- `cl_analyze_project`, `cl_scan_all` and `cl_action_plan` declare their result-size limit to Claude Code
  (`_meta["anthropic/maxResultSizeChars"]`, 200,000), so these responses stay in the conversation (the default
  threshold is 50,000 characters). With an mcp SDK too old to carry tool metadata the tools work as before.

### Added — `cl_scan_all` totals that say what they count
- New `totals` block: articles by the AI's assessment, findings (one per obligation) by the AI's assessment, and
  findings as `cl_sync` records them on the dashboard. A scan could be reported in the terminal as "15 articles
  non-compliant" and shown on the dashboard as "Non-Compliant 2 of 145 findings": the first counts articles, the
  second counts findings after the sync rule that holds the AI's verdict on a human-judgment obligation as "needs
  review" until a person confirms it in Human Gates. The block states the unit of each count and that rule.

## [1.2.1] — 2026-10-10

### Fixed — the first scan of a new project reads the dashboard settings
- `cl_connect` now stores the dashboard's repo id (`.compliancelint/local/metadata.json`) when it registers the
  project. Before, only `cl_sync` stored it, so a scan run before the first sync could not read the dashboard
  settings (Profiling Wizard answers, roles, applicable obligations) and reported `dashboard_settings:
  "unavailable"` with a warning to re-run the scan — although `cl_connect` invites the user to fill the wizard
  before the first scan.

## [1.2.0] — 2026-10-10

### Changed — Art. 111(1) and 111(4) records
- **ART111-OBL-1** (Art. 111(1), AI systems that are components of the Annex X large-scale IT
  systems): addressee `provider` → `provider_and_deployer`. The paragraph names no operator ("shall be
  brought into compliance"); compliance is role-specific (Art. 16 for providers, Art. 26 for deployers),
  so deployers now see the 31 December 2030 deadline too.
- **ART111-OBL-4** (Art. 111(4)): `context_skip_field` `is_generating_synthetic_content` (not
  applicable when false); automation level `full` — the record is reported as informational without a
  human attestation (Art. 50(2) itself is assessed under ART50-OBL-2).

### Fixed — compliance_answers template now covers every field the article modules read
- 51 answer fields that article modules read were missing from the template returned by
  `cl_analyze_project`, so the AI was never asked for them and the obligations they decide were
  always `unable_to_determine` — e.g. Art. 16(d)-(l) (documentation kept, log retention, conformity
  assessment, EU declaration, CE marking, registration, corrective actions, conformity on request,
  accessibility), Art. 53(1)(c)-(d) (copyright policy, training-content summary), Art. 55(1)(c)-(d),
  Art. 22(3), Art. 25(4), Art. 26(6) and (11), Art. 6(4). They are now in the template, each with a
  description in `compliance_answers_field_descriptions` (verified against the consolidated text).
- New number fields: `retention_days` (Art. 12 / 19 / 26) and `art51.training_compute_flops`. Numeric
  strings such as `"180"`, `"180 days"`, `"1e25"` or `"3.5 x 10^26"` are converted; other values are
  reported as format errors.
- **ART10-OBL-6** (Art. 10(6)) is `not_applicable` when the new field `art10.uses_model_training` is
  `true` (the paragraph covers systems developed without training techniques).
- Removed: the 15 legacy answer-field aliases (e.g. `art15.has_cybersecurity` was read as
  `has_fallback_behavior`, a different Art. 15 duty), and the validation gate's fuzzy renaming of
  unknown field names (it could turn a near-miss name into another obligation's answer). Unknown
  fields are now kept unread and listed as `unknown_field` in the coercion log.

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

### Added / changed — Regulation (EU) 2026/1744, Art. 4a, 6, 10, 60
- New Art. 4a: providers of high-risk AI systems may exceptionally process special categories of
  personal data to the extent strictly necessary to ensure bias detection and correction in
  accordance with Art. 10(2), points (f) and (g), subject to all the conditions in points (a)-(f)
  (`ART04a-PERM-1`; formerly Art. 10(5), `ART10-PERM-5` is removed). Providers and deployers of other
  AI systems and models and deployers of high-risk AI systems may do so on the conditions of
  Art. 4a(2), which does not create any obligation to conduct bias detection and correction
  (`ART04a-PERM-2`). Art. 4a contains permissions only and has no scanning module; it applies from
  2 August 2026.
- Art. 10(1) and (6) refer to Art. 10(2), (3) and (4) and Art. 4a(1).
- Art. 6(1a)-(1c): AI systems solely used for non-safety related aspects of user assistance,
  performance optimisation, service efficiency, automation or convenience or quality control are
  not safety components unless their failure or malfunctioning would endanger health and safety;
  a third-party conformity assessment required solely because of risks other than risks to health
  and safety does not meet Art. 6(1), point (b). `ART06-CLS-1` covers points (a) and (b) and
  paragraphs 1a-1c and requires both conditions.
- Art. 60(1) and (2): testing in real world conditions outside AI regulatory sandboxes also covers
  high-risk AI systems covered by Union harmonisation legislation listed in Section A of Annex I.
- `scanner/data/application_dates.json` also lists the articles inserted by Regulation (EU)
  2026/1744 (4a, 60a, 75a-75d).

### Changed — Regulation (EU) 2026/1744, Annex I and Art. 63
- Art. 6 interim standard: the Annex I product list now states the section of each act — Section A
  (toys, lifts, medical devices, …) or Section B (civil aviation security, vehicles, marine
  equipment, rail, specified unmanned aircraft, and machinery, Regulation (EU) 2023/1230, moved to
  Section B). Fixed: the decision tree named Art. 52 for transparency obligations; it is Art. 50.
- Art. 17 action plan: the Art. 17(2) proportionality item also mentions the Art. 63(1) option for
  SMEs, including start-ups, without partner or linked enterprises.

### Changed
- Application dates follow Art. 113 as amended (`scanner/data/application_dates.json`):
  `compliance_summary.applicable_from` (plus `applicable_from_annex_i` for Chapter III
  Sections 1-3 and `applicable_from_exceptions`), `cl_check_updates` (status computed against
  today) and `cl_explain` `enforcement_date`.
- `cl_version` reports the regulation text version(s) the obligations were verified against.
- EUR-Lex links point at the consolidated text.
- Obligation count in messages and docs is derived from the data: 248 unique obligations
  (three IDs are listed in two article files) across 45 articles (44 with a scanning module).

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
