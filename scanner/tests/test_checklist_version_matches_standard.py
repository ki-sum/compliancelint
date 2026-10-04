"""The checklist version named in a module's explain() text must be the version of its interim standard.

Found 2026-10-04 (Omnibus batch-3 self-review): the interim standards of Art 4, 6, 27, 43 and 50 were bumped to
v0.2 while `compliance_checklist_summary` still said "Compliance Checklist v0.1".
"""
import glob
import json
import os
import re

import pytest

MODULES = os.path.join(os.path.dirname(__file__), "..", "modules")
WITH_STANDARD = sorted(os.path.basename(os.path.dirname(p))
                       for p in glob.glob(os.path.join(MODULES, "*", "interim-standard.json")))


def test_modules_with_a_standard_are_found():
    assert len(WITH_STANDARD) >= 25 and "art43-conformity-assessment" in WITH_STANDARD


@pytest.mark.parametrize("module", WITH_STANDARD)
def test_checklist_version_in_module_text_matches_standard(module):
    with open(os.path.join(MODULES, module, "interim-standard.json"), encoding="utf-8") as f:
        standard_id = json.load(f)["_metadata"]["standard_id"]
    version = re.search(r"-v(\d+\.\d+)$", standard_id).group(1)
    with open(os.path.join(MODULES, module, "module.py"), encoding="utf-8") as f:
        named = set(re.findall(r"Compliance Checklist v(\d+\.\d+)", f.read()))
    assert named <= {version}, f"{module}: module text names v{sorted(named)}, standard is {standard_id}"
