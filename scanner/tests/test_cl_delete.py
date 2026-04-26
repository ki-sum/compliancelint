"""Coverage for MCP tool cl_delete.

Directory v2 (2026-04-24) semantics:
  - target="local" (default): only .compliancelint/local/ + home log dir.
    Evidence/ and .compliancelintrc are preserved.
  - target="all": full working-tree wipe (local/, evidence/, .compliancelintrc).
  - target="dashboard": server-side purge only.

Safety hardening (2026-04-24, commit 8f659e1):
  - target in {"local", "dashboard"} requires confirm=True.
  - target="all" requires confirm_phrase="I understand this is irreversible"
    (exact string). Boolean confirm=True is NOT sufficient for target="all".
  - Abort response carries will_delete / will_keep / reversibility /
    action_to_proceed so the LLM can echo concrete consequences.

Covers:
  - safety gate: confirm=False returns status="aborted" with will_delete list
  - target="local" removes .compliancelint/local/ but preserves
    .compliancelint/evidence/ and .compliancelintrc (v2 regression)
  - target="all" removes local/, evidence/, and .compliancelintrc — only
    when the magic phrase is supplied
  - error path: invalid target returns error listing legal values
  - abort message contents: concrete paths, reversibility wording,
    audit-trail warning for target="all"
  - magic-phrase gate: rejects empty / partial / wrong phrases; accepts the
    exact phrase even without boolean confirm
  - paths.human_size helper: missing path, file, directory tree
  - BUG-1 regression: cl_delete after a real cl_scan-style logger attach
    must succeed (no WinError 32 sharing violation on Windows)
  - BUG-1 regression: scanner.log must live under Path.home(), not inside
    the project tree (so it can't block shutil.rmtree)
"""
import json
import os
import sys
from pathlib import Path

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def _seed_cl_dir(project_path):
    cl_dir = os.path.join(project_path, ".compliancelint")
    local_articles = os.path.join(cl_dir, "local", "articles")
    os.makedirs(local_articles, exist_ok=True)
    with open(os.path.join(local_articles, "art12.json"), "w", encoding="utf-8") as f:
        json.dump({"article": 12, "findings": {}}, f)
    return cl_dir


def test_delete_without_confirm_is_safety_abort(tmp_path):
    cl_dir = _seed_cl_dir(str(tmp_path))

    raw = server.cl_delete(str(tmp_path), target="local", confirm=False)
    parsed = json.loads(raw)

    assert parsed["status"] == "aborted", f"expected safety gate, got: {parsed}"
    assert "will_delete" in parsed
    assert "will_keep" in parsed
    assert os.path.isdir(cl_dir), "safety gate must NOT delete data"


def test_delete_local_with_confirm_removes_state(tmp_path):
    cl_dir = _seed_cl_dir(str(tmp_path))
    local_dir = os.path.join(cl_dir, "local")

    raw = server.cl_delete(str(tmp_path), target="local", confirm=True)
    parsed = json.loads(raw)

    assert parsed["status"] == "deleted", f"unexpected status: {parsed}"
    assert parsed["results"]["local"] == "deleted"
    assert not os.path.exists(local_dir), (
        ".compliancelint/local/ must be removed after confirmed target=local delete"
    )


def test_delete_local_preserves_evidence_and_rc(tmp_path):
    """v2 regression (§3): target=local must NOT touch audit-trail evidence/
    or the .compliancelintrc dashboard binding. Removing those requires the
    explicit target=all (working-tree wipe) or the dashboard UI's own delete.
    """
    _seed_cl_dir(str(tmp_path))

    # Seed a committed-side evidence payload + rc file
    evidence_dir = tmp_path / ".compliancelint" / "evidence" / "f-art09-bias"
    evidence_dir.mkdir(parents=True)
    ev_file = evidence_dir / "bias-report.pdf"
    ev_file.write_bytes(b"%PDF-1.4 fake evidence")
    rc_file = tmp_path / ".compliancelintrc"
    rc_file.write_text(json.dumps({"project_id": "git-fakefake12345678"}), encoding="utf-8")

    raw = server.cl_delete(str(tmp_path), target="local", confirm=True)
    parsed = json.loads(raw)

    assert parsed["status"] == "deleted"
    assert parsed["results"]["local"] == "deleted"
    assert ev_file.exists(), (
        "target=local must preserve .compliancelint/evidence/ — removing it "
        "destroys the audit trail (only the dashboard UI may delete evidence)"
    )
    assert rc_file.exists(), (
        "target=local must preserve .compliancelintrc — removing it orphans "
        "the dashboard row; use cl_disconnect or target=all for full wipe"
    )


def test_delete_all_removes_everything(tmp_path):
    """v2 regression (§3): target=all wipes the entire .compliancelint/ tree
    plus .compliancelintrc. Dashboard server state is untouched."""
    _seed_cl_dir(str(tmp_path))
    evidence_dir = tmp_path / ".compliancelint" / "evidence" / "f-art09-bias"
    evidence_dir.mkdir(parents=True)
    ev_file = evidence_dir / "bias-report.pdf"
    ev_file.write_bytes(b"%PDF-1.4 fake evidence")
    rc_file = tmp_path / ".compliancelintrc"
    rc_file.write_text(json.dumps({"project_id": "git-fakefake12345678"}), encoding="utf-8")

    raw = server.cl_delete(
        str(tmp_path),
        target="all",
        confirm=True,
        confirm_phrase="I understand this is irreversible",
    )
    parsed = json.loads(raw)

    assert parsed["status"] == "deleted"
    assert parsed["results"]["root"] == "deleted"
    assert parsed["results"]["rc"] == "deleted"
    assert not (tmp_path / ".compliancelint").exists()
    assert not rc_file.exists()


def test_delete_invalid_target_returns_error(tmp_path):
    _seed_cl_dir(str(tmp_path))

    raw = server.cl_delete(str(tmp_path), target="invalid", confirm=True)
    parsed = json.loads(raw)

    assert "error" in parsed, f"expected error, got: {parsed}"
    assert "invalid" in parsed["error"].lower()
    for legal in ("local", "all", "dashboard"):
        assert legal in parsed["error"], f"error must list legal target '{legal}'"


# ── Regression: cl_delete on Windows with an open scanner.log handle ────────

def test_delete_works_after_real_cl_scan_without_monkeypatch(tmp_path):
    """Regression for BUG-1: cl_delete must succeed on Windows even after a
    real RotatingFileHandler has been attached for this project (what every
    prior cl_scan / cl_sync call in the same MCP process does). Pre-fix this
    raises PermissionError: WinError 32 because scanner.log is still open
    inside the very directory rmtree is trying to remove.
    """
    _seed_cl_dir(str(tmp_path))

    # Trigger the real get_scanner_logger path — no monkeypatch. Mirrors what
    # happens in a long-running MCP process after any earlier scan.
    from core.scanner_log import get_scanner_logger
    log = get_scanner_logger(str(tmp_path))
    log.info("simulating a prior cl_scan writing to scanner.log for %s", tmp_path)

    raw = server.cl_delete(str(tmp_path), target="local", confirm=True)
    parsed = json.loads(raw)

    assert parsed["status"] == "deleted", f"cl_delete failed post-scan: {parsed}"
    assert parsed["results"]["local"] == "deleted"
    assert not (tmp_path / ".compliancelint" / "local").exists(), (
        "project .compliancelint/local/ must be gone after confirmed target=local delete"
    )


def test_scanner_log_lives_outside_project_tree(tmp_path):
    """BUG-1 fix: scanner.log MUST be written under Path.home() / .compliancelint/,
    not inside {project}/.compliancelint/. Placing log state outside the project
    tree is what makes cl_delete safe on Windows — rmtree of the project dir
    can never hit an open log handle.
    """
    from logging.handlers import RotatingFileHandler
    from core.scanner_log import get_scanner_logger

    log = get_scanner_logger(str(tmp_path))
    log.info("where does this handler's baseFilename land?")

    project_log = tmp_path / ".compliancelint" / "logs" / "scanner.log"
    assert not project_log.exists(), (
        f"scanner.log leaked back into project tree at {project_log}"
    )

    file_handlers = [h for h in log.handlers if isinstance(h, RotatingFileHandler)]
    assert len(file_handlers) >= 1, (
        "expected at least one RotatingFileHandler attached to the project logger"
    )

    home_resolved = Path.home().resolve()
    for h in file_handlers:
        bf = Path(h.baseFilename).resolve()
        assert str(bf).startswith(str(home_resolved)), (
            f"log file at {bf} is not under home {home_resolved}"
        )
        assert ".compliancelint" in bf.parts, (
            f"log file {bf} must live under a .compliancelint directory"
        )


# ── Delete safety hardening (2026-04-24) ─────────────────────────────────────
# Three-layer defense against LLM misinterpreting destructive intent:
#   L1. Abort response lists concrete paths (will_delete / will_keep).
#   L2. target="all" demands a magic phrase — boolean confirm is not enough.
#   L3. Docstring instructs LLM to disambiguate ambiguous "delete" requests.

def test_abort_message_lists_concrete_paths_for_local(tmp_path):
    """L1: target=local abort must list the local/ path as will_delete and
    explicitly preserve evidence/ + .compliancelintrc in will_keep so the LLM
    can echo concrete consequences back to the user."""
    _seed_cl_dir(str(tmp_path))
    (tmp_path / ".compliancelint" / "evidence" / "f-art09").mkdir(parents=True)
    (tmp_path / ".compliancelintrc").write_text("{}", encoding="utf-8")

    raw = server.cl_delete(str(tmp_path), target="local", confirm=False)
    parsed = json.loads(raw)

    assert parsed["status"] == "aborted"
    assert parsed["target"] == "local"
    assert "will_delete" in parsed and isinstance(parsed["will_delete"], list)
    assert "will_keep" in parsed and isinstance(parsed["will_keep"], list)
    assert "reversibility" in parsed
    assert "action_to_proceed" in parsed
    assert any(
        ".compliancelint/local" in item or ".compliancelint\\local" in item
        for item in parsed["will_delete"]
    ), f"will_delete must name the local dir, got: {parsed['will_delete']}"
    assert any("evidence" in item.lower() for item in parsed["will_keep"]), (
        f"will_keep must mention evidence/, got: {parsed['will_keep']}"
    )
    assert any(".compliancelintrc" in item for item in parsed["will_keep"]), (
        f"will_keep must mention .compliancelintrc, got: {parsed['will_keep']}"
    )


def test_abort_message_lists_concrete_paths_for_all(tmp_path):
    """L1: target=all abort must warn about the git-committed audit trail
    being destroyed, and label reversibility as IRREVERSIBLE."""
    _seed_cl_dir(str(tmp_path))
    ev_dir = tmp_path / ".compliancelint" / "evidence" / "f-art09"
    ev_dir.mkdir(parents=True)
    (ev_dir / "report.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / ".compliancelintrc").write_text("{}", encoding="utf-8")

    raw = server.cl_delete(str(tmp_path), target="all", confirm=False)
    parsed = json.loads(raw)

    assert parsed["status"] == "aborted"
    assert parsed["target"] == "all"
    assert "will_delete" in parsed
    assert any("audit trail" in item for item in parsed["will_delete"]), (
        f"target=all must flag audit trail loss, got: {parsed['will_delete']}"
    )
    assert any(".compliancelintrc" in item for item in parsed["will_delete"])
    assert "IRREVERSIBLE" in parsed["reversibility"].upper(), (
        f"target=all reversibility must scream irreversibility, got: {parsed['reversibility']}"
    )


def test_abort_message_lists_concrete_paths_for_dashboard(tmp_path):
    """L1: target=dashboard abort must mention server-side repo row + say
    local/ and evidence/ are preserved."""
    _seed_cl_dir(str(tmp_path))

    raw = server.cl_delete(str(tmp_path), target="dashboard", confirm=False)
    parsed = json.loads(raw)

    assert parsed["status"] == "aborted"
    assert parsed["target"] == "dashboard"
    assert any("dashboard repo row" in item.lower() for item in parsed["will_delete"]), (
        f"dashboard abort must list the repo row, got: {parsed['will_delete']}"
    )
    assert any("local" in item.lower() for item in parsed["will_keep"])


def test_target_all_rejects_boolean_confirm(tmp_path):
    """L2: boolean confirm=True is NOT sufficient for target='all'. Must
    still require the magic phrase or nothing is destroyed."""
    _seed_cl_dir(str(tmp_path))
    ev_dir = tmp_path / ".compliancelint" / "evidence" / "f-art09"
    ev_dir.mkdir(parents=True)
    (ev_dir / "report.pdf").write_bytes(b"%PDF-1.4 fake")
    rc = tmp_path / ".compliancelintrc"
    rc.write_text("{}", encoding="utf-8")

    raw = server.cl_delete(str(tmp_path), target="all", confirm=True, confirm_phrase="")
    parsed = json.loads(raw)

    assert parsed["status"] == "aborted", (
        f"target='all' must reject boolean-only confirmation, got: {parsed}"
    )
    assert (tmp_path / ".compliancelint").exists(), "no deletion must have occurred"
    assert rc.exists()


def test_target_all_requires_exact_phrase(tmp_path):
    """L2: close-but-not-exact phrase must still abort. Prevents typo/
    paraphrase from nuking the audit trail."""
    _seed_cl_dir(str(tmp_path))
    rc = tmp_path / ".compliancelintrc"
    rc.write_text("{}", encoding="utf-8")

    raw = server.cl_delete(
        str(tmp_path),
        target="all",
        confirm=True,
        confirm_phrase="I understand",  # close, but not exact
    )
    parsed = json.loads(raw)

    assert parsed["status"] == "aborted", (
        f"inexact phrase must not trigger deletion, got: {parsed}"
    )
    assert (tmp_path / ".compliancelint").exists()
    assert rc.exists()


def test_target_all_accepts_exact_phrase(tmp_path):
    """L2: exact magic phrase is the only way to execute target='all'."""
    _seed_cl_dir(str(tmp_path))
    ev_dir = tmp_path / ".compliancelint" / "evidence" / "f-art09"
    ev_dir.mkdir(parents=True)
    (ev_dir / "report.pdf").write_bytes(b"%PDF-1.4 fake")
    rc = tmp_path / ".compliancelintrc"
    rc.write_text("{}", encoding="utf-8")

    raw = server.cl_delete(
        str(tmp_path),
        target="all",
        confirm=True,
        confirm_phrase="I understand this is irreversible",
    )
    parsed = json.loads(raw)

    assert parsed["status"] == "deleted", (
        f"exact phrase must trigger deletion, got: {parsed}"
    )
    assert parsed["results"]["root"] == "deleted"
    assert not (tmp_path / ".compliancelint").exists()
    assert not rc.exists()


def test_target_all_phrase_alone_suffices_without_boolean_confirm(tmp_path):
    """L2 edge case: magic phrase REPLACES (not augments) the boolean gate
    for target='all'. confirm=False + exact phrase must still execute,
    because the phrase is the sole authority for irreversible target='all'.
    Documents intent: do NOT add a "phrase AND confirm" rule by accident.
    """
    _seed_cl_dir(str(tmp_path))
    rc = tmp_path / ".compliancelintrc"
    rc.write_text("{}", encoding="utf-8")

    raw = server.cl_delete(
        str(tmp_path),
        target="all",
        confirm=False,  # explicitly False
        confirm_phrase="I understand this is irreversible",
    )
    parsed = json.loads(raw)

    assert parsed["status"] == "deleted", (
        f"target='all' with exact phrase must execute regardless of boolean "
        f"confirm; got: {parsed}"
    )
    assert parsed["results"]["root"] == "deleted"
    assert not (tmp_path / ".compliancelint").exists()
    assert not rc.exists()


# ── paths.human_size unit tests (covers helper directly) ─────────────────────

def test_human_size_missing_path_returns_zero(tmp_path):
    """human_size of a non-existent path is the safe '0 B' rather than raising."""
    from core.paths import human_size

    assert human_size(tmp_path / "does-not-exist") == "0 B"


def test_human_size_single_file_reports_byte_count(tmp_path):
    """human_size of a regular file reports its byte count, not a directory walk."""
    from core.paths import human_size

    f = tmp_path / "tiny.bin"
    f.write_bytes(b"x" * 500)
    assert human_size(f) == "500 B"


def test_human_size_directory_sums_subtree(tmp_path):
    """human_size of a directory walks the subtree and aggregates all file sizes,
    rolling up to KB/MB units as the total grows."""
    from core.paths import human_size

    sub = tmp_path / "sub" / "deeper"
    sub.mkdir(parents=True)
    # 3 KB total spread across 3 files in 2 directory levels
    (tmp_path / "a.bin").write_bytes(b"x" * 1024)
    (sub / "b.bin").write_bytes(b"y" * 1024)
    (sub / "c.bin").write_bytes(b"z" * 1024)

    result = human_size(tmp_path)
    assert result.endswith(" KB"), f"expected KB unit for ~3 KB tree, got: {result!r}"
    # 3072 B / 1024 = 3.0 KB → formatter renders "3 KB"
    assert result == "3 KB", f"expected exactly '3 KB' for 3×1024 B, got: {result!r}"
