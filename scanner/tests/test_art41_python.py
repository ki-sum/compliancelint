"""Art. 41 Common Specifications tests — obligation mapping.

Tests verify the obligation mapper logic: AI answers → Finding.
The scanner does no detection; the AI provides compliance_answers.

Obligation mapping:
  follows_common_specifications + has_alternative_justification → ART41-OBL-5
  - follows_common_specifications=True  → NOT_APPLICABLE (no justification needed)
  - follows_common_specifications=False → check has_alternative_justification
  - follows_common_specifications=None  → UNABLE_TO_DETERMINE (conditional)
"""
from core.protocol import ComplianceLevel, BaseArticleModule
from conftest import _ctx_with


def _full_true_ctx():
    """All automatable fields True — provider follows common specifications."""
    return _ctx_with("art41", {
        "follows_common_specifications": True,
        "has_alternative_justification": True,
    })


def _full_false_ctx():
    """All automatable fields False — provider deviates with no justification."""
    return _ctx_with("art41", {
        "follows_common_specifications": False,
        "has_alternative_justification": False,
    })


def _empty_ctx():
    """No answers provided (all None)."""
    return _ctx_with("art41", {})


def _find(result, obl_id):
    """Get findings for an obligation ID."""
    return [f for f in result.findings if f.obligation_id == obl_id]


# ── ART41-OBL-5: Justify alternative technical solutions ──

class TestArt41Obl5FollowsCS:
    """Tests when provider follows common specifications → NOT_APPLICABLE."""

    def test_follows_cs_true_gives_not_applicable(self, art41_module, tmp_path):
        """follows_common_specifications=True → ART41-OBL-5 NOT_APPLICABLE."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art41_module.scan(str(tmp_path))
        obl = _find(result, "ART41-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NOT_APPLICABLE


class TestArt41Obl5DeviatesWithJustification:
    """Tests when provider deviates but has justification."""

    def test_deviates_with_justification_gives_partial(self, art41_module, tmp_path):
        """follows_common_specifications=False, has_alternative_justification=True → PARTIAL."""
        ctx = _ctx_with("art41", {
            "follows_common_specifications": False,
            "has_alternative_justification": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art41_module.scan(str(tmp_path))
        obl = _find(result, "ART41-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.PARTIAL


class TestArt41Obl5DeviatesNoJustification:
    """Tests when provider deviates without justification."""

    def test_deviates_no_justification_gives_non_compliant(self, art41_module, tmp_path):
        """follows_common_specifications=False, has_alternative_justification=False → NON_COMPLIANT."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art41_module.scan(str(tmp_path))
        obl = _find(result, "ART41-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.NON_COMPLIANT


class TestArt41Obl5DeviatesJustificationUnknown:
    """Tests when provider deviates but justification status unknown."""

    def test_deviates_justification_none_gives_utd(self, art41_module, tmp_path):
        """follows_common_specifications=False, has_alternative_justification=None → UTD."""
        ctx = _ctx_with("art41", {
            "follows_common_specifications": False,
            "has_alternative_justification": None,
        })
        BaseArticleModule.set_context(ctx)
        result = art41_module.scan(str(tmp_path))
        obl = _find(result, "ART41-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


class TestArt41Obl5FollowsCSUnknown:
    """Tests when follows_common_specifications is not provided."""

    def test_follows_cs_none_gives_utd(self, art41_module, tmp_path):
        """follows_common_specifications=None → ART41-OBL-5 UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art41_module.scan(str(tmp_path))
        obl = _find(result, "ART41-OBL-5")
        assert len(obl) > 0
        assert obl[0].level == ComplianceLevel.UNABLE_TO_DETERMINE


# ── Structural tests ──

class TestArt41Structural:

    def test_all_1_obligation_ids_in_json(self, art41_module):
        """Obligation JSON must have exactly 1 obligation."""
        data = art41_module._load_obligations()
        obligations = data.get("obligations", [])
        assert len(obligations) == 1

    def test_obligation_coverage_present(self, art41_module, tmp_path):
        """ScanResult must include obligation_coverage metadata."""
        result = art41_module.scan(str(tmp_path))
        assert result.details.get("obligation_coverage", {}).get("total_obligations", 0) > 0

    def test_no_answers_all_key_obligations_utd(self, art41_module, tmp_path):
        """When AI provides no answers, all obligations → UNABLE_TO_DETERMINE."""
        BaseArticleModule.set_context(_empty_ctx())
        result = art41_module.scan(str(tmp_path))
        all_ids = ["ART41-OBL-5"]
        for obl_id in all_ids:
            findings = _find(result, obl_id)
            assert len(findings) > 0, f"{obl_id} not in findings"
            assert findings[0].level == ComplianceLevel.UNABLE_TO_DETERMINE, (
                f"{obl_id} should be UTD with no answers, got {findings[0].level}"
            )

    def test_description_has_no_legal_citation_prefix(self, art41_module, tmp_path):
        """Finding descriptions must not start with legal citation prefix like [Art. 41(5)]."""
        ctx = _ctx_with("art41", {
            "follows_common_specifications": False,
            "has_alternative_justification": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art41_module.scan(str(tmp_path))
        for f in result.findings:
            assert not f.description.startswith("[Art."), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )
            assert not f.description.startswith("[ART"), (
                f"{f.obligation_id} description starts with legal citation: {f.description[:60]}"
            )

    def test_all_true_no_non_compliant(self, art41_module, tmp_path):
        """All-true answers → no NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_true_ctx())
        result = art41_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT and not f.is_informational
        ]
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} NON_COMPLIANT: "
            f"{[(f.obligation_id, f.description[:40]) for f in non_compliant]}"
        )

    def test_all_false_has_non_compliant(self, art41_module, tmp_path):
        """All-false answers → at least some NON_COMPLIANT findings."""
        BaseArticleModule.set_context(_full_false_ctx())
        result = art41_module.scan(str(tmp_path))
        non_compliant = [
            f for f in result.findings
            if f.level == ComplianceLevel.NON_COMPLIANT
        ]
        assert len(non_compliant) > 0

    def test_all_1_obligations_appear_in_findings(self, art41_module, tmp_path):
        """All 1 obligation must appear in findings."""
        ctx = _ctx_with("art41", {
            "follows_common_specifications": False,
            "has_alternative_justification": True,
        })
        BaseArticleModule.set_context(ctx)
        result = art41_module.scan(str(tmp_path))
        found_ids = {f.obligation_id for f in result.findings}
        expected_ids = {"ART41-OBL-5"}
        missing = expected_ids - found_ids
        assert not missing, f"Missing obligation IDs in findings: {missing}"

    def test_summary_present(self, art41_module, tmp_path):
        """ScanResult must include article title and number."""
        result = art41_module.scan(str(tmp_path))
        assert result.article_number == 41
        assert result.article_title == "Common specifications"
