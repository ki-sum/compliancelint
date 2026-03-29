"""Art. 27 Fundamental Rights Impact Assessment tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_fria_documentation     → ART27-OBL-1
  has_fria_versioning        → ART27-OBL-2
  Conditional (scope_limitation) → ART27-OBL-3 (is_public_law_or_annex_iii_5bc)
  Conditional (scope_limitation) → ART27-OBL-4 (has_existing_dpia)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art27", {
        "has_fria_documentation": True,
        "has_fria_versioning": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art27", {
        "has_fria_documentation": False,
        "has_fria_versioning": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art27", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART27-OBL-1: FRIA documentation (has_fria_documentation) ──

class TestArt27Obl1:

    def test_has_fria_doc_true_gives_partial(self, art27_module, tmp_path):
        """has_fria_documentation=True → ART27-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art27_module.scan(str(tmp_path))
        obl = _find(result, "ART27-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_fria_doc_false_gives_non_compliant(self, art27_module, tmp_path):
        """has_fria_documentation=False → ART27-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art27_module.scan(str(tmp_path))
        obl = _find(result, "ART27-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_fria_doc_none_gives_utd(self, art27_module, tmp_path):
        """has_fria_documentation=None → ART27-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art27_module.scan(str(tmp_path))
        obl = _find(result, "ART27-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART27-OBL-2: FRIA versioning (has_fria_versioning) ──

class TestArt27Obl2:

    def test_has_versioning_true_gives_partial(self, art27_module, tmp_path):
        """has_fria_versioning=True → ART27-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art27_module.scan(str(tmp_path))
        obl = _find(result, "ART27-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_versioning_false_gives_non_compliant(self, art27_module, tmp_path):
        """has_fria_versioning=False → ART27-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art27_module.scan(str(tmp_path))
        obl = _find(result, "ART27-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_versioning_none_gives_utd(self, art27_module, tmp_path):
        """has_fria_versioning=None → ART27-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art27_module.scan(str(tmp_path))
        obl = _find(result, "ART27-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Conditional obligations: scope_limitation handling ──

class TestArt27ConditionalObligations:

    def test_obl3_conditional_when_no_context(self, art27_module, tmp_path):
        """OBL-3 has scope_limitation → CONDITIONAL (UTD) when is_public_law_or_annex_iii_5bc not provided."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art27_module.scan(str(tmp_path))
        obl = _find(result, "ART27-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_obl3_not_applicable_when_not_public_law(self, art27_module, tmp_path):
        """OBL-3 → NOT_APPLICABLE when is_public_law_or_annex_iii_5bc=False."""
        ctx = _ctx_with("art27", {
            "has_fria_documentation": True,
            "has_fria_versioning": True,
            "is_public_law_or_annex_iii_5bc": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art27_module.scan(str(tmp_path))
        obl = _find(result, "ART27-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_obl4_conditional_when_no_dpia_context(self, art27_module, tmp_path):
        """OBL-4 has scope_limitation → CONDITIONAL (UTD) when has_existing_dpia not provided."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art27_module.scan(str(tmp_path))
        obl = _find(result, "ART27-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_obl4_not_applicable_when_no_dpia(self, art27_module, tmp_path):
        """OBL-4 → NOT_APPLICABLE when has_existing_dpia=False."""
        ctx = _ctx_with("art27", {
            "has_fria_documentation": True,
            "has_fria_versioning": True,
            "has_existing_dpia": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art27_module.scan(str(tmp_path))
        obl = _find(result, "ART27-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_obl3_utd_when_in_scope(self, art27_module, tmp_path):
        """OBL-3 (manual) → UTD even when is_public_law_or_annex_iii_5bc=True."""
        ctx = _ctx_with("art27", {
            "has_fria_documentation": True,
            "has_fria_versioning": True,
            "is_public_law_or_annex_iii_5bc": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art27_module.scan(str(tmp_path))
        obl = _find(result, "ART27-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_obl4_utd_when_dpia_exists(self, art27_module, tmp_path):
        """OBL-4 (manual) → UTD when has_existing_dpia=True (scope applies, but manual)."""
        ctx = _ctx_with("art27", {
            "has_fria_documentation": True,
            "has_fria_versioning": True,
            "has_existing_dpia": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art27_module.scan(str(tmp_path))
        obl = _find(result, "ART27-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt27Structural:

    def test_all_4_obligation_ids_in_json(self, art27_module):
        """Obligation JSON must have exactly 4 obligations."""
        data = art27_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 4

    def test_obligation_coverage_present(self, art27_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art27_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_automatable_obligations_utd(self, art27_module, tmp_path):
        """When AI provides no answers, automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art27_module.scan(str(tmp_path))
        automatable_ids = ["ART27-OBL-1", "ART27-OBL-2"]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art27_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 27(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art27_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art27_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art27_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art27_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art27_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_4_obligations_appear_in_findings(self, art27_module, tmp_path):
        """All 4 obligations must appear in findings (explicit or gap)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art27_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART27-OBL-1", "ART27-OBL-2", "ART27-OBL-3", "ART27-OBL-4"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"
