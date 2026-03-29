"""Art. 53 Obligations for Providers of General-Purpose AI Models tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_technical_documentation       → ART53-OBL-1a (_finding_from_answer, open-source exempt)
  has_downstream_documentation      → ART53-OBL-1b (_finding_from_answer, open-source exempt)
  has_copyright_policy              → ART53-OBL-1c (_finding_from_answer)
  has_training_data_summary         → ART53-OBL-1d (_finding_from_answer)
  is_open_source_gpai               → ART53-EXC-2 (exception, custom Finding)
  always UTD                        → ART53-OBL-3 (manual, authority cooperation)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art53", {
        "has_technical_documentation": True,
        "documentation_evidence": ["docs/model_card.md"],
        "has_downstream_documentation": True,
        "downstream_doc_evidence": ["docs/api_guide.md"],
        "has_copyright_policy": True,
        "copyright_policy_evidence": ["docs/copyright_policy.md"],
        "has_training_data_summary": True,
        "training_data_summary_public": True,
        "training_data_evidence": ["docs/training_data_summary.md"],
        "is_open_source_gpai": False,
        "has_systemic_risk": False,
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art53", {
        "has_technical_documentation": False,
        "has_downstream_documentation": False,
        "has_copyright_policy": False,
        "has_training_data_summary": False,
        "is_open_source_gpai": False,
        "has_systemic_risk": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art53", {})


def _open_source_ctx():
    """Open-source GPAI without systemic risk — exception applies."""
    return _ctx_with("art53", {
        "has_technical_documentation": True,
        "has_downstream_documentation": True,
        "has_copyright_policy": True,
        "has_training_data_summary": True,
        "is_open_source_gpai": True,
        "has_systemic_risk": False,
    })


def _open_source_systemic_risk_ctx():
    """Open-source GPAI WITH systemic risk — exception does NOT apply."""
    return _ctx_with("art53", {
        "has_technical_documentation": True,
        "has_downstream_documentation": True,
        "has_copyright_policy": True,
        "has_training_data_summary": True,
        "is_open_source_gpai": True,
        "has_systemic_risk": True,
    })


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART53-OBL-1a: Technical documentation ──

class TestArt53Obl1a:

    def test_true_gives_partial(self, art53_module, tmp_path):
        """has_technical_documentation=True → ART53-OBL-1a PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art53_module, tmp_path):
        """has_technical_documentation=False → ART53-OBL-1a NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art53_module, tmp_path):
        """has_technical_documentation=None → ART53-OBL-1a UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_open_source_exception_makes_na(self, art53_module, tmp_path):
        """Open-source GPAI without systemic risk → ART53-OBL-1a NOT_APPLICABLE."""
        BaseArticleModule.set_context(_open_source_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_open_source_with_systemic_risk_still_applies(self, art53_module, tmp_path):
        """Open-source WITH systemic risk → OBL-1a still PARTIAL (exception revoked)."""
        BaseArticleModule.set_context(_open_source_systemic_risk_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL


# ── ART53-OBL-1b: Downstream documentation ──

class TestArt53Obl1b:

    def test_true_gives_partial(self, art53_module, tmp_path):
        """has_downstream_documentation=True → ART53-OBL-1b PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art53_module, tmp_path):
        """has_downstream_documentation=False → ART53-OBL-1b NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art53_module, tmp_path):
        """has_downstream_documentation=None → ART53-OBL-1b UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_open_source_exception_makes_na(self, art53_module, tmp_path):
        """Open-source GPAI without systemic risk → ART53-OBL-1b NOT_APPLICABLE."""
        BaseArticleModule.set_context(_open_source_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE


# ── ART53-OBL-1c: Copyright compliance policy ──

class TestArt53Obl1c:

    def test_true_gives_partial(self, art53_module, tmp_path):
        """has_copyright_policy=True → ART53-OBL-1c PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1c")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art53_module, tmp_path):
        """has_copyright_policy=False → ART53-OBL-1c NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1c")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art53_module, tmp_path):
        """has_copyright_policy=None → ART53-OBL-1c UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1c")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_not_exempted_by_open_source(self, art53_module, tmp_path):
        """Copyright policy NOT exempted by open-source exception."""
        BaseArticleModule.set_context(_open_source_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1c")
        assert len(obl) > 0
        # Open-source exception does NOT exempt 1(c) — should still be PARTIAL
        assert obl[0].level == ComplianceLevel.PARTIAL


# ── ART53-OBL-1d: Training data summary ──

class TestArt53Obl1d:

    def test_true_gives_partial(self, art53_module, tmp_path):
        """has_training_data_summary=True → ART53-OBL-1d PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art53_module, tmp_path):
        """has_training_data_summary=False → ART53-OBL-1d NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art53_module, tmp_path):
        """has_training_data_summary=None → ART53-OBL-1d UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_not_exempted_by_open_source(self, art53_module, tmp_path):
        """Training data summary NOT exempted by open-source exception."""
        BaseArticleModule.set_context(_open_source_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-1d")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL


# ── ART53-EXC-2: Open-source exception ──

class TestArt53Exc2:

    def test_open_source_no_systemic_risk_compliant(self, art53_module, tmp_path):
        """Open-source without systemic risk → ART53-EXC-2 COMPLIANT."""
        BaseArticleModule.set_context(_open_source_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-EXC-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.COMPLIANT

    def test_open_source_with_systemic_risk_non_compliant(self, art53_module, tmp_path):
        """Open-source WITH systemic risk → ART53-EXC-2 NON_COMPLIANT."""
        BaseArticleModule.set_context(_open_source_systemic_risk_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-EXC-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_not_open_source_gives_na(self, art53_module, tmp_path):
        """Not open-source → ART53-EXC-2 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-EXC-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_unknown_gives_utd(self, art53_module, tmp_path):
        """is_open_source_gpai=None → ART53-EXC-2 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-EXC-2")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART53-OBL-3: Authority cooperation ──

class TestArt53Obl3:

    def test_always_utd(self, art53_module, tmp_path):
        """ART53-OBL-3 → always UNABLE_TO_DETERMINE (manual, process)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_utd_even_with_no_answers(self, art53_module, tmp_path):
        """ART53-OBL-3 → UTD even with empty context."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art53_module.scan(str(tmp_path))
        obl = _find(result, "ART53-OBL-3")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt53Structural:

    def test_all_6_obligation_ids_in_json(self, art53_module):
        """Obligation JSON must have exactly 8 obligations."""
        data = art53_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 8

    def test_obligation_coverage_present(self, art53_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art53_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art53_module, tmp_path):
        """When AI provides no answers, automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art53_module.scan(str(tmp_path))
        utd_ids = ["ART53-OBL-1a", "ART53-OBL-1b", "ART53-OBL-1c",
                    "ART53-OBL-1d", "ART53-EXC-2", "ART53-OBL-3"]
        for obl_id in utd_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art53_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 53(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art53_module.scan(str(tmp_path))
        for f in result.findings:
            if f.is_informational:
                continue
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_6_obligations_appear_in_findings(self, art53_module, tmp_path):
        """All 6 obligations must appear in findings (explicit or gap)."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art53_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART53-OBL-1a", "ART53-OBL-1b", "ART53-OBL-1c",
                        "ART53-OBL-1d", "ART53-EXC-2", "ART53-OBL-3"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"

    def test_uses_finding_from_answer(self, art53_module):
        """Module must use _finding_from_answer() (gate check)."""
        import inspect
        source = inspect.getsource(art53_module.__class__.scan)
        assert "_finding_from_answer" in source, (
            "Module must use _finding_from_answer() for provider obligations"
        )
