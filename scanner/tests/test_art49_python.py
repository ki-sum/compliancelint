"""Art. 49 Registration tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_eu_database_registration → ART49-OBL-1
  gap_findings (conditional)   → ART49-OBL-2 (context_skip_field: claims_art6_3_exception)
  gap_findings (conditional)   → ART49-OBL-3 (context_skip_field: is_public_authority)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art49", {
        "has_eu_database_registration": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art49", {
        "has_eu_database_registration": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art49", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART49-OBL-1: Provider and system registration (has_eu_database_registration) ──

class TestArt49Obl1:

    def test_true_gives_partial(self, art49_module, tmp_path):
        """has_eu_database_registration=True → ART49-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art49_module.scan(str(tmp_path))
        obl = _find(result, "ART49-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art49_module, tmp_path):
        """has_eu_database_registration=False → ART49-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art49_module.scan(str(tmp_path))
        obl = _find(result, "ART49-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art49_module, tmp_path):
        """has_eu_database_registration=None → ART49-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art49_module.scan(str(tmp_path))
        obl = _find(result, "ART49-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART49-OBL-2: Art. 6(3) exception registration (conditional, via gap_findings) ──

class TestArt49Obl2:

    def test_conditional_utd_when_field_absent(self, art49_module, tmp_path):
        """ART49-OBL-2 → UNABLE_TO_DETERMINE [CONDITIONAL] when claims_art6_3_exception not provided."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art49_module.scan(str(tmp_path))
        obl = _find(result, "ART49-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_not_applicable_when_skip_false(self, art49_module, tmp_path):
        """ART49-OBL-2 → NOT_APPLICABLE when claims_art6_3_exception=false."""
        ctx = _ctx_with("art49", {
            "has_eu_database_registration": True,
            "claims_art6_3_exception": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art49_module.scan(str(tmp_path))
        obl = _find(result, "ART49-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE


# ── ART49-OBL-3: Public authority deployer registration (conditional, via gap_findings) ──

class TestArt49Obl3:

    def test_conditional_utd_when_field_absent(self, art49_module, tmp_path):
        """ART49-OBL-3 → UNABLE_TO_DETERMINE [CONDITIONAL] when is_public_authority not provided."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art49_module.scan(str(tmp_path))
        obl = _find(result, "ART49-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_not_applicable_when_skip_false(self, art49_module, tmp_path):
        """ART49-OBL-3 → NOT_APPLICABLE when is_public_authority=false."""
        ctx = _ctx_with("art49", {
            "has_eu_database_registration": True,
            "is_public_authority": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art49_module.scan(str(tmp_path))
        obl = _find(result, "ART49-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE


# ── Structural tests ──

class TestArt49Structural:

    def test_all_3_obligation_ids_in_json(self, art49_module):
        """Obligation JSON must have exactly 3 obligations."""
        data = art49_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 3

    def test_obligation_coverage_present(self, art49_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art49_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art49_module, tmp_path):
        """When AI provides no answers, all obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art49_module.scan(str(tmp_path))
        all_ids = ["ART49-OBL-1", "ART49-OBL-2", "ART49-OBL-3"]
        for obl_id in all_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art49_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 49(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art49_module.scan(str(tmp_path))
        for f in result.findings:
            # Skip informational gap findings which use [CONDITIONAL]/[APPLICABLE] prefix
            if f.is_informational:
                continue
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art49_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art49_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art49_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art49_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_3_obligations_appear_in_findings(self, art49_module, tmp_path):
        """All 3 obligations must appear in findings (explicit or gap)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art49_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART49-OBL-1", "ART49-OBL-2", "ART49-OBL-3"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"
