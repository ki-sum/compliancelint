"""Compliance state persistence — per-article file architecture.

Storage layout:
  .compliancelint/
    articles/
      art5.json       ← each article scan saved independently (no write conflicts)
      art9.json
      art12.json
    state.json        ← merged view (regenerated on load_state)
    baselines/        ← timestamped snapshots (max 20, auto-cleanup)
    reports/          ← exported reports

Handles:
- Saving scan results per-article (concurrent-safe: different files)
- Loading merged state from all article files
- Updating individual findings (evidence, suppression, status)
- Exporting reports with full descriptions and evidence
- Computing overall compliance level across all articles
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional


_STATE_DIR = ".compliancelint"
_ARTICLES_DIR = "articles"
_BASELINES_DIR = "baselines"
_MAX_BASELINES = 20
_PROJECT_FILE = "project.json"

# D1: exception derogation map.
# Populated on first use from scanner/obligations/*.json linked_obligation
# fields. Key = EXC obligation id; value = list of main obligation ids that
# become not_applicable when the EXC is attested.
_DEROGATION_MAP: Optional[dict] = None


def _load_derogation_map() -> dict:
    """Load linked_obligation data from scanner/obligations/*.json.

    Returns dict[exc_obligation_id, list[main_obligation_id]].
    Memoised at module level — scanner obligations are static per release.
    """
    global _DEROGATION_MAP
    if _DEROGATION_MAP is not None:
        return _DEROGATION_MAP

    obligations_dir = os.path.join(os.path.dirname(__file__), "..", "obligations")
    result: dict = {}
    if not os.path.isdir(obligations_dir):
        _DEROGATION_MAP = result
        return result

    for fname in sorted(os.listdir(obligations_dir)):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(obligations_dir, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        for obl in data.get("obligations", []):
            oid = obl.get("id")
            linked = obl.get("linked_obligation")
            if oid and isinstance(linked, list) and linked:
                result[oid] = list(linked)

    _DEROGATION_MAP = result
    return result


def _state_dir(project_path: str) -> str:
    return os.path.join(project_path, _STATE_DIR)


def get_project_id(project_path: str) -> str:
    """Derive a stable project identity — zero friction, no config files.

    Strategy (zero user action needed):
      1. Try .compliancelintrc (cached by cl_connect or npx init — fastest)
      2. Fall back to UUID cached in .compliancelint/project.json

    IMPORTANT: Does NOT call git subprocess. In MCP context, git hangs
    the event loop. project_id must be pre-computed by `npx compliancelint init`
    and saved to .compliancelintrc.
    """
    from core.config import ProjectConfig

    # 1. Try cached project_id from .compliancelintrc
    config = ProjectConfig.load(project_path)
    if config.project_id:
        return config.project_id

    # 2. NO git fallback — derive_git_identity() hangs in MCP context.
    # project_id is pre-derived by `npx compliancelint init`.

    # Fallback for non-git projects: cached UUID in project.json
    sd = _state_dir(project_path)
    project_file = os.path.join(sd, _PROJECT_FILE)

    if os.path.isfile(project_file):
        try:
            with open(project_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            pid = data.get("project_id", "")
            if pid:
                return pid
        except (json.JSONDecodeError, OSError):
            pass

    # Generate and cache UUID
    pid = str(uuid.uuid4())
    os.makedirs(sd, exist_ok=True)
    with open(project_file, "w", encoding="utf-8") as f:
        json.dump({"project_id": pid, "created_at": datetime.now(timezone.utc).isoformat()}, f, indent=2)
    return pid


def save_metadata(project_path: str, ai_provider: str = "") -> None:
    """Save AI provider metadata to .compliancelint/metadata.json."""
    meta_path = os.path.join(_state_dir(project_path), "metadata.json")
    os.makedirs(_state_dir(project_path), exist_ok=True)
    meta = {}
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    if ai_provider:
        meta["ai_provider"] = ai_provider
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def _articles_dir(project_path: str) -> str:
    return os.path.join(_state_dir(project_path), _ARTICLES_DIR)


def _article_path(project_path: str, article_number: int) -> str:
    return os.path.join(_articles_dir(project_path), f"art{article_number}.json")


def load_state(project_path: str) -> dict:
    """Load merged state from all per-article files.

    Reads each .compliancelint/articles/artN.json and merges into
    a single state dict. No single state.json is required.
    """
    state = _empty_state(project_path)
    articles_dir = _articles_dir(project_path)

    if not os.path.isdir(articles_dir):
        return state

    last_scan = None
    last_updated = None

    for fname in sorted(os.listdir(articles_dir)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(articles_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                art_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        art_key = fname.replace(".json", "")
        state["articles"][art_key] = art_data

        # Track latest timestamps
        scan_date = art_data.get("scan_date")
        updated = art_data.get("last_updated", scan_date)
        if scan_date and (last_scan is None or scan_date > last_scan):
            last_scan = scan_date
        if updated and (last_updated is None or updated > last_updated):
            last_updated = updated

    if last_scan:
        state["last_scan"] = last_scan
    if last_updated:
        state["last_updated"] = last_updated

    # Compute overall compliance level
    state["overall_compliance"] = _compute_overall(state["articles"])

    return state


def _empty_state(project_path: str, regulation: str = "eu-ai-act") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "project_path": project_path,
        "created": now,
        "last_scan": now,
        "last_updated": now,
        "regulation": regulation,
        "overall_compliance": "no_data",
        "articles": {},
    }


def _compute_overall(articles: dict) -> str:
    """Compute overall compliance level across all articles."""
    if not articles:
        return "no_data"
    levels = [a.get("overall_level", "unable_to_determine") for a in articles.values()]
    if "non_compliant" in levels:
        return "non_compliant"
    if "partial" in levels:
        return "partial"
    if all(l in ("compliant", "not_applicable") for l in levels):
        return "compliant"
    return "unable_to_determine"


def save_article_result(
    project_path: str,
    article_number: int,
    scan_result_dict: dict,
) -> Optional[str]:
    """Save a single article's scan result to its own file.

    Writes to .compliancelint/articles/artN.json — independent per article,
    so concurrent scans of different articles never conflict.

    Preserves evidence and suppressions from previous scans.

    Returns: path to article file on success, None on failure.
    """
    now = datetime.now(timezone.utc).isoformat()
    article_path = _article_path(project_path, article_number)

    # Load existing article data (if any)
    existing = {}
    if os.path.isfile(article_path):
        try:
            with open(article_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    existing_findings = existing.get("findings", {})

    # D1: Build exception-derogation overlay.
    # An EXCEPTION obligation with prev_status="evidence_provided" derogates
    # its linked_obligation main obligations — they become not_applicable by
    # legal carve-out, regardless of what the scanner says about the code.
    # Example: ART53-EXC-2 (FOSS GPAI) attested → ART53-OBL-1a/1b legally
    # do not apply.
    derogation_map = _load_derogation_map()
    derogation_overlay: dict = {}  # main_obl_id -> list[exc_obl_id] that derogate it
    for exc_oid, linked_mains in derogation_map.items():
        exc_prev = existing_findings.get(exc_oid, {})
        if exc_prev.get("status") == "evidence_provided":
            for main_oid in linked_mains:
                derogation_overlay.setdefault(main_oid, []).append(exc_oid)

    # Build new findings dict, preserving user-provided data
    new_findings = {}
    for finding in scan_result_dict.get("findings", []):
        obl_id = finding.get("obligation_id", "")
        if not obl_id:
            continue

        prev = existing_findings.get(obl_id, {})
        prev_level = prev.get("level")
        new_level = finding.get("level", "unable_to_determine")

        # Determine baselineState
        if not prev:
            baseline_state = "new"
        elif prev_level == new_level:
            baseline_state = "unchanged"
        else:
            baseline_state = "updated"

        # If human has provided evidence and scanner says partial/utd,
        # upgrade to compliant — the human took responsibility.
        # Also upgrade classification_rule NC (e.g. ART06-CLS-2) — these are
        # "confirm this classification" findings, not "you did something wrong".
        prev_status = prev.get("status", "open")
        effective_level = new_level
        if prev_status == "evidence_provided":
            if new_level in ("partial", "unable_to_determine"):
                effective_level = "compliant"
            elif new_level == "non_compliant" and obl_id.startswith(("ART06-CLS", "ART06-COM", "ART06-CON")):
                # Classification confirmations: NC means "detected, needs confirmation"
                effective_level = "compliant"

        # D1: If this obligation is derogated by any attested EXCEPTION,
        # overlay effective_level to not_applicable. The derogation is a
        # legal carve-out — the scanner's finding about the code remains
        # in description/source_quote for audit, but the compliance status
        # reflects the legal reality.
        derogated_by = derogation_overlay.get(obl_id, [])
        if derogated_by:
            effective_level = "not_applicable"

        # Evidence quality check: if compliant but description lacks file path,
        # downgrade confidence to low (flag for human review)
        description = finding.get("description") or ""
        confidence = finding.get("confidence", "low")
        if effective_level == "compliant" and description:
            # Check if evidence mentions a specific file path
            import re as _re
            has_file_ref = bool(_re.search(
                r'[a-zA-Z0-9_/\\-]+\.\w{1,5}[\s:,]|\.py|\.ts|\.js|\.md|\.json|\.yaml|\.yml|line \d|L\d',
                description
            ))
            if not has_file_ref and confidence in ("high", "medium"):
                confidence = "low"  # Downgrade: no specific file evidence

        record = {
            "status": prev_status,
            "level": effective_level,
            "confidence": confidence,
            "description": description,
            "source_quote": finding.get("source_quote") or prev.get("source_quote") or "",
            "remediation": finding.get("remediation"),
            "baselineState": baseline_state,
            "suppression": prev.get("suppression"),
            "evidence": prev.get("evidence", []),
            "history": prev.get("history", []) + [
                {"date": now, "action": "scanned", "level": effective_level, "by": "scanner"}
            ],
        }
        # D1: record which EXCs drove the derogation, for audit trail
        if derogated_by:
            record["derogated_by"] = sorted(derogated_by)
        new_findings[obl_id] = record

    # Mark absent findings
    for obl_id, prev_finding in existing_findings.items():
        if obl_id not in new_findings:
            prev_finding["baselineState"] = "absent"
            prev_finding["history"] = prev_finding.get("history", []) + [
                {"date": now, "action": "absent", "by": "scanner"}
            ]
            new_findings[obl_id] = prev_finding

    article_data = {
        "overall_level": scan_result_dict.get("overall_level", "unable_to_determine"),
        "overall_confidence": scan_result_dict.get("overall_confidence", "low"),
        "scan_date": now,
        "last_updated": now,
        "assessed_by": scan_result_dict.get("assessed_by", ""),
        "findings": new_findings,
    }

    # Write per-article file
    try:
        os.makedirs(_articles_dir(project_path), exist_ok=True)
        with open(article_path, "w", encoding="utf-8") as f:
            json.dump(article_data, f, indent=2, ensure_ascii=False)
        # Also save merged state.json for convenience
        _save_merged_state(project_path)
        _save_baseline(project_path)
        return article_path
    except OSError:
        return None


def _save_merged_state(project_path: str) -> None:
    """Regenerate state.json from all article files."""
    try:
        state = load_state(project_path)
        path = os.path.join(_state_dir(project_path), "state.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def _save_baseline(project_path: str) -> None:
    """Save a timestamped snapshot. Keep max 20, delete oldest."""
    try:
        baselines_dir = os.path.join(_state_dir(project_path), _BASELINES_DIR)
        os.makedirs(baselines_dir, exist_ok=True)

        # Cleanup: keep only last _MAX_BASELINES
        existing = sorted(os.listdir(baselines_dir))
        while len(existing) >= _MAX_BASELINES:
            oldest = existing.pop(0)
            os.remove(os.path.join(baselines_dir, oldest))

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
        state = load_state(project_path)
        path = os.path.join(baselines_dir, f"{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def _load_article_index(project_path: str) -> tuple[dict, dict]:
    """Load all article files and build obligation index.

    Returns:
        (file_cache, obl_index) where:
        - file_cache: {fname: (fpath, data)}
        - obl_index: {obligation_id: (fname, finding_dict)}
    """
    articles_dir = _articles_dir(project_path)
    file_cache: dict[str, tuple[str, dict]] = {}
    obl_index: dict[str, tuple[str, dict]] = {}

    if not os.path.isdir(articles_dir):
        return file_cache, obl_index

    for fname in os.listdir(articles_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(articles_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        file_cache[fname] = (fpath, data)
        for obl_id in data.get("findings", {}):
            obl_index[obl_id] = (fname, data["findings"][obl_id])

    return file_cache, obl_index


def expand_article_evidence(
    project_path: str,
    evidence_items: list[dict],
) -> list[dict]:
    """Expand article-level evidence into per-obligation updates.

    Takes evidence like:
        [{"article": "art9", "action": "provide_evidence",
          "evidence_type": "file", "evidence_value": "docs/risk-management.md"}]

    Expands to one update per open finding in that article:
        [{"obligation_id": "ART09-OBL-1", "action": "provide_evidence", ...},
         {"obligation_id": "ART09-OBL-2", "action": "provide_evidence", ...},
         ...]

    Only expands to findings with status in ("open", "evidence_provided") and
    level in ("unable_to_determine", "partial", "non_compliant").

    Args:
        evidence_items: List of dicts with "article" key (e.g. "art9") instead of "obligation_id".

    Returns: Expanded list of per-obligation updates ready for update_findings_batch().
    """
    _, obl_index = _load_article_index(project_path)
    _ACTIONABLE_LEVELS = {"unable_to_determine", "partial", "non_compliant"}
    _ACTIONABLE_STATUSES = {"open", "evidence_provided"}

    expanded = []
    for item in evidence_items:
        article = item.get("article", "")  # e.g. "art9"
        action = item.get("action", "provide_evidence")
        evidence_type = item.get("evidence_type", "")
        evidence_value = item.get("evidence_value", "")
        justification = item.get("justification", "")

        # Find matching prefix: art9 → ART09-, art12 → ART12-
        art_num = article.replace("art", "").replace("Art", "")
        # Zero-pad single digits to match obligation IDs (ART09-, not ART9-)
        if art_num.isdigit():
            art_num = str(int(art_num))  # normalize "09" → "9"
            prefix = f"ART{int(art_num):02d}-"  # "9" → "ART09-"
        else:
            prefix = f"ART{art_num}-"

        for obl_id, (fname, finding) in obl_index.items():
            if not obl_id.startswith(prefix):
                continue
            level = finding.get("level", "")
            status = finding.get("status", "open")
            if level not in _ACTIONABLE_LEVELS:
                continue
            if status not in _ACTIONABLE_STATUSES:
                continue
            expanded.append({
                "obligation_id": obl_id,
                "action": action,
                "evidence_type": evidence_type,
                "evidence_value": evidence_value,
                "justification": justification,
            })

    return expanded


def update_findings_batch(
    project_path: str,
    updates: list[dict],
    attester: dict | None = None,
) -> dict:
    """Update multiple findings in one operation.

    Loads each article file at most once, applies all updates, writes once per file,
    and regenerates merged state only at the end.

    Args:
        updates: List of dicts, each with keys:
            obligation_id, action, evidence_type (opt), evidence_value (opt), justification (opt)
        attester: Shared attester identity for all updates.

    Returns: {"updated": N, "errors": [...], "details": [...]}
    """
    now = datetime.now(timezone.utc).isoformat()
    articles_dir = _articles_dir(project_path)
    if not os.path.isdir(articles_dir):
        return {"error": "No scan data found. Run a scan first."}

    by_info = attester if attester else {"name": "unknown", "email": "", "role": "", "source": "none"}

    # Load all article files once → build obligation→(file, data, finding) index
    file_cache, obl_index = _load_article_index(project_path)

    updated_count = 0
    errors = []
    details = []
    dirty_files: set[str] = set()  # fnames that need saving

    _VALID_ACTIONS = {"provide_evidence", "rebut", "acknowledge", "defer", "resolve"}

    for upd in updates:
        obl_id = upd.get("obligation_id", "")
        action = upd.get("action", "")
        evidence_type = upd.get("evidence_type", "")
        evidence_value = upd.get("evidence_value", "")
        justification = upd.get("justification", "")

        if action not in _VALID_ACTIONS:
            errors.append({"obligation_id": obl_id, "error": f"Invalid action: {action}"})
            continue
        if obl_id not in obl_index:
            errors.append({"obligation_id": obl_id, "error": "Finding not found"})
            continue

        fname, finding = obl_index[obl_id]
        history_entry = {"date": now, "action": action, "by": by_info}

        if action == "provide_evidence":
            finding.setdefault("evidence", []).append({
                "type": evidence_type,
                "value": evidence_value,
                "date": now,
                "provided_by": by_info,
            })
            finding["status"] = "evidence_provided"
            history_entry["evidence_type"] = evidence_type
            history_entry["evidence_value"] = evidence_value
        elif action == "rebut":
            finding["suppression"] = {
                "kind": "external",
                "status": "underReview",
                "justification": justification,
                "date": now,
                "submitted_by": by_info,
            }
            finding["status"] = "rebutted"
            history_entry["justification"] = justification
        elif action == "acknowledge":
            finding["status"] = "acknowledged"
        elif action == "defer":
            finding["status"] = "deferred"
        elif action == "resolve":
            finding["status"] = "resolved"
            if evidence_value:
                history_entry["note"] = evidence_value

        finding.setdefault("history", []).append(history_entry)
        file_cache[fname][1]["last_updated"] = now
        dirty_files.add(fname)
        updated_count += 1
        details.append({"obligation_id": obl_id, "action": action, "status": "updated"})

    # Write only modified files
    write_errors = []
    for fname in dirty_files:
        fpath, data = file_cache[fname]
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            write_errors.append(f"{fname}: {e}")

    # Regenerate merged state once
    if dirty_files:
        _save_merged_state(project_path)

    result = {"updated": updated_count, "errors": errors, "total_requested": len(updates)}
    if write_errors:
        result["write_errors"] = write_errors
    return result


def update_finding(
    project_path: str,
    obligation_id: str,
    action: str,
    evidence_type: str = "",
    evidence_value: str = "",
    justification: str = "",
    attester: dict | None = None,
) -> dict:
    """Update a single finding in its per-article file.

    Args:
        action: "provide_evidence" | "rebut" | "acknowledge" | "defer" | "resolve"
        attester: {"name": str, "email": str, "role": str, "source": str} or None.
                  If None, recorded as "unknown" (should be rejected by caller).

    Returns: updated finding dict, or error dict.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Find which article file contains this obligation
    articles_dir = _articles_dir(project_path)
    if not os.path.isdir(articles_dir):
        return {"error": "No scan data found. Run a scan first."}

    target_file = None
    target_data = None
    finding = None

    for fname in os.listdir(articles_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(articles_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if obligation_id in data.get("findings", {}):
            target_file = fpath
            target_data = data
            finding = data["findings"][obligation_id]
            break

    if finding is None:
        return {"error": f"Finding {obligation_id} not found. Run a scan first."}

    # Build structured history entry with attester identity
    by_info = attester if attester else {"name": "unknown", "email": "", "role": "", "source": "none"}
    history_entry = {"date": now, "action": action, "by": by_info}

    if action == "provide_evidence":
        finding.setdefault("evidence", []).append({
            "type": evidence_type,
            "value": evidence_value,
            "date": now,
            "provided_by": by_info,
        })
        finding["status"] = "evidence_provided"
        history_entry["evidence_type"] = evidence_type
        history_entry["evidence_value"] = evidence_value

    elif action == "rebut":
        finding["suppression"] = {
            "kind": "external",
            "status": "underReview",
            "justification": justification,
            "date": now,
            "submitted_by": by_info,
        }
        finding["status"] = "rebutted"
        history_entry["justification"] = justification

    elif action == "acknowledge":
        finding["status"] = "acknowledged"

    elif action == "defer":
        finding["status"] = "deferred"

    elif action == "resolve":
        finding["status"] = "resolved"
        if evidence_value:
            history_entry["note"] = evidence_value

    else:
        return {"error": f"Unknown action: {action}. Use: provide_evidence, rebut, acknowledge, defer, resolve"}

    finding.setdefault("history", []).append(history_entry)
    target_data["last_updated"] = now

    # Save to per-article file only (no global lock needed)
    try:
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(target_data, f, indent=2, ensure_ascii=False)
        _save_merged_state(project_path)
        return {"status": "updated", "obligation_id": obligation_id, "finding": finding}
    except OSError as e:
        return {"error": f"Cannot write: {e}"}




