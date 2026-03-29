"""Art. 23 Obligations of importers tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  is_importer=True             → obligations apply
  is_importer=False            → all obligations NOT_APPLICABLE
  has_pre_market_verification  → ART23-OBL-1
  has_conformity_review        → ART23-OBL-2
  has_importer_identification  → ART23-OBL-3
  has_documentation_retention  → ART23-OBL-5
  has_authority_documentation  → ART23-OBL-6
  ART23-OBL-4                 → always gap finding (manual — storage/transport)
  ART23-OBL-2b                → always gap finding (manual — inform provider/authorities)
  ART23-OBL-7                 → always gap finding (manual — cooperate with authorities)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _importer_true_ctx():
    """Importer with all automatable fields True."""
    return _ctx_with("art23", {
        "is_importer": True,
        "has_pre_market_verification": True,
        "has_conformity_review": True,
        "has_importer_identification": True,
        "has_documentation_retention": True,
        "has_authority_documentation": True,
    })


def _importer_false_ctx():
    """Importer with all automatable fields False."""
    return _ctx_with("art23", {
        "is_importer": True,
        "has_pre_market_verification": False,
        "has_conformity_review": False,
        "has_importer_identification": False,
        "has_documentation_retention": False,
        "has_authority_documentation": False,
    })


def _not_importer_ctx():
    """Not an importer — Art. 23 obligations are NOT_APPLICABLE."""
    return _ctx_with("art23", {
        "is_importer": False,
        "has_pre_market_verification": None,
        "has_conformity_review": None,
        "has_importer_identification": None,
        "has_documentation_retention": None,
        "has_authority_documentation": None,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art23", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART23-OBL-1: Pre-market conformity verification ──

class TestArt23Obl1:

    def test_has_pre_market_verification_true_gives_partial(self, art23_module, tmp_path):
        """has_pre_market_verification=True → ART23-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_importer_true_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_pre_market_verification_false_gives_non_compliant(self, art23_module, tmp_path):
        """has_pre_market_verification=False → ART23-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_importer_false_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_pre_market_verification_none_gives_utd(self, art23_module, tmp_path):
        """has_pre_market_verification=None → ART23-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART23-OBL-2: Don't place non-conforming systems (prohibition) ──

class TestArt23Obl2:

    def test_has_conformity_review_true_gives_partial(self, art23_module, tmp_path):
        """has_conformity_review=True → ART23-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_importer_true_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_conformity_review_false_gives_non_compliant(self, art23_module, tmp_path):
        """has_conformity_review=False → ART23-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_importer_false_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_conformity_review_none_gives_utd(self, art23_module, tmp_path):
        """has_conformity_review=None → ART23-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART23-OBL-3: Importer identification on system ──

class TestArt23Obl3:

    def test_has_importer_identification_true_gives_partial(self, art23_module, tmp_path):
        """has_importer_identification=True → ART23-OBL-3 PARTIAL."""
        BaseArticleModule.set_context(_importer_true_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_importer_identification_false_gives_non_compliant(self, art23_module, tmp_path):
        """has_importer_identification=False → ART23-OBL-3 NON_COMPLIANT."""
        BaseArticleModule.set_context(_importer_false_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_importer_identification_none_gives_utd(self, art23_module, tmp_path):
        """has_importer_identification=None → ART23-OBL-3 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART23-OBL-5: Document retention (10 years) ──

class TestArt23Obl5:

    def test_has_documentation_retention_true_gives_partial(self, art23_module, tmp_path):
        """has_documentation_retention=True → ART23-OBL-5 PARTIAL."""
        BaseArticleModule.set_context(_importer_true_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_documentation_retention_false_gives_non_compliant(self, art23_module, tmp_path):
        """has_documentation_retention=False → ART23-OBL-5 NON_COMPLIANT."""
        BaseArticleModule.set_context(_importer_false_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_documentation_retention_none_gives_utd(self, art23_module, tmp_path):
        """has_documentation_retention=None → ART23-OBL-5 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART23-OBL-6: Provide information to authorities on request ──

class TestArt23Obl6:

    def test_has_authority_documentation_true_gives_partial(self, art23_module, tmp_path):
        """has_authority_documentation=True → ART23-OBL-6 PARTIAL."""
        BaseArticleModule.set_context(_importer_true_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_authority_documentation_false_gives_non_compliant(self, art23_module, tmp_path):
        """has_authority_documentation=False → ART23-OBL-6 NON_COMPLIANT."""
        BaseArticleModule.set_context(_importer_false_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_authority_documentation_none_gives_utd(self, art23_module, tmp_path):
        """has_authority_documentation=None → ART23-OBL-6 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Non-importer tests ──

class TestArt23NonImporter:

    def test_non_importer_obl1_not_applicable(self, art23_module, tmp_path):
        """is_importer=False → ART23-OBL-1 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_not_importer_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_non_importer_obl2_not_applicable(self, art23_module, tmp_path):
        """is_importer=False → ART23-OBL-2 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_not_importer_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_non_importer_obl3_not_applicable(self, art23_module, tmp_path):
        """is_importer=False → ART23-OBL-3 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_not_importer_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_non_importer_obl5_not_applicable(self, art23_module, tmp_path):
        """is_importer=False → ART23-OBL-5 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_not_importer_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_non_importer_obl6_not_applicable(self, art23_module, tmp_path):
        """is_importer=False → ART23-OBL-6 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_not_importer_ctx())
        result = art23_module.scan(str(tmp_path))
        obl = _find(result, "ART23-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_non_importer_manual_obligations_not_applicable(self, art23_module, tmp_path):
        """is_importer=False → manual obligations (OBL-4, OBL-2b, OBL-7) NOT_APPLICABLE."""
        BaseArticleModule.set_context(_not_importer_ctx())
        result = art23_module.scan(str(tmp_path))
        for obl_id in ["ART23-OBL-4", "ART23-OBL-2b", "ART23-OBL-7"]:
            obl = _find(result, obl_id)
            assert len(obl) > 0, f"{obl_id} not in findings"
            assert obl[0].level == ComplianceLevel.NOT_APPLICABLE, (
                f"{obl_id} should be NOT_APPLICABLE for non-importer, got {obl[0].level}"
            )


# ── Structural tests ──

class TestArt23Structural:

    def test_all_8_obligation_ids_in_json(self, art23_module):
        """Obligation JSON must have exactly 8 obligations."""
        data = art23_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 8

    def test_obligation_coverage_present(self, art23_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art23_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_automatable_obligations_utd(self, art23_module, tmp_path):
        """When AI provides no answers, automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art23_module.scan(str(tmp_path))
        automatable_ids = [
            "ART23-OBL-1", "ART23-OBL-2", "ART23-OBL-3",
            "ART23-OBL-5", "ART23-OBL-6",
        ]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art23_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 23(1)]."""
        BaseArticleModule.set_context(_importer_true_ctx())
        result = art23_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art23_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_importer_true_ctx())
        result = art23_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art23_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_importer_false_ctx())
        result = art23_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_obligation_findings_present(self, art23_module, tmp_path):
        """All 8 obligations must appear in findings."""
        BaseArticleModule.set_context(_importer_true_ctx())
        result = art23_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {
            "ART23-OBL-1", "ART23-OBL-2", "ART23-OBL-3",
            "ART23-OBL-4", "ART23-OBL-2b", "ART23-OBL-5",
            "ART23-OBL-6", "ART23-OBL-7",
        }
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"

    def test_manual_obligations_are_gap_findings(self, art23_module, tmp_path):
        """Manual obligations (OBL-4, OBL-2b, OBL-7) appear as gap findings with UTD."""
        BaseArticleModule.set_context(_importer_true_ctx())
        result = art23_module.scan(str(tmp_path))
        for obl_id in ["ART23-OBL-4", "ART23-OBL-2b", "ART23-OBL-7"]:
            obl = _find(result, obl_id)
            assert len(obl) > 0, f"{obl_id} not in findings"
            assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD (manual), got {obl[0].level}"
            )

    def test_summary_present(self, art23_module, tmp_path):
        """ScanResult must include article_number and article_title."""
        result = art23_module.scan(str(tmp_path))
        assert result.article_number == 23
        assert result.article_title == "Obligations of importers"

    def test_invalid_directory_returns_error(self, art23_module):
        """Scanning a non-existent directory should not crash."""
        result = art23_module.scan("/nonexistent/path/that/does/not/exist")
        assert result is not None
