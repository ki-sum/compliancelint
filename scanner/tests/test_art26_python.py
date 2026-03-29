"""Art. 26 Obligations of Deployers of High-Risk AI Systems tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_deployment_documentation     → ART26-OBL-1
  has_human_oversight_assignment   → ART26-OBL-2
  has_operational_monitoring       → ART26-OBL-5
  has_log_retention + retention_days → ART26-OBL-6
  has_affected_persons_notification → ART26-OBL-11
  Conditional (scope_limitation)   → ART26-OBL-4, OBL-7, OBL-8, OBL-9, OBL-10
  Manual (always UTD)              → ART26-OBL-12
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art26", {
        "has_deployment_documentation": True,
        "has_human_oversight_assignment": True,
        "has_operational_monitoring": True,
        "has_log_retention": True,
        "retention_days": 365,
        "retention_evidence": "logrotate configured",
        "has_affected_persons_notification": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art26", {
        "has_deployment_documentation": False,
        "has_human_oversight_assignment": False,
        "has_operational_monitoring": False,
        "has_log_retention": False,
        "retention_days": None,
        "retention_evidence": "",
        "has_affected_persons_notification": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art26", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART26-OBL-1: Use per instructions (has_deployment_documentation) ──

class TestArt26Obl1:

    def test_has_deployment_doc_true_gives_partial(self, art26_module, tmp_path):
        """has_deployment_documentation=True → ART26-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_deployment_doc_false_gives_non_compliant(self, art26_module, tmp_path):
        """has_deployment_documentation=False → ART26-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_deployment_doc_none_gives_utd(self, art26_module, tmp_path):
        """has_deployment_documentation=None → ART26-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART26-OBL-2: Human oversight assignment (has_human_oversight_assignment) ──

class TestArt26Obl2:

    def test_true_gives_partial(self, art26_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art26_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art26_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART26-OBL-5: Operational monitoring (has_operational_monitoring) ──

class TestArt26Obl5:

    def test_true_gives_partial(self, art26_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art26_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art26_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART26-OBL-6: Log retention (has_log_retention + retention_days) ──

class TestArt26Obl6:

    def test_retention_true_365_days_gives_partial(self, art26_module, tmp_path):
        """has_log_retention=True, retention_days=365 → PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_retention_false_gives_non_compliant(self, art26_module, tmp_path):
        """has_log_retention=False → NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_retention_none_gives_utd(self, art26_module, tmp_path):
        """has_log_retention=None → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_retention_true_below_180_gives_non_compliant(self, art26_module, tmp_path):
        """has_log_retention=True, retention_days=30 → NON_COMPLIANT."""
        ctx = _ctx_with("art26", {
            "has_deployment_documentation": True,
            "has_human_oversight_assignment": True,
            "has_operational_monitoring": True,
            "has_log_retention": True,
            "retention_days": 30,
            "has_affected_persons_notification": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_retention_true_exactly_180_gives_partial(self, art26_module, tmp_path):
        """has_log_retention=True, retention_days=180 → PARTIAL."""
        ctx = _ctx_with("art26", {
            "has_deployment_documentation": True,
            "has_human_oversight_assignment": True,
            "has_operational_monitoring": True,
            "has_log_retention": True,
            "retention_days": 180,
            "has_affected_persons_notification": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_retention_true_no_days_gives_partial(self, art26_module, tmp_path):
        """has_log_retention=True, retention_days=None → PARTIAL (period unknown)."""
        ctx = _ctx_with("art26", {
            "has_deployment_documentation": True,
            "has_human_oversight_assignment": True,
            "has_operational_monitoring": True,
            "has_log_retention": True,
            "retention_days": None,
            "has_affected_persons_notification": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_retention_true_179_gives_non_compliant(self, art26_module, tmp_path):
        """has_log_retention=True, retention_days=179 (just below threshold) → NON_COMPLIANT."""
        ctx = _ctx_with("art26", {
            "has_deployment_documentation": True,
            "has_human_oversight_assignment": True,
            "has_operational_monitoring": True,
            "has_log_retention": True,
            "retention_days": 179,
            "has_affected_persons_notification": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT


# ── ART26-OBL-11: Affected persons notification (has_affected_persons_notification) ──

class TestArt26Obl11:

    def test_true_gives_partial(self, art26_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-11")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art26_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-11")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art26_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-11")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Conditional obligations: scope_limitation handling ──

class TestArt26ConditionalObligations:

    def test_obl4_conditional_when_no_context(self, art26_module, tmp_path):
        """OBL-4 has scope_limitation → CONDITIONAL when no context for deployer_controls_input_data."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-4")
        assert len(obl) > 0
        # Without deployer_controls_input_data in context → CONDITIONAL (UTD)
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_obl4_not_applicable_when_no_input_control(self, art26_module, tmp_path):
        """OBL-4 → NOT_APPLICABLE when deployer_controls_input_data=False."""
        ctx = _ctx_with("art26", {
            "has_deployment_documentation": True,
            "has_human_oversight_assignment": True,
            "has_operational_monitoring": True,
            "has_log_retention": True,
            "retention_days": 365,
            "has_affected_persons_notification": True,
            "deployer_controls_input_data": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_obl7_conditional_when_no_context(self, art26_module, tmp_path):
        """OBL-7 has scope_limitation → CONDITIONAL when is_workplace_deployment not provided."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-7")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_obl7_not_applicable_when_not_workplace(self, art26_module, tmp_path):
        """OBL-7 → NOT_APPLICABLE when is_workplace_deployment=False."""
        ctx = _ctx_with("art26", {
            "has_deployment_documentation": True,
            "has_human_oversight_assignment": True,
            "has_operational_monitoring": True,
            "has_log_retention": True,
            "retention_days": 365,
            "has_affected_persons_notification": True,
            "is_workplace_deployment": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-7")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_obl8_not_applicable_when_not_public_authority(self, art26_module, tmp_path):
        """OBL-8 → NOT_APPLICABLE when is_public_authority=False."""
        ctx = _ctx_with("art26", {
            "has_deployment_documentation": True,
            "has_human_oversight_assignment": True,
            "has_operational_monitoring": True,
            "has_log_retention": True,
            "retention_days": 365,
            "has_affected_persons_notification": True,
            "is_public_authority": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-8")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_obl9_not_applicable_when_no_dpia(self, art26_module, tmp_path):
        """OBL-9 → NOT_APPLICABLE when requires_dpia=False."""
        ctx = _ctx_with("art26", {
            "has_deployment_documentation": True,
            "has_human_oversight_assignment": True,
            "has_operational_monitoring": True,
            "has_log_retention": True,
            "retention_days": 365,
            "has_affected_persons_notification": True,
            "requires_dpia": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-9")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_obl10_not_applicable_when_not_biometric(self, art26_module, tmp_path):
        """OBL-10 → NOT_APPLICABLE when is_post_remote_biometric_id=False."""
        ctx = _ctx_with("art26", {
            "has_deployment_documentation": True,
            "has_human_oversight_assignment": True,
            "has_operational_monitoring": True,
            "has_log_retention": True,
            "retention_days": 365,
            "has_affected_persons_notification": True,
            "is_post_remote_biometric_id": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-10")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE


# ── Manual obligations: always UNABLE_TO_DETERMINE ──

class TestArt26ManualObligations:

    def test_obl12_always_utd_with_all_true(self, art26_module, tmp_path):
        """OBL-12 (authority cooperation) always UTD even with all-true answers."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-12")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_obl12_always_utd_with_all_false(self, art26_module, tmp_path):
        """OBL-12 (authority cooperation) always UTD even with all-false answers."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art26_module.scan(str(tmp_path))
        obl = _find(result, "ART26-OBL-12")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt26Structural:

    def test_all_11_obligation_ids_in_json(self, art26_module):
        """Obligation JSON must have exactly 11 obligations."""
        data = art26_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 11

    def test_obligation_coverage_present(self, art26_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art26_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art26_module, tmp_path):
        """When AI provides no answers, key automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art26_module.scan(str(tmp_path))
        automatable_ids = [
            "ART26-OBL-1", "ART26-OBL-2", "ART26-OBL-5", "ART26-OBL-6", "ART26-OBL-11",
        ]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art26_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 26(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art26_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art26_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art26_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art26_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art26_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_11_obligations_appear_in_findings(self, art26_module, tmp_path):
        """All 11 obligations must appear in findings (explicit or gap)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art26_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {
            "ART26-OBL-1", "ART26-OBL-2", "ART26-OBL-4", "ART26-OBL-5",
            "ART26-OBL-6", "ART26-OBL-7", "ART26-OBL-8", "ART26-OBL-9",
            "ART26-OBL-10", "ART26-OBL-11", "ART26-OBL-12",
        }
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"
