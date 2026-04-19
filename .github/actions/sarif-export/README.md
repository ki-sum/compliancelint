# ComplianceLint SARIF Export — GitHub Action

Download a ComplianceLint compliance scan as **SARIF 2.1.0** so it can be
uploaded to **GitHub Code Scanning** (the Security tab + inline PR comments).

This means: **PR reviewers see EU AI Act findings without leaving GitHub.** No
extra ComplianceLint dashboard login needed for read-only review.

## Quick start (recommended workflow)

```yaml
# .github/workflows/compliance.yml
name: EU AI Act Compliance

on:
  pull_request:
  push:
    branches: [main]

jobs:
  compliance:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write   # required for upload-sarif step
    steps:
      - uses: actions/checkout@v4

      # 1. Run ComplianceLint scan and sync to dashboard
      - uses: ki-sum/compliancelint-action@v1
        with:
          api-key: ${{ secrets.COMPLIANCELINT_API_KEY }}

      # 2. Export the latest scan as SARIF
      - id: sarif
        uses: ki-sum/compliancelint-sarif-export-action@v1
        with:
          api-key: ${{ secrets.COMPLIANCELINT_API_KEY }}
          level: scan          # one row per article (~30)

      # 3. Upload to GitHub Code Scanning (Security tab + PR alerts)
      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: ${{ steps.sarif.outputs.sarif-file }}
          category: compliancelint
```

After a few PRs you will see, in the GitHub UI:

- **Security tab → Code scanning → Tool: ComplianceLint** — full alert list
- **PR conversation tab** — inline annotations for any new violations introduced
- **Files changed tab** — red squiggle on the offending lines

## Inputs

| Name | Required | Default | Description |
|------|----------|---------|-------------|
| `api-key` | yes | — | ComplianceLint API key (starts with `cl_`). Store as a GitHub secret. |
| `scan-id` | no | latest scan for `repo-name` | Specific scan UUID to export. |
| `repo-name` | no | `${{ github.repository }}` | When `scan-id` is omitted, look up latest scan for this repo. |
| `level` | no | `scan` | `status-summary` (1 row per scan) \| `scan` (1 row per article) \| `full` (1 row per obligation, ~247) |
| `output-file` | no | `compliancelint.sarif` | Where to write the SARIF JSON. |
| `dashboard-url` | no | `https://compliancelint.dev` | Override for self-hosted / staging. |

## Outputs

| Name | Description |
|------|-------------|
| `sarif-file` | Absolute path to the downloaded SARIF file. Pass directly to `upload-sarif`. |
| `result-count` | Number of results in the SARIF doc (use in conditionals to skip empty uploads). |

## Picking the right `level`

- **`status-summary`** — Use when you want a single PR check ("is this branch
  compliant: yes/no"). One Code Scanning alert per scan.
- **`scan`** *(default)* — Use for normal team review. ~30 alerts (one per
  article). Each alert links to the article and shows obligation totals.
- **`full`** — Use when audit teams need every individual obligation finding
  surfaced as its own alert. ~247 results per scan; can be noisy.

## Tier requirement

The underlying `GET /api/v1/sarif/{scanId}` endpoint requires the **Pro** plan
or higher. Free / Starter API keys will get an HTTP 403 from this action.

## See also

- [`compliancelint-action`](../compliancelint-action) — the upstream action
  that runs the scan and syncs results. Use it before this action.
- [SARIF 2.1.0 spec](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html)
- [GitHub Code Scanning docs](https://docs.github.com/en/code-security/code-scanning)
