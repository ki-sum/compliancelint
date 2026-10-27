"""Every requirement of an interim standard (modules/*/interim-standard.json, served by cl_interim_standard and copied
to the dashboard) refers to an obligation that exists in scanner/obligations/.

Found 2026-10-27: IS-ART10-R05 (data set separation, an Art. 10(3) quality point) referred to ART10-OBL-5, which does
not exist: Art. 10(5) was deleted by Regulation (EU) 2026/1744 and its content moved to Art. 4a(1). An assistant that
reads the checklist could cite the deleted paragraph.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
OBLIGATION_IDS = {
    o["id"]
    for f in (ROOT / "obligations").glob("*.json")
    for o in json.loads(f.read_text(encoding="utf-8")).get("obligations", [])
    if isinstance(o, dict) and "id" in o
}
STANDARDS = sorted((ROOT / "modules").glob("*/interim-standard.json"))


def _refs(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    for req in data.get("requirements", []):
        ref = req.get("obligation_ref")
        if ref:
            for one in (ref if isinstance(ref, list) else [ref]):
                yield req.get("id"), one


def test_the_obligation_list_is_loaded():
    assert len(OBLIGATION_IDS) > 200
    assert len(STANDARDS) > 15


@pytest.mark.parametrize("path", STANDARDS, ids=lambda p: p.parent.name)
def test_every_interim_requirement_refers_to_an_existing_obligation(path):
    missing = [(req, ref) for req, ref in _refs(path) if ref not in OBLIGATION_IDS]
    assert missing == [], missing


# Independent legal check of 2026-10-27, cross-checked the same day: the 27 refs that did not exist and 13 that
# pointed to an unrelated obligation of the same article. IS-ART11-R06 (changes through the lifecycle) is Annex IV(6),
# which Art. 11(1) makes part of the technical documentation, as well as Art. 11(1) "kept up-to date".
EXPECTED = {
    "IS-ART10-R03": ["ART10-OBL-2f", "ART10-OBL-2g"],
    "IS-ART10-R04": "ART10-OBL-2",
    "IS-ART10-R05": ["ART10-OBL-1", "ART10-OBL-3"],
    "IS-ART10-R06": "ART15-OBL-4b",
    "IS-ART11-R02": "ART11-OBL-1c",
    "IS-ART11-R03": "ART11-OBL-1c",
    "IS-ART11-R04": "ART11-OBL-1c",
    "IS-ART11-R05": "ART11-OBL-1c",
    "IS-ART11-R06": ["ART11-OBL-1c", "ART11-OBL-1"],
    "IS-ART11-R07": "ART11-OBL-1c",
    "IS-ART13-R01": "ART13-OBL-2",
    "IS-ART13-R02": "ART13-OBL-1",
    "IS-ART13-R04": "ART13-OBL-3",
    "IS-ART13-R05": "ART13-OBL-3",
    "IS-ART13-R06": "ART13-OBL-3",
    "IS-ART14-R02": "ART14-OBL-4",
    "IS-ART14-R03": "ART14-OBL-4",
    "IS-ART14-R05": "ART14-OBL-4",
    "IS-ART14-R06": "ART14-OBL-4",
    "IS-ART14-R07": "ART14-OBL-5",
    "IS-ART15-R02": ["ART15-OBL-1", "ART15-OBL-4"],
    "IS-ART15-R03": "ART15-OBL-4",
    "IS-ART15-R06": "ART15-OBL-5",
    "IS-ART15-R07": "ART15-OBL-5",
    "IS-ART15-R08": "ART15-OBL-5b",
    "IS-ART15-R09": "ART15-PERM-4c",
    "IS-ART17-R02": ["ART17-OBL-1c", "ART17-OBL-1d"],
    "IS-ART51-R01": "ART51-CLS-2",
    "IS-ART51-R02": "ART51-CLS-1",
    "IS-ART51-R03": "ART51-CLS-1",
    "IS-ART52-R02": "ART52-OBL-1",
    "IS-ART52-R03": "ART52-PERM-2",
    "IS-ART53-R01": "ART53-OBL-1a",
    "IS-ART53-R02": "ART53-OBL-1b",
    "IS-ART53-R03": "ART53-OBL-1c",
    "IS-ART53-R04": "ART53-OBL-1d",
    "IS-ART55-R01": "ART55-OBL-1a",
    "IS-ART55-R02": "ART55-OBL-1b",
    "IS-ART55-R03": "ART55-OBL-1c",
    "IS-ART55-R04": "ART55-OBL-1d",
}


def _all_requirements():
    for path in STANDARDS:
        for req in json.loads(path.read_text(encoding="utf-8")).get("requirements", []):
            yield req["id"], req.get("obligation_ref")


def test_the_checked_refs_point_to_the_obligation_the_requirement_implements():
    got = dict(_all_requirements())
    wrong = {rid: (got.get(rid), want) for rid, want in EXPECTED.items() if got.get(rid) != want}
    assert wrong == {}, wrong
