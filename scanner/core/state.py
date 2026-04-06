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


def _state_dir(project_path: str) -> str:
    return os.path.join(project_path, _STATE_DIR)


def get_project_id(project_path: str) -> str:
    """Derive a stable project identity — zero friction, no config files.

    Strategy (zero user action needed):
      1. Try .compliancelintrc (cached by cl_connect — fastest, no git needed)
      2. Compute git fingerprint via ProjectConfig.derive_git_identity()
      3. If not a git repo: fall back to UUID cached in .compliancelint/project.json

    Uses the same formula as cl_connect: SHA256(remote_url:root_commit)[:16]
    """
    from core.config import ProjectConfig

    # 1. Try cached project_id from .compliancelintrc
    config = ProjectConfig.load(project_path)
    if config.project_id:
        return config.project_id

    # 2. Derive from git (shared method — same formula everywhere)
    config.derive_git_identity(project_path)
    if config.project_id:
        return config.project_id

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

        new_findings[obl_id] = {
            "status": prev_status,
            "level": effective_level,
            "confidence": finding.get("confidence", "low"),
            "description": finding.get("description") or "",
            "source_quote": finding.get("source_quote") or prev.get("source_quote") or "",
            "remediation": finding.get("remediation"),
            "baselineState": baseline_state,
            "suppression": prev.get("suppression"),
            "evidence": prev.get("evidence", []),
            "history": prev.get("history", []) + [
                {"date": now, "action": "scanned", "level": effective_level, "by": "scanner"}
            ],
        }

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


def export_report(project_path: str, fmt: str = "md") -> dict:
    """Export compliance state as a formatted report.

    Args:
        fmt: "md" (markdown) or "json"

    Returns: {"path": str, "content": str} or {"error": str}
    """
    state = load_state(project_path)
    if not state.get("articles"):
        return {"error": "No scan data found. Run a scan first."}

    if fmt == "json":
        content = json.dumps(state, indent=2, ensure_ascii=False)
    elif fmt == "md":
        content = _render_markdown(state)
    else:
        return {"error": f"Unknown format: {fmt}. Use: md, json"}

    try:
        reports_dir = os.path.join(_state_dir(project_path), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
        ext = "md" if fmt == "md" else "json"
        path = os.path.join(reports_dir, f"report-{ts}.{ext}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"path": path, "content": content}
    except OSError as e:
        return {"error": f"Cannot write report: {e}", "content": content}


def _render_markdown(state: dict) -> str:
    """Render state as a detailed Markdown compliance report."""
    overall = state.get("overall_compliance", "no_data")

    # Collect assessed_by across all articles (pick first non-empty value)
    articles = state.get("articles", {})
    assessed_by_values = [
        a.get("assessed_by", "") for a in articles.values()
        if a.get("assessed_by", "")
    ]
    assessed_by = assessed_by_values[0] if assessed_by_values else ""
    assessed_by_display = assessed_by if assessed_by else "⚠️ not recorded — set `ai_model` in project_context"

    lines = [
        "# EU AI Act Compliance Report",
        "",
        f"**Project:** `{state.get('project_path', 'unknown')}`",
        f"**Overall compliance:** {overall.upper()}",
        f"**Last scan:** {state.get('last_scan', 'never')}",
        f"**Regulation:** EU AI Act (Regulation (EU) 2024/1689)",
        f"**Assessed by:** {assessed_by_display}",
        f"**Scan tool:** ComplianceLint MCP Server (github.com/ki-sum/compliancelint)",
        "",
        "---",
        "",
    ]

    # Sort articles numerically (art5 < art6 < art9 < art10 ... < art50)
    def _art_sort_key(item):
        key = item[0]  # e.g. "art12"
        try:
            return int(key.replace("art", ""))
        except ValueError:
            return 999

    for art_key, art_data in sorted(articles.items(), key=_art_sort_key):
        art_num = art_key.replace("art", "")
        art_overall = art_data.get("overall_level", "unknown")
        lines.append(f"## Art. {art_num} — {art_overall.upper()}")
        lines.append("")
        lines.append(f"- **Overall:** {art_overall}")
        lines.append(f"- **Confidence:** {art_data.get('overall_confidence', 'unknown')}")
        lines.append(f"- **Assessed by:** {art_data.get('assessed_by', 'unknown')}")
        lines.append(f"- **Scan date:** {art_data.get('scan_date', 'unknown')}")
        lines.append("")

        findings = art_data.get("findings", {})
        if not findings:
            lines.append("*No findings.*")
            lines.append("")
            continue

        # Summary table
        lines.append("| Obligation | Level | Status | Baseline | Evidence |")
        lines.append("|-----------|-------|--------|----------|----------|")
        for obl_id, f in sorted(findings.items()):
            level = f.get("level", "?")
            status = f.get("status", "open")
            baseline = f.get("baselineState", "?")
            ev_count = len(f.get("evidence", []))
            lines.append(f"| {obl_id} | {level} | {status} | {baseline} | {ev_count} items |")
        lines.append("")

        # Detailed findings (non-compliant and partial only)
        actionable = [(k, v) for k, v in sorted(findings.items())
                      if v.get("level") in ("non_compliant", "partial")]
        if actionable:
            lines.append("### Details")
            lines.append("")
            for obl_id, f in actionable:
                level = f.get("level", "?")
                lines.append(f"**{obl_id}** — {level.upper()}")
                lines.append("")
                desc = f.get("description", "")
                if desc:
                    lines.append(f"> {desc[:300]}")
                    lines.append("")
                remediation = f.get("remediation")
                if remediation:
                    lines.append(f"**Remediation:** {remediation[:300]}")
                    lines.append("")
                evidence = f.get("evidence", [])
                if evidence:
                    lines.append("**Evidence provided:**")
                    for ev in evidence:
                        lines.append(f"- [{ev.get('type', '?')}] {ev.get('value', '')}")
                    lines.append("")
                supp = f.get("suppression")
                if supp:
                    lines.append(f"**Suppression:** {supp.get('status', '?')} — {supp.get('justification', '')}")
                    lines.append("")

    lines.extend([
        "---",
        "",
        "*This report is an AI-assisted compliance assessment, not a legal opinion.*",
        "*All findings require human review and legal counsel before use in regulatory submissions.*",
        "",
        f"*Generated: {datetime.now(timezone.utc).isoformat()}*",
    ])

    return "\n".join(lines)
