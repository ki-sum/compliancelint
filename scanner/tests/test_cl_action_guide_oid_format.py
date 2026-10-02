"""cl_action_guide must accept every obligation ID the scanner ships.

Regression (found 2026-10-02 during the Omnibus NCII migration): the format
check upper-cased the ID and then matched a lowercase `[a-z]?` suffix, so
every letter-suffixed ID (83 of 246, e.g. ART05-PRO-1a, ART09-OBL-2a, and the
new ART05-PRO-1ba / 1bb) was rejected with "Invalid obligation ID format".
"""
import glob
import json
import os
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402

_INVALID = "Invalid obligation ID format"


def _action_guide(obligation_id: str) -> str:
    fn = getattr(server.cl_action_guide, "fn", server.cl_action_guide)
    return fn(obligation_id)


def _all_obligation_ids() -> list[str]:
    ids = set()
    for path in glob.glob(os.path.join(SCANNER_ROOT, "obligations", "*.json")):
        with open(path, encoding="utf-8") as f:
            ids.update(o["id"] for o in json.load(f)["obligations"])
    return sorted(ids)


def test_every_shipped_obligation_id_passes_format_check():
    rejected = [oid for oid in _all_obligation_ids() if _INVALID in _action_guide(oid)]
    assert rejected == [], f"{len(rejected)} shipped IDs rejected: {rejected[:10]}"


@pytest.mark.parametrize("oid", ["ART05-PRO-1a", "art05-pro-1a", "ART05-PRO-1ba", "ART05-PRO-1bb", "ART09-OBL-2a"])
def test_letter_suffixed_ids_accepted(oid):
    assert _INVALID not in _action_guide(oid)


@pytest.mark.parametrize("oid", ["", "ART5", "ART05-PRO-", "ART05-PRO-1abc", "FOO-BAR-1", "ART05-PRO-1a; DROP"])
def test_malformed_ids_still_rejected(oid):
    assert _INVALID in _action_guide(oid)
