"""
ComplianceLint — Project-Level Evidence Declaration (v4)

Allows project maintainers to declare compliance evidence in
compliance-evidence.json. The scanner reads this file and returns
verification instructions to the AI client (e.g. Claude in the IDE).

Aligned with v4 evidence architecture (shipped 2026-04-21). The four
storage kinds are the single source of truth — no separate "attestation"
or "screenshot" type. A screenshot is just a `repo_file` (PNG committed
to the repo) or a `url_reference` (external link). A free-text declaration
is `text`. The scanner finds what it can in code; this file fills the gaps
that are not directly inferable from code structure (legal documents,
external policy URLs, inline declarations).

storage_kind ∈ {text, repo_file, git_path, url_reference}
  text          — Inline declaration. The description IS the evidence.
  repo_file     — File committed to the repo (any binary or text file).
                  AI client uses Read to inspect the bytes and judge.
  git_path      — Specific path[:line] in the repo (e.g. src/api.py:34).
                  AI client reads the cited code/text and judges.
  url_reference — External URL. Second-class evidence (no durability /
                  provenance proof). AI client fetches and judges.

storage_kind values must stay in sync with the dashboard's storageKind
column and the evidence-respond route. When changing this set, audit the
SaaS schema + the upload-file / respond endpoints in lock-step.

Workflow:
  1. PM runs scan → finds NON_COMPLIANT findings
  2. PM creates compliance-evidence.json in project root using v4 kinds
  3. cl_verify_evidence() returns evidence list with verification instructions
  4. AI client inspects each item per its storage_kind and evaluates adequacy
  5. AI synthesizes final report: scanner findings + verified evidence
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional


EVIDENCE_FILE = "compliance-evidence.json"

# v4 storage kinds — single source of truth, synced with dashboard schema.
STORAGE_KINDS = frozenset({"text", "repo_file", "git_path", "url_reference"})

# Pre-v4 vocabulary. Rejected at load time with a migration message.
_DEPRECATED_KINDS = {
    "url":         "url_reference",
    "file":        "repo_file (or git_path for path:line citations)",
    "attestation": "text (inline declaration)",
    "screenshot":  "repo_file (commit the PNG to the repo) or url_reference (external link)",
    "google_drive": "repo_file (download + commit) or url_reference",
    "github":       "url_reference (paste the GitHub link)",
}


@dataclass
class EvidenceItem:
    """A single piece of compliance evidence provided by the project maintainer."""
    obligation_id: str             # e.g. "ART13" or "ART12-OBL-1"
    storage_kind: str              # v4: text | repo_file | git_path | url_reference
    location: Optional[str]        # path / path:line / URL — None for `text`
    description: str               # inline content for text; human description otherwise
    provided_by: Optional[str]     # who provided this evidence (name/role)

    @property
    def requires_ai_verification(self) -> bool:
        """All v4 kinds require the AI client to inspect content and judge.

        v4 removed the "attested but not verified" loophole. Every declared
        item must be inspectable — either inline text the AI judges, a file
        the AI reads, a code line the AI reads, or a URL the AI fetches.
        """
        return True

    @property
    def verification_instruction(self) -> str:
        """Returns the instruction the AI client must follow for this item."""
        if self.storage_kind == "text":
            return (
                f"Inline text evidence for {self.obligation_id}: \"{self.description}\"\n"
                f"Evaluate whether this declaration adequately satisfies the legal "
                f"obligation. Reject if vague (e.g. 'I think we're fine'). Accept if "
                f"specific (e.g. 'docs/risk.md §2 lists 7 identified risks with mitigations')."
            )
        if self.storage_kind == "repo_file":
            return (
                f"Read file: {self.location}\n"
                f"Evaluate whether the content satisfies {self.obligation_id}.\n"
                f"Maintainer says: \"{self.description}\""
            )
        if self.storage_kind == "git_path":
            return (
                f"Read the cited path/line: {self.location}\n"
                f"Evaluate whether the cited code or text satisfies {self.obligation_id}.\n"
                f"Maintainer says: \"{self.description}\""
            )
        if self.storage_kind == "url_reference":
            return (
                f"Fetch URL: {self.location}\n"
                f"Evaluate whether the page content satisfies {self.obligation_id}.\n"
                f"NOTE: url_reference is second-class evidence — no durability or "
                f"provenance proof. Flag this caveat in the final report.\n"
                f"Maintainer says: \"{self.description}\""
            )
        # Should be unreachable — load_evidence rejects unknown kinds.
        return f"Unknown storage_kind: {self.storage_kind}"

    def to_dict(self) -> dict:
        return {
            "obligation_id": self.obligation_id,
            "storage_kind": self.storage_kind,
            "location": self.location,
            "description": self.description,
            "provided_by": self.provided_by,
            "requires_ai_verification": self.requires_ai_verification,
            "verification_instruction": self.verification_instruction,
        }


@dataclass
class ProjectEvidence:
    """All evidence declared for a project."""
    project_path: str
    evidence_file: str
    items: list[EvidenceItem] = field(default_factory=list)
    load_error: Optional[str] = None

    @property
    def has_evidence(self) -> bool:
        return len(self.items) > 0

    @staticmethod
    def _normalize_art_prefix(s: str) -> str:
        """Normalize ART prefix to zero-padded form: ART9 → ART09, ART12 → ART12."""
        import re
        m = re.match(r"^(ART)(\d+)(.*)", s, re.IGNORECASE)
        if m:
            return f"ART{int(m.group(2)):02d}{m.group(3)}"
        return s

    def get_for_obligation(self, obligation_id: str) -> Optional[EvidenceItem]:
        """
        Match evidence to an obligation ID.
        Supports both exact match (ART13-OBL-1) and article-level match (ART13).
        Handles zero-padding: ART9 matches ART09-OBL-1.
        """
        norm_obl = self._normalize_art_prefix(obligation_id).upper()
        for item in self.items:
            norm_item = self._normalize_art_prefix(item.obligation_id).upper()
            if norm_item == norm_obl:
                return item
            # Article-level: "ART09" matches "ART09-OBL-1", "ART09-OBL-2a", etc.
            if norm_obl.startswith(norm_item + "-"):
                return item
            # Reverse: evidence "ART09-OBL-1" matches query "ART09"
            if norm_item.startswith(norm_obl + "-"):
                return item
        return None

    def covers_obligation(self, obligation_id: str) -> bool:
        return self.get_for_obligation(obligation_id) is not None

    def to_summary_dict(self) -> dict:
        return {
            "evidence_file": self.evidence_file,
            "total_items": len(self.items),
            "items": [i.to_dict() for i in self.items],
        }


def load_evidence(project_path: str) -> ProjectEvidence:
    """
    Load compliance-evidence.json from the project root.

    Returns a ProjectEvidence object. If the file doesn't exist, returns an
    empty ProjectEvidence (no error — evidence is optional).

    Hard-rejects pre-v4 storage kinds (`url`, `file`, `attestation`,
    `screenshot`, `google_drive`, `github`) with a migration message in
    `load_error`. Mixed files are rejected entirely — partial load would
    silently drop evidence the maintainer intended to declare.
    """
    evidence_path = os.path.join(project_path, EVIDENCE_FILE)

    if not os.path.exists(evidence_path):
        return ProjectEvidence(
            project_path=project_path,
            evidence_file=evidence_path,
            items=[],
        )

    try:
        with open(evidence_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return ProjectEvidence(
            project_path=project_path,
            evidence_file=evidence_path,
            items=[],
            load_error=str(e),
        )

    items: list[EvidenceItem] = []
    rejected: list[dict] = []
    for obligation_id, val in data.get("evidence", {}).items():
        if not isinstance(val, dict):
            continue
        kind = val.get("storage_kind") or val.get("type") or ""
        if kind in _DEPRECATED_KINDS:
            rejected.append({
                "obligation_id": obligation_id,
                "deprecated_kind": kind,
                "migrate_to": _DEPRECATED_KINDS[kind],
            })
            continue
        if kind not in STORAGE_KINDS:
            rejected.append({
                "obligation_id": obligation_id,
                "unknown_kind": kind or "(missing)",
                "valid_kinds": sorted(STORAGE_KINDS),
            })
            continue
        items.append(EvidenceItem(
            obligation_id=obligation_id,
            storage_kind=kind,
            location=val.get("location"),
            description=val.get("description", ""),
            provided_by=val.get("provided_by"),
        ))

    if rejected:
        return ProjectEvidence(
            project_path=project_path,
            evidence_file=evidence_path,
            items=[],
            load_error=json.dumps({
                "message": (
                    "compliance-evidence.json uses pre-v4 storage kinds. v4 (shipped "
                    "2026-04-21) accepts only: " + ", ".join(sorted(STORAGE_KINDS)) + "."
                ),
                "rejected": rejected,
            }),
        )

    return ProjectEvidence(
        project_path=project_path,
        evidence_file=evidence_path,
        items=items,
    )


def apply_evidence_to_findings(findings: list[dict], evidence: ProjectEvidence) -> list[dict]:
    """
    Annotate scan findings with available evidence.

    Does NOT change compliance levels — that is the AI client's job after
    verification. Adds an 'evidence' key to findings where evidence is declared.

    The AI client reads the evidence per `verification_instruction`, then
    decides the final compliance level.
    """
    if not evidence.has_evidence:
        return findings

    annotated = []
    for finding in findings:
        obligation_id = finding.get("obligation_id", "")
        level = finding.get("level", "")

        # Only annotate non-compliant or unable_to_determine findings
        if level in ("non_compliant", "unable_to_determine", "partial"):
            ev = evidence.get_for_obligation(obligation_id)
            if ev:
                finding = dict(finding)  # don't mutate original
                finding["evidence"] = ev.to_dict()
                finding["evidence_note"] = (
                    f"Maintainer has provided {ev.storage_kind} evidence. "
                    f"AI client must follow `verification_instruction` and judge adequacy."
                )

        annotated.append(finding)

    return annotated
