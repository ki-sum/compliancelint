"""Art. 54 Authorised Representatives of Providers of GPAI Models tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  is_third_country_provider + has_authorised_representative → ART54-OBL-1 (_finding_from_answer, conditional)
  is_third_country_provider                                → ART54-OBL-3 (manual, always UTD when applicable)
  is_third_country_provider                                → ART54-OBL-5 (manual, always UTD when applicable)
  is_open_source_gpai                                      → ART54-EXC-6 (exception, custom Finding)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _third_country_true_ctx():
    """Third-country provider with authorised representative."""
    return _ctx_with("art54", {
        "is_third_country_provider": True,
        "has_authorised_representative": True,
        "representative_evidence": ["docs/authorised_representative.md"],
        "has_written_mandate": True,
        "mandate_evidence": ["docs/mandate.pdf"],
        "is_open_source_gpai": False,
        "has_systemic_risk": False,
    })


def _third_country_false_ctx():
    """Third-country provider WITHOUT authorised representative."""
    return _ctx_with("art54", {
        "is_third_country_provider": True,
        "has_authorised_representative": False,
        "has_written_mandate": False,
        "is_open_source_gpai": False,
        "has_systemic_risk": False,
    })


def _eu_provider_ctx():
    """EU-based provider — Art. 54 does not apply."""
    return _ctx_with("art54", {
        "is_third_country_provider": False,
        "has_authorised_representative": None,
        "is_open_source_gpai": False,
        "has_systemic_risk": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art54", {})


def _open_source_ctx():
    """Open-source GPAI without systemic risk — exception applies."""
    return _ctx_with("art54", {
        "is_third_country_provider": True,
        "has_authorised_representative": None,
        "is_open_source_gpai": True,
        "has_systemic_risk": False,
    })


def _open_source_systemic_risk_ctx():
    """Open-source GPAI WITH systemic risk — exception does NOT apply."""
    return _ctx_with("art54", {
        "is_third_country_provider": True,
        "has_authorised_representative": True,
        "is_open_source_gpai": True,
        "has_systemic_risk": True,
    })


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART54-OBL-1: Appoint authorised representative ──

class TestArt54Obl1:

    def test_third_country_with_rep_gives_partial(self, art54_module, tmp_path):
        """Third-country + has_authorised_representative=True → ART54-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_third_country_true_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_third_country_without_rep_gives_non_compliant(self, art54_module, tmp_path):
        """Third-country + has_authorised_representative=False → ART54-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_third_country_false_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_eu_provider_gives_na(self, art54_module, tmp_path):
        """EU-based provider → ART54-OBL-1 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_eu_provider_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_none_gives_utd(self, art54_module, tmp_path):
        """is_third_country_provider=None → ART54-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_open_source_exception_makes_na(self, art54_module, tmp_path):
        """Open-source GPAI without systemic risk → ART54-OBL-1 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_open_source_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_open_source_with_systemic_risk_still_applies(self, art54_module, tmp_path):
        """Open-source WITH systemic risk → OBL-1 still PARTIAL (exception revoked)."""
        BaseArticleModule.set_context(_open_source_systemic_risk_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL


# ── ART54-OBL-3: Mandate tasks and AI Office cooperation ──

class TestArt54Obl3:

    def test_third_country_gives_utd(self, art54_module, tmp_path):
        """Third-country provider → ART54-OBL-3 always UNABLE_TO_DETERMINE (manual)."""
        BaseArticleModule.set_context(_third_country_true_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_eu_provider_gives_na(self, art54_module, tmp_path):
        """EU-based provider → ART54-OBL-3 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_eu_provider_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_unknown_gives_utd(self, art54_module, tmp_path):
        """is_third_country_provider=None → ART54-OBL-3 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_open_source_exception_makes_na(self, art54_module, tmp_path):
        """Open-source GPAI without systemic risk → ART54-OBL-3 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_open_source_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE


# ── ART54-OBL-5: Mandate termination obligation ──

class TestArt54Obl5:

    def test_third_country_gives_utd(self, art54_module, tmp_path):
        """Third-country provider → ART54-OBL-5 always UNABLE_TO_DETERMINE (manual)."""
        BaseArticleModule.set_context(_third_country_true_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_eu_provider_gives_na(self, art54_module, tmp_path):
        """EU-based provider → ART54-OBL-5 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_eu_provider_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_unknown_gives_utd(self, art54_module, tmp_path):
        """is_third_country_provider=None → ART54-OBL-5 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_open_source_exception_makes_na(self, art54_module, tmp_path):
        """Open-source GPAI without systemic risk → ART54-OBL-5 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_open_source_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE


# ── ART54-EXC-6: Open-source exception ──

class TestArt54Exc6:

    def test_open_source_no_systemic_risk_compliant(self, art54_module, tmp_path):
        """Open-source without systemic risk → ART54-EXC-6 COMPLIANT."""
        BaseArticleModule.set_context(_open_source_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-EXC-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.COMPLIANT

    def test_open_source_with_systemic_risk_non_compliant(self, art54_module, tmp_path):
        """Open-source WITH systemic risk → ART54-EXC-6 NON_COMPLIANT."""
        BaseArticleModule.set_context(_open_source_systemic_risk_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-EXC-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_not_open_source_gives_na(self, art54_module, tmp_path):
        """Not open-source → ART54-EXC-6 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_third_country_true_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-EXC-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_unknown_gives_utd(self, art54_module, tmp_path):
        """is_open_source_gpai=None → ART54-EXC-6 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art54_module.scan(str(tmp_path))
        obl = _find(result, "ART54-EXC-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt54Structural:

    def test_all_4_obligation_ids_in_json(self, art54_module):
        """Obligation JSON must have exactly 6 obligations."""
        data = art54_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 6

    def test_obligation_coverage_present(self, art54_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art54_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art54_module, tmp_path):
        """When AI provides no answers, all obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art54_module.scan(str(tmp_path))
        utd_ids = ["ART54-OBL-1", "ART54-OBL-3", "ART54-OBL-5", "ART54-EXC-6"]
        for obl_id in utd_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art54_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 54(1)]."""
        BaseArticleModule.set_context(_third_country_true_ctx())
        result = art54_module.scan(str(tmp_path))
        for f in result.findings:
            if f.is_informational:
                continue
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_4_obligations_appear_in_findings(self, art54_module, tmp_path):
        """All 4 obligations must appear in findings (explicit or gap)."""
        BaseArticleModule.set_context(_third_country_true_ctx())
        result = art54_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART54-OBL-1", "ART54-OBL-3", "ART54-OBL-5", "ART54-EXC-6"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"

    def test_uses_finding_from_answer(self, art54_module):
        """Module must use _finding_from_answer() (gate check)."""
        import inspect
        source = inspect.getsource(art54_module.__class__.scan)
        assert "_finding_from_answer" in source, (
            "Module must use _finding_from_answer() for provider obligations"
        )
