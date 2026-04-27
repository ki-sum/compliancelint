# Contributing to ComplianceLint

Thanks for your interest in ComplianceLint. This document covers the most
common ways to contribute.

## Asking a question

- **Product / onboarding help** → email `support@compliancelint.dev`.
- **Bug reports** → open a [GitHub issue](https://github.com/ki-sum/compliancelint/issues/new/choose) using the **Bug Report** template.
- **Feature requests** → open a [GitHub issue](https://github.com/ki-sum/compliancelint/issues/new/choose) using the **Feature Request** template.
- **Security vulnerabilities** → see [SECURITY.md](SECURITY.md) (do **not** open a public issue).

Bug reports submitted via GitHub or email are processed by Kisum GmbH
and (for GitHub-hosted reports) GitHub, Inc. as a sub-processor. See
our [Privacy Policy](https://compliancelint.dev/legal/privacy) for
details on legal basis, retention, and your rights.

## Reporting bugs effectively

Bug reports that include reproduction steps, version information, and
relevant diagnostics are easier for us to triage. If key information is
missing, we may ask for additional details before investigation can
proceed.

The fastest path:

1. Run `cl_report_bug` from your MCP client. This creates a local
   bug-report file (`~/compliancelint-bugreport-{timestamp}.md`)
   containing diagnostic metadata, scanner logs, version information,
   and environment details. The tool is **designed to exclude** project
   source code, secrets, request bodies, and customer datasets, but
   you must **review and redact the file** before submitting it.

2. Do not include personal data, secrets, credentials, customer
   identifiers, proprietary source code, security vulnerabilities, or
   non-public operational details in a public GitHub issue.

3. If the bug report contains confidential, personal, security-
   sensitive, or customer-specific information, **do not open a public
   GitHub issue**. Email `support@compliancelint.dev` or, for security
   issues, `security@compliancelint.dev`.

4. If the dashboard or MCP server displayed an **Error ID** (e.g.
   `err_abc123def456`), you may include only the Error ID. We use it
   internally to locate the relevant server-side diagnostic record
   under access controls.

## Submitting a pull request

ComplianceLint is **source-available** under the [Business Source License 1.1](LICENSE).
External contributions are welcome but please open an issue first to
discuss design / scope before opening a PR. This avoids wasted work on
changes that don't fit the roadmap.

Process:

1. Fork the repo and create a branch from `master`.
2. Make your change. Keep PRs focused — one logical change per PR.
3. Add or update tests. We do not merge code without tests.
4. Run the test suite locally and confirm 0 failures.
5. Open a PR. Fill in the description: what changed, why, and how to verify.

## Code style

- **Python**: follow PEP 8. We do not require black / ruff yet but pull
  requests with consistent style are appreciated.
- **TypeScript / React**: this repository covers the MCP server and
  scanner components. The hosted dashboard is maintained in a separate
  private repository. Dashboard-related proposals should be submitted
  as feature requests; if accepted, implementation will be handled
  through our internal development process.
- **Tests**: prefer integration tests over heavily-mocked unit tests.
  Mocks hide real bugs.
- **Comments**: comment the *why*, not the *what*. Well-named
  identifiers document themselves.

## Scope limits

ComplianceLint is licensed under BSL 1.1 (production use is restricted
— see [LICENSE](LICENSE)).

- **Do not contribute code that bypasses the licence** (e.g. helpers
  that enable competing SaaS deployments before the BSL change date).
- **Personal data must not be committed.** Test fixtures that look like
  real customer data must be clearly synthetic.

### Regulatory-content contributions

Regulatory-content contributions must include source provenance. If
you contribute obligation mappings, translations, summaries, citations,
or derived regulatory content, identify the **source**, **version /
date accessed**, **jurisdiction**, and **licence or reuse basis**. Do
not contribute content copied or derived from commercial regulatory
databases, paywalled legal research tools, proprietary annotations, or
third-party translations unless redistribution is expressly permitted.
EUR-Lex content is acceptable under its terms.

## Contributor licensing

By submitting a pull request, you certify that:

1. You have the right to submit the contribution under the licence
   set out below (Developer Certificate of Origin v1.1 — see
   [developercertificate.org](https://developercertificate.org/)).
2. The contribution is your original work or you have sufficient
   rights to license it to us, and it does not contain third-party
   proprietary code, trade secrets, personal data, credentials, or
   confidential customer information.
3. If you are contributing on behalf of an employer or client, you
   are responsible for ensuring you have authority to do so. We may
   require a signed Contributor License Agreement (CLA) for certain
   contributions.
4. You grant Kisum GmbH a perpetual, worldwide, non-exclusive,
   royalty-free, irrevocable licence to use, reproduce, modify,
   distribute, and sublicense your contribution under (a) the
   Business Source License 1.1 currently applied to the project, and
   (b) any successor licence applied at or after the Change Date
   (currently Apache License 2.0).
5. You grant Kisum GmbH and downstream recipients a perpetual,
   worldwide, non-exclusive, royalty-free patent licence covering
   claims you can license that read on your contribution.

The explicit grant in points 4 and 5 is necessary because German
copyright law (§ 31 Abs. 5 UrhG, *Zweckübertragungslehre*) construes
ambiguous licence grants narrowly in favour of the author.

## Local development

The public repo contains the MCP server and scanner. Local setup:

```bash
git clone https://github.com/ki-sum/compliancelint.git
cd compliancelint
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
pytest
```

## Code of conduct

We expect respectful, professional communication in all project venues
(issues, pull requests, email, and any future community channels).
Disagreement on technical or design decisions is welcome and expected;
personal attacks, harassment, and discriminatory language are not.

Reports of conduct violations may be sent to
`support@compliancelint.dev` and will be reviewed and acted upon at
our discretion, up to and including blocking accounts from the
project.

## License

By contributing, you agree that your contributions will be licensed
under the same [Business Source License 1.1](LICENSE) as the rest of
the project, subject to the explicit grant in the *Contributor
licensing* section above.
