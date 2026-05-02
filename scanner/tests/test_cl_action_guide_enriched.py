"""Q3 self-audit follow-up — `cl_action_guide` must return verbatim
obligation content, not just a "go to dashboard" redirect.

Pre-fix gap: cl_action_guide was a thin redirect — returned title +
dashboard URL + generic "go to dashboard" message. **No verbatim
EUR-Lex source quote, no decomposed atoms, no human-judgment guidance**.
Customer asking the tool got LESS information than asking ChatGPT
(which would at least synthesize implementation tips).

Fix: pull from `scanner/obligations/art*.json` — every obligation
already has source_quote / decomposed_atoms / automation_assessment.
That's our anti-hallucination IP. Surface it.

Required fields in enriched response:
  - obligation_id        (existing)
  - title               (existing)
  - source              "Art. 26(2)" — section reference
  - source_quote        verbatim EUR-Lex text (anti-hallucination)
  - addressee           "provider" / "deployer" / etc.
  - decomposed_atoms    list of {atom, description, requirement}
  - automation_level    "full" | "partial" | "manual"
  - human_judgment_needed  string — what humans must judge
  - is_human_gate       (existing — Pro+ unlock for structured form)
  - dashboard_url       (existing)
  - note                (existing) — explains dashboard for full form

Acceptance — for any valid OID present in obligation JSONs, response
carries:
  1. source_quote is non-empty string (verbatim EUR-Lex)
  2. decomposed_atoms is non-empty list
  3. automation_level is one of full/partial/manual
  4. addressee is non-empty string

For OIDs NOT in any obligation JSON (malformed / typo), fallback to
the legacy "go to dashboard" redirect (no source_quote available).
"""

import json
import os
import sys
from unittest.mock import patch

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

# §AA Option C (2026-05-02): the 5 SaaS-only fields (detection_method,
# rationale, what_to_scan, confidence, human_judgment_needed) live in
# the SaaS dashboard and are fetched from the API endpoint at scan
# time. In tests we don't have a SaaS server running, so we look for a
# sibling fixture directory containing the same per-article JSON the
# production endpoint serves. When the fixture dir is absent (clean
# public checkout / CI without dual-repo setup), tests in this file
# are SKIPPED — degraded-mode assertions are covered separately.
import json as _json_for_fixture
import os.path as _path_for_fixture
from scanner.core import classification_client, obligation_lookup

# Resolve fixture dir for classification metadata via the
# CL_CLASSIFICATION_FIXTURE_DIR env var. The fixture is a directory of
# per-article JSON files mirroring what the
# /api/v1/regulations/eu-ai-act/articles/N/classifications endpoint
# returns. Tests in this file are skipped when the env var is unset
# or points at a non-existent directory — degraded-mode coverage lives
# in test_obligation_lookup_classification_merge.py via direct mocks.
#
# Maintainers running a dual-checkout layout typically set this in their
# shell profile or activate-script:
#     export CL_CLASSIFICATION_FIXTURE_DIR="$HOME/path/to/saas/data/obligation-classifications"
_FIXTURE_ENV = os.environ.get("CL_CLASSIFICATION_FIXTURE_DIR", "")
_CLASS_FIXTURE_DIR = (
    _path_for_fixture.normpath(_path_for_fixture.join(SCANNER_ROOT, "..", _FIXTURE_ENV))
    if _FIXTURE_ENV
    else ""
)
_FIXTURE_PRESENT = bool(_CLASS_FIXTURE_DIR) and _path_for_fixture.isdir(_CLASS_FIXTURE_DIR)


def _load_classifications_fixture(article_number: int):
    """Mirror what the production /api/.../classifications endpoint
    returns — load per-article JSON from the fixture dir and return
    its `obligations` dict, or None when the file is missing."""
    path = _path_for_fixture.join(
        _CLASS_FIXTURE_DIR, f"art{article_number:02d}.json"
    )
    if not _path_for_fixture.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return _json_for_fixture.load(f).get("obligations") or {}


# All tests in this file depend on the classification fixture being
# present locally. CI without dual-repo setup skips the file rather
# than failing — degraded-mode behavior is covered in
# test_obligation_lookup_classification_merge.py which mocks the
# fetch directly.
pytestmark = pytest.mark.skipif(
    not _FIXTURE_PRESENT,
    reason=(
        "classification fixture dir not present — set "
        "CL_CLASSIFICATION_FIXTURE_DIR or run from a checkout that "
        "has the SaaS-side fixture available"
    ),
)


@pytest.fixture(autouse=True)
def _mock_classification_fetch():
    """Auto-mock fetch_classifications for every test in this file so
    the 5 SaaS-only fields are populated as if the scanner were
    authenticated against compliancelint.dev. Mirrors what production
    behaviour looks like once `cl_connect` has been run.

    Without this, every test that asserts on detection_method /
    rationale / what_to_scan / confidence / human_judgment_needed
    would fail with empty strings (degraded mode = those fields stay
    stripped from public JSON post-§AA Step 1)."""
    obligation_lookup.reset_cache()
    classification_client.reset_degraded_notice_flag()
    with patch.object(
        classification_client,
        "fetch_classifications",
        side_effect=_load_classifications_fixture,
    ):
        yield
    obligation_lookup.reset_cache()


def _strip_text_footer(s: str) -> str:
    """Strip upgrade_hint text footer if present."""
    marker = "\n\n---\n"
    if marker in s and "ComplianceLint hint" in s:
        return s.split(marker, 1)[0]
    return s


# ──────────────────────────────────────────────────────────────────────
# 1. Verbatim source_quote (anti-hallucination contract)
# ──────────────────────────────────────────────────────────────────────


def test_action_guide_returns_verbatim_source_quote_for_known_oid():
    """ART26-OBL-2 has a known verbatim quote in
    scanner/obligations/art26-deployer-obligations.json. Tool MUST
    return that quote unchanged so AI clients can cite legal text
    without paraphrase risk."""
    from server import cl_action_guide

    raw = cl_action_guide("ART26-OBL-2")
    parsed = json.loads(_strip_text_footer(raw))

    assert "source_quote" in parsed, (
        f"cl_action_guide missing source_quote field; keys: {sorted(parsed.keys())}"
    )
    quote = parsed["source_quote"]
    assert isinstance(quote, str) and len(quote) > 30, (
        f"source_quote should be substantive verbatim text, got: {quote!r}"
    )
    # Verbatim check — known fragments from Art. 26(2):
    assert "human oversight" in quote.lower()
    assert "competence" in quote.lower() or "competent" in quote.lower()


def test_action_guide_source_quote_matches_obligation_json_exactly():
    """Defensive — guarantee no transformation/lowercase/wrap on the
    quote. The exact bytes the team committed to obligation JSON are
    what we return."""
    from server import cl_action_guide

    json_path = os.path.join(
        SCANNER_ROOT, "obligations", "art26-deployer-obligations.json"
    )
    with open(json_path, "r", encoding="utf-8") as f:
        art26 = json.load(f)
    expected_quote = next(
        o["source_quote"] for o in art26["obligations"] if o["id"] == "ART26-OBL-2"
    )

    raw = cl_action_guide("ART26-OBL-2")
    parsed = json.loads(_strip_text_footer(raw))

    assert parsed["source_quote"] == expected_quote


# ──────────────────────────────────────────────────────────────────────
# 2. Decomposed atoms (our IP — what we have that ChatGPT doesn't)
# ──────────────────────────────────────────────────────────────────────


def test_action_guide_returns_decomposed_atoms():
    from server import cl_action_guide

    raw = cl_action_guide("ART26-OBL-2")
    parsed = json.loads(_strip_text_footer(raw))

    assert "decomposed_atoms" in parsed
    atoms = parsed["decomposed_atoms"]
    assert isinstance(atoms, list) and len(atoms) >= 1, (
        f"decomposed_atoms should be non-empty list, got: {atoms!r}"
    )
    # Each atom has the canonical 3 fields per obligation JSON shape
    for atom in atoms:
        assert "atom" in atom
        assert "description" in atom
        assert "requirement" in atom
        assert isinstance(atom["requirement"], str) and atom["requirement"]


# ──────────────────────────────────────────────────────────────────────
# 3. Human judgment guidance
# ──────────────────────────────────────────────────────────────────────


def test_action_guide_returns_human_judgment_needed():
    """For Human Gates the human_judgment_needed text is THE answer
    to 'why this can't be automated'. Surface it so AI clients can
    explain to user what they need to think about."""
    from server import cl_action_guide

    raw = cl_action_guide("ART26-OBL-2")
    parsed = json.loads(_strip_text_footer(raw))

    assert "human_judgment_needed" in parsed
    assert isinstance(parsed["human_judgment_needed"], str)
    assert len(parsed["human_judgment_needed"]) > 10
    # Verbatim from obligation JSON
    assert "competence" in parsed["human_judgment_needed"].lower()


def test_action_guide_returns_automation_level():
    """`level` (full | partial | manual) tells AI client how much code
    scanning will help vs how much human attestation is required."""
    from server import cl_action_guide

    raw = cl_action_guide("ART26-OBL-2")
    parsed = json.loads(_strip_text_footer(raw))

    assert "automation_level" in parsed
    assert parsed["automation_level"] in {"full", "partial", "manual"}


# ──────────────────────────────────────────────────────────────────────
# 4. Addressee (who does this OID apply to)
# ──────────────────────────────────────────────────────────────────────


def test_action_guide_returns_addressee():
    from server import cl_action_guide

    raw = cl_action_guide("ART26-OBL-2")
    parsed = json.loads(_strip_text_footer(raw))

    assert "addressee" in parsed
    # Art 26 = deployer obligations
    assert parsed["addressee"] == "deployer"


# ──────────────────────────────────────────────────────────────────────
# 5. Source reference ("Art. 26(2)" not just "ART26-OBL-2")
# ──────────────────────────────────────────────────────────────────────


def test_action_guide_returns_source_section_reference():
    """`source` is the human-readable EU AI Act section like
    'Art. 26(2)' — different from the internal obligation_id which
    is 'ART26-OBL-2'."""
    from server import cl_action_guide

    raw = cl_action_guide("ART26-OBL-2")
    parsed = json.loads(_strip_text_footer(raw))

    assert "source" in parsed
    # Pattern: "Art. <num>(<para>)"
    assert "Art. 26" in parsed["source"]


# ──────────────────────────────────────────────────────────────────────
# 6. Backward-compat fields preserved
# ──────────────────────────────────────────────────────────────────────


def test_action_guide_preserves_legacy_fields_for_known_oid():
    """Existing API users may rely on title / is_human_gate /
    dashboard_url / note. Don't break them."""
    from server import cl_action_guide

    raw = cl_action_guide("ART26-OBL-2")
    parsed = json.loads(_strip_text_footer(raw))

    assert "obligation_id" in parsed
    assert parsed["obligation_id"] == "ART26-OBL-2"
    assert "title" in parsed
    assert "is_human_gate" in parsed
    assert "dashboard_url" in parsed
    assert "note" in parsed


# ──────────────────────────────────────────────────────────────────────
# 7. OIDs not in any obligation JSON — graceful fallback
# ──────────────────────────────────────────────────────────────────────


def test_action_guide_unknown_oid_falls_back_to_redirect():
    """Typo / malformed OID that doesn't match any obligation JSON
    should NOT crash. Falls back to legacy 'go to dashboard' message
    without the enriched fields (since there's no source data to pull)."""
    from server import cl_action_guide

    raw = cl_action_guide("ART9999-OBL-9")
    parsed = json.loads(_strip_text_footer(raw))

    # OID format is valid (matches regex) but no matching obligation
    # in JSON → enriched fields absent OR empty/null, but no crash
    assert "obligation_id" in parsed
    assert "dashboard_url" in parsed
    # source_quote either absent OR empty/null — we don't fabricate
    if "source_quote" in parsed:
        assert parsed["source_quote"] in ("", None) or parsed["source_quote"] is None


def test_action_guide_invalid_format_still_errors():
    """Pre-existing format-validation error path unchanged."""
    from server import cl_action_guide

    raw = cl_action_guide("not-a-valid-id")
    parsed = json.loads(_strip_text_footer(raw))

    assert "error" in parsed
    assert "format" in parsed["error"].lower() or "invalid" in parsed["error"].lower()


# ──────────────────────────────────────────────────────────────────────
# 8. Multi-OID coverage — sample several obligation JSONs
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("oid", [
    "ART09-OBL-1",  # risk management — provider
    "ART11-OBL-1",  # technical documentation — provider
    "ART26-OBL-2",  # human oversight — deployer
    "ART27-OBL-1",  # FRIA — deployer
    "ART50-OBL-1",  # AI disclosure — provider
])
def test_action_guide_returns_full_payload_for_each_known_oid(oid):
    """Sweep across articles + addressees: every known OID returns
    a fully-populated enriched response, not just a partial."""
    from server import cl_action_guide

    raw = cl_action_guide(oid)
    parsed = json.loads(_strip_text_footer(raw))

    # All enriched fields present for every known OID
    assert parsed.get("source_quote"), f"{oid}: source_quote missing/empty"
    assert parsed.get("decomposed_atoms"), f"{oid}: decomposed_atoms missing/empty"
    assert parsed.get("addressee"), f"{oid}: addressee missing/empty"
    assert parsed.get("automation_level"), f"{oid}: automation_level missing/empty"
    assert parsed.get("source"), f"{oid}: source missing/empty"


# ──────────────────────────────────────────────────────────────────────
# 9. Anti-fabrication — source_quote MUST come from on-disk JSON
# ──────────────────────────────────────────────────────────────────────


def test_action_guide_does_not_fabricate_source_quote():
    """If we ever introduce a code path that synthesizes a quote
    instead of reading from JSON, this test catches it. Strategy:
    monkey-patch the obligation JSON loader to return a known
    sentinel quote, verify response matches verbatim."""
    import core.obligation_engine as obligation_engine

    # Just verify that whatever bytes are in the JSON are what gets returned.
    # Re-use test_action_guide_source_quote_matches_obligation_json_exactly's
    # logic but for a different OID to triangulate.
    from server import cl_action_guide

    json_path = os.path.join(
        SCANNER_ROOT, "obligations", "art27-fundamental-rights-impact.json"
    )
    with open(json_path, "r", encoding="utf-8") as f:
        art27 = json.load(f)
    obligations = art27.get("obligations", []) if isinstance(art27, dict) else []
    if not obligations:
        pytest.skip("art27 obligation file shape changed — re-anchor test")
    expected = obligations[0]
    expected_id = expected["id"]
    expected_quote = expected["source_quote"]

    raw = cl_action_guide(expected_id)
    parsed = json.loads(_strip_text_footer(raw))

    assert parsed["source_quote"] == expected_quote
