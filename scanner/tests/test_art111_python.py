"""Art. 111 Transitional provisions tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_transition_plan              → ART111-OBL-1 (Annex X legacy system transition)
  has_significant_change_tracking  → ART111-OBL-2 (pre-existing high-risk + public authority)
  has_gpai_compliance_timeline     → ART111-OBL-3 (GPAI model compliance by 2 Aug 2027)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art111", {
        "has_transition_plan": True,
        "transition_evidence": "Compliance roadmap documented in docs/transition-plan.md",
        "has_significant_change_tracking": True,
        "change_tracking_evidence": "Change log maintained in CHANGELOG.md with design change tracking",
        "has_gpai_compliance_timeline": True,
        "gpai_timeline_evidence": "GPAI compliance timeline in docs/gpai-compliance.md",
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art111", {
        "has_transition_plan": False,
        "transition_evidence": "",
        "has_significant_change_tracking": False,
        "change_tracking_evidence": "",
        "has_gpai_compliance_timeline": False,
        "gpai_timeline_evidence": "",
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art111", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── A0: Code quality gate ──

class TestArt111CodeQuality:

    def test_uses_finding_from_answer(self, art111_module):
        """Module must use _finding_from_answer() (gate check)."""
        import inspect
        source = inspect.getsource(art111_module.__class__.scan)
        assert "_finding_from_answer" in source, (
            "Module must use _finding_from_answer() for provider obligations"
        )


# ── A1: Basic scan (all true → no NON_COMPLIANT) ──

class TestArt111BasicScan:

    def test_all_true_no_non_compliant(self, art111_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art111_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )


# ── A2: Feature detected → PARTIAL finding ─���

class TestArt111Obl1Detected:

    def test_transition_plan_true_gives_partial(self, art111_module, tmp_path):
        """has_transition_plan=True → ART111-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art111_module.scan(str(tmp_path))
        obl = _find(result, "ART111-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_evidence_in_description_when_true(self, art111_module, tmp_path):
        """When transition plan present, evidence should appear in description."""
        ctx = _ctx_with("art111", {
            "has_transition_plan": True,
            "transition_evidence": "Roadmap in docs/transition-plan.md",
            "has_significant_change_tracking": True,
            "has_gpai_compliance_timeline": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art111_module.scan(str(tmp_path))
        obl = _find(result, "ART111-OBL-1")
        assert len(obl) > 0
        assert "transition-plan.md" in obl[0].description


class TestArt111Obl2Detected:

    def test_change_tracking_true_gives_partial(self, art111_module, tmp_path):
        """has_significant_change_tracking=True → ART111-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art111_module.scan(str(tmp_path))
        obl = _find(result, "ART111-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL


class TestArt111Obl3Detected:

    def test_gpai_timeline_true_gives_partial(self, art111_module, tmp_path):
        """has_gpai_compliance_timeline=True → ART111-OBL-3 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art111_module.scan(str(tmp_path))
        obl = _find(result, "ART111-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL


# ── A3: Feature absent → NON_COMPLIANT finding ──

class TestArt111Obl1Absent:

    def test_transition_plan_false_gives_non_compliant(self, art111_module, tmp_path):
        """has_transition_plan=False → ART111-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art111_module.scan(str(tmp_path))
        obl = _find(result, "ART111-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT


class TestArt111Obl2Absent:

    def test_change_tracking_false_gives_non_compliant(self, art111_module, tmp_path):
        """has_significant_change_tracking=False → ART111-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art111_module.scan(str(tmp_path))
        obl = _find(result, "ART111-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT


class TestArt111Obl3Absent:

    def test_gpai_timeline_false_gives_non_compliant(self, art111_module, tmp_path):
        """has_gpai_compliance_timeline=False → ART111-OBL-3 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art111_module.scan(str(tmp_path))
        obl = _find(result, "ART111-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_all_false_has_non_compliant(self, art111_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art111_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0


# ── A4: No context → UTD ──

class TestArt111NoContext:

    def test_obl1_none_gives_utd(self, art111_module, tmp_path):
        """has_transition_plan=None → ART111-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art111_module.scan(str(tmp_path))
        obl = _find(result, "ART111-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_obl2_none_gives_utd(self, art111_module, tmp_path):
        """has_significant_change_tracking=None → ART111-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art111_module.scan(str(tmp_path))
        obl = _find(result, "ART111-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_obl3_none_gives_utd(self, art111_module, tmp_path):
        """has_gpai_compliance_timeline=None → ART111-OBL-3 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art111_module.scan(str(tmp_path))
        obl = _find(result, "ART111-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_no_answers_all_key_obligations_utd(self, art111_module, tmp_path):
        """When AI provides no answers, all automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art111_module.scan(str(tmp_path))
        automatable_ids = ["ART111-OBL-1", "ART111-OBL-2", "ART111-OBL-3"]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )


# ── A5: Invalid directory → error ──

class TestArt111InvalidDirectory:

    def test_invalid_directory(self, art111_module):
        """Non-existent directory should still produce a result (scan handles gracefully)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art111_module.scan("/nonexistent/path/12345")
        assert result is not None
        assert result.article_number == 111


# ── A6: Summary present ──

class TestArt111Summary:

    def test_summary_present(self, art111_module, tmp_path):
        """ScanResult must have article_number and article_title."""
        result = art111_module.scan(str(tmp_path))
        assert result.article_number == 111
        assert result.article_title is not None
        assert len(result.article_title) > 0

    def test_obligation_coverage_present(self, art111_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art111_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0


# ── A7: All obligation IDs in findings ��─

class TestArt111ObligationIds:

    def test_all_3_obligation_ids_in_json(self, art111_module):
        """Obligation JSON must have exactly 3 obligations."""
        data = art111_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 3

    def test_all_3_obligations_appear_in_findings(self, art111_module, tmp_path):
        """All 3 obligations must appear in findings (explicit or gap)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art111_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART111-OBL-1", "ART111-OBL-2", "ART111-OBL-3"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"

    def test_zero_coverage_gaps(self, art111_module, tmp_path):
        """All obligations must be explicitly covered (0 gaps)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art111_module.scan(str(tmp_path))
        cov = result.details.get("obligation_coverage", {})
        assert cov.get("coverage_gaps", -1) == 0, (
            f"Expected 0 coverage gaps, got {cov.get('coverage_gaps')}: {cov.get('gap_obligation_ids')}"
        )


# ── Structural tests ──

class TestArt111Structural:

    def test_description_has_no_legal_citation_prefix(self, art111_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 111(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art111_module.scan(str(tmp_path))
        for f in result.findings:
            if f.is_informational:
                continue
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
