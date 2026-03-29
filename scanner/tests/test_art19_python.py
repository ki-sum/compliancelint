"""Art. 19 Automatically generated logs tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_log_retention / has_retention_config → ART19-OBL-1 (provider keeps logs)
  has_retention_config + retention_days    → ART19-OBL-1b (>= 180 day minimum)
  Scope-limited (gap)                     → ART19-OBL-2 (financial institution)
"""
import pytest
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _load_module, _ctx_with


@pytest.fixture
def art19_module():
    return _load_module("art19-automatically-generated-logs")


RETENTION_MINIMUM_DAYS = 180


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art19", {
        "has_log_retention": True,
        "has_retention_config": True,
        "retention_days": 365,
        "retention_evidence": "LOG_RETENTION=365d in config.yaml",
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art19", {
        "has_log_retention": False,
        "has_retention_config": False,
        "retention_days": None,
        "retention_evidence": "",
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art19", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART19-OBL-1: Provider keeps Art. 12(1) logs (has_log_retention) ──

class TestArt19Obl1:

    def test_true_gives_partial(self, art19_module, tmp_path):
        """has_log_retention=True → ART19-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_false_gives_non_compliant(self, art19_module, tmp_path):
        """has_log_retention=False → ART19-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_none_gives_utd(self, art19_module, tmp_path):
        """has_log_retention=None → ART19-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_true_includes_evidence(self, art19_module, tmp_path):
        """When True with evidence, description should include it."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1")
        assert len(obl) > 0
        assert "retention" in obl[0].description.lower()

    def test_fallback_to_art12(self, art19_module, tmp_path):
        """When art19 is empty, falls back to art12 retention fields."""
        from core.context import ProjectContext
        ctx = ProjectContext(
            primary_language="python",
            risk_classification="likely high-risk",
            compliance_answers={
                "art12": {
                    "has_retention_config": True,
                    "retention_days": 365,
                    "retention_evidence": "from art12",
                },
                "art19": {},
            },
        )
        BaseArticleModule.set_context(ctx)
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL


# ── ART19-OBL-1b: Retention period (has_retention_config + retention_days) ──

class TestArt19Obl1b:

    def test_retention_above_180_gives_partial(self, art19_module, tmp_path):
        """has_retention_config=True, retention_days >= 180 → ART19-OBL-1b PARTIAL."""
        BaseArticleModule.set_context(_ctx_with("art19", {
            "has_log_retention": True,
            "has_retention_config": True,
            "retention_days": 365,
        }))
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_retention_below_180_gives_non_compliant(self, art19_module, tmp_path):
        """has_retention_config=True, retention_days < 180 → ART19-OBL-1b NON_COMPLIANT."""
        BaseArticleModule.set_context(_ctx_with("art19", {
            "has_log_retention": True,
            "has_retention_config": True,
            "retention_days": 30,
        }))
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_retention_days_none_gives_partial(self, art19_module, tmp_path):
        """has_retention_config=True, retention_days=None → ART19-OBL-1b PARTIAL."""
        BaseArticleModule.set_context(_ctx_with("art19", {
            "has_log_retention": True,
            "has_retention_config": True,
            "retention_days": None,
        }))
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_no_retention_config_gives_non_compliant(self, art19_module, tmp_path):
        """has_retention_config=False → ART19-OBL-1b NON_COMPLIANT."""
        BaseArticleModule.set_context(_ctx_with("art19", {
            "has_log_retention": False,
            "has_retention_config": False,
        }))
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_retention_config_none_gives_utd(self, art19_module, tmp_path):
        """has_retention_config=None → ART19-OBL-1b UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_retention_boundary_180_gives_partial(self, art19_module, tmp_path):
        """retention_days == 180 (boundary) → ART19-OBL-1b PARTIAL."""
        BaseArticleModule.set_context(_ctx_with("art19", {
            "has_log_retention": True,
            "has_retention_config": True,
            "retention_days": 180,
        }))
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_retention_boundary_179_gives_non_compliant(self, art19_module, tmp_path):
        """retention_days == 179 (just below threshold) → ART19-OBL-1b NON_COMPLIANT."""
        BaseArticleModule.set_context(_ctx_with("art19", {
            "has_log_retention": True,
            "has_retention_config": True,
            "retention_days": 179,
        }))
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT


# ── ART19-OBL-2: Financial institution (context_skip_field) ──

class TestArt19Obl2:

    def test_financial_institution_false_gives_not_applicable(self, art19_module, tmp_path):
        """is_financial_institution=False → ART19-OBL-2 NOT_APPLICABLE via gap_findings."""
        from core.context import ProjectContext
        ctx = ProjectContext(
            primary_language="python",
            risk_classification="likely high-risk",
            compliance_answers={
                "art19": {
                    "has_log_retention": True,
                    "has_retention_config": True,
                    "retention_days": 365,
                },
                "_scope": {"is_financial_institution": False},
            },
        )
        BaseArticleModule.set_context(ctx)
        result = art19_module.scan(str(tmp_path))
        obl2 = _find(result, "ART19-OBL-2")
        assert len(obl2) > 0
        assert obl2[0].level == ComplianceLevel.NOT_APPLICABLE

    def test_financial_institution_not_set_gives_gap(self, art19_module, tmp_path):
        """is_financial_institution not set → ART19-OBL-2 appears as gap finding."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art19_module.scan(str(tmp_path))
        obl2 = _find(result, "ART19-OBL-2")
        # Should exist as a gap finding (either UTD or CONDITIONAL)
        assert len(obl2) > 0


# ── Structural tests ──

class TestArt19Structural:

    def test_obligation_json_has_3_obligations(self, art19_module):
        """Obligation JSON must have exactly 3 obligations."""
        data = art19_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 3

    def test_obligation_coverage_present(self, art19_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art19_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_obl1_utd(self, art19_module, tmp_path):
        """When AI provides no answers, ART19-OBL-1 → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_description_has_no_legal_citation_prefix(self, art19_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art19_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art19_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings for covered obligations."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art19_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
            and f.obligation_id in ("ART19-OBL-1", "ART19-OBL-1b")
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art19_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art19_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_obl_ids_present(self, art19_module, tmp_path):
        """All 3 obligation IDs must appear in scan findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art19_module.scan(str(tmp_path))
        obl_ids = {f.obligation_id for f in result.findings}
        for expected in ["ART19-OBL-1", "ART19-OBL-1b", "ART19-OBL-2"]:
            assert expected in obl_ids, f"Missing {expected} in findings: {obl_ids}"


# ── Alias tests ──

class TestArt19Aliases:

    def test_has_retention_policy_alias(self, art19_module, tmp_path):
        """has_retention_policy (alias for has_retention_config) should work."""
        ctx = _ctx_with("art19", {
            "has_log_retention": True,
            "has_retention_policy": True,
            "retention_days": 365,
        })
        BaseArticleModule.set_context(ctx)
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_retention_policy_alias_false(self, art19_module, tmp_path):
        """has_retention_policy=False (alias) → ART19-OBL-1b NON_COMPLIANT."""
        ctx = _ctx_with("art19", {
            "has_log_retention": True,
            "has_retention_policy": False,
        })
        BaseArticleModule.set_context(ctx)
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_log_retention_fallback_to_retention_config(self, art19_module, tmp_path):
        """has_log_retention not set but has_retention_config=True → ART19-OBL-1 PARTIAL."""
        ctx = _ctx_with("art19", {
            "has_retention_config": True,
            "retention_days": 365,
        })
        BaseArticleModule.set_context(ctx)
        result = art19_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL


# ── High-risk gate test ──

class TestArt19HighRiskGate:

    def test_not_high_risk_returns_not_applicable(self, art19_module, tmp_path):
        """Not-high-risk classification → NOT_APPLICABLE."""
        from core.context import ProjectContext
        ctx = ProjectContext(
            primary_language="python",
            risk_classification="not high-risk",
            risk_classification_confidence="high",
            compliance_answers={"art19": {}},
        )
        BaseArticleModule.set_context(ctx)
        result = art19_module.scan(str(tmp_path))
        assert result.overall_level == ComplianceLevel.NOT_APPLICABLE
