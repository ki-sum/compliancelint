"""Art. 60 Testing of high-risk AI systems in real world conditions tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_testing_plan                      → ART60-OBL-4
  has_incident_reporting_for_testing    → ART60-OBL-7
  has_authority_notification_procedure  → ART60-OBL-8
  Manual (always UTD)                   → ART60-OBL-9

Scope gate: conducts_real_world_testing — all obligations skip when false.
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art60", {
        "conducts_real_world_testing": True,
        "has_testing_plan": True,
        "has_incident_reporting_for_testing": True,
        "has_authority_notification_procedure": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art60", {
        "conducts_real_world_testing": True,
        "has_testing_plan": False,
        "has_incident_reporting_for_testing": False,
        "has_authority_notification_procedure": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art60", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART60-OBL-4: Real-world testing plan (has_testing_plan) ──

class TestArt60Obl4:

    def test_has_testing_plan_true_gives_partial(self, art60_module, tmp_path):
        """has_testing_plan=True → ART60-OBL-4 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art60_module.scan(str(tmp_path))
        obl = _find(result, "ART60-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_testing_plan_false_gives_non_compliant(self, art60_module, tmp_path):
        """has_testing_plan=False → ART60-OBL-4 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art60_module.scan(str(tmp_path))
        obl = _find(result, "ART60-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_testing_plan_none_gives_utd(self, art60_module, tmp_path):
        """has_testing_plan=None → ART60-OBL-4 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art60_module.scan(str(tmp_path))
        obl = _find(result, "ART60-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART60-OBL-7: Incident reporting for testing (has_incident_reporting_for_testing) ──

class TestArt60Obl7:

    def test_has_incident_reporting_true_gives_partial(self, art60_module, tmp_path):
        """has_incident_reporting_for_testing=True → ART60-OBL-7 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art60_module.scan(str(tmp_path))
        obl = _find(result, "ART60-OBL-7")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_incident_reporting_false_gives_non_compliant(self, art60_module, tmp_path):
        """has_incident_reporting_for_testing=False → ART60-OBL-7 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art60_module.scan(str(tmp_path))
        obl = _find(result, "ART60-OBL-7")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_incident_reporting_none_gives_utd(self, art60_module, tmp_path):
        """has_incident_reporting_for_testing=None → ART60-OBL-7 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art60_module.scan(str(tmp_path))
        obl = _find(result, "ART60-OBL-7")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART60-OBL-8: Authority notification procedure (has_authority_notification_procedure) ──

class TestArt60Obl8:

    def test_has_notification_true_gives_partial(self, art60_module, tmp_path):
        """has_authority_notification_procedure=True → ART60-OBL-8 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art60_module.scan(str(tmp_path))
        obl = _find(result, "ART60-OBL-8")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_notification_false_gives_non_compliant(self, art60_module, tmp_path):
        """has_authority_notification_procedure=False → ART60-OBL-8 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art60_module.scan(str(tmp_path))
        obl = _find(result, "ART60-OBL-8")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_notification_none_gives_utd(self, art60_module, tmp_path):
        """has_authority_notification_procedure=None → ART60-OBL-8 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art60_module.scan(str(tmp_path))
        obl = _find(result, "ART60-OBL-8")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART60-OBL-9: Manual obligation — liability for testing damage ──

class TestArt60Obl9Manual:

    def test_obl9_always_utd_with_all_true(self, art60_module, tmp_path):
        """ART60-OBL-9 (liability) always UTD even with all-true answers."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art60_module.scan(str(tmp_path))
        obl = _find(result, "ART60-OBL-9")
        assert len(obl) > 0, "ART60-OBL-9 not in findings"
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
            f"ART60-OBL-9 should always be UTD, got {obl[0].level}"
        )

    def test_obl9_always_utd_with_all_false(self, art60_module, tmp_path):
        """ART60-OBL-9 always UTD even with all-false answers."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art60_module.scan(str(tmp_path))
        obl = _find(result, "ART60-OBL-9")
        assert len(obl) > 0, "ART60-OBL-9 not in findings"
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
            f"ART60-OBL-9 should always be UTD, got {obl[0].level}"
        )


# ── Structural tests ──

class TestArt60Structural:

    def test_all_4_obligation_ids_in_json(self, art60_module):
        """Obligation JSON must have exactly 4 obligations."""
        data = art60_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 4

    def test_obligation_coverage_present(self, art60_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art60_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_automatable_obligations_utd(self, art60_module, tmp_path):
        """When AI provides no answers, automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art60_module.scan(str(tmp_path))
        automatable_ids = ["ART60-OBL-4", "ART60-OBL-7", "ART60-OBL-8"]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art60_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 60(4)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art60_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art60_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art60_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art60_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art60_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_obligation_findings_present(self, art60_module, tmp_path):
        """All 4 obligations must appear in findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art60_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART60-OBL-4", "ART60-OBL-7", "ART60-OBL-8", "ART60-OBL-9"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"
