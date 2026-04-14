"""Art. 72 Post-Market Monitoring by Providers tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_pmm_system              → ART72-OBL-1
  has_active_data_collection  → ART72-OBL-2
  has_pmm_plan                → ART72-OBL-3
  Conditional (permission)    → ART72-PER-1 (is_annex_i_product)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art72", {
        "has_pmm_system": True,
        "has_active_data_collection": True,
        "has_pmm_plan": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art72", {
        "has_pmm_system": False,
        "has_active_data_collection": False,
        "has_pmm_plan": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art72", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART72-OBL-1: PMM system (has_pmm_system) ──

class TestArt72Obl1:

    def test_has_pmm_system_true_gives_partial(self, art72_module, tmp_path):
        """has_pmm_system=True → ART72-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art72_module.scan(str(tmp_path))
        obl = _find(result, "ART72-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_pmm_system_false_gives_non_compliant(self, art72_module, tmp_path):
        """has_pmm_system=False → ART72-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art72_module.scan(str(tmp_path))
        obl = _find(result, "ART72-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_pmm_system_none_gives_utd(self, art72_module, tmp_path):
        """has_pmm_system=None → ART72-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art72_module.scan(str(tmp_path))
        obl = _find(result, "ART72-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART72-OBL-2: Active data collection (has_active_data_collection) ──

class TestArt72Obl2:

    def test_has_data_collection_true_gives_partial(self, art72_module, tmp_path):
        """has_active_data_collection=True → ART72-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art72_module.scan(str(tmp_path))
        obl = _find(result, "ART72-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_data_collection_false_gives_non_compliant(self, art72_module, tmp_path):
        """has_active_data_collection=False → ART72-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art72_module.scan(str(tmp_path))
        obl = _find(result, "ART72-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_data_collection_none_gives_utd(self, art72_module, tmp_path):
        """has_active_data_collection=None → ART72-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art72_module.scan(str(tmp_path))
        obl = _find(result, "ART72-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART72-OBL-3: PMM plan (has_pmm_plan) ──

class TestArt72Obl3:

    def test_has_pmm_plan_true_gives_partial(self, art72_module, tmp_path):
        """has_pmm_plan=True → ART72-OBL-3 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art72_module.scan(str(tmp_path))
        obl = _find(result, "ART72-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_pmm_plan_false_gives_non_compliant(self, art72_module, tmp_path):
        """has_pmm_plan=False → ART72-OBL-3 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art72_module.scan(str(tmp_path))
        obl = _find(result, "ART72-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_pmm_plan_none_gives_utd(self, art72_module, tmp_path):
        """has_pmm_plan=None → ART72-OBL-3 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art72_module.scan(str(tmp_path))
        obl = _find(result, "ART72-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Conditional obligations: scope_limitation handling ──

class TestArt72ConditionalObligations:

    def test_per1_permission_skipped(self, art72_module, tmp_path):
        """PER-1 is a permission (right, not obligation) → no finding generated."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art72_module.scan(str(tmp_path))
        obl = _find(result, "ART72-PER-1")
        assert len(obl) == 0, "Permissions should not generate findings"

    def test_per1_permission_skipped_even_with_context(self, art72_module, tmp_path):
        """PER-1 → skipped even when context provides is_annex_i_product=False."""
        ctx = _ctx_with("art72", {
            "has_pmm_system": True,
            "has_active_data_collection": True,
            "has_pmm_plan": True,
            "is_annex_i_product": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art72_module.scan(str(tmp_path))
        obl = _find(result, "ART72-PER-1")
        assert len(obl) == 0, "Permissions should not generate findings"


# ── Structural tests ──

class TestArt72Structural:

    def test_all_4_obligation_ids_in_json(self, art72_module):
        """Obligation JSON must have exactly 4 obligations."""
        data = art72_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 4

    def test_obligation_coverage_present(self, art72_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art72_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_automatable_obligations_utd(self, art72_module, tmp_path):
        """When AI provides no answers, automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art72_module.scan(str(tmp_path))
        automatable_ids = ["ART72-OBL-1", "ART72-OBL-2", "ART72-OBL-3"]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art72_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 72(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art72_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art72_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art72_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art72_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art72_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_4_obligations_appear_in_findings(self, art72_module, tmp_path):
        """All 4 obligations must appear in findings (explicit or gap)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art72_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART72-OBL-1", "ART72-OBL-2", "ART72-OBL-3"}  # PER-1 is a permission, skipped
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"
