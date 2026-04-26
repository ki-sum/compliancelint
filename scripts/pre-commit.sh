#!/bin/bash
# ComplianceLint pre-commit hook (canonical, tracked).
#
# Guards the public repo against:
#   1. Files in known-private paths being committed
#   2. Chinese characters in public source/docs (warn only)
#   3. Real API tokens / secrets
#   4. References to `private/` in any staged file content
#
# Install (run once per fresh clone):
#   ln -sf ../../scripts/pre-commit.sh .git/hooks/pre-commit
#   chmod +x scripts/pre-commit.sh
#
# Or on systems where symlinks don't work (some Windows setups):
#   the local .git/hooks/pre-commit can be a thin wrapper:
#     #!/bin/bash
#     exec bash "$(git rev-parse --show-toplevel)/scripts/pre-commit.sh"

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

# --- Check 1: Block private files from being committed ---

PRIVATE_PATTERNS=(
    "backup/"
    "scanner/tools/"
    "docs/research/"
    "docs/blog/"
    "docs/prompts/"
    "docs/PLAN.md"
    "docs/solo-founder-strategy.md"
    "docs/global-regulation-strategy.md"
    "docs/current-state.md"
    "docs/feature-boundary.md"
    "docs/legal-verification-template.md"
    "docs/obligation-verification-plan.md"
    "docs/audit-"
    "docs/art09-reference-model.md"
    "docs/art10-reference-model.md"
    "docs/art11-reference-model.md"
    "docs/art12-reference-model.md"
    "docs/art13-reference-model.md"
    "docs/art14-reference-model.md"
    "docs/art15-reference-model.md"
    "docs/art50-reference-model.md"
    "docs/art05-reference-model.md"
    "docs/art06-reference-model.md"
    "docs/architecture.md"
    "docs/ai-first-architecture.md"
    "docs/pre-commit-checklist.md"
    "docs/quality-audit-results.md"
    "docs/regulation-sources.md"
    "docs/concept-en.md"
    "docs/concept-zh.md"
    "docs/testing-plan.md"
    "docs/consensus-lock/"
    "scanner/regulations/"
    ".compliancelint/"
)

for file in $STAGED_FILES; do
    for pattern in "${PRIVATE_PATTERNS[@]}"; do
        if [[ "$file" == *"$pattern"* ]]; then
            echo -e "${RED}BLOCKED: $file is a private file and must not be committed to the public repo.${NC}"
            ERRORS=$((ERRORS + 1))
        fi
    done
done

# --- Check 2: Warn about Chinese characters in public files ---

for file in $STAGED_FILES; do
    if [[ "$file" == *.png || "$file" == *.jpg || "$file" == *.pdf || "$file" == *.svg ]]; then
        continue
    fi

    if git diff --cached -- "$file" | grep '^+' | grep -P '[\x{4e00}-\x{9fff}]' > /dev/null 2>&1; then
        echo -e "${YELLOW}WARNING: $file contains Chinese characters. Public files should be in English.${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
done

# --- Check 3: Block secrets ---

for file in $STAGED_FILES; do
    if [[ "$file" == "scripts/pre-commit.sh" ]]; then
        continue
    fi

    if git diff --cached -- "$file" | grep '^+' | grep -E '(ghp_[a-zA-Z0-9]{36}|sk-ant-[a-zA-Z0-9]{40,})' > /dev/null 2>&1; then
        echo -e "${RED}BLOCKED: $file appears to contain a secret/API key.${NC}"
        ERRORS=$((ERRORS + 1))
    fi
done

# --- Check 4: Block references to `private/` directory ---
#
# The private/ directory is gitignored, so anything referring to a path
# under it is (a) a broken link from the public repo's perspective and
# (b) leaks the existence + naming convention of internal docs/code.
# Allow-list:
#   - .gitignore   (the rule itself: `private/`)
#   - scripts/pre-commit.sh (this guard contains the literal as a check)

for file in $STAGED_FILES; do
    if [[ "$file" == ".gitignore" || "$file" == "scripts/pre-commit.sh" ]]; then
        continue
    fi
    if [[ "$file" == *.png || "$file" == *.jpg || "$file" == *.pdf || "$file" == *.svg || "$file" == *.ico || "$file" == *.zip || "$file" == *.gz ]]; then
        continue
    fi
    if git diff --cached -- "$file" | grep '^+' | grep -E '(^|[^a-zA-Z0-9_-])private/' > /dev/null 2>&1; then
        echo -e "${RED}BLOCKED: $file references 'private/' — leaks the existence of internal directory layout.${NC}"
        echo -e "${RED}         Either remove the reference, or commit the file to the private repo instead.${NC}"
        ERRORS=$((ERRORS + 1))
    fi
done

# --- Summary ---

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo -e "${RED}Commit blocked: $ERRORS issue(s) detected.${NC}"
    echo "Remove offending files from staging with: git reset HEAD <file>"
    exit 1
fi

if [ $WARNINGS -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}$WARNINGS file(s) contain Chinese characters. Consider translating to English.${NC}"
    echo "Proceeding with commit anyway."
fi

exit 0
