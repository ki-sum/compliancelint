"""Validation gate must not fuzzy-rename fields that article modules read.

Self-audit A1 (2026-10-02): `_coerce_article_fields` fuzzy-renamed every
non-schema key (difflib cutoff 0.7) onto the closest schema field and
overwrote whatever was there. Module-read keys outside the bool/list schema
were silently destroyed:

  - Art 5 `<practice>_evidence` strings (read by module.py next to each
    `has_<practice>` boolean) replaced the boolean → Art 5 rejected with
    "not a string description".
  - Legacy aliases (Art 9 `has_risk_code`, Art 10 `has_bias_detection`,
    Art 12/19 `has_retention_policy`, Art 15 `has_accuracy_metrics`) overwrote
    the canonical field, although the modules treat them as fallbacks only
    (canonical wins); Art 9 `has_risk_code` even landed on `has_risk_docs`,
    a different obligation.
"""
import glob
import os
import re

import pytest

from core.context import _BOOL_FIELDS, _LIST_FIELDS
from core.validation_gate import coerce_answers, validate_answers

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")


def _art5_evidence_pairs(art05_module):
    fields = type(art05_module).scan.__globals__["_PROHIBITION_FIELDS"]
    return [(name, name.replace("has_", "") + "_evidence") for name, _oid, _label in fields]


def _module_read_keys() -> list[tuple[str, str]]:
    """Every literal key a module reads via `answers.get("...")`, per article."""
    pairs = []
    for path in sorted(glob.glob(os.path.join(SCANNER_ROOT, "modules", "art*", "module.py"))):
        art = "art" + str(int(re.search(r"art(\d+)", os.path.basename(os.path.dirname(path))).group(1)))
        with open(path, encoding="utf-8") as f:
            src = f.read()
        for key in sorted(set(re.findall(r'answers\.get\(\s*"([a-z0-9_]+)"', src))):
            pairs.append((art, key))
    return pairs


class TestArt5EvidenceFields:

    def test_boolean_and_evidence_both_preserved(self, art05_module):
        pairs = _art5_evidence_pairs(art05_module)
        assert len(pairs) == 10
        answers = {"art5": {}}
        for has_field, ev_field in pairs:
            answers["art5"][has_field] = False
            answers["art5"][ev_field] = f"No {has_field} patterns found in src/"

        coerced, log = coerce_answers(answers)

        for has_field, ev_field in pairs:
            assert coerced["art5"][has_field] is False, has_field
            assert coerced["art5"][ev_field] == f"No {has_field} patterns found in src/", ev_field
        assert not [l for l in log if l["action"] == "field_renamed"]
        errors, missing = validate_answers(coerced)
        assert "art5" not in errors
        assert "art5" not in missing

    def test_evidence_without_boolean_is_not_promoted_to_boolean(self, art05_module):
        for has_field, ev_field in _art5_evidence_pairs(art05_module):
            coerced, _ = coerce_answers({"art5": {ev_field: "Image pipeline with NSFW filter"}})
            assert coerced["art5"] == {ev_field: "Image pipeline with NSFW filter"}, ev_field


# (article, alias read as fallback, canonical schema field the module prefers)
_ALIASES = [
    ("art9", "has_risk_code", "has_risk_code_patterns"),
    ("art9", "has_metrics", "has_defined_metrics"),
    ("art10", "has_bias_detection", "has_bias_mitigation"),
    ("art12", "has_retention_policy", "has_retention_config"),
    ("art15", "has_accuracy_metrics", "has_accuracy_testing"),
    ("art19", "has_retention_policy", "has_retention_config"),
]


class TestModuleAliasesNotRenamed:

    @pytest.mark.parametrize("art,alias,canonical", _ALIASES)
    def test_alias_does_not_overwrite_canonical(self, art, alias, canonical):
        coerced, _ = coerce_answers({art: {canonical: True, alias: False}})
        assert coerced[art] == {canonical: True, alias: False}

    def test_art9_risk_code_alias_does_not_land_on_risk_docs(self):
        coerced, _ = coerce_answers({"art9": {"has_risk_docs": True, "has_risk_code": False}})
        assert coerced["art9"] == {"has_risk_docs": True, "has_risk_code": False}

    @pytest.mark.parametrize("art,key", _module_read_keys())
    def test_every_module_read_key_survives_coercion(self, art, key):
        """Drift guard: a key a module reads must reach the module under its own name."""
        coerced, _ = coerce_answers({art: {key: "sentinel"}})
        assert key in coerced[art], f"{art}.{key} was renamed to {sorted(coerced[art])}"

    def test_art5_dynamic_evidence_keys_covered_by_drift_guard(self, art05_module):
        for _has, ev_field in _art5_evidence_pairs(art05_module):
            coerced, _ = coerce_answers({"art5": {ev_field: "sentinel"}})
            assert ev_field in coerced["art5"]


class TestFuzzyRenameNeverOverwrites:

    def test_typo_still_renamed_when_canonical_absent(self):
        coerced, log = coerce_answers({"art50": {"has_ai_disclosure_to_user": False}})
        assert coerced["art50"] == {"has_ai_disclosure_to_users": False}
        assert any(l["action"] == "field_renamed" for l in log)

    def test_typo_does_not_overwrite_present_canonical(self):
        coerced, log = coerce_answers({"art50": {
            "has_ai_disclosure_to_users": True,
            "has_ai_disclosure_to_user": False,
        }})
        assert coerced["art50"]["has_ai_disclosure_to_users"] is True
        assert coerced["art50"]["has_ai_disclosure_to_user"] is False
        assert any(l["action"] == "field_rename_skipped" for l in log)

    def test_schema_fields_disjoint_from_module_aliases(self):
        for art, alias, canonical in _ALIASES:
            assert alias not in set(_BOOL_FIELDS.get(art, [])) | set(_LIST_FIELDS.get(art, []))
            assert canonical in _BOOL_FIELDS[art]
