"""Directory v2 path helpers — ephemeral `local/` vs committed `evidence/`.

Central source of truth for every path under `.compliancelint/`. Split into
two halves:

  .compliancelint/local/      ← gitignored ephemeral cache + tool state
      state.json              ← merged view (regenerated)
      articles/artN.json      ← per-article scan cache
      baselines/*.json        ← local history snapshots (max 20)
      metadata.json           ← repo_id + ai_provider cache
      project.json            ← UUID fallback for project_id
      reports/                ← generated reports

  .compliancelint/evidence/   ← committed audit trail
      {findingId}/manifest.json
      {findingId}/{original-filename}

Only log data lives outside the project at ~/.compliancelint/logs/{hash}/
(see scanner/core/scanner_log.py — separate module, intentionally isolated
from BUG-1).

Keep this module dependency-free — nothing in here should import anything
else from scanner/ (state.py / pending_evidence.py / server.py all call it).
"""
from __future__ import annotations

import os
from pathlib import Path


_ROOT_DIR = ".compliancelint"
_LOCAL_DIR = "local"
_EVIDENCE_DIR = "evidence"
_ARTICLES_DIR = "articles"
_BASELINES_DIR = "baselines"
_REPORTS_DIR = "reports"


def root_dir(project_path: str) -> Path:
    """`<project>/.compliancelint/` — the top-level compliance dir."""
    return Path(project_path) / _ROOT_DIR


def local_dir(project_path: str) -> Path:
    """`<project>/.compliancelint/local/` — ephemeral, gitignored."""
    return root_dir(project_path) / _LOCAL_DIR


def evidence_dir(project_path: str) -> Path:
    """`<project>/.compliancelint/evidence/` — committed audit trail."""
    return root_dir(project_path) / _EVIDENCE_DIR


def state_file(project_path: str) -> Path:
    return local_dir(project_path) / "state.json"


def metadata_file(project_path: str) -> Path:
    return local_dir(project_path) / "metadata.json"


def project_file(project_path: str) -> Path:
    return local_dir(project_path) / "project.json"


def articles_dir(project_path: str) -> Path:
    return local_dir(project_path) / _ARTICLES_DIR


def article_file(project_path: str, article_number: int) -> Path:
    return articles_dir(project_path) / f"art{article_number}.json"


def baselines_dir(project_path: str) -> Path:
    return local_dir(project_path) / _BASELINES_DIR


def reports_dir(project_path: str) -> Path:
    return local_dir(project_path) / _REPORTS_DIR


def evidence_finding_dir(project_path: str, finding_id: str) -> Path:
    return evidence_dir(project_path) / finding_id


def evidence_manifest_file(project_path: str, finding_id: str) -> Path:
    return evidence_finding_dir(project_path, finding_id) / "manifest.json"


# ── String helpers for os.path.join callers still using strings ──────────────
# state.py / server.py / pending_evidence.py contain os.path.join calls that
# expect strings. Exposing str variants avoids sprinkling str(Path(...)) at
# every call site.

def local_dir_str(project_path: str) -> str:
    return str(local_dir(project_path))


def evidence_dir_str(project_path: str) -> str:
    return str(evidence_dir(project_path))


def metadata_file_str(project_path: str) -> str:
    return str(metadata_file(project_path))


def project_file_str(project_path: str) -> str:
    return str(project_file(project_path))


def state_file_str(project_path: str) -> str:
    return str(state_file(project_path))


def articles_dir_str(project_path: str) -> str:
    return str(articles_dir(project_path))


def ensure_local_dir(project_path: str) -> str:
    """Create `local/` if missing. Returns the directory as a string."""
    path = local_dir(project_path)
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def ensure_evidence_dir(project_path: str) -> str:
    """Create `evidence/` if missing. Returns the directory as a string."""
    path = evidence_dir(project_path)
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
