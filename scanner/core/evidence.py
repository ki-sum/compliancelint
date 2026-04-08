"""
ComplianceLint — Evidence Management System

Allows project maintainers to declare compliance evidence that exists
outside the scanned codebase (e.g., external URLs, legal documents,
configuration screenshots).

The scanner finds what it can in code. Evidence fills the gaps.

Evidence types:
  url         — External URL (Terms of Service, Privacy Policy, etc.)
                AI client MUST fetch and verify content adequacy.
  file        — Local file path relative to project root
                AI client MUST read and verify content adequacy.
  attestation — Human declaration with description only.
                Accepted with a warning: not AI-verifiable.
  screenshot  — Visual evidence (config panels, UI screenshots).
                Accepted with a warning: not AI-verifiable.

Workflow:
  1. PM runs scan → finds NON_COMPLIANT findings
  2. PM creates compliance-evidence.json in project root
  3. cl_verify_evidence() returns evidence list with verification instructions
  4. AI client fetches URLs / reads files / evaluates legal adequacy
  5. AI synthesizes final report: scanner findings + verified evidence
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional


EVIDENCE_FILE = "compliance-evidence.json"

# Evidence types that require AI fetch/read to verify
AI_VERIFIABLE_TYPES = {"url", "file"}

# Evidence types accepted on human declaration only
ATTESTATION_TYPES = {"attestation", "screenshot"}


@dataclass
class EvidenceItem:
    """A single piece of compliance evidence provided by the project maintainer."""
    obligation_id: str          # e.g. "ART13" or "ART12-OBL-1" (article-level or specific)
    evidence_type: str          # "url" | "file" | "attestation" | "screenshot"
    location: Optional[str]     # URL or relative file path (None for attestation/screenshot)
    description: str            # Human description of what this evidence proves
    provided_by: Optional[str]  # Optional: who provided this evidence (name/role)

    @property
    def requires_ai_verification(self) -> bool:
        return self.evidence_type in AI_VERIFIABLE_TYPES

    @property
    def verification_instruction(self) -> str:
        """Returns instruction for the AI client on how to verify this evidence."""
        if self.evidence_type == "url":
            return (
                f"Fetch URL: {self.location}\n"
                f"Evaluate whether the content satisfies the legal obligation for {self.obligation_id}.\n"
                f"Look for: specific disclosures, policy language, or information required by the article.\n"
                f"The maintainer says: \"{self.description}\""
            )
        elif self.evidence_type == "file":
            return (
                f"Read file: {self.location}\n"
                f"Evaluate whether the content satisfies the legal obligation for {self.obligation_id}.\n"
                f"The maintainer says: \"{self.description}\""
            )
        elif self.evidence_type == "screenshot":
            return (
                f"Screenshot provided — cannot be automatically verified.\n"
                f"Accept as human attestation: \"{self.description}\"\n"
                f"Mark as ATTESTED (unverified) in the report."
            )
        else:  # attestation
            return (
                f"Human attestation — cannot be automatically verified.\n"
                f"Accept as declared: \"{self.description}\"\n"
                f"Mark as ATTESTED (unverified) in the report."
            )

    def to_dict(self) -> dict:
        return {
            "obligation_id": self.obligation_id,
            "evidence_type": self.evidence_type,
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

    @property
    def needs_ai_verification(self) -> list[EvidenceItem]:
        """Items that require AI to fetch/read and verify."""
        return [i for i in self.items if i.requires_ai_verification]

    @property
    def attestation_only(self) -> list[EvidenceItem]:
        """Items accepted on human declaration only."""
        return [i for i in self.items if not i.requires_ai_verification]

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
            "needs_ai_verification": len(self.needs_ai_verification),
            "attestation_only": len(self.attestation_only),
            "items": [i.to_dict() for i in self.items],
        }


def load_evidence(project_path: str) -> ProjectEvidence:
    """
    Load compliance-evidence.json from the project root.

    Returns a ProjectEvidence object. If the file doesn't exist,
    returns an empty ProjectEvidence (no error — evidence is optional).
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

    items = []
    for obligation_id, val in data.get("evidence", {}).items():
        if not isinstance(val, dict):
            continue
        items.append(EvidenceItem(
            obligation_id=obligation_id,
            evidence_type=val.get("type", "attestation"),
            location=val.get("location"),
            description=val.get("description", ""),
            provided_by=val.get("provided_by"),
        ))

    return ProjectEvidence(
        project_path=project_path,
        evidence_file=evidence_path,
        items=items,
    )


def apply_evidence_to_findings(findings: list[dict], evidence: ProjectEvidence) -> list[dict]:
    """
    Annotate scan findings with available evidence.

    Does NOT change compliance levels — that is the AI client's job after verification.
    Adds an 'evidence' key to findings where evidence is declared.

    The AI client reads the evidence, fetches/verifies, then decides the final level.
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
                    f"Maintainer has provided {ev.evidence_type} evidence for this obligation. "
                    f"AI verification {'required' if ev.requires_ai_verification else 'not possible (attestation only)'}."
                )

        annotated.append(finding)

    return annotated
