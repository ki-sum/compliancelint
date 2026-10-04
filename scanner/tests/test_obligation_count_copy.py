"""Obligation / article counts in user-facing text must match the data.

Self-audit A13 (2026-10-02): "247 obligations" was hard-coded in scanner messages, both
READMEs, bin/init.js and the CI workflow (`assert total == 247`, which counts rows — 249
after Regulation (EU) 2026/1744 added ART05-PRO-1ba/1bb, so CI would have failed on push).
The canonical number is the count of unique obligation IDs; three IDs appear in two
obligation files (ART19-OBL-1b, ART19-OBL-2, ART26-OBL-6).
"""
import glob
import json
import os
import re

import pytest

SCANNER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.dirname(SCANNER_ROOT)
KNOWN_DUPLICATE_IDS = {"ART19-OBL-1b", "ART19-OBL-2", "ART26-OBL-6"}


def _rows() -> list[str]:
    ids = []
    for p in glob.glob(os.path.join(SCANNER_ROOT, "obligations", "art*.json")):
        with open(p, encoding="utf-8") as f:
            ids += [o["id"] for o in json.load(f)["obligations"]]
    return ids


def _unique() -> int:
    return len(set(_rows()))


def _articles() -> int:
    # lettered articles (Art 4a, inserted by Reg (EU) 2026/1744) are articles of their own
    return len({re.match(r"ART0*(\d+[a-z]?)-", i).group(1) for i in _rows()})


def test_helper_counts_unique_ids():
    from core.obligation_lookup import unique_obligation_count, article_count
    assert unique_obligation_count() == _unique()
    assert article_count() == _articles()


def test_only_known_ids_are_duplicated():
    rows = _rows()
    dupes = {i for i in rows if rows.count(i) > 1}
    assert dupes == KNOWN_DUPLICATE_IDS


def test_upgrade_hint_uses_derived_counts():
    from core.upgrade_hint import TOOL_HINTS
    msg = TOOL_HINTS["cl_scan_all"]["free_message"]
    assert f"all {_unique()} obligations across {_articles()} articles" in msg


@pytest.mark.parametrize("rel", ["scanner/server.py", "scanner/core/classification_client.py",
                                 "scanner/core/upgrade_hint.py"])
def test_no_hardcoded_count_in_scanner_messages(rel):
    with open(os.path.join(REPO_ROOT, rel), encoding="utf-8") as f:
        assert not re.search(r"\b24\d (atomic )?obligations\b", f.read()), rel


@pytest.mark.parametrize("rel", ["README.md", "scanner/README.md", "bin/init.js"])
def test_static_docs_state_the_data_count(rel):
    with open(os.path.join(REPO_ROOT, rel), encoding="utf-8") as f:
        text = f.read()
    # " " in prose, "_" in the README shields.io badge ("EU_AI_Act-248_obligations")
    stated = {int(n) for n in re.findall(r"\b(\d{3})[ _](?:atomic )?obligations\b", text)}
    assert stated <= {_unique()}, f"{rel} states {sorted(stated)}; data has {_unique()}"
    articles = {int(n) for n in re.findall(r"\b(\d{2}) (?:EU AI Act )?articles\b", text)}
    assert articles <= {_articles()}, f"{rel} states {sorted(articles)} articles; data has {_articles()}"


def test_ci_workflow_does_not_pin_a_row_count():
    with open(os.path.join(REPO_ROOT, ".github", "workflows", "ci.yml"), encoding="utf-8") as f:
        ci = f.read()
    assert "== 247" not in ci
    assert all(i in ci for i in KNOWN_DUPLICATE_IDS)
