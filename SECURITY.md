# Security Policy

ComplianceLint is a compliance tooling product. We take the security of the
project — and of the customer data flowing through it — seriously.

## Reporting a vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Instead, email **security@compliancelint.dev** with:

1. A description of the vulnerability and its impact.
2. Steps to reproduce (proof of concept code if applicable).
3. The version / commit you tested against.
4. Optional: your name and a link for credit (see [Acknowledgements](#acknowledgements)).

You will receive an acknowledgement within **3 business days**. If you do not,
please retry — the message may have been filtered. We will keep you informed
of progress toward a fix.

## Disclosure timeline

- **Day 0**: report received, acknowledgement sent within 3 business days.
- **Day 0–14**: triage, severity assessment, reproduction.
- **Day 14–60**: fix developed, tested, and released.
- **Day 60–90**: coordinated public disclosure (or earlier if a fix is shipped
  and customers have been notified).

If you believe the vulnerability is being actively exploited, say so in the
report and we will compress the timeline.

## Scope

In scope:
- The MCP server source (this repository).
- The scanner / obligation engine.
- The dashboard SaaS at `https://compliancelint.dev`.
- The PDF report generation pipeline.
- Authentication, authorization, and data isolation between accounts.

Out of scope:
- Issues in third-party dependencies (please report to the dependency upstream).
- Physical or social-engineering attacks against ComplianceLint staff.
- Denial-of-service attacks against the SaaS that require sustained traffic
  beyond a normal customer's quota (rate-limiting and abuse handling are
  separate; reports of weak rate limits are welcome and in scope).
- Findings that require a compromised user device (malware, browser
  extensions, etc.).

## Coordinated disclosure

We support coordinated disclosure. We will:

- Credit you in the release notes (or anonymously, if you prefer).
- Not pursue legal action against good-faith research that follows this
  policy.
- Notify affected customers before public disclosure.

## Acknowledgements

Researchers who have helped improve ComplianceLint security will be listed
here once the project moves out of pre-launch. If you would like your name
included (or excluded), say so in your initial report.

## PGP

A PGP key for `security@compliancelint.dev` will be published here once we
finish the launch checklist. Until then, please send vulnerability reports
in plain text — sensitive operational details (e.g. customer-identifying
data) can be redacted, and we will request more detail on a secure channel
once contact is established.

---

For non-security questions, see [SUPPORT](https://github.com/ki-sum/compliancelint/issues)
or email `support@compliancelint.dev`.
