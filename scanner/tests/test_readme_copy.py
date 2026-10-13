"""Facts stated in the README files follow the data (2026-10-12).

Three statements had gone stale because they were typed in:
  - the application dates still described Regulation (EU) 2026/1744 as a provisional political agreement and put
    Art. 99 under 2025-02-02 (Chapter XII applies from 2025-08-02);
  - the coverage table listed 8 obligations for Art. 5 (10 since Art. 5(1)(ba)/(bb)) and 3 for Art. 111 (4);
  - scanner/README.md said "14 tools".
The dates come from scanner/data/application_dates.json, the table from the obligation files, the tool count from
the @mcp.tool functions in server.py.
"""
import glob
import json
import os
import re

import pytest

SCANNER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.dirname(SCANNER_ROOT)


def _read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), encoding="utf-8") as f:
        return f.read()


# ── Application dates ──

README_DATES = ("2025-02-02", "2025-08-02", "2026-08-02", "2026-12-02", "2027-12-02", "2028-08-02")


def _milestones() -> dict[str, list[str]]:
    with open(os.path.join(SCANNER_ROOT, "data", "application_dates.json"), encoding="utf-8") as f:
        by_date: dict[str, list[str]] = {}
        for m in json.load(f)["milestones"]:
            by_date.setdefault(m["date"], []).append(m["event"])
    return by_date


def _readme_dates_block() -> str:
    text = _read("README.md")
    start = text.index("> **EU AI Act application dates**")
    end = text.index("> Track current status in-app", start)
    return text[start:end]


def test_readme_names_the_amending_regulation_in_the_dates_heading():
    heading = _readme_dates_block().splitlines()[0]
    assert "Regulation (EU) 2024/1689 as amended by Regulation (EU) 2026/1744" in heading
    assert "consolidated text of 2026-07-27" in heading


@pytest.mark.parametrize("day", README_DATES)
def test_readme_application_date_states_what_application_dates_json_states(day):
    lines = [ln for ln in _readme_dates_block().splitlines() if ln.startswith(f"> - **{day}** — ")]
    assert len(lines) == 1, f"expected one README line for {day}, found {len(lines)}"
    stated = lines[0][len(f"> - **{day}** — "):].strip()
    assert stated == "; ".join(_milestones()[day])


def test_readme_dates_block_lists_no_other_date_line():
    days = re.findall(r"^> - \*\*(\d{4}-\d{2}-\d{2})\*\*", _readme_dates_block(), flags=re.MULTILINE)
    assert tuple(days) == README_DATES


def test_readme_does_not_call_the_amending_regulation_pending():
    text = _read("README.md")
    for stale in ("political agreement", "Provisional pending formal adoption", "the original timeline applies",
                  "Art. 99 penalty regime in force"):
        assert stale not in text, stale


# ── Coverage table ──

def _rows_per_article() -> dict[str, int]:
    """Obligation records per obligation file, keyed like the README table ("5", "4a", "111")."""
    out: dict[str, int] = {}
    for p in glob.glob(os.path.join(SCANNER_ROOT, "obligations", "art*.json")):
        key = re.match(r"art0*(\d+[a-z]?)-", os.path.basename(p)).group(1)
        with open(p, encoding="utf-8") as f:
            out[key] = len(json.load(f)["obligations"])
    return out


def _readme_table() -> dict[str, int]:
    return {
        m.group(1): int(m.group(2))
        for m in re.finditer(r"^\| Art\. (\d+[a-z]?) \| [^|]+ \| (\d+) \|$", _read("README.md"), flags=re.MULTILINE)
    }


def test_readme_coverage_table_has_a_row_for_every_obligation_file():
    assert set(_readme_table()) == set(_rows_per_article())


@pytest.mark.parametrize("article", sorted(_rows_per_article(), key=lambda k: (int(re.match(r"\d+", k).group()), k)))
def test_readme_coverage_table_count_is_the_number_of_records_in_the_file(article):
    assert _readme_table().get(article) == _rows_per_article()[article]


def test_readme_explains_why_the_table_sums_to_more_than_the_obligation_count():
    rows = sum(_rows_per_article().values())
    unique = len({o["id"] for p in glob.glob(os.path.join(SCANNER_ROOT, "obligations", "art*.json"))
                  for o in json.load(open(p, encoding="utf-8"))["obligations"]})
    assert rows > unique
    assert sum(_readme_table().values()) == rows
    assert f"The table has {rows} rows for {unique} obligations" in _read("README.md")


# ── Tool count ──

@pytest.mark.parametrize("rel", ["README.md", "scanner/README.md", "bin/README.md", "docs/user-guide.md"])
def test_docs_state_no_tool_count_other_than_the_registered_tools(rel):
    with open(os.path.join(SCANNER_ROOT, "server.py"), encoding="utf-8") as f:
        registered = len(re.findall(r"^@mcp\.tool\(", f.read(), flags=re.MULTILINE))
    stated = {int(n) for n in re.findall(r"\b(\d+) (?:MCP )?tools\b", _read(rel))}
    assert stated <= {registered}, f"{rel} states {sorted(stated)} tools; server.py registers {registered}"


# ── Scan progress in the user guide ──

def test_user_guide_counts_scanned_articles_as_the_scan_modules():
    modules = len([d for d in os.listdir(os.path.join(SCANNER_ROOT, "modules")) if re.match(r"art\d+[a-z]?-", d)])
    guide = _read("docs/user-guide.md")
    stated = {int(n) for n in re.findall(r"\b(\d{2}) scanned articles\b", guide)} | {
        int(n) for n in re.findall(r"\(\d+/(\d{2})\)", guide)}
    assert stated == {modules}
    assert "Low-risk classification" not in guide


# ── Claims about where the code goes, review time saved, and the licence (founder decisions 2026-10-12) ──
# An audit of the demo videos found "your code never leaves your machine" too broad: the code is read by the AI
# assistant the developer already uses, which may be a cloud service. What ComplianceLint can state is its own part.
# "~70 % review time" had no measurement behind it. package.json declared Apache-2.0 for a BSL 1.1 project.

USER_VISIBLE_TEXT_FILES = ("README.md", "scanner/server.py", "scanner/core/upgrade_hint.py", "bin/init.js",
                           "docs/user-guide.md", "scanner/README.md")


@pytest.mark.parametrize("rel", USER_VISIBLE_TEXT_FILES)
def test_no_claim_that_code_never_leaves_the_machine(rel):
    text = _read(rel)
    for claim in ("never leaves your machine", "never leaves the machine", "never leaves the developer's machine",
                  "Code stays local", "stays on your machine"):
        assert claim not in text, f"{rel}: {claim!r}"


def test_readme_states_what_compliancelint_receives():
    readme = _read("README.md")
    assert "ComplianceLint never receives your code" in readme


@pytest.mark.parametrize("rel", USER_VISIBLE_TEXT_FILES)
def test_no_unmeasured_review_time_figure(rel):
    assert "70%" not in _read(rel), rel


def test_npm_package_declares_the_project_licence():
    licence_file = _read("LICENSE")
    assert licence_file.lstrip().startswith("Business Source License 1.1")
    assert json.loads(_read("package.json"))["license"] == "BUSL-1.1"  # SPDX identifier of the Business Source License 1.1
    assert 'license = {text = "BSL-1.1"}' in _read("pyproject.toml")


def test_readme_makes_no_unmeasured_false_positive_claim():
    # Founder decision 2026-10-13: "near zero" false positives was never measured; the comparison stays qualitative.
    readme = _read("README.md")
    assert "near zero" not in readme.lower()
    assert "| **False positives** | Keyword matching → many | AI understands context → fewer than keyword matching |" in readme


# ── What the headline number counts (founder decision 2026-10-13) ──
# "255 obligations" stays the headline number. The records behind it are obligations and prohibitions plus the
# provisions that decide whether and how those apply; the README says so once, with numbers counted from the files.

def _record_breakdown() -> dict:
    seen = {}
    for path in glob.glob(os.path.join(SCANNER_ROOT, "obligations", "*.json")):
        with open(path, encoding="utf-8") as f:
            for o in json.load(f).get("obligations", []):
                seen[o["id"]] = o
    records = list(seen.values())
    obligations = sum(1 for r in records if r["deontic_type"] == "obligation")
    prohibitions = sum(1 for r in records if r["deontic_type"] == "prohibition")
    return {
        "total": len(records),
        "obligations": obligations,
        "prohibitions": prohibitions,
        "related": len(records) - obligations - prohibitions,
        "upstream": sum(1 for r in records if r["addressee"] in ("commission", "ai_office", "notified_bodies")),
    }


def test_readme_says_what_the_headline_number_counts():
    b = _record_breakdown()
    assert b["obligations"] + b["prohibitions"] + b["related"] == b["total"]
    sentence = (
        f"The {b['total']} are {b['obligations']} obligations and {b['prohibitions']} prohibitions, plus "
        f"{b['related']} related provisions that decide whether and how they apply: permissions, exceptions, "
        f"classification rules and similar clauses. {b['upstream']} of them are addressed to the Commission or to "
        "notified bodies and never appear as your tasks."
    )
    assert sentence in _read("README.md")
