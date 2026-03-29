"""Art. 10 Data and Data Governance tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_data_governance_doc → ART10-OBL-1 (quality criteria), ART10-OBL-2 (governance practices)
  has_bias_mitigation     → ART10-OBL-2f (bias examination), ART10-OBL-2g (bias measures)
  Manual (always UTD)     → ART10-OBL-2h, OBL-3, OBL-3b, OBL-4
  Permissions (gap)       → ART10-PERM-3, ART10-PERM-5
  Scope rule (gap)        → ART10-OBL-6
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art10", {
        "has_data_governance_doc": True,
        "data_doc_paths": ["docs/data_sheet.md"],
        "has_bias_mitigation": True,
        "bias_evidence": ["fairlearn"],
        "has_data_lineage": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art10", {
        "has_data_governance_doc": False,
        "data_doc_paths": [],
        "has_bias_mitigation": False,
        "bias_evidence": [],
        "has_data_lineage": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art10", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART10-OBL-1: Data quality criteria (has_data_governance_doc) ──

class TestArt10Obl1:

    def test_has_data_doc_true_gives_partial(self, art10_module, tmp_path):
        """has_data_governance_doc=True → ART10-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art10_module.scan(str(tmp_path))
        obl = _find(result, "ART10-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_data_doc_false_gives_non_compliant(self, art10_module, tmp_path):
        """has_data_governance_doc=False → ART10-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art10_module.scan(str(tmp_path))
        obl = _find(result, "ART10-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_data_doc_none_gives_utd(self, art10_module, tmp_path):
        """has_data_governance_doc=None → ART10-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art10_module.scan(str(tmp_path))
        obl = _find(result, "ART10-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART10-OBL-2: Data governance practices a-e (has_data_governance_doc) ──

class TestArt10Obl2:

    def test_has_data_doc_true_gives_partial(self, art10_module, tmp_path):
        """has_data_governance_doc=True → ART10-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art10_module.scan(str(tmp_path))
        obl = _find(result, "ART10-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_data_doc_false_gives_non_compliant(self, art10_module, tmp_path):
        """has_data_governance_doc=False → ART10-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art10_module.scan(str(tmp_path))
        obl = _find(result, "ART10-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_data_doc_none_gives_utd(self, art10_module, tmp_path):
        """has_data_governance_doc=None → ART10-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art10_module.scan(str(tmp_path))
        obl = _find(result, "ART10-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART10-OBL-2f: Bias examination (has_bias_mitigation) ──

class TestArt10Obl2f:

    def test_has_bias_true_gives_partial(self, art10_module, tmp_path):
        """has_bias_mitigation=True → ART10-OBL-2f PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art10_module.scan(str(tmp_path))
        obl = _find(result, "ART10-OBL-2f")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_bias_false_gives_non_compliant(self, art10_module, tmp_path):
        """has_bias_mitigation=False → ART10-OBL-2f NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art10_module.scan(str(tmp_path))
        obl = _find(result, "ART10-OBL-2f")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_bias_none_gives_utd(self, art10_module, tmp_path):
        """has_bias_mitigation=None → ART10-OBL-2f UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art10_module.scan(str(tmp_path))
        obl = _find(result, "ART10-OBL-2f")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART10-OBL-2g: Bias mitigation measures (has_bias_mitigation) ──

class TestArt10Obl2g:

    def test_has_bias_true_gives_partial(self, art10_module, tmp_path):
        """has_bias_mitigation=True → ART10-OBL-2g PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art10_module.scan(str(tmp_path))
        obl = _find(result, "ART10-OBL-2g")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_bias_false_gives_non_compliant(self, art10_module, tmp_path):
        """has_bias_mitigation=False → ART10-OBL-2g NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art10_module.scan(str(tmp_path))
        obl = _find(result, "ART10-OBL-2g")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_bias_none_gives_utd(self, art10_module, tmp_path):
        """has_bias_mitigation=None → ART10-OBL-2g UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art10_module.scan(str(tmp_path))
        obl = _find(result, "ART10-OBL-2g")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Manual obligations: always UNABLE_TO_DETERMINE ──

class TestArt10ManualObligations:

    def test_manual_obligations_always_utd_with_all_true(self, art10_module, tmp_path):
        """Manual obligations always UTD even with all-true answers."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art10_module.scan(str(tmp_path))
        manual_ids = ["ART10-OBL-2h", "ART10-OBL-3", "ART10-OBL-3b", "ART10-OBL-4"]
        for obl_id in manual_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should always be UTD, got {findings[0].level}"
            )

    def test_manual_obligations_always_utd_with_all_false(self, art10_module, tmp_path):
        """Manual obligations always UTD even with all-false answers."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art10_module.scan(str(tmp_path))
        manual_ids = ["ART10-OBL-2h", "ART10-OBL-3", "ART10-OBL-3b", "ART10-OBL-4"]
        for obl_id in manual_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should always be UTD, got {findings[0].level}"
            )


# ── Structural tests ──

class TestArt10Structural:

    def test_all_11_obligation_ids_in_json(self, art10_module):
        """Obligation JSON must have exactly 11 obligations."""
        data = art10_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 11

    def test_obligation_coverage_present(self, art10_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art10_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art10_module, tmp_path):
        """When AI provides no answers, key automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art10_module.scan(str(tmp_path))
        automatable_ids = [
            "ART10-OBL-1", "ART10-OBL-2",
            "ART10-OBL-2f", "ART10-OBL-2g",
        ]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art10_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 10(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art10_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art10_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art10_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art10_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art10_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0


# ── Alias tests ──

class TestArt10Aliases:

    def test_has_bias_detection_alias(self, art10_module, tmp_path):
        """has_bias_detection (alias for has_bias_mitigation) should work."""
        ctx = _ctx_with("art10", {
            "has_data_governance_doc": True,
            "has_bias_detection": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art10_module.scan(str(tmp_path))
        obl = _find(result, "ART10-OBL-2f")
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_data_versioning_alias(self, art10_module, tmp_path):
        """has_data_versioning (alias for has_data_lineage) should work."""
        ctx = _ctx_with("art10", {
            "has_data_governance_doc": True,
            "has_bias_mitigation": True,
            "has_data_versioning": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art10_module.scan(str(tmp_path))
        # has_data_lineage is not directly mapped to an obligation finding,
        # but should be stored in details
        assert result.details.get("has_data_lineage") is True
