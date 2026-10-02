"""Interim standard IDs must match their version, and scans must report the real one.

Self-audit A16 (2026-10-02): Art 5's interim standard said standard_id "CL-IS-ART05-v0.1"
with version "0.2.0"; compliance_summary.compliance_checklist_version was hard-coded to
"CL-IS-ARTnn-v0.1" for every article, including the 19 that have no interim standard.
"""
import glob
import json
import os
import re

import pytest

from core.context import ProjectContext

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
STANDARDS = sorted(glob.glob(os.path.join(SCANNER_ROOT, "modules", "art*", "interim-standard.json")))


@pytest.mark.parametrize("path", STANDARDS, ids=lambda p: os.path.basename(os.path.dirname(p)))
def test_standard_id_matches_version(path):
    with open(path, encoding="utf-8") as f:
        md = json.load(f)["_metadata"]
    major, minor = md["version"].split(".")[:2]
    assert md["standard_id"].endswith(f"-v{major}.{minor}"), (md["standard_id"], md["version"])


def _summary(n, tmp_path):
    import server
    ctx = ProjectContext.from_json(json.dumps({"ai_model": "t", f"art{n}": {}}))
    (tmp_path / "a.py").write_text("x = 1")
    return json.loads(server._scan_single_article(n, str(tmp_path), context=ctx))["compliance_summary"]


def test_summary_reports_the_modules_standard_id(tmp_path):
    with open(os.path.join(SCANNER_ROOT, "modules", "art05-prohibited-practices", "interim-standard.json"),
              encoding="utf-8") as f:
        sid = json.load(f)["_metadata"]["standard_id"]
    assert _summary(5, tmp_path)["compliance_checklist_version"] == sid


def test_summary_has_no_checklist_version_without_a_standard(tmp_path):
    with_std = {int(re.match(r"art0*(\d+)", os.path.basename(os.path.dirname(p))).group(1)) for p in STANDARDS}
    without = sorted({4, 8, 16, 18, 20, 21, 22, 23, 24, 25, 41, 51, 52, 60, 61, 71, 80, 82, 91, 92, 111} - with_std)
    assert without, "expected at least one article without an interim standard"
    assert _summary(without[0], tmp_path)["compliance_checklist_version"] is None
