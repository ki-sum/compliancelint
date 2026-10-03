"""ObligationEngine.enrich_finding must keep is_informational and human_gate_hint.

Pre-existing bug found 2026-10-03 (Omnibus batch 1): enrich_finding rebuilt the Finding without
these two fields, so every informational NOT_APPLICABLE a module emits (e.g. Art 22 "provider is
established in the EU") reached the output as a normal finding. Founder: fix together.
"""
import json
import os

from core.obligation_engine import ObligationEngine
from core.protocol import BaseArticleModule, ComplianceLevel, Confidence, Finding, GapType
from conftest import _ctx_with

OBL = os.path.join(os.path.dirname(__file__), "..", "obligations", "art22-authorised-representatives.json")


def _engine():
    with open(OBL, encoding="utf-8") as f:
        return ObligationEngine(json.load(f))


def _finding(**kw):
    base = dict(obligation_id="ART22-OBL-1", file_path="project-wide", line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE, confidence=Confidence.HIGH,
                description="Provider is established in the EU.", gap_type=GapType.PROCESS)
    base.update(kw)
    return Finding(**base)


def test_enrich_keeps_is_informational():
    out = _engine().enrich_finding(_finding(is_informational=True))
    assert out.is_informational is True
    assert out.source_quote  # enrichment still happened


def test_enrich_keeps_human_gate_hint():
    out = _engine().enrich_finding(_finding(level=ComplianceLevel.UNABLE_TO_DETERMINE, human_gate_hint="Confirm in the dashboard"))
    assert out.human_gate_hint == "Confirm in the dashboard"


def test_enrich_keeps_defaults_for_normal_findings():
    out = _engine().enrich_finding(_finding(level=ComplianceLevel.NON_COMPLIANT))
    assert out.is_informational is False and out.human_gate_hint is None


def test_art25_classification_rule_stays_informational(art25_module, tmp_path):
    """ART25-CLS-1 tells the user they may be a provider; by design it does not move the overall level."""
    BaseArticleModule.set_context(_ctx_with("art25", {"has_rebranding_or_modification": True}))
    result = art25_module.scan(str(tmp_path))
    cls1 = [f for f in result.findings if f.obligation_id == "ART25-CLS-1"]
    assert len(cls1) == 1 and cls1[0].is_informational and cls1[0].level == ComplianceLevel.PARTIAL


def test_art22_scope_verdict_still_drives_the_overall_level(art22_module, tmp_path):
    """Scope verdicts ("provider is established in the EU") are findings, not information: the article is NA."""
    BaseArticleModule.set_context(_ctx_with("art22", {"is_eu_established_provider": True}))
    result = art22_module.scan(str(tmp_path))
    assert result.overall_level == ComplianceLevel.NOT_APPLICABLE


def test_art25_unanswered_duties_are_not_masked_by_classification_findings(art25_module, tmp_path):
    """15 of 243 answer combinations changed with the fix, all PARTIAL -> UNABLE_TO_DETERMINE: when the
    classification rules say the party may be a provider (CLS-1/CLS-3 PARTIAL) but the duties
    (ART25-OBL-2, ART25-OBL-4) are unanswered, the article no longer reports PARTIAL progress."""
    BaseArticleModule.set_context(_ctx_with("art25", {
        "has_rebranding_or_modification": True, "is_safety_component_annex_i": True,
        "has_provider_cooperation_documentation": None, "has_third_party_written_agreement": None}))
    result = art25_module.scan(str(tmp_path))
    cls = {f.obligation_id: f for f in result.findings if f.obligation_id in ("ART25-CLS-1", "ART25-CLS-3")}
    assert set(cls) == {"ART25-CLS-1", "ART25-CLS-3"}
    assert all(f.level == ComplianceLevel.PARTIAL and f.is_informational for f in cls.values())
    assert result.overall_level == ComplianceLevel.UNABLE_TO_DETERMINE
