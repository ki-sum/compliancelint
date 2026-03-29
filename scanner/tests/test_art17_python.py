"""Art. 17 Quality Management System tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_qms_documentation       → ART17-OBL-1
  has_compliance_strategy     → ART17-OBL-1a
  has_design_procedures       → ART17-OBL-1b
  has_qa_procedures           → ART17-OBL-1c
  has_testing_procedures      → ART17-OBL-1d
  has_technical_specifications → ART17-OBL-1e
  has_data_management         → ART17-OBL-1f
  has_risk_management_in_qms  → ART17-OBL-1g
  has_post_market_monitoring  → ART17-OBL-1h
  has_record_keeping          → ART17-OBL-1k
  has_accountability_framework → ART17-OBL-1m
  Manual (always UTD)         → ART17-OBL-1i, OBL-1j, OBL-1l, OBL-2
  Permission (skipped)        → ART17-PERM-3
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art17", {
        "has_qms_documentation": True,
        "qms_evidence": ["docs/quality-manual.md"],
        "has_compliance_strategy": True,
        "has_design_procedures": True,
        "has_qa_procedures": True,
        "has_testing_procedures": True,
        "has_technical_specifications": True,
        "has_data_management": True,
        "has_risk_management_in_qms": True,
        "has_post_market_monitoring": True,
        "has_record_keeping": True,
        "has_accountability_framework": True,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art17", {
        "has_qms_documentation": False,
        "qms_evidence": [],
        "has_compliance_strategy": False,
        "has_design_procedures": False,
        "has_qa_procedures": False,
        "has_testing_procedures": False,
        "has_technical_specifications": False,
        "has_data_management": False,
        "has_risk_management_in_qms": False,
        "has_post_market_monitoring": False,
        "has_record_keeping": False,
        "has_accountability_framework": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art17", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART17-OBL-1: QMS documented (has_qms_documentation) ──

class TestArt17Obl1:

    def test_has_qms_true_gives_partial(self, art17_module, tmp_path):
        """has_qms_documentation=True → ART17-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_qms_false_gives_non_compliant(self, art17_module, tmp_path):
        """has_qms_documentation=False → ART17-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_qms_none_gives_utd(self, art17_module, tmp_path):
        """has_qms_documentation=None → ART17-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART17-OBL-1a: Compliance strategy (has_compliance_strategy) ──

class TestArt17Obl1a:

    def test_true_gives_partial(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART17-OBL-1b: Design procedures (has_design_procedures) ──

class TestArt17Obl1b:

    def test_true_gives_partial(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART17-OBL-1c: QA procedures (has_qa_procedures) ──

class TestArt17Obl1c:

    def test_true_gives_partial(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1c")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1c")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1c")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART17-OBL-1d: Testing procedures (has_testing_procedures) ──

class TestArt17Obl1d:

    def test_true_gives_partial(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART17-OBL-1e: Technical specifications (has_technical_specifications) ──

class TestArt17Obl1e:

    def test_true_gives_partial(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1e")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1e")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1e")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART17-OBL-1f: Data management (has_data_management) ──

class TestArt17Obl1f:

    def test_true_gives_partial(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1f")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1f")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1f")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART17-OBL-1g: Risk management in QMS (has_risk_management_in_qms) ──

class TestArt17Obl1g:

    def test_true_gives_partial(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1g")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1g")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1g")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART17-OBL-1h: Post-market monitoring (has_post_market_monitoring) ──

class TestArt17Obl1h:

    def test_true_gives_partial(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1h")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1h")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1h")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART17-OBL-1k: Record-keeping (has_record_keeping) ──

class TestArt17Obl1k:

    def test_true_gives_partial(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1k")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1k")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1k")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART17-OBL-1m: Accountability framework (has_accountability_framework) ──

class TestArt17Obl1m:

    def test_true_gives_partial(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_true_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1m")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_full_false_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1m")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art17_module, tmp_path):
        BaseArticleModule.set_context(_empty_ctx())
        result = art17_module.scan(str(tmp_path))
        obl = _find(result, "ART17-OBL-1m")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Manual obligations: always UNABLE_TO_DETERMINE ──

class TestArt17ManualObligations:

    def test_manual_obligations_always_utd_with_all_true(self, art17_module, tmp_path):
        """Manual obligations always UTD even with all-true answers."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art17_module.scan(str(tmp_path))
        manual_ids = [
            "ART17-OBL-1i", "ART17-OBL-1j", "ART17-OBL-1l", "ART17-OBL-2",
        ]
        for obl_id in manual_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should always be UTD, got {findings[0].level}"
            )

    def test_manual_obligations_always_utd_with_all_false(self, art17_module, tmp_path):
        """Manual obligations always UTD even with all-false answers."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art17_module.scan(str(tmp_path))
        manual_ids = [
            "ART17-OBL-1i", "ART17-OBL-1j", "ART17-OBL-1l", "ART17-OBL-2",
        ]
        for obl_id in manual_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should always be UTD, got {findings[0].level}"
            )


# ── Structural tests ──

class TestArt17Structural:

    def test_all_16_obligation_ids_in_json(self, art17_module):
        """Obligation JSON must have exactly 16 obligations."""
        data = art17_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 16

    def test_obligation_coverage_present(self, art17_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art17_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art17_module, tmp_path):
        """When AI provides no answers, key automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art17_module.scan(str(tmp_path))
        automatable_ids = [
            "ART17-OBL-1", "ART17-OBL-1a", "ART17-OBL-1b", "ART17-OBL-1c",
            "ART17-OBL-1d", "ART17-OBL-1e", "ART17-OBL-1f", "ART17-OBL-1g",
            "ART17-OBL-1h", "ART17-OBL-1k", "ART17-OBL-1m",
        ]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art17_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 17(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art17_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art17_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art17_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art17_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art17_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0
