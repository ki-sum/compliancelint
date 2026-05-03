"""Coverage for README:53 'Python 3.10+ is required' claim (C011).

§Y bootstrap pass 2026-05-03 — F-005 mechanical 1-liner test.

Pinning pyproject.toml requires-python field to README claim. If
either drifts, this test fails and forces a sync — preventing the
classic 'README says 3.10 but pyproject silently bumped to 3.11'
class of bug.
"""
import os

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYPROJECT = os.path.join(REPO_ROOT, "pyproject.toml")


def test_pyproject_requires_python_matches_readme_claim_3_10():
    with open(PYPROJECT, "r", encoding="utf-8") as f:
        content = f.read()
    assert 'requires-python = ">=3.10"' in content, (
        "pyproject.toml must declare 'requires-python = \">=3.10\"' to "
        "match README:53 'Python 3.10+ is required'. Either update the "
        "README OR keep pyproject in sync."
    )
