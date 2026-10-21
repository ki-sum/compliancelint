"""Harmonised standards and the instruments each article waits for — legal review of 2026-10-21.

EN 18286:2026 is the first harmonised standard whose reference is published in the Official Journal under the AI Act:
Commission Implementing Decision (EU) 2026/2274 of 12 October 2026, OJ L 2026/2274, 14.10.2026 (CELEX 32026D2274),
in force on publication. Before, the scanner said "prEN 18286 — Public Enquiry phase, expected Q4 2026" (EU AI Act
Newsletter #113). The other "waiting_for" texts promised "CEN-CENELEC harmonized standard ... (expected Q4 2026 /
2027)" for 40 articles, also where no standard is requested (importers, deployers, Art. 50, GPAI ...); the
action-plan disclaimers said standards "may modify these requirements". The review replaced all of them; the texts live in
core/harmonised_standards.py.
"""
import json
import os
import re
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402
from core import harmonised_standards as hs  # noqa: E402

OBLIGATIONS = os.path.join(SCANNER_ROOT, "obligations")
MODULES = os.path.join(SCANNER_ROOT, "modules")
STALE = re.compile(r"expected (Q4 )?20(26|27)|may modify (these )?(requirements|criteria)|Public Enquiry", re.I)


def _load(raw: str) -> dict:
    obj, _ = json.JSONDecoder().raw_decode(raw)
    return obj


def _explain(article: int) -> dict:
    return json.loads(server.cl_explain(regulation="eu-ai-act", article=article))


def _json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _module_dirs() -> dict[int, str]:
    out = {}
    for name in os.listdir(MODULES):
        m = re.match(r"art(\d+)-", name)
        if m and os.path.isdir(os.path.join(MODULES, name)):
            out[int(m.group(1))] = name
    return out


def _obligation_files() -> list[str]:
    return sorted(f for f in os.listdir(OBLIGATIONS) if f.endswith(".json"))


# ── the record ────────────────────────────────────────────────────────


def test_cited_standard_record_matches_the_decision():
    cited = hs.cited_for_article(17)
    assert len(cited) == 1
    std = cited[0]
    assert std["reference"] == "EN 18286:2026"
    assert std["title"] == "Artificial intelligence — Quality management system for EU AI Act regulatory purposes"
    assert std["implementing_decision"] == "Commission Implementing Decision (EU) 2026/2274"
    assert std["celex"] == "32026D2274"
    assert std["oj_citation"] == "OJ L 2026/2274, 14.10.2026"
    assert std["published_on"] == "14 October 2026"
    assert std["presumption_from"] == "2026-10-14"
    assert hs.cited_for_article(9) == []
    assert hs.cited_for_article(72) == []  # Annex ZA not read — no presumption stated for Art. 72


def test_review_texts_for_articles_16_and_17():
    assert hs.standard_status(17) == (
        "A harmonised standard supporting Article 17 is now cited. The reference of EN 18286:2026, Artificial "
        "intelligence — Quality management system for EU AI Act regulatory purposes, was published in the Official "
        "Journal of the European Union on 14 October 2026 by Commission Implementing Decision (EU) 2026/2274. The "
        "European Commission states that providers implementing EN 18286:2026 benefit from a presumption of "
        "conformity with the Article 17 requirements covered by the standard. The exact coverage is determined by "
        "the standard, in particular Annex ZA, which ComplianceLint has not reviewed."
    )
    assert hs.standard_status(16).startswith(
        "Harmonised standards and European standardisation deliverables supporting the Chapter III, Section 2 "
        "requirements are being developed by CEN and CENELEC under Commission Implementing Decision C(2025) 3871.")
    assert "Article 16(c) through Article 17" in hs.standard_status(16)


def test_requested_areas_name_their_annex_point():
    expected = {9: "point 1", 10: "point 2", 12: "point 3", 13: "point 4", 14: "point 5", 15: "points 6 to 8",
                43: "point 10"}
    for art, point in expected.items():
        text = hs.standard_status(art)
        assert f"C(2025) 3871, Annex I, {point}" in text, art
        assert "No official date" in text, art


def test_status_texts_are_formal_and_free_of_reviewer_remarks():
    for art, text in hs.STANDARD_STATUS.items():
        assert not STALE.search(text), art
        assert not re.search(r"\bI did not\b|in this review|\bOJ\b|\bArt\. \d", text), art
        assert "Official Journal" not in text or "Official Journal of the European Union" in text, art


# ── what users see ────────────────────────────────────────────────────


def test_every_module_waiting_for_uses_the_central_text():
    server._ensure_all_modules_loaded()
    assert set(hs.STANDARD_STATUS) <= set(server._modules)
    for art in server._modules:
        waiting = _explain(art)["waiting_for"]
        assert not STALE.search(waiting), (art, waiting)
        if art in hs.STANDARD_STATUS:
            assert waiting == hs.standard_status(art), art


def test_check_updates_reports_en18286_as_cited():
    resp = _load(server.cl_check_updates())
    entries = [s for s in resp["standards_status"] if "18286" in s["standard"]]
    assert len(entries) == 1
    entry = entries[0]
    assert "prEN" not in json.dumps(entry) and "expected" not in entry
    assert entry["standard"] == (
        "EN 18286:2026 — Artificial intelligence — Quality management system for EU AI Act regulatory purposes")
    assert entry["status"] == (
        "Harmonised standard: its reference was published in the Official Journal of the European Union on 14 "
        "October 2026 by Commission Implementing Decision (EU) 2026/2274. The European Commission states that "
        "providers implementing EN 18286:2026 benefit from a presumption of conformity with the Article 17 "
        "requirements covered by the standard. The exact scope is determined by the standard, in particular "
        "Annex ZA.")
    assert entry["presumption_of_conformity_from"] == "2026-10-14"


def test_interim_standard_payloads():
    p17 = _load(server.cl_interim_standard(17))
    assert p17["is_official_standard"] is False
    assert [s["reference"] for s in p17["official_harmonised_standards"]] == ["EN 18286:2026"]
    assert p17["superseded_when"] == hs.standard_status(17)
    assert p17["_metadata"]["disclaimer"] == hs.interim_checklist_disclaimer(17)
    p12 = _load(server.cl_interim_standard(12))
    assert p12["official_harmonised_standards"] == []
    assert p12["superseded_when"] == hs.standard_status(12)


@pytest.mark.parametrize("art,name", sorted(_module_dirs().items()))
def test_interim_standard_files(art, name):
    path = os.path.join(MODULES, name, "interim-standard.json")
    if not os.path.exists(path):
        pytest.skip("no interim standard")
    md = _json(path)["_metadata"]
    assert not STALE.search(json.dumps(md, ensure_ascii=False)), art
    if art in hs.STANDARD_STATUS:
        assert md["disclaimer"] == hs.interim_checklist_disclaimer(art), art
        assert md["awaiting_standard"] == hs.standard_status(art), art


def test_action_plan_disclaimers():
    assert hs.ACTION_PLAN_DISCLAIMER.startswith(
        "This action plan is based on the ComplianceLint compliance checklist and good practice; it is not a "
        "harmonised standard and does not itself give a presumption of conformity.")
    from core.protocol import ComplianceLevel, Confidence, ScanResult

    server._ensure_all_modules_loaded()
    for art, mod in server._modules.items():
        result = ScanResult(
            article_number=art, article_title=mod.article_title, project_path="/tmp/test",
            scan_date="2026-10-21T00:00:00+00:00", files_scanned=0, language_detected="python",
            overall_level=ComplianceLevel.NON_COMPLIANT, overall_confidence=Confidence.HIGH, details={},
        )
        plan = mod.action_plan(result)
        assert not STALE.search(plan.disclaimer or ""), (art, plan.disclaimer)


def test_action_plan_response_carries_the_review_disclaimer(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')")
    resp = _load(server.cl_action_plan(project_path=str(tmp_path), article=12))
    assert resp["disclaimer"].startswith(hs.ACTION_PLAN_DISCLAIMER)


def test_art17_action_plan_mentions_en18286():
    from core.protocol import ComplianceLevel, Confidence, ScanResult

    server._ensure_module_loaded(17)
    result = ScanResult(
        article_number=17, article_title="Quality Management System", project_path="/tmp/test",
        scan_date="2026-10-21T00:00:00+00:00", files_scanned=0, language_detected="python",
        overall_level=ComplianceLevel.NON_COMPLIANT, overall_confidence=Confidence.HIGH,
        details={"has_qms_documentation": False},
    )
    qms = [a for a in server._modules[17].action_plan(result).actions if a.article == "Art. 17(1)"][0]
    assert "EN 18286:2026" in qms.details
    assert "Official Journal of the European Union on 14 October 2026" in qms.details


# ── obligation files ──────────────────────────────────────────────────


@pytest.mark.parametrize("fname", _obligation_files())
def test_obligation_related_standards(fname):
    std = _json(os.path.join(OBLIGATIONS, fname)).get("_metadata", {}).get("related_standards")
    if not std:
        pytest.skip("no related_standards")
    assert not STALE.search(json.dumps(std, ensure_ascii=False)), fname
    assert not any("CEN-CENELEC guidance on prohibited practice" in s for s in std.get("upcoming", [])), fname


def test_obligation_related_standards_named():
    s17 = _json(os.path.join(OBLIGATIONS, "art17-quality-management.json"))["_metadata"]["related_standards"]
    assert any(s.startswith("EN 18286:2026") for s in s17["published"])
    s05 = _json(os.path.join(OBLIGATIONS, "art05-prohibited-practices.json"))["_metadata"]["related_standards"]
    assert any("C(2025) 884" in s for s in s05["published"])
    s09 = _json(os.path.join(OBLIGATIONS, "art09-risk-management.json"))["_metadata"]["related_standards"]
    assert any("C(2025) 3871" in s for s in s09["upcoming"])


def test_no_stale_dates_left_in_scanner_sources():
    hits = []
    for root, _dirs, files in os.walk(SCANNER_ROOT):
        if os.sep + "tests" in root or "__pycache__" in root:
            continue
        for f in files:
            if f.endswith((".py", ".json")):
                with open(os.path.join(root, f), encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if re.search(r"expected (Q4 )?20(26|27)\)|\(expected Q4 2026\)", line):
                            hits.append(f"{os.path.relpath(os.path.join(root, f), SCANNER_ROOT)}:{i}")
    assert hits == []
