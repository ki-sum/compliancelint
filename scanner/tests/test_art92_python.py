"""Art. 92 Power to conduct evaluations tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_evaluation_cooperation_readiness  → ART92-OBL-5 (provider obligation, _finding_from_answer)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art92", {
        "has_evaluation_cooperation_readiness": True,
        "cooperation_evidence": "GPAI documentation maintained, evaluation cooperation procedure in place",
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art92", {
        "has_evaluation_cooperation_readiness": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art92", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── A1: Basic scan (all true → no NON_COMPLIANT) ──

class TestArt92BasicScan:

    def test_all_true_no_non_compliant(self, art92_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art92_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )


# ── A2: Feature detected → PARTIAL finding ──

class TestArt92Obl5Detected:

    def test_true_gives_partial(self, art92_module, tmp_path):
        """has_evaluation_cooperation_readiness=True → ART92-OBL-5 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art92_module.scan(str(tmp_path))
        obl = _find(result, "ART92-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_evidence_in_description_when_true(self, art92_module, tmp_path):
        """When readiness present, evidence should appear in description."""
        ctx = _ctx_with("art92", {
            "has_evaluation_cooperation_readiness": True,
            "cooperation_evidence": "GPAI docs maintained via internal wiki",
        })
        BaseArticleModule.set_context(ctx)
        result = art92_module.scan(str(tmp_path))
        obl = _find(result, "ART92-OBL-5")
        assert len(obl) > 0
        assert "internal wiki" in obl[0].description


# ── A3: Feature absent → NON_COMPLIANT finding ──

class TestArt92Obl5Absent:

    def test_false_gives_non_compliant(self, art92_module, tmp_path):
        """has_evaluation_cooperation_readiness=False → ART92-OBL-5 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art92_module.scan(str(tmp_path))
        obl = _find(result, "ART92-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_all_false_has_non_compliant(self, art92_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art92_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0


# ── A4: No context → UTD ──

class TestArt92NoContext:

    def test_none_gives_utd(self, art92_module, tmp_path):
        """has_evaluation_cooperation_readiness=None → ART92-OBL-5 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art92_module.scan(str(tmp_path))
        obl = _find(result, "ART92-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_no_answers_all_key_obligations_utd(self, art92_module, tmp_path):
        """When AI provides no answers, all automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art92_module.scan(str(tmp_path))
        automatable_ids = ["ART92-OBL-5"]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )


# ── A5: Invalid directory → error ──

class TestArt92InvalidDirectory:

    def test_invalid_directory(self, art92_module):
        """Non-existent directory should still produce a result (scan handles gracefully)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art92_module.scan("/nonexistent/path/12345")
        assert result is not None
        assert result.article_number == 92


# ── A6: Summary present ──

class TestArt92Summary:

    def test_summary_present(self, art92_module, tmp_path):
        """ScanResult must have article_number and article_title."""
        result = art92_module.scan(str(tmp_path))
        assert result.article_number == 92
        assert result.article_title is not None
        assert len(result.article_title) > 0

    def test_obligation_coverage_present(self, art92_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art92_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0


# ── A7: All obligation IDs in findings ──

class TestArt92ObligationIds:

    def test_all_1_obligation_ids_in_json(self, art92_module):
        """Obligation JSON must have exactly 1 obligation."""
        data = art92_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 1

    def test_all_1_obligations_appear_in_findings(self, art92_module, tmp_path):
        """All 1 obligation must appear in findings (explicit or gap)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art92_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART92-OBL-5"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"

    def test_zero_coverage_gaps(self, art92_module, tmp_path):
        """All obligations must be explicitly covered (0 gaps)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art92_module.scan(str(tmp_path))
        cov = result.details.get("obligation_coverage", {})
        assert cov.get("coverage_gaps", -1) == 0, (
            f"Expected 0 coverage gaps, got {cov.get('coverage_gaps')}: {cov.get('gap_obligation_ids')}"
        )


# ── Structural tests ──

class TestArt92Structural:

    def test_description_has_no_legal_citation_prefix(self, art92_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 92(5)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art92_module.scan(str(tmp_path))
        for f in result.findings:
            if f.is_informational:
                continue
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_uses_finding_from_answer(self, art92_module):
        """Module must use _finding_from_answer() (gate check)."""
        import inspect
        source = inspect.getsource(art92_module.__class__.scan)
        assert "_finding_from_answer" in source, (
            "Module must use _finding_from_answer() for provider obligations"
        )
