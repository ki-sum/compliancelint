"""§W Wave 1 — Python ComplianceLevel cross-system contract.

The Python scanner serializes ComplianceLevel as lowercase wire-format strings.
A SaaS-side TypeScript companion test (in the dashboard repo) pins the same
contract and normalizes the values to UPPERCASE FindingStatus on receipt
(PARTIAL → UNABLE_TO_DETERMINE). If either side adds/removes/renames a value
without the other, cl_sync silently drops or mis-categorizes findings.

Both this test and the SaaS-side companion pin the contract; both must
change together when the enum legitimately evolves.
"""

from scanner.core.protocol import ComplianceLevel


# Wire-format values that Python ComplianceLevel.value emits.
# Mirror of PYTHON_WIRE_VALUES in finding-status-cross-system.test.ts.
PYTHON_WIRE_VALUES = frozenset({
    "compliant",
    "partial",
    "non_compliant",
    "not_applicable",
    "unable_to_determine",
})


def test_compliance_level_has_exactly_5_members():
    """Drift gate: adding/removing a member breaks the cross-system contract."""
    members = {m.value for m in ComplianceLevel}
    assert members == PYTHON_WIRE_VALUES, (
        f"ComplianceLevel drifted from cross-system contract.\n"
        f"  Expected: {sorted(PYTHON_WIRE_VALUES)}\n"
        f"  Got:      {sorted(members)}\n"
        f"If this is intentional, update both this test AND the SaaS-side "
        f"companion finding-status-cross-system.test.ts."
    )


def test_compliance_level_values_are_lowercase():
    """Wire-format must be lowercase. UPPERCASE is the TS convention."""
    for member in ComplianceLevel:
        assert member.value == member.value.lower(), (
            f"ComplianceLevel.{member.name} = {member.value!r} is not lowercase. "
            f"Wire-format must be lowercase to match TS normalizeFindingStatus contract."
        )


def test_compliance_level_names_are_uppercase_snake():
    """Python convention: enum member NAMES are UPPER_SNAKE_CASE."""
    for member in ComplianceLevel:
        assert member.name == member.name.upper(), (
            f"ComplianceLevel.{member.name} should be UPPER_SNAKE_CASE."
        )


def test_partial_is_distinguishable_from_unable_to_determine():
    """PARTIAL and UNABLE_TO_DETERMINE are distinct on the Python side.

    They collapse to the same TS value (UNABLE_TO_DETERMINE) by intentional
    design, but Python should preserve the semantic distinction internally
    so detectors can return PARTIAL when evidence exists but completeness
    cannot be confirmed.
    """
    assert ComplianceLevel.PARTIAL != ComplianceLevel.UNABLE_TO_DETERMINE
    assert ComplianceLevel.PARTIAL.value == "partial"
    assert ComplianceLevel.UNABLE_TO_DETERMINE.value == "unable_to_determine"
