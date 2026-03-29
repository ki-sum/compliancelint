"""Art. 43 Conformity Assessment tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_internal_control_assessment   → ART43-OBL-2
  has_change_management_procedures  → ART43-OBL-4
  Conditional (scope_limitation)    → ART43-OBL-1 (is_annex_iii_point_1)
  Conditional (scope_limitation)    → ART43-OBL-3 (is_annex_i_product)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art43", {
        "has_internal_control_assessment": True,
        "has_change_management_procedures": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art43", {
        "has_internal_control_assessment": False,
        "has_change_management_procedures": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art43", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART43-OBL-2: Internal control assessment (has_internal_control_assessment) ──

class TestArt43Obl2:

    def test_true_gives_partial(self, art43_module, tmp_path):
        """has_internal_control_assessment=True → ART43-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art43_module.scan(str(tmp_path))
        obl = _find(result, "ART43-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art43_module, tmp_path):
        """has_internal_control_assessment=False → ART43-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art43_module.scan(str(tmp_path))
        obl = _find(result, "ART43-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art43_module, tmp_path):
        """has_internal_control_assessment=None → ART43-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art43_module.scan(str(tmp_path))
        obl = _find(result, "ART43-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART43-OBL-4: Change management procedures (has_change_management_procedures) ──

class TestArt43Obl4:

    def test_true_gives_partial(self, art43_module, tmp_path):
        """has_change_management_procedures=True → ART43-OBL-4 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art43_module.scan(str(tmp_path))
        obl = _find(result, "ART43-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art43_module, tmp_path):
        """has_change_management_procedures=False → ART43-OBL-4 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art43_module.scan(str(tmp_path))
        obl = _find(result, "ART43-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art43_module, tmp_path):
        """has_change_management_procedures=None → ART43-OBL-4 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art43_module.scan(str(tmp_path))
        obl = _find(result, "ART43-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Conditional obligations: scope_limitation handling ──

class TestArt43ConditionalObligations:

    def test_obl1_conditional_when_no_context(self, art43_module, tmp_path):
        """OBL-1 has scope_limitation → CONDITIONAL when is_annex_iii_point_1 not provided."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art43_module.scan(str(tmp_path))
        obl = _find(result, "ART43-OBL-1")
        assert len(obl) > 0
        # Without is_annex_iii_point_1 in context → CONDITIONAL (UTD)
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_obl1_not_applicable_when_not_annex_iii_point_1(self, art43_module, tmp_path):
        """OBL-1 → NOT_APPLICABLE when is_annex_iii_point_1=False."""
        ctx = _ctx_with("art43", {
            "has_internal_control_assessment": True,
            "has_change_management_procedures": True,
            "is_annex_iii_point_1": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art43_module.scan(str(tmp_path))
        obl = _find(result, "ART43-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_obl3_conditional_when_no_context(self, art43_module, tmp_path):
        """OBL-3 has scope_limitation → CONDITIONAL when is_annex_i_product not provided."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art43_module.scan(str(tmp_path))
        obl = _find(result, "ART43-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_obl3_not_applicable_when_not_annex_i(self, art43_module, tmp_path):
        """OBL-3 → NOT_APPLICABLE when is_annex_i_product=False."""
        ctx = _ctx_with("art43", {
            "has_internal_control_assessment": True,
            "has_change_management_procedures": True,
            "is_annex_i_product": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art43_module.scan(str(tmp_path))
        obl = _find(result, "ART43-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE


# ── Structural tests ──

class TestArt43Structural:

    def test_all_4_obligation_ids_in_json(self, art43_module):
        """Obligation JSON must have exactly 4 obligations."""
        data = art43_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 4

    def test_obligation_coverage_present(self, art43_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art43_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art43_module, tmp_path):
        """When AI provides no answers, all obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art43_module.scan(str(tmp_path))
        all_ids = ["ART43-OBL-1", "ART43-OBL-2", "ART43-OBL-3", "ART43-OBL-4"]
        for obl_id in all_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art43_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 43(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art43_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art43_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art43_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art43_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art43_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_4_obligations_appear_in_findings(self, art43_module, tmp_path):
        """All 4 obligations must appear in findings (explicit or gap)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art43_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART43-OBL-1", "ART43-OBL-2", "ART43-OBL-3", "ART43-OBL-4"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"
