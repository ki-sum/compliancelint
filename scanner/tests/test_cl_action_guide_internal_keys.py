"""cl_action_guide must serve only the current obligation text.

Self-audit A2 (2026-10-02): atoms corrected by the Art 5 consensus lock keep
their superseded wording in a per-atom `_history` list (audit trail in the
obligation JSON). cl_action_guide returned `decomposed_atoms` verbatim, so the
corrected errors ("judicial authorization" only, access-controlled spaces,
drowsiness exception, ...) reached AI clients again.
"""
import glob
import json
import os

import pytest

import server
from core.obligation_lookup import extract_action_guide_fields

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")


def _guide(obligation_id: str) -> dict:
    fn = getattr(server.cl_action_guide, "fn", server.cl_action_guide)
    raw = fn(obligation_id)
    return json.JSONDecoder().raw_decode(raw)[0]


def _rows_with_internal_atom_keys() -> list[str]:
    ids = []
    for path in glob.glob(os.path.join(SCANNER_ROOT, "obligations", "*.json")):
        with open(path, encoding="utf-8") as f:
            for o in json.load(f)["obligations"]:
                if any(k.startswith("_") for a in o.get("decomposed_atoms", []) for k in a):
                    ids.append(o["id"])
    return sorted(ids)


def test_fixture_has_atoms_with_history():
    """Guard: the tests below are only meaningful while `_history` exists in shipped data."""
    assert {"ART05-PRO-1a", "ART05-PRO-1b", "ART05-PRO-1c", "ART05-PRO-1f", "ART05-PRO-1h"} <= set(
        _rows_with_internal_atom_keys())


@pytest.mark.parametrize("oid", _rows_with_internal_atom_keys())
def test_no_underscore_keys_in_served_atoms(oid):
    atoms = _guide(oid)["decomposed_atoms"]
    assert atoms, oid
    for atom in atoms:
        assert not [k for k in atom if k.startswith("_")], (oid, atom.get("atom"))


def test_superseded_1h_wording_not_served():
    text = json.dumps(_guide("ART05-PRO-1h")).lower()
    assert "judicial authorization" not in text
    assert "access-controlled" not in text
    assert "superseded_on" not in text


def test_current_1h_wording_still_served():
    atoms = {a["atom"]: a for a in _guide("ART05-PRO-1h")["decomposed_atoms"]}
    req = atoms["exception_requires_prior_authorisation"]["requirement"]
    assert "judicial authority or an independent administrative authority whose decision is binding" in req


def test_extract_does_not_mutate_cached_row():
    row = {"decomposed_atoms": [{"atom": "a", "description": "d", "_history": [{"description": "old"}]}]}
    out = extract_action_guide_fields(row)
    assert out["decomposed_atoms"] == [{"atom": "a", "description": "d"}]
    assert row["decomposed_atoms"][0]["_history"] == [{"description": "old"}]
