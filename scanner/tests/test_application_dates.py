"""Application dates must follow Art. 113 as amended by Regulation (EU) 2026/1744.

Self-audit A9 (2026-10-02): the version tag says consolidated text 02024R1689-20260727, but
the scanner reported the original dates — compliance_summary.applicable_from defaulted to
2026-08-02 for every article, cl_check_updates showed high-risk as "APPROACHING" with negative
days, module explain().enforcement_date said 2026-08-02 for Arts 6-27 and 2025-08-02 for
Arts 91/92 (Chapter IX, general date), and eur_lex_official_url pointed at the original CELEX.
Single source: scanner/data/application_dates.json (generated from the consolidated text).
"""
import glob
import json
import os
import re
from datetime import date

import pytest

from core import application_dates as ad
from core.context import ProjectContext
from core.obligation_lookup import eur_lex_url_for_article

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")


def _scanner_articles() -> list[int]:
    return sorted({int(re.match(r"art0*(\d+)", os.path.basename(p)).group(1))
                   for p in glob.glob(os.path.join(SCANNER_ROOT, "obligations", "art*.json"))})


def _server():
    import server
    return server


# ── data ─────────────────────────────────────────────────────────────────────

def test_table_is_tagged_with_the_consolidated_text():
    assert ad.load()["regulation_text_version"] == "02024R1689-20260727"


@pytest.mark.parametrize("n", _scanner_articles())
def test_every_scanner_article_has_a_date(n):
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", ad.applicable_from(n))


@pytest.mark.parametrize("n,expected", [
    (4, "2025-02-02"), (5, "2025-02-02"),          # Art. 113 (a)
    (9, "2027-12-02"), (26, "2027-12-02"),          # (c)(i) Annex III
    (53, "2025-08-02"),                             # (b) Chapter V
    (50, "2026-08-02"), (43, "2026-08-02"),         # general date (Chapter IV, Chapter III Section 5)
    (91, "2026-08-02"), (92, "2026-08-02"),         # Chapter IX — not listed in (b)
])
def test_known_dates(n, expected):
    assert ad.applicable_from(n) == expected


def test_high_risk_annex_i_date_and_art5_exception():
    assert ad.article(9)["applicable_from_annex_i"] == "2028-08-02"
    exc = ad.article(5)["exceptions"]
    assert [e["applicable_from"] for e in exc] == ["2026-12-02"]
    assert "(ba)" in exc[0]["provisions"] and "(bb)" in exc[0]["provisions"]


# ── module explain() ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("n", _scanner_articles())
def test_module_explain_enforcement_date_matches_table(n):
    server = _server()
    server._ensure_module_loaded(n)
    assert server._modules[n].explain().enforcement_date == ad.applicable_from(n)


# ── compliance_summary ───────────────────────────────────────────────────────

def _summary(n: int, answers: dict, tmp_path) -> dict:
    server = _server()
    ctx = ProjectContext.from_json(json.dumps({"ai_model": "test", f"art{n}": answers}))
    (tmp_path / "app.py").write_text("print('x')")
    return json.loads(server._scan_single_article(n, str(tmp_path), context=ctx))["compliance_summary"]


def test_summary_high_risk_article_reports_both_chapter_iii_dates(tmp_path):
    s = _summary(12, {"has_logging": True, "has_retention_config": True}, tmp_path)
    assert s["applicable_from"] == "2027-12-02"
    assert s["applicable_from_annex_i"] == "2028-08-02"
    assert s["regulation_text_version"] == "02024R1689-20260727"
    assert "2026/1744" in s["regulation"]


def test_summary_art5_reports_ba_bb_exception(tmp_path):
    s = _summary(5, {}, tmp_path)
    assert s["applicable_from"] == "2025-02-02"
    assert s["applicable_from_exceptions"][0]["applicable_from"] == "2026-12-02"


# ── cl_check_updates ─────────────────────────────────────────────────────────

def _updates(monkeypatch, today: date) -> dict:
    server = _server()
    monkeypatch.setattr(ad, "_today", lambda: today)
    monkeypatch.setattr(server, "_check_latest_version", lambda: {"status": "skipped in test"})
    fn = getattr(server.cl_check_updates, "fn", server.cl_check_updates)
    return json.JSONDecoder().raw_decode(fn())[0]


def test_check_updates_statuses_follow_the_clock(monkeypatch):
    out = _updates(monkeypatch, date(2026, 10, 2))
    by_date = {}
    for d in out["upcoming_deadlines"]:
        by_date.setdefault(d["date"], []).append(d)
    assert {d["status"] for d in by_date["2026-08-02"]} == {"APPLICABLE"}
    assert {d["status"] for d in by_date["2026-12-02"]} == {"UPCOMING"}
    assert {d["days_remaining"] for d in by_date["2026-12-02"]} == {61}
    assert {"2027-12-02", "2028-08-02"} <= set(by_date)
    for d in out["upcoming_deadlines"]:
        assert d["status"] in ("APPLICABLE", "UPCOMING"), d
        assert d.get("days_remaining", 0) >= 0, d


def test_check_updates_after_all_dates(monkeypatch):
    out = _updates(monkeypatch, date(2031, 1, 1))
    assert {d["status"] for d in out["upcoming_deadlines"]} == {"APPLICABLE"}


def test_check_updates_names_the_text_version(monkeypatch):
    assert _updates(monkeypatch, date(2026, 10, 2))["regulation_text_version"] == "02024R1689-20260727"


def test_today_tracks_the_real_clock():
    from datetime import datetime, timezone
    assert ad._today() == datetime.now(timezone.utc).date()


# ── EUR-Lex URL ──────────────────────────────────────────────────────────────

def test_eur_lex_url_points_at_the_consolidated_text():
    url = eur_lex_url_for_article(5)
    assert "CELEX:02024R1689-20260727" in url
    assert url.endswith("#art_5")


def test_summary_does_not_promise_standards_by_a_past_date(tmp_path):
    """The checklist note said harmonised standards were 'expected 2026-08-02' — unsourced and past."""
    s = _summary(12, {"has_logging": True, "has_retention_config": True}, tmp_path)
    assert "expected 2026-08-02" not in s["compliance_checklist_note"]


# ── helpers for copy that names a date (Omnibus batch 1, 2026-10-03) ─────────

def test_milestone_date_by_basis():
    assert ad.milestone_date("Art. 111(4)") == "2026-12-02"
    assert ad.milestone_date("Art. 111(2)") == "2030-08-02"
    with pytest.raises(KeyError):
        ad.milestone_date("Art. 999")


def test_chapter_iii_dates_follow_art_113_point_c():
    assert ad.chapter_iii_dates() == {"annex_iii": "2027-12-02", "annex_i": "2028-08-02"}


@pytest.mark.parametrize("iso,text", [("2027-12-02", "2 December 2027"), ("2028-08-02", "2 August 2028"),
                                      ("2030-12-31", "31 December 2030")])
def test_long_date(iso, text):
    assert ad.long_date(iso) == text
