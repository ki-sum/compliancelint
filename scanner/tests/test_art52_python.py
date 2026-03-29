"""Art. 52 Procedure for Classification and Notification of Systemic Risk tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_commission_notification          → ART52-OBL-1 (provider obligation, _finding_from_answer)
  always UTD                           → ART52-PERM-2 (permission, not obligation)
  always UTD                           → ART52-OBL-5 (manual, reassessment request content)
  always UTD                           → ART52-PERM-5 (permission, reassessment request right)
  always UTD                           → ART52-OBL-6 (Commission obligation)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art52", {
        "has_commission_notification": True,
        "notification_evidence": "Notification sent to Commission on 2026-03-15",
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art52", {
        "has_commission_notification": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art52", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART52-OBL-1: Commission notification ──

class TestArt52Obl1:

    def test_true_gives_partial(self, art52_module, tmp_path):
        """has_commission_notification=True → ART52-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art52_module.scan(str(tmp_path))
        obl = _find(result, "ART52-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art52_module, tmp_path):
        """has_commission_notification=False → ART52-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art52_module.scan(str(tmp_path))
        obl = _find(result, "ART52-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art52_module, tmp_path):
        """has_commission_notification=None → ART52-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art52_module.scan(str(tmp_path))
        obl = _find(result, "ART52-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_evidence_in_description_when_true(self, art52_module, tmp_path):
        """When notification present, evidence should appear in description."""
        ctx = _ctx_with("art52", {
            "has_commission_notification": True,
            "notification_evidence": "Commission notified via AI Office portal on 2026-03-15",
        })
        BaseArticleModule.set_context(ctx)
        result = art52_module.scan(str(tmp_path))
        obl = _find(result, "ART52-OBL-1")
        assert len(obl) > 0
        assert "2026-03-15" in obl[0].description


# ── ART52-PERM-2: Rebuttal right (permission) ──

class TestArt52Perm2:

    def test_always_utd(self, art52_module, tmp_path):
        """ART52-PERM-2 → always UNABLE_TO_DETERMINE (permission, not obligation)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art52_module.scan(str(tmp_path))
        obl = _find(result, "ART52-PERM-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_utd_even_with_no_answers(self, art52_module, tmp_path):
        """ART52-PERM-2 → UTD even with empty context."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art52_module.scan(str(tmp_path))
        obl = _find(result, "ART52-PERM-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART52-OBL-5: Reassessment request content (manual) ──

class TestArt52Obl5:

    def test_always_utd(self, art52_module, tmp_path):
        """ART52-OBL-5 → always UNABLE_TO_DETERMINE (manual obligation)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art52_module.scan(str(tmp_path))
        obl = _find(result, "ART52-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_utd_even_with_no_answers(self, art52_module, tmp_path):
        """ART52-OBL-5 → UTD even with empty context."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art52_module.scan(str(tmp_path))
        obl = _find(result, "ART52-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_utd_even_with_all_false(self, art52_module, tmp_path):
        """ART52-OBL-5 → UTD even with all-false answers."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art52_module.scan(str(tmp_path))
        obl = _find(result, "ART52-OBL-5")
        assert len(obl) > 0, "ART52-OBL-5 not in findings"
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
            f"ART52-OBL-5 should always be UTD, got {obl[0].level}"
        )


# ── ART52-PERM-5: Reassessment request right (permission) ──

class TestArt52Perm5:

    def test_always_utd(self, art52_module, tmp_path):
        """ART52-PERM-5 → always UNABLE_TO_DETERMINE (permission, not obligation)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art52_module.scan(str(tmp_path))
        obl = _find(result, "ART52-PERM-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_utd_even_with_no_answers(self, art52_module, tmp_path):
        """ART52-PERM-5 → UTD even with empty context."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art52_module.scan(str(tmp_path))
        obl = _find(result, "ART52-PERM-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART52-OBL-6: Commission publishes list ──

class TestArt52Obl6:

    def test_always_utd(self, art52_module, tmp_path):
        """ART52-OBL-6 → always UNABLE_TO_DETERMINE (Commission obligation)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art52_module.scan(str(tmp_path))
        obl = _find(result, "ART52-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_utd_even_with_no_answers(self, art52_module, tmp_path):
        """ART52-OBL-6 → UTD even with empty context."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art52_module.scan(str(tmp_path))
        obl = _find(result, "ART52-OBL-6")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt52Structural:

    def test_all_5_obligation_ids_in_json(self, art52_module):
        """Obligation JSON must have exactly 5 obligations."""
        data = art52_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 5

    def test_obligation_coverage_present(self, art52_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art52_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art52_module, tmp_path):
        """When AI provides no answers, all obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art52_module.scan(str(tmp_path))
        all_ids = ["ART52-OBL-1", "ART52-PERM-2", "ART52-OBL-5", "ART52-PERM-5", "ART52-OBL-6"]
        for obl_id in all_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art52_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 52(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art52_module.scan(str(tmp_path))
        for f in result.findings:
            if f.is_informational:
                continue
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_5_obligations_appear_in_findings(self, art52_module, tmp_path):
        """All 5 obligations must appear in findings (explicit or gap)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art52_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART52-OBL-1", "ART52-PERM-2", "ART52-OBL-5", "ART52-PERM-5", "ART52-OBL-6"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"

    def test_all_true_no_non_compliant(self, art52_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art52_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art52_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art52_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_uses_finding_from_answer(self, art52_module):
        """Module must use _finding_from_answer() (gate check)."""
        import inspect
        source = inspect.getsource(art52_module.__class__.scan)
        assert "_finding_from_answer" in source, (
            "Module must use _finding_from_answer() for provider obligations"
        )

    def test_summary_present(self, art52_module, tmp_path):
        """ScanResult must have article_number and article_title."""
        result = art52_module.scan(str(tmp_path))
        assert result.article_number == 52
        assert result.article_title is not None
        assert len(result.article_title) > 0

    def test_zero_coverage_gaps(self, art52_module, tmp_path):
        """All 5 obligations must be explicitly covered (0 gaps)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art52_module.scan(str(tmp_path))
        cov = result.details.get("obligation_coverage", {})
        assert cov.get("coverage_gaps", -1) == 0, (
            f"Expected 0 coverage gaps, got {cov.get('coverage_gaps')}: {cov.get('gap_obligation_ids')}"
        )
