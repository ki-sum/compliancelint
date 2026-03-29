"""Art. 21 Cooperation with competent authorities tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_conformity_documentation   → ART21-OBL-1
  has_log_export_capability      → ART21-OBL-2
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art21", {
        "has_conformity_documentation": True,
        "has_log_export_capability": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art21", {
        "has_conformity_documentation": False,
        "has_log_export_capability": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art21", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART21-OBL-1: Conformity documentation ──

class TestArt21Obl1:

    def test_has_conformity_docs_true_gives_partial(self, art21_module, tmp_path):
        """has_conformity_documentation=True → ART21-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art21_module.scan(str(tmp_path))
        obl = _find(result, "ART21-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_conformity_docs_false_gives_non_compliant(self, art21_module, tmp_path):
        """has_conformity_documentation=False → ART21-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art21_module.scan(str(tmp_path))
        obl = _find(result, "ART21-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_conformity_docs_none_gives_utd(self, art21_module, tmp_path):
        """has_conformity_documentation=None → ART21-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art21_module.scan(str(tmp_path))
        obl = _find(result, "ART21-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART21-OBL-2: Log export capability ──

class TestArt21Obl2:

    def test_has_log_export_true_gives_partial(self, art21_module, tmp_path):
        """has_log_export_capability=True → ART21-OBL-2 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art21_module.scan(str(tmp_path))
        obl = _find(result, "ART21-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_log_export_false_gives_non_compliant(self, art21_module, tmp_path):
        """has_log_export_capability=False → ART21-OBL-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art21_module.scan(str(tmp_path))
        obl = _find(result, "ART21-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_log_export_none_gives_utd(self, art21_module, tmp_path):
        """has_log_export_capability=None → ART21-OBL-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art21_module.scan(str(tmp_path))
        obl = _find(result, "ART21-OBL-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt21Structural:

    def test_all_2_obligation_ids_in_json(self, art21_module):
        """Obligation JSON must have exactly 2 obligations."""
        data = art21_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 2

    def test_obligation_coverage_present(self, art21_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art21_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_automatable_obligations_utd(self, art21_module, tmp_path):
        """When AI provides no answers, automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art21_module.scan(str(tmp_path))
        automatable_ids = ["ART21-OBL-1", "ART21-OBL-2"]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art21_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 21(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art21_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art21_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art21_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art21_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art21_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_obligation_findings_present(self, art21_module, tmp_path):
        """All 2 obligations must appear in findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art21_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART21-OBL-1", "ART21-OBL-2"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"
