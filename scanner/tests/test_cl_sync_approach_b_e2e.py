"""§AT.19 Phase 3 LE #7 (2026-05-13) — cl_sync Approach (b) E2E test.

Full flow exercised:

    1. Seed `.compliancelint/local/articles/art50.json` containing AI's
       hypothesis for a HYBRID obligation (ART50-OBL-3) at level=compliant.
    2. Stub subprocess.run so curl-POST to /api/v1/scans is captured
       (no real network).
    3. Call cl_sync(project_path).
    4. Assert the captured POST body has ART50-OBL-3 rewritten to
       level=unable_to_determine + a Human Gates hint. This proves
       Approach (b) runs at the cl_sync boundary — the IDE AI client
       can still see the raw hypothesis from cl_scan_all, but the SaaS
       dashboard is shown the structurally-correct UTD state.

Why this matters: pre-Phase-2 the variance was 29 / 87 / 101 / 87 / 227
findings across scans of unchanged code (Bug 2). Approach (b) collapses
hybrid OIDs to UTD at the cl_sync boundary so AI variance can no longer
infect the dashboard. The existing `test_approach_b_post_process.py`
pins the helper in isolation; THIS test pins the full pipeline path.

Companion test on the SaaS side would mock the /scans POST handler and
assert the parsed body lands in the DB with level=unable_to_determine.
That side is exercised by `tests/route/post-scans.test.ts` in the
dashboard repo (out of scope here).
"""
import json
import os
import subprocess
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


def _seed_rc(project_path: str) -> None:
    rc = os.path.join(project_path, ".compliancelintrc")
    with open(rc, "w", encoding="utf-8") as f:
        json.dump(
            {
                "saas_api_key": "test-approach-b-key",
                "saas_url": "https://dash.test.local",
                "project_id": "proj-approach-b-fixture",
                "repo_name": "acme/hybrid-test-repo",
                "attester_name": "QA Bot",
                "attester_email": "qa@example.test",
            },
            f,
        )


def _seed_art50_state_with_hybrid_compliant(project_path: str) -> None:
    """Seed art50.json with a HYBRID OID at level=compliant (AI's verdict)
    and a CODE OID at level=full so we can verify only hybrids get rewritten.

    ART50-OBL-3 is type=hybrid in obligation-classification.json — it gates
    on AI-generated content disclosure, where the legal-interpretation half
    cannot be answered from code alone. AI may guess COMPLIANT based on
    finding the disclosure string in source, but final attestation must
    come from a human (HG wizard or cl_update_finding).

    ART50-OBL-1 is type=code — scanner detection is authoritative. The
    post-process must NOT touch this one.
    """
    art_dir = os.path.join(project_path, ".compliancelint", "local", "articles")
    os.makedirs(art_dir, exist_ok=True)
    art_file = os.path.join(art_dir, "art50.json")
    with open(art_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "article": 50,
                "last_scan": "2026-05-13T20:00:00+00:00",
                "findings": {
                    "ART50-OBL-3": {
                        "obligation_id": "ART50-OBL-3",
                        "level": "compliant",
                        "description": "AI detected synthetic content disclosure in src/api.py:42",
                        "source_quote": "verbatim Art. 50(3) stub",
                        "confidence": "high",
                        "status": "open",
                        "history": [],
                        "evidence": [],
                    },
                    "ART50-OBL-1": {
                        "obligation_id": "ART50-OBL-1",
                        "level": "compliant",
                        "description": "Chatbot disclosure detected (code-only attestation OK)",
                        "source_quote": "verbatim Art. 50(1) stub",
                        "confidence": "high",
                        "status": "open",
                        "history": [],
                        "evidence": [],
                    },
                },
                "regulation": "eu-ai-act",
            },
            f,
        )


def _make_fake_run(captured: dict):
    """subprocess.run stand-in — captures the /api/v1/scans payload, fakes
    a 200 OK so cl_sync exits cleanly."""

    def fake_run(cmd, *args, **kwargs):
        if not isinstance(cmd, (list, tuple)) or not cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        head = cmd[0]

        if head == "git":
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        if head == "curl":
            url = next(
                (c for c in cmd if isinstance(c, str) and c.startswith("http")),
                "",
            )
            for i, arg in enumerate(cmd):
                if arg == "-d" and i + 1 < len(cmd):
                    raw = cmd[i + 1]
                    if isinstance(raw, str) and raw.startswith("@"):
                        with open(raw[1:], "r", encoding="utf-8") as fh:
                            captured["payload"] = json.load(fh)
                            captured["url"] = url
                    break

            if "/api/v1/scans" in url:
                body = json.dumps(
                    {
                        "scan_id": "scan-approach-b-fake",
                        "dashboard_url": "https://dash.test.local/dashboard/scans/scan-approach-b-fake",
                    }
                )
                return subprocess.CompletedProcess(
                    cmd, 0, stdout=f"{body}\n200", stderr=""
                )
            if "/api/v1/repos" in url:
                return subprocess.CompletedProcess(cmd, 0, stdout="[]\n200", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="\n200", stderr="")

        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return fake_run


def test_cl_sync_rewrites_hybrid_to_UTD_before_posting_to_saas(tmp_path, monkeypatch):
    """E2E: AI hypothesis (COMPLIANT on hybrid OID) → cl_sync → SaaS sees UTD.

    This is the full Approach (b) loop. AI may say anything about a
    hybrid obligation in any single scan run (Bug 2); cl_sync rewrites
    every hybrid OID to UTD+HG hint right before the HTTP POST so the
    SaaS database can never absorb the AI variance.
    """
    _seed_rc(str(tmp_path))
    _seed_art50_state_with_hybrid_compliant(str(tmp_path))

    captured: dict = {}
    monkeypatch.setattr(subprocess, "run", _make_fake_run(captured))

    raw = server.cl_sync(str(tmp_path), regulation="")
    parsed = json.loads(raw)
    assert "error" not in parsed, f"cl_sync surfaced error: {parsed}"

    assert "payload" in captured, "fake curl never saw the /api/v1/scans POST"
    payload = captured["payload"]
    assert "/api/v1/scans" in captured["url"]
    assert "art50" in payload["articles"], (
        f"art50 missing from payload: {list(payload['articles'].keys())}"
    )

    findings = payload["articles"]["art50"]["findings"]
    assert "ART50-OBL-3" in findings, (
        f"ART50-OBL-3 missing from payload: {list(findings.keys())}"
    )
    hybrid_finding = findings["ART50-OBL-3"]

    # ── Core E2E invariant ──
    # ART50-OBL-3 is type=hybrid. The seeded value was level=compliant
    # (AI's verdict). After Approach (b) runs at cl_sync boundary, the
    # POST body must show UTD (unable_to_determine) so SaaS doesn't
    # silently absorb AI variance into the compliance score.
    assert hybrid_finding["level"] == "unable_to_determine", (
        f"Approach (b) did not rewrite ART50-OBL-3 — payload still shows "
        f"level={hybrid_finding['level']!r}. The IDE AI client's "
        f"hypothesis is leaking into SaaS state."
    )
    assert "human_gate_hint" in hybrid_finding, (
        "Hybrid finding rewrite missing Human Gates hint — the dashboard "
        "needs this to route users to the HG wizard for attestation."
    )
    assert hybrid_finding.get("confidence") == "low", (
        f"Confidence not downgraded — got {hybrid_finding.get('confidence')!r}, "
        f"expected 'low'. AI-high confidence on a rewritten hybrid is "
        f"misleading: the new state is a placeholder, not an assertion."
    )

    # ── Negative invariant: code-type OID passes through unchanged ──
    # ART50-OBL-1 is type=code. Scanner detection is authoritative
    # there; post-process must NOT touch it.
    code_finding = findings["ART50-OBL-1"]
    assert code_finding["level"] == "compliant", (
        f"Code-type ART50-OBL-1 was rewritten — got level="
        f"{code_finding['level']!r}, expected 'compliant'. Approach (b) "
        f"should ONLY rewrite hybrid (type=hybrid in classification.json)."
    )
    assert code_finding.get("confidence") == "high", (
        "Code-type finding's confidence should not be downgraded."
    )


def test_cl_sync_three_AI_runs_on_hybrid_collapse_to_same_UTD(tmp_path, monkeypatch):
    """Variance elimination at the pipeline level: three cl_sync runs
    with three different AI verdicts for the same hybrid OID must
    produce three identical POST bodies (modulo timestamps).

    This is the END-TO-END proof of Bug 2 structural elimination.
    `test_approach_b_post_process.py::test_three_AI_runs_on_hybrid_OID_all_collapse_to_UTD`
    proves the unit; this test proves the integration.
    """
    levels_observed = []
    for ai_verdict in ("compliant", "non_compliant", "unable_to_determine"):
        _seed_rc(str(tmp_path))
        # Re-seed art50.json with a different AI verdict each iteration.
        art_dir = os.path.join(tmp_path, ".compliancelint", "local", "articles")
        os.makedirs(art_dir, exist_ok=True)
        art_file = os.path.join(art_dir, "art50.json")
        with open(art_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "article": 50,
                    "last_scan": f"2026-05-13T20:0{len(levels_observed)}:00+00:00",
                    "findings": {
                        "ART50-OBL-3": {
                            "obligation_id": "ART50-OBL-3",
                            "level": ai_verdict,
                            "description": f"AI run with level={ai_verdict}",
                            "source_quote": "verbatim Art. 50(3) stub",
                            "confidence": "high",
                            "status": "open",
                            "history": [],
                            "evidence": [],
                        }
                    },
                    "regulation": "eu-ai-act",
                },
                f,
            )

        captured: dict = {}
        monkeypatch.setattr(subprocess, "run", _make_fake_run(captured))
        server.cl_sync(str(tmp_path), regulation="")

        payload = captured.get("payload") or {}
        finding = payload["articles"]["art50"]["findings"]["ART50-OBL-3"]
        levels_observed.append((finding["level"], finding.get("confidence")))

    # All three AI verdicts must produce the same post-cl_sync state.
    assert levels_observed[0] == levels_observed[1] == levels_observed[2], (
        f"Variance leaked through cl_sync: {levels_observed}. "
        f"Approach (b) must collapse all three to the same UTD state."
    )
    assert levels_observed[0] == ("unable_to_determine", "low"), (
        f"Expected collapsed state ('unable_to_determine', 'low'), got "
        f"{levels_observed[0]}."
    )
