"""Coverage for Directory v2 .gitignore contract (dimensions.md:1466).

§Y bootstrap pass 2026-05-03 — F-005 mechanical 1-liner test for
README claims C120 ("Scan cache lives in .compliancelint/local/ and
is gitignored") + C121 ("Only evidence and .compliancelintrc project
binding are committed").

The Directory v2 split (2026-04-24) requires:
  - .compliancelint/local/ MUST be gitignored (cache, regeneratable)
  - .compliancelint/evidence/ MUST NOT be gitignored (audit trail)
  - .compliancelintrc IS the binding file (committed by user choice;
    public .gitignore lists it under Private section because the public
    repo doesn't itself bind to a SaaS instance)
"""
import os

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
GITIGNORE = os.path.join(REPO_ROOT, ".gitignore")


def _read_gitignore() -> str:
    with open(GITIGNORE, "r", encoding="utf-8") as f:
        return f.read()


def test_gitignore_excludes_compliancelint_local():
    """C120 — local/ cache is gitignored."""
    content = _read_gitignore()
    assert ".compliancelint/local/" in content, (
        ".gitignore must list '.compliancelint/local/' to keep scan "
        "cache out of git per Directory v2 split (dimensions.md:1466)."
    )


def test_gitignore_does_not_exclude_compliancelint_evidence():
    """C121 — evidence/ is the committed audit trail; MUST NOT be gitignored."""
    content = _read_gitignore()
    # Specifically: the path '.compliancelint/evidence/' must not be a
    # standalone ignore entry. (We allow .compliancelint/local/ which
    # is a sibling directory.)
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        assert stripped != ".compliancelint/evidence/", (
            ".compliancelint/evidence/ must be COMMITTED — it's the "
            "regulator-facing audit trail. Found a gitignore entry "
            "excluding it. See dimensions.md:1498."
        )
        assert stripped != ".compliancelint/", (
            "A blanket .compliancelint/ ignore would also exclude "
            "evidence/. Use .compliancelint/local/ specifically."
        )


def test_gitignore_treats_compliancelintrc_per_section_intent():
    """C121 — .compliancelintrc handling. In the public repo it's
    listed under the Private section comment; what matters is that it
    is NOT under the Runtime section that would conflict with the
    'binding file is per-clone user choice' contract."""
    content = _read_gitignore()
    assert ".compliancelintrc" in content, (
        ".gitignore should reference .compliancelintrc (per public-repo "
        "convention — the SaaS binding is per-clone, not committed in "
        "the public scanner repo itself)."
    )
