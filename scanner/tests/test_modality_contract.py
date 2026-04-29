"""§W Wave 5 — Deontic modality contract.

Every obligation in scanner/obligations/*.json carries a `modality` field
that classifies the deontic force of the requirement. Wire-format pinned
here so any new value (or accidental case/separator drift) surfaces in CI.

Canonical values (4):
  shall          — mandatory positive obligation (do this)
  shall not      — mandatory prohibition (with SPACE, not underscore)
  may            — permission (allowed, not required)
  is empowered   — Commission empowerment (Art. 6(6), Art. 11(3) etc.)

Pre-§W (2026-04-29): art53 + art54 had `shall_not` (underscore) instead of
`shall not` (space). Wave 5 corrected those to the majority canonical form.
"""

import glob
import json
import os

CANONICAL_MODALITIES = frozenset({
    "shall",
    "shall not",
    "may",
    "is empowered",
})

# Forbidden variants — would surface as silent drift if reintroduced.
FORBIDDEN_VARIANTS = frozenset({
    "shall_not",       # underscore form — pre-Wave 5 typo, eliminated
    "MAY",             # uppercase — fine in legal text but not as enum value
    "SHALL",
    "SHALL NOT",
    "must",            # not used by AI Act (it uses "shall" exclusively)
    "must not",
})


def _all_obligation_files():
    obl_dir = os.path.join(
        os.path.dirname(__file__), "..", "obligations",
    )
    return glob.glob(os.path.join(obl_dir, "*.json"))


def _all_obligations_with_modality():
    """Yield (file, obligation_dict) for every obligation that has modality."""
    for path in _all_obligation_files():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            continue
        for key, val in data.items():
            if not isinstance(val, list):
                continue
            for item in val:
                if isinstance(item, dict) and "modality" in item:
                    yield (path, item)


def test_every_obligation_modality_is_canonical():
    """Drift gate: any modality value outside the 4 canonical set fails CI.

    Currently 245+ obligations across 50+ files. If anyone adds a 5th
    modality value or reintroduces `shall_not` underscore, this test
    pinpoints the offending file + obligation id.
    """
    bad = []
    for path, obl in _all_obligations_with_modality():
        m = obl["modality"]
        if m not in CANONICAL_MODALITIES:
            bad.append(
                f"  {os.path.basename(path)}: {obl.get('id', '?')} "
                f"modality={m!r}"
            )
    assert not bad, (
        f"{len(bad)} obligation(s) use non-canonical modality:\n"
        + "\n".join(bad)
        + f"\nCanonical set: {sorted(CANONICAL_MODALITIES)}"
    )


def test_no_forbidden_variant_anywhere():
    """Belt-and-suspenders: no forbidden variant appears as a modality value."""
    for path, obl in _all_obligations_with_modality():
        m = obl["modality"]
        assert m not in FORBIDDEN_VARIANTS, (
            f"{os.path.basename(path)} obligation {obl.get('id')} uses "
            f"forbidden modality variant {m!r}"
        )


def test_majority_modality_is_shall():
    """Sanity gate: most obligations are positive `shall` requirements.

    If this ever flips (more `may` than `shall`), something has gone
    structurally wrong with the obligation decomposition methodology.
    """
    counts = {}
    for _, obl in _all_obligations_with_modality():
        m = obl["modality"]
        counts[m] = counts.get(m, 0) + 1
    assert counts.get("shall", 0) > sum(
        v for k, v in counts.items() if k != "shall"
    ), f"Expected `shall` to dominate, got: {counts}"


def test_canonical_set_size():
    """Drift gate on the canonical set itself — adding a 5th value
    requires updating this test AND auditing every consumer."""
    assert len(CANONICAL_MODALITIES) == 4
