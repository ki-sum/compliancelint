# Contributing to ComplianceLint

Thanks for your interest in ComplianceLint. This document covers the most
common ways to contribute.

## Asking a question

- **Product / onboarding help** → email `support@compliancelint.dev`.
- **Bug reports** → open a [GitHub issue](https://github.com/ki-sum/compliancelint/issues/new/choose) using the **Bug Report** template.
- **Feature requests** → open a [GitHub issue](https://github.com/ki-sum/compliancelint/issues/new/choose) using the **Feature Request** template.
- **Security vulnerabilities** → see [SECURITY.md](SECURITY.md) (do **not** open a public issue).

## Reporting bugs effectively

A good bug report saves everyone time. The fastest path is:

1. Run `cl_report_bug` from your MCP client. This produces
   `~/compliancelint-bugreport-{timestamp}.md` containing your scanner logs
   and environment info, with no source code or sensitive data.
2. Open a [Bug Report](https://github.com/ki-sum/compliancelint/issues/new?template=bug_report.yml).
3. Paste the bundle contents (or attach the file) into the Bug report bundle
   field.
4. If the dashboard or MCP server displayed an **Error ID** (e.g.
   `err_abc123def456`), include it. We use this to look up the full
   server-side stack trace.

Bugs without reproduction steps or version info usually get bounced back
with a request for more info — please save us a round-trip.

## Submitting a pull request

ComplianceLint is **source-available** under the [Business Source License 1.1](LICENSE).
External contributions are welcome but please open an issue first to discuss
design / scope before opening a PR. This avoids wasted work on changes that
don't fit the roadmap.

Process:

1. Fork the repo and create a branch from `master`.
2. Make your change. Keep PRs focused — one logical change per PR.
3. Add or update tests. We do not merge code without tests.
4. Run the test suite locally and confirm 0 failures.
5. Open a PR. Fill in the description: what changed, why, and how to verify.

## Code style

- **Python**: follow PEP 8. We do not require black / ruff yet but pull
  requests with consistent style are appreciated.
- **TypeScript / React**: the dashboard SaaS lives outside this repo —
  external dashboard contributions go through GitHub issues; the
  conventions are documented in code review comments at PR time.
- **Tests**: prefer integration tests over heavily-mocked unit tests. Mocks
  hide real bugs.
- **Comments**: comment the *why*, not the *what*. Well-named identifiers
  document themselves.

## Scope limits

ComplianceLint is licensed under BSL 1.1 (production use is restricted —
see [LICENSE](LICENSE)). A few things to keep in mind for contributions:

- **Do not contribute work derived from regulatory text** without making sure
  the source is appropriate for redistribution. EUR-Lex content is acceptable
  under its terms; commercial regulatory databases are not.
- **Do not contribute code that bypasses the license** (e.g. helpers that
  enable competing SaaS deployments before the BSL change date).
- **Personal data** must not be committed. Test fixtures that look like real
  customer data must be clearly synthetic.

## Local development

The public repo contains the MCP server and scanner. Local setup:

```bash
git clone https://github.com/ki-sum/compliancelint.git
cd compliancelint
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
pytest
```

The dashboard SaaS lives in a separate (private) repository. External
contributions to dashboard features should go through GitHub issues — we
will land the changes on your behalf.

## Code of conduct

Be civil. Disagreements about technical decisions are fine; personal
attacks, harassment, or discriminatory language are not. Reports of
unacceptable behaviour to `support@compliancelint.dev` will be reviewed.

## License

By contributing, you agree that your contributions will be licensed under
the same [Business Source License 1.1](LICENSE) as the rest of the project.
