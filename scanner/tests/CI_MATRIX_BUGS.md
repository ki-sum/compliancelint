# CI Matrix Expansion Findings

First CI run after expanding `.github/workflows/ci.yml` from
`ubuntu-latest × 4 Python` to `(ubuntu|windows|macos)-latest × 4 Python`
(commit `ad4c01e`, run `24897042523`).

Per `private/docs/handoff/2026-04-24-CI-matrix-expansion-handoff.md` §4
Phase 4, issues are documented here and **not fixed in this task** — each
gets its own follow-up task.

---

## BUG-CI-1 — pytest collection breaks on ALL OSes due to conftest.py shadowing

**Status**: FIXED 2026-04-24 via Option 1 (add `--ignore=tests/e2e` to both
ci.yml and test.yml). e2e tests are cross-system flows requiring a deployed
dashboard + MCP server, which CI runners don't have — `--ignore` is the
semantically correct choice for CI scope, not a workaround.


**Failing OS × Python**: ALL 12 combinations
(ubuntu/windows/macos-latest × Python 3.10/3.11/3.12/3.13)

**Failing step**: `Run tests` — `python -m pytest tests/ -v --tb=short` in
`scanner/` working dir.

**Error (verbatim fragment)**:
```
ERROR collecting scanner/tests/test_art04_python.py
ImportError: cannot import name '_ctx_with' from 'conftest'
  (/Users/runner/work/compliancelint/compliancelint/scanner/tests/e2e/conftest.py)
...
Interrupted: 46 errors during collection
```

**Category**: (c) CI infra bug — more specifically, a pytest-collection
interaction, not a true code or test bug.

**Root cause** (from local diagnosis, previously documented in
`scanner/tests/G1_COMPLETE.md`): the top-level `scanner/tests/conftest.py`
defines a helper `_ctx_with` that the `test_art*_python.py` modules import
via `from conftest import _ctx_with`. When pytest's collection includes
both `scanner/tests/` and `scanner/tests/e2e/` in one run, the `conftest`
name in `sys.modules` resolves to `scanner/tests/e2e/conftest.py` (which
does NOT define `_ctx_with`), and all 46 article tests fail at import.

Locally this is avoided by running with `--ignore=scanner/tests/e2e`, but
the CI step does not pass that flag, so every `ci.yml` run — on ALL OSes
— trips this failure before any test actually executes.

**What the matrix expansion showed**: the failure is **uniform across all
12 OS × Python combinations**, confirming this is **not** an OS-specific
problem. Without the matrix, the same bug was only visible on
ubuntu-latest and could have been mistaken for a Linux quirk.

**Pre-existing**: yes. The previous commit (`bf1715e`, BUG-1 fix) also
shows `conclusion: failure` on its CI run for the same reason, as did
`eeae243` (G1 completion). The matrix expansion is orthogonal to this bug
— it did not introduce the failure, only broadened the evidence.

**Fix options (for the follow-up task)**:
1. Add `--ignore=scanner/tests/e2e` to the `Run tests` step in ci.yml.
   Pro: one-line change. Con: changes pytest flags, which the matrix
   expansion handoff §7 explicitly forbids — needs owner approval.
2. Move e2e/conftest.py helpers so its `conftest` shadowing is harmless
   (e.g. rename to a non-`conftest.py` file with explicit `from ... import`).
3. Restructure so `_ctx_with` lives in a dedicated helper module instead
   of conftest.py, and article tests import from that.

Option 3 is the most architecturally clean; option 1 is the fastest
unblocker. **Not decided in this task.**

**Scope note**: this affects only the `ci.yml` "Run tests" step. The
`test.yml` workflow was not triggered by `ad4c01e` (paths-filtered on
`scanner/**`, and the commit only changed `.github/workflows/`), so its
3 OS × Python 3.12 matrix has not yet produced evidence — this will
surface on the next scanner-touching commit.
