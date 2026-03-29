"""Art. 22 Authorised representatives tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  is_eu_established_provider=True   → ART22-OBL-1/2/4 NOT_APPLICABLE
  has_authorised_representative     → ART22-OBL-1
  has_representative_enablement     → ART22-OBL-2
  has_mandate_authority_contact     → ART22-OBL-4
  ART22-OBL-3                      → always gap finding (manual, authorised_representative)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _non_eu_true_ctx():
    """Non-EU provider with all automatable fields True."""
    return _ctx_with("art22", {
        "is_eu_established_provider": False,
        "has_authorised_representative": True,
        "has_representative_enablement": True,
        "has_mandate_authority_contact": True,
    })


def _non_eu_false_ctx():
    """Non-EU provider with all automatable fields False."""
    return _ctx_with("art22", {
        "is_eu_established_provider": False,
        "has_authorised_representative": False,
        "has_representative_enablement": False,
        "has_mandate_authority_contact": False,
    })


def _eu_provider_ctx():
    """EU-established provider — Art. 22 obligations are NOT_APPLICABLE."""
    return _ctx_with("art22", {
        "is_eu_established_provider": True,
        "has_authorised_representative": None,
        "has_representative_enablement": None,
        "has_mandate_authority_contact": None,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art22", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART22-OBL-1: Appoint authorised representative ──

class TestArt22Obl1:

    def test_has_representative_true_gives_partial(self, art22_module, tmp_path):
        """has_authorised_representative=True → ART22-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_non_eu_true_ctx())
        result = art22_module.scan(str(tmp_path))
        obl = _find(result, "ART22-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_representative_false_gives_non_compliant(self, art22_module, tmp_path):
        """has_authorised_representative=False → ART22-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_non_eu_false_ctx())
        result = art22_module.scan(str(tmp_path))
        obl = _find(result, "ART22-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_representative_none_gives_utd(self, art22_module, tmp_path):
        """has_authorised_representative=None → ART22-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art22_module.scan(str(tmp_path))
        obl = _find(result, "ART22-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART22-OBL-2: Enable representative to perform tasks ──

class TestArt22Obl2:

    def test_has_enablement_true_gives_partial(self, art22_module, tmp_path):
        """has_representative_enablement=True → ART22-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_non_eu_true_ctx())
        result = art22_module.scan(str(tmp_path))
        obl = _find(result, "ART22-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_enablement_false_gives_non_compliant(self, art22_module, tmp_path):
        """has_representative_enablement=False → ART22-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_non_eu_false_ctx())
        result = art22_module.scan(str(tmp_path))
        obl = _find(result, "ART22-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_enablement_none_gives_utd(self, art22_module, tmp_path):
        """has_representative_enablement=None → ART22-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art22_module.scan(str(tmp_path))
        obl = _find(result, "ART22-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART22-OBL-4: Mandate authority contact ��─

class TestArt22Obl4:

    def test_has_mandate_contact_true_gives_partial(self, art22_module, tmp_path):
        """has_mandate_authority_contact=True → ART22-OBL-4 PARTIAL."""
        BaseArticleModule.set_context(_non_eu_true_ctx())
        result = art22_module.scan(str(tmp_path))
        obl = _find(result, "ART22-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_mandate_contact_false_gives_non_compliant(self, art22_module, tmp_path):
        """has_mandate_authority_contact=False → ART22-OBL-4 NON_COMPLIANT."""
        BaseArticleModule.set_context(_non_eu_false_ctx())
        result = art22_module.scan(str(tmp_path))
        obl = _find(result, "ART22-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_mandate_contact_none_gives_utd(self, art22_module, tmp_path):
        """has_mandate_authority_contact=None → ART22-OBL-4 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art22_module.scan(str(tmp_path))
        obl = _find(result, "ART22-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── EU-established provider tests ──

class TestArt22EuProvider:

    def test_eu_provider_obl1_not_applicable(self, art22_module, tmp_path):
        """is_eu_established_provider=True → ART22-OBL-1 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_eu_provider_ctx())
        result = art22_module.scan(str(tmp_path))
        obl = _find(result, "ART22-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_eu_provider_obl2_not_applicable(self, art22_module, tmp_path):
        """is_eu_established_provider=True ��� ART22-OBL-2 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_eu_provider_ctx())
        result = art22_module.scan(str(tmp_path))
        obl = _find(result, "ART22-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_eu_provider_obl4_not_applicable(self, art22_module, tmp_path):
        """is_eu_established_provider=True → ART22-OBL-4 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_eu_provider_ctx())
        result = art22_module.scan(str(tmp_path))
        obl = _find(result, "ART22-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE


# ── Structural tests ──

class TestArt22Structural:

    def test_all_4_obligation_ids_in_json(self, art22_module):
        """Obligation JSON must have exactly 4 obligations."""
        data = art22_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 4

    def test_obligation_coverage_present(self, art22_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art22_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_automatable_obligations_utd(self, art22_module, tmp_path):
        """When AI provides no answers, automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art22_module.scan(str(tmp_path))
        automatable_ids = ["ART22-OBL-1", "ART22-OBL-2", "ART22-OBL-4"]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art22_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 22(1)]."""
        BaseArticleModule.set_context(_non_eu_true_ctx())
        result = art22_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art22_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_non_eu_true_ctx())
        result = art22_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art22_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_non_eu_false_ctx())
        result = art22_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_obligation_findings_present(self, art22_module, tmp_path):
        """All 4 obligations must appear in findings."""
        BaseArticleModule.set_context(_non_eu_true_ctx())
        result = art22_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART22-OBL-1", "ART22-OBL-2", "ART22-OBL-3", "ART22-OBL-4"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"

    def test_obl3_is_gap_finding(self, art22_module, tmp_path):
        """ART22-OBL-3 (manual, authorised_representative) appears as gap finding."""
        BaseArticleModule.set_context(_non_eu_true_ctx())
        result = art22_module.scan(str(tmp_path))
        obl3 = _find(result, "ART22-OBL-3")
        assert len(obl3) > 0
        assert obl3[0].level == ComplianceLevel.UNABLE_TO_DETERMINE
