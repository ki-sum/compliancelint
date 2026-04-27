# Security Policy

ComplianceLint is a compliance tooling product. Our security programme
focuses on protecting customer workspaces, authentication flows, tenant
isolation, diagnostic logs, generated reports, and the integrity of the
obligation engine.

## Reporting a vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Email **security@compliancelint.dev** with:

1. A description of the vulnerability and its impact.
2. Steps to reproduce (proof of concept code if applicable).
3. The version / commit you tested against.
4. Optional: your name and a link for credit (see [Acknowledgements](#acknowledgements)).

Please do not include secrets, personal data, customer data, exploit
payloads that expose third-party data, or sensitive operational details
in an initial email. Send a concise description, affected component,
reproduction outline, and contact details. If additional sensitive
material is required, we will provide a secure transfer channel. We
plan to publish a PGP key or secure vulnerability intake form as part
of our launch security checklist.

You will receive an acknowledgement within **3 business days** (Monday
–Friday, excluding public holidays in Bavaria, Germany). If you do not,
please retry — the message may have been filtered.

## Coordinated disclosure target timeline

The following is our **target** timeline for good-faith vulnerability
reports. Actual timing may vary depending on severity, exploitability,
affected components, customer impact, third-party dependencies, and
legal or regulatory obligations.

- **Day 0**: report received; acknowledgement sent within 3 business days.
- **Day 0–14**: triage, severity assessment, and reproduction.
- **Day 14–60**: we **aim to** develop, test, and release a fix.
  Critical vulnerabilities may be remediated faster; complex issues
  (architectural changes, upstream dependency patches, coordinated
  multi-vendor disclosure, schema migrations) may take longer. We will
  keep the reporter informed of progress and revised timelines.
- **Day 60–90**: we **aim** to coordinate public disclosure, unless an
  earlier disclosure is appropriate (e.g. a fix is already shipped and
  affected customers have been notified) or a later disclosure is
  necessary (e.g. complex remediation in progress, legal obligations,
  protection of customers). The final disclosure date is set in
  coordination with the reporter where reasonably possible.

If you believe the vulnerability is being actively exploited, say so in
the report and we will compress the timeline.

## Personal-data breach notification

Customer notification and legal breach notification are handled
**separately from coordinated public disclosure of vulnerabilities**.

Where a security incident results in a personal-data breach as defined
in Art. 4(12) GDPR:

- We will notify the competent supervisory authority — the
  *Bayerisches Landesamt für Datenschutzaufsicht* (BayLDA) — within
  **72 hours** of becoming aware of the breach, in accordance with
  **Art. 33 GDPR**.
- We will notify affected customers acting as joint controller or data
  controller **without undue delay**, and in any event before public
  disclosure, in accordance with **Art. 34 GDPR** and our Data
  Processing Agreement.
- For customers on a signed Data Processing Agreement (DPA),
  notification follows the timelines in the DPA, which take precedence
  over this policy.

These obligations are independent of the coordinated vulnerability-
disclosure timeline above.

## Scope

In scope:
- The MCP server source (this repository).
- The scanner / obligation engine.
- The dashboard SaaS at `https://compliancelint.dev`.
- The PDF report generation pipeline.
- Authentication, authorization, and tenant isolation between accounts.
- Third-party dependency vulnerabilities that can be exploited through
  ComplianceLint or materially affect the confidentiality, integrity,
  availability, authentication, authorization, tenant isolation, or
  data protection of the service.

Out of scope:
- Vulnerabilities that exist solely in a third-party dependency and do
  not create an exploitable impact in ComplianceLint (please report
  upstream).
- Physical or social-engineering attacks against ComplianceLint staff.
- Denial-of-service attacks against the SaaS that require sustained
  traffic beyond a normal customer's quota (rate-limiting and abuse
  handling are separate; reports of weak rate limits are welcome and
  in scope).
- Findings that require a compromised user device (malware, browser
  extensions, etc.).

## Coordinated disclosure

We support coordinated disclosure. We will:

- Credit you in the release notes (or anonymously, if you prefer).
- Notify affected customers as required (see "Personal-data breach
  notification" above).
- Apply the safe-harbor commitment below.

## Safe harbor

We will not initiate civil action and will not file criminal
complaints (*Strafanzeige*) under §§ 202a, 202b, or 202c StGB
against security research conducted in good faith and in compliance
with this policy, **provided that the researcher**:

- avoids privacy violations, data exfiltration, service disruption,
  persistence, lateral movement, extortion, social engineering, and
  access to data that is not their own;
- stops testing immediately, does not copy or disclose the data, and
  reports the issue to us promptly if customer data, personal data,
  secrets, or non-public information are encountered.

We cannot bind public prosecutors, but in practice German prosecutors
require a complaint (*Strafantrag*) for these offences in most cases.

## Acknowledgements

Researchers who have helped improve ComplianceLint security will be
listed here once the project moves out of pre-launch. If you would
like your name included (or excluded), say so in your initial report.

## PGP

A PGP key for `security@compliancelint.dev` will be published here
once we finish the launch checklist. Until then, please follow the
guidance under "Reporting a vulnerability" above and avoid placing
sensitive content in plain-text email; we will provide a secure
channel on request.

---

For non-security questions, open an issue at
[github.com/ki-sum/compliancelint/issues](https://github.com/ki-sum/compliancelint/issues)
or email `support@compliancelint.dev`.
