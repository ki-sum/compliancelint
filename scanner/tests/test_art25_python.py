"""Art. 25 Responsibilities along the AI value chain tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_rebranding_or_modification          → ART25-CLS-1 (classification: triggers provider status)
  has_provider_cooperation_documentation  → ART25-OBL-2 (initial provider cooperation)
  is_safety_component_annex_i             → ART25-CLS-3 (classification: product manufacturer = provider)
  has_third_party_written_agreement       → ART25-OBL-4 (written agreement with suppliers)
  Gap findings (obligation engine)        → ART25-SAV-5 (savings clause: IP/trade secret)

Exception obligations (ART25-EXC-2, ART25-EXC-4) are silently skipped by the
obligation engine gap_findings() since they have deontic_type="exception" without
scope_limitation.

Classification rules (CLS-1, CLS-3) use custom Finding() construction since they
determine a legal classification, not a compliance requirement.
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art25", {
        "has_rebranding_or_modification": True,
        "has_provider_cooperation_documentation": True,
        "is_safety_component_annex_i": True,
        "has_third_party_written_agreement": True,
        "has_open_source_exception": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art25", {
        "has_rebranding_or_modification": False,
        "has_provider_cooperation_documentation": False,
        "is_safety_component_annex_i": False,
        "has_third_party_written_agreement": False,
        "has_open_source_exception": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art25", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# Obligations that appear in findings (5 of 7).
# ART25-EXC-2 and ART25-EXC-4 are exceptions without scope_limitation,
# silently skipped by gap_findings per obligation engine rules.
ALL_FINDING_IDS = [
    "ART25-CLS-1", "ART25-OBL-2",
    "ART25-CLS-3", "ART25-OBL-4",
    "ART25-SAV-5",
]

AUTOMATABLE_IDS = ["ART25-OBL-2", "ART25-OBL-4"]

CLASSIFICATION_IDS = ["ART25-CLS-1", "ART25-CLS-3"]


# ── ART25-CLS-1: Rebranding/modification triggers provider status ──

class TestArt25Cls1:

    def test_rebranding_true_gives_partial(self, art25_module, tmp_path):
        """has_rebranding_or_modification=True → ART25-CLS-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art25_module.scan(str(tmp_path))
        obl = _find(result, "ART25-CLS-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_rebranding_false_gives_compliant(self, art25_module, tmp_path):
        """has_rebranding_or_modification=False → ART25-CLS-1 COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art25_module.scan(str(tmp_path))
        obl = _find(result, "ART25-CLS-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.COMPLIANT

    def test_rebranding_none_gives_utd(self, art25_module, tmp_path):
        """has_rebranding_or_modification=None → ART25-CLS-1 UTD."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art25_module.scan(str(tmp_path))
        obl = _find(result, "ART25-CLS-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART25-OBL-2: Initial provider cooperation ──

class TestArt25Obl2:

    def test_cooperation_true_gives_partial(self, art25_module, tmp_path):
        """has_provider_cooperation_documentation=True → ART25-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art25_module.scan(str(tmp_path))
        obl = _find(result, "ART25-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_cooperation_false_gives_non_compliant(self, art25_module, tmp_path):
        """has_provider_cooperation_documentation=False → ART25-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art25_module.scan(str(tmp_path))
        obl = _find(result, "ART25-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_cooperation_none_gives_utd(self, art25_module, tmp_path):
        """has_provider_cooperation_documentation=None → ART25-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art25_module.scan(str(tmp_path))
        obl = _find(result, "ART25-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART25-CLS-3: Product manufacturer = provider (Annex I safety component) ──

class TestArt25Cls3:

    def test_safety_component_true_gives_partial(self, art25_module, tmp_path):
        """is_safety_component_annex_i=True → ART25-CLS-3 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art25_module.scan(str(tmp_path))
        obl = _find(result, "ART25-CLS-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_safety_component_false_gives_not_applicable(self, art25_module, tmp_path):
        """is_safety_component_annex_i=False → ART25-CLS-3 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art25_module.scan(str(tmp_path))
        obl = _find(result, "ART25-CLS-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_safety_component_none_gives_utd(self, art25_module, tmp_path):
        """is_safety_component_annex_i=None → ART25-CLS-3 UTD."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art25_module.scan(str(tmp_path))
        obl = _find(result, "ART25-CLS-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART25-OBL-4: Written agreement with third-party suppliers ──

class TestArt25Obl4:

    def test_agreement_true_gives_partial(self, art25_module, tmp_path):
        """has_third_party_written_agreement=True → ART25-OBL-4 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art25_module.scan(str(tmp_path))
        obl = _find(result, "ART25-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_agreement_false_gives_non_compliant(self, art25_module, tmp_path):
        """has_third_party_written_agreement=False → ART25-OBL-4 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art25_module.scan(str(tmp_path))
        obl = _find(result, "ART25-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_agreement_none_gives_utd(self, art25_module, tmp_path):
        """has_third_party_written_agreement=None → ART25-OBL-4 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art25_module.scan(str(tmp_path))
        obl = _find(result, "ART25-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt25Structural:

    def test_all_7_obligation_ids_in_json(self, art25_module):
        """Obligation JSON must have exactly 7 obligations."""
        data = art25_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 7

    def test_obligation_coverage_present(self, art25_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art25_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_automatable_obligations_utd(self, art25_module, tmp_path):
        """When AI provides no answers, automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art25_module.scan(str(tmp_path))
        for obl_id in AUTOMATABLE_IDS:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art25_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 25(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art25_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art25_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art25_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art25_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art25_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_finding_ids_in_findings(self, art25_module, tmp_path):
        """All expected finding IDs (5 of 7) must appear in scan findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art25_module.scan(str(tmp_path))
        finding_ids = {f.obligation_id for f in result.findings}
        for obl_id in ALL_FINDING_IDS:
            assert obl_id in finding_ids, (
                f"{obl_id} not in findings. Found: {sorted(finding_ids)}"
            )

    def test_summary_present(self, art25_module, tmp_path):
        """ScanResult must have article_number and overall_level."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art25_module.scan(str(tmp_path))
        assert result.article_number == 25
        assert result.overall_level is not None
