"""Every runtime JSON under scanner/ must be shipped in the PyPI wheel.

Regression for the 2026-10-02 finding (NCII migration gap-analysis): the
wheel built from pyproject.toml omitted scanner/data/*.json (Recitals) and
scanner/interpretive-materials/*.json (C(2026) 5054 Layer 2). Both loaders
fall back to empty data with only a log warning, so pip-installed users
silently lost those features.
"""
import fnmatch
import os
import re

SCANNER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYPROJECT = os.path.join(SCANNER_DIR, "..", "pyproject.toml")
# Not runtime data: test fixtures and local scan state.
_EXCLUDED_TOP_DIRS = {"tests", ".compliancelint", "__pycache__"}


def _package_data_globs() -> list[str]:
    # tomllib is 3.11+ and CI also runs 3.10, so read the one list we need directly.
    with open(PYPROJECT, encoding="utf-8") as f:
        text = f.read()
    section = text.split("[tool.setuptools.package-data]", 1)[1]
    block = re.search(r"^scanner\s*=\s*\[(.*?)\]", section, re.S | re.M)
    assert block, "scanner package-data list not found in pyproject.toml"
    return re.findall(r'"([^"]+)"', block.group(1))


def _matches(rel_path: str, pattern: str) -> bool:
    if "**/" in pattern:
        head, tail = pattern.split("**/", 1)
        if not rel_path.startswith(head):
            return False
        rest = rel_path[len(head):]
        parts = rest.split("/")
        return any(fnmatch.fnmatch("/".join(parts[i:]), tail) for i in range(len(parts)))
    return fnmatch.fnmatch(rel_path, pattern) and rel_path.count("/") == pattern.count("/")


def _runtime_json_files() -> list[str]:
    found = []
    for root, dirs, files in os.walk(SCANNER_DIR):
        rel_root = os.path.relpath(root, SCANNER_DIR).replace(os.sep, "/")
        top = rel_root.split("/")[0]
        if top in _EXCLUDED_TOP_DIRS or "__pycache__" in rel_root or "/tests" in f"/{rel_root}":
            dirs[:] = []
            continue
        for name in files:
            if name.endswith(".json"):
                found.append(name if rel_root == "." else f"{rel_root}/{name}")
    return sorted(found)


def test_runtime_json_files_found():
    files = _runtime_json_files()
    assert "data/recitals.json" in files
    assert "obligations/art05-prohibited-practices.json" in files


def test_every_runtime_json_is_in_package_data():
    globs = _package_data_globs()
    missing = [f for f in _runtime_json_files() if not any(_matches(f, g) for g in globs)]
    assert missing == [], f"not shipped in the wheel (add to [tool.setuptools.package-data]): {missing}"


def test_known_runtime_files_are_covered():
    globs = _package_data_globs()
    for rel in ("data/recitals.json", "data/article_recital_index.json", "data/_versions.json",
                "interpretive-materials/C2026-5054-art50-guidelines-2026-07-20.json",
                "modules/art05-prohibited-practices/interim-standard.json"):
        assert any(_matches(rel, g) for g in globs), rel
