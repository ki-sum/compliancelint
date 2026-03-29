"""Art. 24 Obligations of distributors tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_pre_market_verification  → ART24-OBL-1 (verify CE marking, declaration, instructions)
  has_conformity_review        → ART24-OBL-2 (prohibition: don't distribute if non-conforming)
  has_authority_documentation   → ART24-OBL-5 (provide info/documentation on request)
  Manual (always UTD)          → ART24-OBL-3 (storage/transport conditions)
  Manual (always UTD)          → ART24-OBL-2b (inform provider/importer of risk)
  Manual (always UTD)          → ART24-OBL-4 (corrective actions)
  Manual (always UTD)          → ART24-OBL-4b (immediately inform authorities of risk)
  Manual (always UTD)          → ART24-OBL-6 (cooperate with authorities)

Conditional logic:
  is_distributor=False → all NOT_APPLICABLE
  is_distributor=None  → obligations proceed (conservative)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True (distributor with all procedures in place)."""
    return _ctx_with("art24", {
        "is_distributor": True,
        "has_pre_market_verification": True,
        "has_conformity_review": True,
        "has_authority_documentation": True,
    })


def _full_false_ctx():
    """All automatable fields False (distributor with no procedures)."""
    return _ctx_with("art24", {
        "is_distributor": True,
        "has_pre_market_verification": False,
        "has_conformity_review": False,
        "has_authority_documentation": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art24", {})


def _not_distributor_ctx():
    """Organisation is not a distributor."""
    return _ctx_with("art24", {
        "is_distributor": False,
        "has_pre_market_verification": None,
        "has_conformity_review": None,
        "has_authority_documentation": None,
    })


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


ALL_OBLIGATION_IDS = [
    "ART24-OBL-1", "ART24-OBL-2", "ART24-OBL-3",
    "ART24-OBL-2b", "ART24-OBL-4", "ART24-OBL-4b",
    "ART24-OBL-5", "ART24-OBL-6",
]

AUTOMATABLE_IDS = ["ART24-OBL-1", "ART24-OBL-2", "ART24-OBL-5"]

MANUAL_IDS = ["ART24-OBL-3", "ART24-OBL-2b", "ART24-OBL-4", "ART24-OBL-4b", "ART24-OBL-6"]


# ── ART24-OBL-1: Pre-market verification (has_pre_market_verification) ──

class TestArt24Obl1:

    def test_has_pre_market_verification_true_gives_partial(self, art24_module, tmp_path):
        """has_pre_market_verification=True → ART24-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art24_module.scan(str(tmp_path))
        obl = _find(result, "ART24-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_pre_market_verification_false_gives_non_compliant(self, art24_module, tmp_path):
        """has_pre_market_verification=False → ART24-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art24_module.scan(str(tmp_path))
        obl = _find(result, "ART24-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_pre_market_verification_none_gives_utd(self, art24_module, tmp_path):
        """has_pre_market_verification=None → ART24-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art24_module.scan(str(tmp_path))
        obl = _find(result, "ART24-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART24-OBL-2: Conformity review (has_conformity_review) ──

class TestArt24Obl2:

    def test_has_conformity_review_true_gives_partial(self, art24_module, tmp_path):
        """has_conformity_review=True → ART24-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art24_module.scan(str(tmp_path))
        obl = _find(result, "ART24-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_conformity_review_false_gives_non_compliant(self, art24_module, tmp_path):
        """has_conformity_review=False → ART24-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art24_module.scan(str(tmp_path))
        obl = _find(result, "ART24-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_conformity_review_none_gives_utd(self, art24_module, tmp_path):
        """has_conformity_review=None → ART24-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art24_module.scan(str(tmp_path))
        obl = _find(result, "ART24-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART24-OBL-5: Authority documentation (has_authority_documentation) ──

class TestArt24Obl5:

    def test_has_authority_documentation_true_gives_partial(self, art24_module, tmp_path):
        """has_authority_documentation=True → ART24-OBL-5 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art24_module.scan(str(tmp_path))
        obl = _find(result, "ART24-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_authority_documentation_false_gives_non_compliant(self, art24_module, tmp_path):
        """has_authority_documentation=False → ART24-OBL-5 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art24_module.scan(str(tmp_path))
        obl = _find(result, "ART24-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_authority_documentation_none_gives_utd(self, art24_module, tmp_path):
        """has_authority_documentation=None → ART24-OBL-5 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art24_module.scan(str(tmp_path))
        obl = _find(result, "ART24-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Conditional: is_distributor=False → all NOT_APPLICABLE ──

class TestArt24NotDistributor:

    def test_not_distributor_all_obligations_not_applicable(self, art24_module, tmp_path):
        """is_distributor=False → all 8 obligations NOT_APPLICABLE."""
        BaseArticleModule.set_context(_not_distributor_ctx())
        result = art24_module.scan(str(tmp_path))
        for obl_id in ALL_OBLIGATION_IDS:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.NOT_APPLICABLE, (
                f"{obl_id} should be NOT_APPLICABLE for non-distributor, got {findings[0].level}"
            )

    def test_not_distributor_overall_not_applicable(self, art24_module, tmp_path):
        """is_distributor=False → overall level NOT_APPLICABLE."""
        BaseArticleModule.set_context(_not_distributor_ctx())
        result = art24_module.scan(str(tmp_path))
        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE


# ── Structural tests ──

class TestArt24Structural:

    def test_all_8_obligation_ids_in_json(self, art24_module):
        """Obligation JSON must have exactly 8 obligations."""
        data = art24_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 8

    def test_obligation_coverage_present(self, art24_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art24_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_automatable_obligations_utd(self, art24_module, tmp_path):
        """When AI provides no answers, automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art24_module.scan(str(tmp_path))
        for obl_id in AUTOMATABLE_IDS:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art24_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 24(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art24_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art24_module, tmp_path):
        """All-true answers (distributor) → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art24_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art24_module, tmp_path):
        """All-false answers (distributor) → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art24_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_obligation_ids_in_findings(self, art24_module, tmp_path):
        """All 8 obligation IDs must appear in scan findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art24_module.scan(str(tmp_path))
        finding_ids = {f.obligation_id for f in result.findings}
        for obl_id in ALL_OBLIGATION_IDS:
            assert obl_id in finding_ids, (
                f"{obl_id} not in findings. Found: {sorted(finding_ids)}"
            )

    def test_summary_present(self, art24_module, tmp_path):
        """ScanResult must have article_number and overall_level."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art24_module.scan(str(tmp_path))
        assert result.article_number == 24
        assert result.overall_level is not None
