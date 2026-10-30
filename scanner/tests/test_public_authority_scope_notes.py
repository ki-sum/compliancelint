"""Scope notes of the public-authority deployer obligations name every addressee the Article names.

The scope note is printed in the finding ("This obligation has a scope limitation: <note>." or
"[NOT APPLICABLE] <source>: <note>."). It read "Only applies to public authority deployers" for Art. 49(3) and
Art. 26(8), which left out Union institutions, bodies, offices or agencies and (Art. 49(3)) persons acting on their
behalf; the Art. 71(3) note left out agencies and bodies. Texts: independent legal check 2026-10-30.
"""
import json
import os

from core.protocol import BaseArticleModule
from conftest import _ctx_with

OBLIGATIONS = os.path.join(os.path.dirname(__file__), "..", "obligations")

NOTES = {
    ("art49-registration.json", "ART49-OBL-3"): (
        "Only applies to deployers that are public authorities, Union institutions, bodies, offices or agencies, "
        "or persons acting on their behalf, and only for high-risk AI systems listed in Annex III, with the "
        "exception of those listed in point 2 of Annex III"
    ),
    ("art26-deployer-obligations.json", "ART26-OBL-8"): (
        "Only applies to deployers that are public authorities, or Union institutions, bodies, offices or agencies"
    ),
    ("art71-eu-database.json", "ART71-OBL-3"): (
        "Only applies to the deployer who is, or who acts on behalf of, a public authority, agency or body, "
        "for high-risk AI systems to be registered in accordance with Article 49(3)"
    ),
}


def _note(file_name, obligation_id):
    with open(os.path.join(OBLIGATIONS, file_name), encoding="utf-8") as f:
        data = json.load(f)
    return next(o for o in data["obligations"] if o["id"] == obligation_id).get("scope_limitation")


def test_the_three_notes_are_the_legal_checked_texts():
    for (file_name, obligation_id), expected in NOTES.items():
        assert _note(file_name, obligation_id) == expected, obligation_id


def test_the_art49_3_finding_names_every_addressee(art49_module, tmp_path):
    BaseArticleModule.set_context(_ctx_with("art49", {"has_eu_database_registration": True}))
    result = art49_module.scan(str(tmp_path))
    finding = next(f for f in result.findings if f.obligation_id == "ART49-OBL-3")
    assert "Union institutions, bodies, offices or agencies" in finding.description
    assert "persons acting on their behalf" in finding.description
    assert "public authority deployers" not in finding.description
