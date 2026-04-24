# G1 Complete — 8 MCP tools thin coverage

Per `scanner/tests/G1_HANDOFF.md`, this run added thin coverage for the
8 previously-untested MCP tools in `scanner/server.py`. One commit per tool,
no changes to `scanner/src/`, `scanner/core/`, `scanner/modules/`, or any
other scanner production code.

## Per-tool summary

| Tool | Test file | Tests | Happy / error breakdown |
|---|---|---:|---|
| `cl_explain` | `test_cl_explain.py` | 3 | 1 happy, 2 error |
| `cl_interim_standard` | `test_cl_interim_standard.py` | 2 | 1 happy, 1 error |
| `cl_disconnect` | `test_cl_disconnect.py` | 2 | 1 happy, 1 not-connected |
| `cl_delete` | `test_cl_delete.py` | 3 | safety gate, happy (with monkeypatch — see G1_BUGS.md BUG-1), invalid target |
| `cl_verify_evidence` | `test_cl_verify_evidence.py` | 3 | declared items, missing file, bad path |
| `cl_update_finding` | `test_cl_update_finding.py` | 3 | acknowledge, invalid action, unknown id |
| `cl_update_finding_batch` | `test_cl_update_finding_batch.py` | 2 | all-valid, partial-failure |
| `cl_sync` | `test_cl_sync.py` | 3 | no-api-key, payload structure (mock curl), 401 |

**Total**: 21 new tests across 8 files. ~722 lines of additions.

## Full pytest (excluding live-dashboard e2e): 2378 passed, 24 skipped in 55.55s

```
python -m pytest scanner/tests -v --ignore=scanner/tests/e2e
====================== 2378 passed, 24 skipped in 55.55s ======================
```

The pre-existing sys.path collision between `scanner/tests/conftest.py`
(exposes `_ctx_with`) and `scanner/tests/e2e/conftest.py` only surfaces when
e2e is collected alongside the top-level tests; this is not introduced by
G1 and is out of scope for thin-coverage work. Running each suite
separately (top-level with `--ignore=scanner/tests/e2e`, or e2e directly
with `scanner/tests/e2e`) resolves without error.

## Bugs surfaced

See `scanner/tests/G1_BUGS.md`:

- **BUG-1** — `cl_delete` + Windows: `get_scanner_logger` holds `scanner.log`
  open via `RotatingFileHandler`, so `shutil.rmtree` raises WinError 32. The
  `test_delete_local_with_confirm_removes_state` test monkeypatches
  `core.scanner_log.get_scanner_logger` to isolate the core delete semantics;
  the underlying tool bug remains for the owner to fix.

## Notes on handoff deltas

- §Tool 5 described a `broken_link` scenario that actually belongs to
  `cl_scan`, not `cl_verify_evidence`. Tests cover actual tool scope: reads
  `compliance-evidence.json`, returns AI-verification instructions.
- §Tool 6 listed `questionnaire_response` and `false_positive` as legal
  actions; the live allow-list in `server.py:1246` is
  `{provide_evidence, rebut, acknowledge, defer, resolve}`. Tests assert
  against the actual allow-list.
- §Tool 8 suggested `pytest-httpserver` / `responses` / `requests-mock`;
  none are installed and the handoff forbids `pip install`. Tests instead
  monkeypatch `subprocess.run` with a curl/git dispatcher — stdlib only.
