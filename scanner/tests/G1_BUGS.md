# G1 Tool Bug Log

Product bugs surfaced while writing G1 thin-coverage tests. Per §3.5 of
`G1_HANDOFF.md`, tests do not weaken assertions and do not modify `scanner/src/`
to work around these; instead they are documented here for the owning session.

---

## BUG-1 — cl_delete target=local can fail on Windows due to open log handle

**Tool**: `cl_delete` (`scanner/server.py:2753`)
**Platform**: Windows
**Trigger**: `cl_delete(project_path, target="local", confirm=True)` in a process
that has already called `get_scanner_logger(project_path)` (which the tool
itself does at `server.py:2774` before `shutil.rmtree` at `server.py:2805`).

**Symptom**: `PermissionError: [WinError 32] Der Prozess kann nicht auf die Datei
zugreifen, da sie von einem anderen Prozess verwendet wird:
'...\.compliancelint\logs\scanner.log'`

**Cause**: `core/scanner_log.py` attaches a `RotatingFileHandler` to the
shared `compliancelint.project` logger, keyed by `project_path`. The handler
keeps `scanner.log` open for the life of the process. `shutil.rmtree` on
Windows cannot remove a file held open by the same process.

**Reproduction**:
```python
server.cl_delete(str(tmp_path), target="local", confirm=True)
# → PermissionError propagates; JSON result is never returned
```

**Test accommodation** (not a src fix): `test_cl_delete.py` monkeypatches
`core.scanner_log.get_scanner_logger` to return a stderr-only logger for the
`test_delete_local_with_confirm_removes_state` test. This isolates the core
delete semantics; the Windows handle bug is left for the owner to fix (e.g.
close+removeHandler before rmtree, or route scanner_log outside the delete
target, or retry with FileHandler.close()).

**Severity**: MEDIUM — reproduces in real MCP server usage (the server is
long-running, so any project that ran `cl_scan` before `cl_delete` will have
the handler open).
