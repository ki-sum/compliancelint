"""Art. 12 Record Keeping tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  has_logging             → ART12-OBL-1, ART12-OBL-2a, ART12-OBL-2b
  has_retention_config    → ART19-OBL-1b (with retention_days for threshold)
  Manual (always UTD)     → ART12-OBL-2c
  Scope-limited (gap)     → ART12-OBL-3a, 3b, 3c, 3d (biometric only)
  Scope-limited (gap)     → ART19-OBL-2 (financial institution), ART26-OBL-6 (deployer)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with

RETENTION_MINIMUM_DAYS = 180


def _full_true_ctx():
    """All automatable fields True."""
    return _ctx_with("art12", {
        "has_logging": True,
        "logging_description": "structlog with JSON output",
        "logging_evidence": ["src/logging_config.py:5"],
        "has_retention_config": True,
        "retention_days": 365,
        "retention_evidence": "LOG_RETENTION=365d in config.yaml",
    })


def _full_false_ctx():
    """All automatable fields False."""
    return _ctx_with("art12", {
        "has_logging": False,
        "logging_description": "",
        "logging_evidence": [],
        "has_retention_config": False,
        "retention_days": None,
        "retention_evidence": "",
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art12", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART12-OBL-1: Logging system (has_logging) ──

class TestArt12Obl1:

    def test_has_logging_true_gives_partial(self, art12_module, tmp_path):
        """has_logging=True → ART12-OBL-1 PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART12-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_logging_false_gives_non_compliant(self, art12_module, tmp_path):
        """has_logging=False → ART12-OBL-1 NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART12-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_logging_none_gives_utd(self, art12_module, tmp_path):
        """has_logging=None → ART12-OBL-1 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART12-OBL-1")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART12-OBL-2a: Risk event logging (has_logging) ──

class TestArt12Obl2a:

    def test_has_logging_true_gives_partial(self, art12_module, tmp_path):
        """has_logging=True → ART12-OBL-2a PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART12-OBL-2a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_logging_false_gives_non_compliant(self, art12_module, tmp_path):
        """has_logging=False → ART12-OBL-2a NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART12-OBL-2a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_logging_none_gives_utd(self, art12_module, tmp_path):
        """has_logging=None → ART12-OBL-2a UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART12-OBL-2a")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART12-OBL-2b: Post-market monitoring logging (has_logging) ──

class TestArt12Obl2b:

    def test_has_logging_true_gives_partial(self, art12_module, tmp_path):
        """has_logging=True → ART12-OBL-2b PARTIAL."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART12-OBL-2b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_has_logging_false_gives_non_compliant(self, art12_module, tmp_path):
        """has_logging=False → ART12-OBL-2b NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART12-OBL-2b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_has_logging_none_gives_utd(self, art12_module, tmp_path):
        """has_logging=None → ART12-OBL-2b UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART12-OBL-2b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── ART19-OBL-1b: Log retention (has_retention_config + retention_days) ──

class TestArt19Obl1Retention:

    def test_retention_sufficient_gives_partial(self, art12_module, tmp_path):
        """has_retention_config=True, retention_days >= 180 → ART19-OBL-1b PARTIAL."""
        ctx = _ctx_with("art12", {
            "has_logging": True,
            "logging_description": "winston",
            "logging_evidence": ["app.js:1"],
            "has_retention_config": True,
            "retention_days": 365,
            "retention_evidence": "LOG_RETENTION=365d in config.yaml",
        })
        BaseArticleModule.set_context(ctx)
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_retention_insufficient_gives_non_compliant(self, art12_module, tmp_path):
        """has_retention_config=True, retention_days < 180 → ART19-OBL-1b NON_COMPLIANT."""
        ctx = _ctx_with("art12", {
            "has_logging": True,
            "logging_description": "logback",
            "logging_evidence": [],
            "has_retention_config": True,
            "retention_days": 30,
            "retention_evidence": "maxHistory=30 in logback.xml",
        })
        BaseArticleModule.set_context(ctx)
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_retention_config_true_days_none_gives_partial(self, art12_module, tmp_path):
        """has_retention_config=True, retention_days=None → ART19-OBL-1b PARTIAL."""
        ctx = _ctx_with("art12", {
            "has_logging": True,
            "logging_description": "structlog",
            "logging_evidence": ["app.py"],
            "has_retention_config": True,
            "retention_days": None,
            "retention_evidence": "retention config found but period unknown",
        })
        BaseArticleModule.set_context(ctx)
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_retention_config_false_gives_non_compliant(self, art12_module, tmp_path):
        """has_retention_config=False → ART19-OBL-1b NON_COMPLIANT."""
        ctx = _ctx_with("art12", {
            "has_logging": True,
            "logging_description": "test",
            "logging_evidence": [],
            "has_retention_config": False,
            "retention_days": None,
            "retention_evidence": "",
        })
        BaseArticleModule.set_context(ctx)
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT

    def test_retention_config_none_gives_utd(self, art12_module, tmp_path):
        """has_retention_config=None → ART19-OBL-1b UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE

    def test_retention_exactly_180_gives_partial(self, art12_module, tmp_path):
        """retention_days == 180 (boundary) → ART19-OBL-1b PARTIAL."""
        ctx = _ctx_with("art12", {
            "has_logging": True,
            "logging_description": "test",
            "logging_evidence": [],
            "has_retention_config": True,
            "retention_days": 180,
            "retention_evidence": "180 days configured",
        })
        BaseArticleModule.set_context(ctx)
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL

    def test_retention_179_gives_non_compliant(self, art12_module, tmp_path):
        """retention_days == 179 (just below threshold) → ART19-OBL-1b NON_COMPLIANT."""
        ctx = _ctx_with("art12", {
            "has_logging": True,
            "logging_description": "test",
            "logging_evidence": [],
            "has_retention_config": True,
            "retention_days": 179,
            "retention_evidence": "179 days",
        })
        BaseArticleModule.set_context(ctx)
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT


# ── Manual obligations: always UNABLE_TO_DETERMINE ──

class TestArt12ManualObligations:

    def test_obl2c_always_utd_with_all_true(self, art12_module, tmp_path):
        """ART12-OBL-2c (deployer monitoring) always UTD even with all-true answers."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART12-OBL-2c")
        assert len(obl) > 0, "ART12-OBL-2c not in findings"
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
            f"ART12-OBL-2c should always be UTD, got {obl[0].level}"
        )

    def test_obl2c_always_utd_with_all_false(self, art12_module, tmp_path):
        """ART12-OBL-2c always UTD even with all-false answers."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART12-OBL-2c")
        assert len(obl) > 0, "ART12-OBL-2c not in findings"
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
            f"ART12-OBL-2c should always be UTD, got {obl[0].level}"
        )


# ── Structural tests ──

class TestArt12Structural:

    def test_all_11_obligation_ids_in_json(self, art12_module):
        """Obligation JSON must have exactly 11 obligations."""
        data = art12_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 11

    def test_obligation_coverage_present(self, art12_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art12_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art12_module, tmp_path):
        """When AI provides no answers, key automatable obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art12_module.scan(str(tmp_path))
        automatable_ids = [
            "ART12-OBL-1", "ART12-OBL-2a", "ART12-OBL-2b",
            "ART19-OBL-1b",
        ]
        for obl_id in automatable_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art12_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 12(1)]."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art12_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art12_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art12_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art12_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art12_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0


# ── Alias tests ──

class TestArt12Aliases:

    def test_has_retention_policy_alias(self, art12_module, tmp_path):
        """has_retention_policy (alias for has_retention_config) should work."""
        ctx = _ctx_with("art12", {
            "has_logging": True,
            "logging_description": "test",
            "logging_evidence": [],
            "has_retention_policy": False,
            "retention_days": None,
            "retention_evidence": "",
        })
        BaseArticleModule.set_context(ctx)
        result = art12_module.scan(str(tmp_path))
        obl = _find(result, "ART19-OBL-1b")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT
