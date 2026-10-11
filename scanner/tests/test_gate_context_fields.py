"""The validation gate must not report the scanner's own fields as "unknown".

Real Claude Code scans of a project connected to the dashboard (2026-10-10 / 2026-10-11) came back with

    "validation_gate": {"coerce_fixes": 1, "coerce_details": [{"action": "unknown_field",
        "key": "art49.claims_art6_3_exception", "reason": "'claims_art6_3_exception' is not a field of art49 in the
        answers template — ignored; use the template's field names"}],
        "note": "Your compliance_answers had format issues that were auto-corrected. …"}

although the assistant had not sent that field: the scanner writes it itself from the dashboard's Profiling Wizard
answer, because ART49-OBL-2's applicability depends on it (`context_skip_field` in the obligation record). The gate
knew only the template's fields. The message was wrong twice — the field is read, and the assistant had nothing to
fix.
"""
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402
from core.validation_gate import _coerce_article_fields, run_gate  # noqa: E402


def _unknown(log):
    return [entry["key"] for entry in log if entry["action"] == "unknown_field"]


def test_an_obligations_context_field_is_a_field_of_its_article():
    # ART49-OBL-2 (Art. 6(3) exception registration) and the Art. 52 obligations (systemic-risk GPAI).
    assert _unknown(_coerce_article_fields("art49", {"claims_art6_3_exception": False})[1]) == []
    assert _unknown(_coerce_article_fields("art52", {"is_gpai_with_systemic_risk": True})[1]) == []


def test_every_field_the_dashboard_settings_pin_passes_the_gate_silently():
    """All wizard answers set → every (article, field) the scanner pins. None is reported as unknown."""
    wizard = {key: True for key in server._WIZARD_TO_SCANNER_FIELDS}
    wizard["euEstablished"] = False  # also pins art54.is_third_country_provider (inverse)
    answers = server._apply_wizard_overrides_to_answers({}, wizard)
    pinned_articles = sorted(k for k in answers if k != "_scope")
    assert {"art49", "art52", "art54"} <= set(pinned_articles), pinned_articles

    for article in pinned_articles:
        assert _unknown(_coerce_article_fields(article, dict(answers[article]))[1]) == [], article

    gate = run_gate(answers)
    assert _unknown(gate.coerce_log or []) == []


def test_a_field_nothing_reads_is_still_reported():
    # A near-miss of the real name, and a context field of another article.
    log = _coerce_article_fields("art49", {"claims_art63_exception": False, "is_gpai_with_systemic_risk": True})[1]
    assert _unknown(log) == ["art49.claims_art63_exception", "art49.is_gpai_with_systemic_risk"]
