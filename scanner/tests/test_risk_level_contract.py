"""§W Wave 3 — RiskLevel cross-system contract (Python side).

Canonical wire-format: 4 hyphenated lowercase values (prohibited / high-risk
/ limited-risk / minimal-risk). A SaaS-side TypeScript companion test pins
the same 4 values; both must change together if the canonical set evolves.

Out of scope: this test does NOT assert anything about the legacy variants
in `_NOT_HIGH_RISK_VALUES` (free-text "not high-risk", "low-risk", etc.).
Those are documented backward-compat for older `.compliancelintrc` files,
not part of the canonical enum.
"""

from scanner.core.protocol import BaseArticleModule


# Canonical risk-level values. Mirror of CANONICAL_RISK_LEVELS in
# risk-level-cross-system.test.ts (TS).
CANONICAL_RISK_LEVELS = frozenset({
    "prohibited",
    "high-risk",
    "limited-risk",
    "minimal-risk",
})


def test_canonical_not_high_risk_subset_present():
    """The 2 canonical not-high-risk values MUST be in _NOT_HIGH_RISK_VALUES.

    The set may have more (legacy free-text aliases) but it MUST contain at
    least these two canonical hyphenated values, otherwise SaaS-emitted
    "minimal-risk" / "limited-risk" would not skip the high-risk-only
    article scans (Art. 9-15 etc.).
    """
    not_hr = BaseArticleModule._NOT_HIGH_RISK_VALUES
    assert "minimal-risk" in not_hr
    assert "limited-risk" in not_hr


def test_no_underscore_variants_of_canonical_names():
    """`high_risk` / `limited_risk` / `minimal_risk` must NOT appear as enum values.

    The canonical 4 are hyphenated. `not_high_risk` IS allowed as a legacy
    alias for "not high-risk" (different semantics, accepted by design),
    but introducing an underscore form of the canonical names would diverge
    from the TS RISK_LEVELS contract.
    """
    not_hr = BaseArticleModule._NOT_HIGH_RISK_VALUES
    assert "high_risk" not in not_hr
    assert "limited_risk" not in not_hr
    assert "minimal_risk" not in not_hr


def test_canonical_values_are_hyphenated_lowercase():
    """Drift gate: every canonical value uses '-' separator and is lowercase."""
    for v in CANONICAL_RISK_LEVELS:
        assert v == v.lower()
        if v != "prohibited":
            assert "-" in v
            assert "_" not in v
