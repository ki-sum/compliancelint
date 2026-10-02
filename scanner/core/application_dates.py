"""Per-article application dates of the EU AI Act (Art. 113 as amended by Regulation (EU) 2026/1744).

Reads scanner/data/application_dates.json, the single source for every date the scanner
reports: compliance_summary.applicable_from, cl_check_updates and module explain().enforcement_date.
The file is generated from the consolidated text's headings and Art. 113; do not edit it by hand.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from functools import lru_cache

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "application_dates.json")


def _today() -> date:
    return datetime.now(timezone.utc).date()


@lru_cache(maxsize=1)
def load() -> dict:
    with open(_PATH, encoding="utf-8") as f:
        return json.load(f)


def article(article_number: int) -> dict:
    return load()["articles"][str(article_number)]


def applicable_from(article_number: int) -> str:
    return article(article_number)["applicable_from"]


def regulation_text_version() -> str:
    return load()["regulation_text_version"]


def eur_lex_url() -> str:
    return load()["eur_lex_url"]


def milestones_status() -> list[dict]:
    """Every Art. 113 / Art. 111 milestone with APPLICABLE / UPCOMING (+ days_remaining) as of today."""
    today = _today()
    out = []
    for m in load()["milestones"]:
        entry = dict(m)
        days = (date.fromisoformat(m["date"]) - today).days
        if days > 0:
            entry.update(status="UPCOMING", days_remaining=days)
        else:
            entry["status"] = "APPLICABLE"
        out.append(entry)
    return out
