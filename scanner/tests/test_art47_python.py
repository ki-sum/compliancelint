"""Art. 47 EU Declaration of Conformity tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_doc_declaration   → ART47-OBL-1
  has_annex_v_content   → ART47-OBL-2
  (manual, always UTD)  → ART47-OBL-4
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art47", {
        "has_doc_declaration": True,
        "has_annex_v_content": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art47", {
        "has_doc_declaration": False,
        "has_annex_v_content": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art47", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART47-OBL-1: EU Declaration of Conformity document (has_doc_declaration) ──

class TestArt47Obl1:

    def test_true_gives_partial(self, art47_module, tmp_path):
        """has_doc_declaration=True → ART47-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art47_module.scan(str(tmp_path))
        obl = _find(result, "ART47-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art47_module, tmp_path):
        """has_doc_declaration=False → ART47-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art47_module.scan(str(tmp_path))
        obl = _find(result, "ART47-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art47_module, tmp_path):
        """has_doc_declaration=None → ART47-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art47_module.scan(str(tmp_path))
        obl = _find(result, "ART47-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART47-OBL-2: Annex V content and translation (has_annex_v_content) ──

class TestArt47Obl2:

    def test_true_gives_partial(self, art47_module, tmp_path):
        """has_annex_v_content=True → ART47-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art47_module.scan(str(tmp_path))
        obl = _find(result, "ART47-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art47_module, tmp_path):
        """has_annex_v_content=False → ART47-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art47_module.scan(str(tmp_path))
        obl = _find(result, "ART47-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art47_module, tmp_path):
        """has_annex_v_content=None → ART47-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art47_module.scan(str(tmp_path))
        obl = _find(result, "ART47-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART47-OBL-4: DoC kept up-to-date (manual, always UTD) ──

class TestArt47Obl4:

    def test_always_utd(self, art47_module, tmp_path):
        """ART47-OBL-4 always UNABLE_TO_DETERMINE (manual obligation)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art47_module.scan(str(tmp_path))
        obl = _find(result, "ART47-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_utd_even_when_all_false(self, art47_module, tmp_path):
        """ART47-OBL-4 stays UTD even when other answers are False."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art47_module.scan(str(tmp_path))
        obl = _find(result, "ART47-OBL-4")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt47Structural:

    def test_all_3_obligation_ids_in_json(self, art47_module):
        """Obligation JSON must have exactly 4 obligations."""
        data = art47_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 4

    def test_obligation_coverage_present(self, art47_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art47_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art47_module, tmp_path):
        """When AI provides no answers, all obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art47_module.scan(str(tmp_path))
        all_ids = ["ART47-OBL-1", "ART47-OBL-2", "ART47-OBL-4"]
        for obl_id in all_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art47_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 47(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art47_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art47_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art47_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art47_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art47_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_3_obligations_appear_in_findings(self, art47_module, tmp_path):
        """All 3 obligations must appear in findings (explicit or gap)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art47_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART47-OBL-1", "ART47-OBL-2", "ART47-OBL-4"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"
