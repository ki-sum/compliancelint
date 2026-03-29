"""Art. 55 Obligations of Providers of GPAI Models with Systemic Risk tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_model_evaluation + has_adversarial_testing → ART55-OBL-1a (_finding_from_answer)
  (systemic risk assessment)                    → ART55-OBL-1b (manual, always UTD when applicable)
  has_incident_tracking                         → ART55-OBL-1c (_finding_from_answer)
  has_cybersecurity_protection                  → ART55-OBL-1d (_finding_from_answer)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _systemic_risk_all_true_ctx():
    """GPAI with systemic risk, all obligations met."""
    return _ctx_with("art55", {
        "has_systemic_risk": True,
        "has_model_evaluation": True,
        "has_adversarial_testing": True,
        "evaluation_evidence": ["docs/model_evaluation.md", "tests/adversarial/"],
        "has_incident_tracking": True,
        "incident_evidence": ["docs/incident_response.md"],
        "has_cybersecurity_protection": True,
        "cybersecurity_evidence": ["docs/security_policy.md"],
    })


def _systemic_risk_all_false_ctx():
    """GPAI with systemic risk, no obligations met."""
    return _ctx_with("art55", {
        "has_systemic_risk": True,
        "has_model_evaluation": False,
        "has_adversarial_testing": False,
        "has_incident_tracking": False,
        "has_cybersecurity_protection": False,
    })


def _no_systemic_risk_ctx():
    """GPAI without systemic risk — Art. 55 does not apply."""
    return _ctx_with("art55", {
        "has_systemic_risk": False,
        "has_model_evaluation": None,
        "has_adversarial_testing": None,
        "has_incident_tracking": None,
        "has_cybersecurity_protection": None,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art55", {})


def _partial_eval_ctx():
    """Has model evaluation but no adversarial testing."""
    return _ctx_with("art55", {
        "has_systemic_risk": True,
        "has_model_evaluation": True,
        "has_adversarial_testing": False,
        "has_incident_tracking": True,
        "has_cybersecurity_protection": True,
    })


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART55-OBL-1a: Model evaluation and adversarial testing ──

class TestArt55Obl1a:

    def test_both_true_gives_partial(self, art55_module, tmp_path):
        """has_model_evaluation=True + has_adversarial_testing=True → PARTIAL."""
        BaseArticleModule.set_context(_systemic_risk_all_true_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_both_false_gives_non_compliant(self, art55_module, tmp_path):
        """has_model_evaluation=False + has_adversarial_testing=False → NON_COMPLIANT."""
        BaseArticleModule.set_context(_systemic_risk_all_false_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_eval_true_adversarial_false_gives_non_compliant(self, art55_module, tmp_path):
        """has_model_evaluation=True + has_adversarial_testing=False → NON_COMPLIANT."""
        BaseArticleModule.set_context(_partial_eval_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_no_systemic_risk_gives_na(self, art55_module, tmp_path):
        """has_systemic_risk=False → ART55-OBL-1a NOT_APPLICABLE."""
        BaseArticleModule.set_context(_no_systemic_risk_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_none_gives_utd(self, art55_module, tmp_path):
        """All None → ART55-OBL-1a UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART55-OBL-1b: Systemic risk assessment (always manual / UTD) ──

class TestArt55Obl1b:

    def test_systemic_risk_always_utd(self, art55_module, tmp_path):
        """ART55-OBL-1b always UNABLE_TO_DETERMINE (manual obligation)."""
        BaseArticleModule.set_context(_systemic_risk_all_true_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_no_systemic_risk_gives_na(self, art55_module, tmp_path):
        """has_systemic_risk=False → ART55-OBL-1b NOT_APPLICABLE."""
        BaseArticleModule.set_context(_no_systemic_risk_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_unknown_systemic_risk_gives_utd(self, art55_module, tmp_path):
        """has_systemic_risk=None → ART55-OBL-1b UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART55-OBL-1c: Incident tracking and reporting ──

class TestArt55Obl1c:

    def test_tracking_true_gives_partial(self, art55_module, tmp_path):
        """has_incident_tracking=True → ART55-OBL-1c PARTIAL."""
        BaseArticleModule.set_context(_systemic_risk_all_true_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1c")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_tracking_false_gives_non_compliant(self, art55_module, tmp_path):
        """has_incident_tracking=False → ART55-OBL-1c NON_COMPLIANT."""
        BaseArticleModule.set_context(_systemic_risk_all_false_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1c")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_no_systemic_risk_gives_na(self, art55_module, tmp_path):
        """has_systemic_risk=False → ART55-OBL-1c NOT_APPLICABLE."""
        BaseArticleModule.set_context(_no_systemic_risk_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1c")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_none_gives_utd(self, art55_module, tmp_path):
        """has_incident_tracking=None → ART55-OBL-1c UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1c")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART55-OBL-1d: Cybersecurity protection ──

class TestArt55Obl1d:

    def test_cyber_true_gives_partial(self, art55_module, tmp_path):
        """has_cybersecurity_protection=True → ART55-OBL-1d PARTIAL."""
        BaseArticleModule.set_context(_systemic_risk_all_true_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_cyber_false_gives_non_compliant(self, art55_module, tmp_path):
        """has_cybersecurity_protection=False → ART55-OBL-1d NON_COMPLIANT."""
        BaseArticleModule.set_context(_systemic_risk_all_false_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_no_systemic_risk_gives_na(self, art55_module, tmp_path):
        """has_systemic_risk=False → ART55-OBL-1d NOT_APPLICABLE."""
        BaseArticleModule.set_context(_no_systemic_risk_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_none_gives_utd(self, art55_module, tmp_path):
        """has_cybersecurity_protection=None → ART55-OBL-1d UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art55_module.scan(str(tmp_path))
        obl = _find(result, "ART55-OBL-1d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt55Structural:

    def test_all_4_obligation_ids_in_json(self, art55_module):
        """Obligation JSON must have exactly 6 obligations."""
        data = art55_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 6

    def test_obligation_coverage_present(self, art55_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art55_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art55_module, tmp_path):
        """When AI provides no answers, all obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art55_module.scan(str(tmp_path))
        utd_ids = ["ART55-OBL-1a", "ART55-OBL-1b", "ART55-OBL-1c", "ART55-OBL-1d"]
        for obl_id in utd_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art55_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 55(1)]."""
        BaseArticleModule.set_context(_systemic_risk_all_true_ctx())
        result = art55_module.scan(str(tmp_path))
        for f in result.findings:
            if f.is_informational:
                continue
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_4_obligations_appear_in_findings(self, art55_module, tmp_path):
        """All 4 obligations must appear in findings (explicit or gap)."""
        BaseArticleModule.set_context(_systemic_risk_all_true_ctx())
        result = art55_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART55-OBL-1a", "ART55-OBL-1b", "ART55-OBL-1c", "ART55-OBL-1d"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"

    def test_uses_finding_from_answer(self, art55_module):
        """Module must use _finding_from_answer() (gate check)."""
        import inspect
        source = inspect.getsource(art55_module.__class__.scan)
        assert "_finding_from_answer" in source, (
            "Module must use _finding_from_answer() for provider obligations"
        )

    def test_no_systemic_risk_all_na(self, art55_module, tmp_path):
        """has_systemic_risk=False → all 4 obligations NOT_APPLICABLE."""
        BaseArticleModule.set_context(_no_systemic_risk_ctx())
        result = art55_module.scan(str(tmp_path))
        for obl_id in ["ART55-OBL-1a", "ART55-OBL-1b", "ART55-OBL-1c", "ART55-OBL-1d"]:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.NOT_APPLICABLE, (
                f"{obl_id} should be NA without systemic risk, got {findings[0].level}"
            )
