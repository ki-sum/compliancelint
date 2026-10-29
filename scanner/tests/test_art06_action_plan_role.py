"""Art. 6 action plan follows the role (series-4 recording, 2026-10-29).

A deployer of a high-risk recruiting system (dashboard role: deployer only) asked "What is still open?" and the plan
listed the provider's items: "Evaluate Art. 6(3) exception applicability" (the derogation and its Art. 6(4)
documentation and registration are the provider's) and "Plan Chapter III, Section 2 compliance" (Arts. 8-15 are
requirements a provider ensures, Art. 16(a)), and the classification action told the reader to document an Art. 6(3)
assessment and register under Art. 49(2). A provider, or a role nobody has confirmed, keeps all three.
"""
from core.protocol import BaseArticleModule
from conftest import _ctx_with

ANNEX_III = {
    "annex_iii_categories": ["Employment"],
    "annex_i_product_type": None,
    "is_high_risk": True,
    "reasoning": "Ranks and filters job applications",
}


def _plan(module, tmp_path, scope: dict | None):
    ctx = _ctx_with("art6", ANNEX_III)
    if scope is not None:
        ctx.compliance_answers["_scope"] = scope
    BaseArticleModule.set_context(ctx)
    return module.action_plan(module.scan(str(tmp_path)))


def _titles(plan) -> list[str]:
    return [a.action for a in plan.actions]


def test_deployer_only_gets_no_provider_actions(art06_module, tmp_path):
    plan = _plan(art06_module, tmp_path, {"is_provider": False, "is_deployer": True})
    titles = _titles(plan)
    assert "Evaluate Art. 6(3) exception applicability" not in titles
    assert not any(a.article == "Arts. 8-15" for a in plan.actions), titles
    assert not any(a.article == "Art. 43" for a in plan.actions), titles
    classification = next(a for a in plan.actions if a.action == "Complete formal Art. 6 risk classification")
    assert "Art. 49(2)" not in classification.details
    assert "Art. 6(4)" not in classification.details


def test_deployer_keeps_the_classification_and_annex_iii_check(art06_module, tmp_path):
    """Guard: whether the system is high-risk decides the deployer's own duties, so those two actions stay."""
    titles = _titles(_plan(art06_module, tmp_path, {"is_provider": False, "is_deployer": True}))
    assert "Complete formal Art. 6 risk classification" in titles
    assert any(t.startswith("Evaluate Annex III classification for:") for t in titles), titles


def test_provider_keeps_all_actions(art06_module, tmp_path):
    plan = _plan(art06_module, tmp_path, {"is_provider": True, "is_deployer": False})
    titles = _titles(plan)
    assert "Evaluate Art. 6(3) exception applicability" in titles
    assert any(a.article == "Arts. 8-15" for a in plan.actions), titles
    assert any(a.article == "Art. 43" for a in plan.actions), titles
    classification = next(a for a in plan.actions if a.action == "Complete formal Art. 6 risk classification")
    assert "Art. 49(2)" in classification.details


def test_unconfirmed_role_keeps_all_actions(art06_module, tmp_path):
    """No role from the dashboard or the assistant: nothing is ruled out."""
    plan = _plan(art06_module, tmp_path, None)
    titles = _titles(plan)
    assert "Evaluate Art. 6(3) exception applicability" in titles
    assert any(a.article == "Arts. 8-15" for a in plan.actions), titles
