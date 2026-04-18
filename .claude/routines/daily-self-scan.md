---
repo: ki-sum/compliancelint
schedule: "30 5 * * *"
environment: compliancelint-scan
model: opus-4.7
description: Dog-food — scan ComplianceLint's own source against EU AI Act + sync to dashboard
---

# Daily Self-Scan + Sync

You are running the ComplianceLint scanner against its own source code every day.
Even though a compliance tool is not itself an AI system (most obligations will
return `Not Applicable`), this serves as:

1. **Dog-fooding evidence** — dashboard shows "scanner scanned itself today"
2. **Continuous validation** — catches regressions in the scanner's own behaviour
3. **Live demo record** — visible at compliancelint.dev for visitors

## Sequence

### 1. Verify infrastructure

```bash
cat /tmp/setup-complete.marker 2>/dev/null || {
  echo "Hook did not run — scanner may not be installed";
  pip install -e . 2>&1 | tail -5
}

python -m scanner.server --version 2>&1 | head -3 || echo "scanner CLI not found"
test -n "$COMPLIANCELINT_API_KEY" && echo "API key OK" || { echo "MISSING api key"; exit 1; }
```

### 2. Write .compliancelintrc with account credentials

Do NOT commit this file (it's already in .gitignore). It's needed for `cl_sync`
to authenticate as the kisum.gmbh.jw@gmail.com account.

```bash
cat > .compliancelintrc <<EOF
{
  "saas_url": "https://compliancelint.dev",
  "saas_api_key": "$COMPLIANCELINT_API_KEY",
  "repo_name": "ki-sum/compliancelint",
  "project_id": "git-e6342302051c45f3",
  "regulation": "eu-ai-act",
  "attester": {
    "name": "Daily Self-Scan (automated)",
    "email": "info@ki-sum.ai",
    "role": "ci-bot"
  }
}
EOF
```

### 3. Run analysis + scan via MCP tools

Use the MCP tools exposed by the scanner (declared in `.mcp.json` at repo root):

1. **`cl_analyze_project`** — understand project structure + scanning strategy
2. **`cl_scan_all`** — scan all 44 articles covered. This is the main work —
   it uses the AI to cross-reference repo contents against EU AI Act obligations.
3. **`cl_sync`** — upload findings to compliancelint.dev/dashboard

If `cl_scan_all` takes more than ~15 minutes, that's unusual — ComplianceLint
itself is small (~5k LOC). Expected scope: most obligations marked
`Not Applicable`; a few `Compliant` around transparency (README, LICENSE,
privacy notes).

### 4. Verify sync succeeded

After `cl_sync`, the response should include a dashboard URL. Confirm:

```bash
curl -sf -H "Authorization: Bearer $COMPLIANCELINT_API_KEY" \
  "https://compliancelint.dev/api/v1/repos?q=compliancelint" | \
  python -c "import json,sys; d=json.load(sys.stdin); print(f'last_scan_at: {d[0].get(\"lastScanAt\")}') if d else print('repo not found')"
```

The `lastScanAt` should be within the last few minutes.

### 5. Generate markdown summary

Path: `test-reports/self-scan-$(date -u +%Y-%m-%d).md`

```markdown
# Self-Scan Report — YYYY-MM-DD

**Target:** ki-sum/compliancelint (scanner source)
**Dashboard:** https://compliancelint.dev/dashboard
**Session:** https://claude.ai/code/{CLAUDE_CODE_REMOTE_SESSION_ID}

## Coverage

- **Articles scanned:** N of 44
- **Obligations evaluated:** M of 247

## Verdicts

- ✅ Compliant: X
- ❌ Non-Compliant: Y
- 🟡 Needs Review: Z
- ⚪ Not Applicable: W

## Delta from yesterday

{Read test-reports/self-scan-(DD-1).md if exists}
- New NC findings: {list}
- Newly resolved: {list}

## Dashboard link

View full findings at compliancelint.dev/dashboard (requires login as
kisum.gmbh.jw@gmail.com).
```

### 6. Commit to `test-reports` branch

```bash
git checkout test-reports 2>/dev/null || git checkout --orphan test-reports
mkdir -p test-reports
# ... write markdown ...
git add test-reports/self-scan-$(date -u +%Y-%m-%d).md
git commit -m "self-scan daily: $(date -u +%Y-%m-%d)"
git push origin test-reports
git checkout master
```

**Do NOT commit `.compliancelintrc`** — it contains the API key. It's
gitignored but double-check before commit.

### 7. One-liner status

- `✅ Self-scan: 247/247 obligations evaluated. 0 new NC findings. Synced.`
- `⚠️ Self-scan: 3 new NC findings — see dashboard`
- `❌ Self-scan failed at step {N}: {reason}`
