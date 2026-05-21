"""Phase 3 (2026-05-21) — Python coverage for MCP AI Observation surface.

The TypeScript-side SaaS API tests verify the server-side contract
(validation, UPSERT, prior/changed semantics). This file pins the
PYTHON-side MCP surface:

  - cl_update_finding accepts the new ai_choose + ai_answer_why params
    WITHOUT breaking existing call signatures (backward compat).
  - cl_update_finding_batch handles per-item ai_choose + ai_answer_why.
  - _post_ai_observation gracefully degrades when SaaS unreachable,
    config missing, project_id absent, ai_choose invalid, or
    ai_answer_why under 20 chars (the anti-laziness invariant). NONE
    of these should fail the local state.json update — they should
    only skip the SaaS observation POST with a logged warning.
  - cl_get_ai_observation honestly returns null/empty when there's no
    prior context to fetch (cl_connect not run, cl_sync not run yet,
    SaaS unreachable) — these are "absence of prior", not errors.

Mocking strategy: monkeypatch `urllib.request.urlopen` at the
scanner.server module level so we don't issue real HTTP. Each test
asserts the EFFECT of calling the MCP tool: returned JSON shape,
warnings logged, local state.json mutations, etc.
"""
import io
import json
import os
import sys
import urllib.error

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)

import server  # noqa: E402


# ── Common fixtures ───────────────────────────────────────────────


def _seed_rc(project_path: str, with_saas: bool = False):
    rc = os.path.join(project_path, ".compliancelintrc")
    payload = {
        "attester_name": "Test User",
        "attester_email": "test@example.com",
        "attester_role": "Engineer",
    }
    if with_saas:
        payload["saas_url"] = "https://saas.test"
        payload["saas_api_key"] = "test_api_key_value"
    with open(rc, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def _seed_finding(project_path: str, article_num: int, obligation_id: str):
    art_dir = os.path.join(project_path, ".compliancelint", "local", "articles")
    os.makedirs(art_dir, exist_ok=True)
    art_file = os.path.join(art_dir, f"art{article_num}.json")
    with open(art_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "article": article_num,
                "findings": {
                    obligation_id: {
                        "obligation_id": obligation_id,
                        "level": "non_compliant",
                        "description": "Seeded for Phase 3 test",
                        "source_quote": "verbatim stub",
                        "status": "open",
                        "history": [],
                        "evidence": [],
                    },
                },
                "regulation": "eu-ai-act",
            },
            f,
        )
    return art_file


def _seed_meta(project_path: str, project_id: str):
    meta_dir = os.path.join(project_path, ".compliancelint", "local")
    os.makedirs(meta_dir, exist_ok=True)
    with open(os.path.join(meta_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"project_id": project_id}, f)


class _MockHttpResponse:
    """Stand-in for urllib.request.urlopen's context-manager response."""

    def __init__(self, status: int = 200, body: dict | None = None):
        self.status = status
        self._body = json.dumps(body or {}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._body


# ── cl_update_finding backward-compat (ai_choose params optional) ──


def test_cl_update_finding_works_without_ai_choose_params(tmp_path):
    """Backward compat: pre-Phase-3 callers don't pass ai_choose. Must
    still succeed exactly as before — local state.json update happens,
    no SaaS POST attempted, no error."""
    _seed_rc(str(tmp_path))
    obligation_id = "ART12-OBL-1"
    _seed_finding(str(tmp_path), 12, obligation_id)

    raw = server.cl_update_finding(
        project_path=str(tmp_path),
        obligation_id=obligation_id,
        action="acknowledge",
    )
    parsed = json.loads(raw)
    assert parsed.get("status") == "updated", f"expected status=updated, got: {parsed}"
    assert "ai_observation" not in parsed, (
        "ai_observation key must be absent when ai_choose/ai_answer_why omitted"
    )


def test_cl_update_finding_with_only_ai_choose_does_not_post(tmp_path, caplog):
    """If only ai_choose passed (no ai_answer_why), the POST must NOT
    happen — _post_ai_observation requires BOTH or it skips entirely.
    Asymmetric input would otherwise write a broken row server-side."""
    _seed_rc(str(tmp_path))
    obligation_id = "ART12-OBL-1"
    _seed_finding(str(tmp_path), 12, obligation_id)

    raw = server.cl_update_finding(
        project_path=str(tmp_path),
        obligation_id=obligation_id,
        action="acknowledge",
        ai_choose="yes",
        ai_answer_why="",  # empty
    )
    parsed = json.loads(raw)
    assert "ai_observation" not in parsed
    # Local update still succeeded
    assert parsed.get("status") == "updated"


# ── _post_ai_observation graceful degradation ──────────────────────


def test_post_ai_observation_skips_when_ai_choose_invalid(tmp_path, caplog):
    result = server._post_ai_observation(
        project_path=str(tmp_path),
        obligation_id="ART12-OBL-1",
        ai_choose="maybe",  # not in {yes, no, needs_review}
        ai_answer_why="long enough explanation here for validation purposes",
        source="mcp_update",
    )
    assert result is None
    # Warning should mention the invalid value
    assert any("invalid ai_choose" in r.message.lower() for r in caplog.records), (
        f"expected 'invalid ai_choose' warning, got: {[r.message for r in caplog.records]}"
    )


def test_post_ai_observation_skips_when_ai_answer_why_too_short(tmp_path, caplog):
    """20-char minimum is the anti-laziness invariant — must be enforced
    client-side as well (server-side enforces too; defense in depth)."""
    result = server._post_ai_observation(
        project_path=str(tmp_path),
        obligation_id="ART12-OBL-1",
        ai_choose="yes",
        ai_answer_why="too short",  # < 20 chars
        source="mcp_update",
    )
    assert result is None
    assert any("too short" in r.message.lower() for r in caplog.records), (
        f"expected 'too short' warning, got: {[r.message for r in caplog.records]}"
    )


def test_post_ai_observation_skips_when_ai_answer_why_only_whitespace(tmp_path, caplog):
    """30 spaces trim to 0 — must reject. Mirrors the server-side
    .trim().length check in src/app/api/v1/findings/.../ai-observation."""
    result = server._post_ai_observation(
        project_path=str(tmp_path),
        obligation_id="ART12-OBL-1",
        ai_choose="yes",
        ai_answer_why="   " * 10,  # 30 whitespace chars
        source="mcp_update",
    )
    assert result is None


def test_post_ai_observation_skips_when_saas_not_configured(tmp_path, caplog):
    """cl_connect not run → no saas_url / saas_api_key → graceful skip."""
    _seed_rc(str(tmp_path), with_saas=False)
    # No meta.json either, but the SaaS-check happens first
    result = server._post_ai_observation(
        project_path=str(tmp_path),
        obligation_id="ART12-OBL-1",
        ai_choose="yes",
        ai_answer_why="this evidence satisfies the obligation per Section 2",
        source="mcp_update",
    )
    assert result is None


def test_post_ai_observation_skips_when_project_id_missing(tmp_path, caplog):
    """saas_url configured but cl_sync never ran → no meta.json
    project_id → graceful skip."""
    _seed_rc(str(tmp_path), with_saas=True)
    # No meta.json written
    result = server._post_ai_observation(
        project_path=str(tmp_path),
        obligation_id="ART12-OBL-1",
        ai_choose="yes",
        ai_answer_why="this evidence satisfies the obligation per Section 2",
        source="mcp_update",
    )
    assert result is None


def test_post_ai_observation_gracefully_handles_http_error(tmp_path, monkeypatch, caplog):
    """SaaS POST returns 500 → log warning + return None. Local update
    is unaffected (caller-side already succeeded)."""
    _seed_rc(str(tmp_path), with_saas=True)
    _seed_meta(str(tmp_path), "proj-test-123")

    def _raise_500(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "Server Error", {}, io.BytesIO(b""))

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _raise_500)

    result = server._post_ai_observation(
        project_path=str(tmp_path),
        obligation_id="ART12-OBL-1",
        ai_choose="yes",
        ai_answer_why="this evidence satisfies the obligation per Section 2",
        source="mcp_update",
    )
    assert result is None


def test_post_ai_observation_gracefully_handles_network_timeout(tmp_path, monkeypatch, caplog):
    """SaaS unreachable → URLError → graceful skip (not raise)."""
    _seed_rc(str(tmp_path), with_saas=True)
    _seed_meta(str(tmp_path), "proj-test-123")

    def _raise_urlerror(req, timeout=None):
        raise urllib.error.URLError("connection timed out")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlerror)

    result = server._post_ai_observation(
        project_path=str(tmp_path),
        obligation_id="ART12-OBL-1",
        ai_choose="yes",
        ai_answer_why="this evidence satisfies the obligation per Section 2",
        source="mcp_update",
    )
    assert result is None


def test_post_ai_observation_returns_saas_response_on_success(tmp_path, monkeypatch):
    """200 OK → return the SaaS response dict (includes prior +
    changed for cross-verify bookkeeping)."""
    _seed_rc(str(tmp_path), with_saas=True)
    _seed_meta(str(tmp_path), "proj-test-123")

    mock_body = {
        "project_id": "proj-test-123",
        "finding_id": "f-abc",
        "obligation_id": "ART12-OBL-1",
        "observation": {"ai_choose": "yes", "ai_answer_why": "..."},
        "prior": {"ai_choose": "no", "ai_answer_why": "different prior reasoning"},
        "changed": True,
    }

    def _ok(req, timeout=None):
        # Verify the request body looks right (sanity check)
        body_str = req.data.decode("utf-8")
        body = json.loads(body_str)
        assert body["obligation_id"] == "ART12-OBL-1"
        assert body["ai_choose"] == "yes"
        assert body["source"] == "mcp_update"
        return _MockHttpResponse(status=200, body=mock_body)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _ok)

    result = server._post_ai_observation(
        project_path=str(tmp_path),
        obligation_id="ART12-OBL-1",
        ai_choose="yes",
        ai_answer_why="this evidence satisfies the obligation per Section 2",
        source="mcp_update",
    )
    assert result is not None
    assert result["changed"] is True
    assert result["prior"]["ai_choose"] == "no"


def test_post_ai_observation_strips_ai_answer_why_whitespace_in_body(tmp_path, monkeypatch):
    """The body sent to SaaS must be trimmed — server-side also trims
    but defense in depth keeps bytes-over-wire honest."""
    _seed_rc(str(tmp_path), with_saas=True)
    _seed_meta(str(tmp_path), "proj-test-123")

    captured = {}

    def _ok(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockHttpResponse(status=200, body={"changed": False})

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _ok)

    result = server._post_ai_observation(
        project_path=str(tmp_path),
        obligation_id="ART12-OBL-1",
        ai_choose="yes",
        ai_answer_why="   leading and trailing whitespace removed by trim   ",
        source="mcp_update",
    )
    assert result is not None
    assert captured["body"]["ai_answer_why"] == "leading and trailing whitespace removed by trim"


# ── cl_update_finding ↔ _post_ai_observation integration ──────────


def test_cl_update_finding_includes_ai_observation_in_response_on_success(
    tmp_path, monkeypatch
):
    """Full flow: update_finding with both ai_choose + ai_answer_why →
    local state updates + SaaS POST succeeds + ai_observation appears
    in the returned JSON."""
    _seed_rc(str(tmp_path), with_saas=True)
    _seed_meta(str(tmp_path), "proj-test-789")
    obligation_id = "ART12-OBL-1"
    _seed_finding(str(tmp_path), 12, obligation_id)

    mock_body = {
        "project_id": "proj-test-789",
        "finding_id": "f-abc",
        "obligation_id": obligation_id,
        "observation": {"ai_choose": "yes"},
        "prior": None,
        "changed": True,
    }

    def _ok(req, timeout=None):
        return _MockHttpResponse(status=200, body=mock_body)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _ok)

    raw = server.cl_update_finding(
        project_path=str(tmp_path),
        obligation_id=obligation_id,
        action="acknowledge",
        ai_choose="yes",
        ai_answer_why="docs/risk.md Section 2 enumerates 7 risks with mitigations",
    )
    parsed = json.loads(raw)
    assert parsed.get("status") == "updated"
    assert "ai_observation" in parsed
    assert parsed["ai_observation"]["changed"] is True


def test_cl_update_finding_ai_observation_post_failure_does_not_fail_local_update(
    tmp_path, monkeypatch
):
    """Critical invariant: SaaS POST failure (network, 500, etc.) must
    NOT roll back the local state.json update. The audit-trail enrichment
    side-effect is best-effort; the source-of-truth state.json write is
    the contract."""
    _seed_rc(str(tmp_path), with_saas=True)
    _seed_meta(str(tmp_path), "proj-test-456")
    obligation_id = "ART12-OBL-1"
    art_file = _seed_finding(str(tmp_path), 12, obligation_id)

    def _explode(req, timeout=None):
        raise urllib.error.URLError("simulated network outage")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _explode)

    raw = server.cl_update_finding(
        project_path=str(tmp_path),
        obligation_id=obligation_id,
        action="acknowledge",
        ai_choose="yes",
        ai_answer_why="docs/risk.md Section 2 enumerates 7 risks with mitigations",
    )
    parsed = json.loads(raw)
    # Local update succeeded despite SaaS failure
    assert parsed.get("status") == "updated"
    assert "ai_observation" not in parsed  # graceful absence

    # The local state file IS mutated even though SaaS POST failed
    on_disk = json.loads(open(art_file, encoding="utf-8").read())
    assert on_disk["findings"][obligation_id]["status"] == "acknowledged"


# ── cl_get_ai_observation honest-absence behavior ──────────────────


def test_cl_get_ai_observation_returns_empty_when_saas_not_configured(tmp_path):
    _seed_rc(str(tmp_path), with_saas=False)
    raw = server.cl_get_ai_observation(project_path=str(tmp_path))
    parsed = json.loads(raw)
    assert parsed["observations"] == {}
    assert parsed["project_id"] is None
    assert "note" in parsed
    assert "cl_connect" in parsed["note"].lower()


def test_cl_get_ai_observation_returns_empty_when_meta_missing(tmp_path):
    _seed_rc(str(tmp_path), with_saas=True)
    # No meta.json
    raw = server.cl_get_ai_observation(project_path=str(tmp_path))
    parsed = json.loads(raw)
    assert parsed["observations"] == {}
    assert "cl_sync" in parsed["note"].lower()


def test_cl_get_ai_observation_returns_null_for_single_obligation_when_unconfigured(
    tmp_path,
):
    """Single-obligation form returns observation:None when unconfigured,
    NOT an empty observations map — different shape per docstring."""
    _seed_rc(str(tmp_path), with_saas=False)
    raw = server.cl_get_ai_observation(
        project_path=str(tmp_path),
        obligation_id="ART12-OBL-1",
    )
    parsed = json.loads(raw)
    assert parsed["observation"] is None


def test_cl_get_ai_observation_rejects_invalid_obligation_id_format(tmp_path):
    raw = server.cl_get_ai_observation(
        project_path=str(tmp_path),
        obligation_id="not-a-valid-format",
    )
    parsed = json.loads(raw)
    assert "error" in parsed
    assert "format" in parsed["error"].lower()


def test_cl_get_ai_observation_returns_full_map_on_success(tmp_path, monkeypatch):
    _seed_rc(str(tmp_path), with_saas=True)
    _seed_meta(str(tmp_path), "proj-test-map")

    mock_body = {
        "project_id": "proj-test-map",
        "scan_id": "scan-1",
        "observations": {
            "ART09-OBL-1": {
                "finding_id": "f-9-1",
                "ai_choose": "yes",
                "ai_answer_why": "risk register exists",
                "source": "mcp_scan",
                "updated_at": "2026-05-22T00:00:00Z",
            },
            "ART10-OBL-1": {
                "finding_id": "f-10-1",
                "ai_choose": "no",
                "ai_answer_why": "training data governance missing",
                "source": "mcp_scan",
                "updated_at": "2026-05-22T00:00:00Z",
            },
        },
    }

    def _ok(req, timeout=None):
        # Verify GET method + correct URL
        assert req.get_method() == "GET"
        assert "/api/v1/projects/proj-test-map/ai-observation" in req.full_url
        return _MockHttpResponse(status=200, body=mock_body)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _ok)

    raw = server.cl_get_ai_observation(project_path=str(tmp_path))
    parsed = json.loads(raw)
    assert parsed["scan_id"] == "scan-1"
    assert "ART09-OBL-1" in parsed["observations"]
    assert parsed["observations"]["ART09-OBL-1"]["ai_choose"] == "yes"


def test_cl_get_ai_observation_returns_single_observation_when_obligation_id_given(
    tmp_path, monkeypatch,
):
    _seed_rc(str(tmp_path), with_saas=True)
    _seed_meta(str(tmp_path), "proj-test-single")

    mock_body = {
        "project_id": "proj-test-single",
        "scan_id": "scan-1",
        "observations": {
            "ART09-OBL-1": {
                "finding_id": "f-9-1",
                "ai_choose": "yes",
                "ai_answer_why": "risk register exists",
                "source": "mcp_scan",
                "updated_at": "2026-05-22T00:00:00Z",
            },
            "ART10-OBL-1": {
                "finding_id": "f-10-1",
                "ai_choose": "no",
                "ai_answer_why": "missing",
                "source": "mcp_scan",
                "updated_at": "2026-05-22T00:00:00Z",
            },
        },
    }

    def _ok(req, timeout=None):
        return _MockHttpResponse(status=200, body=mock_body)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _ok)

    raw = server.cl_get_ai_observation(
        project_path=str(tmp_path),
        obligation_id="ART09-OBL-1",
    )
    parsed = json.loads(raw)
    assert parsed["obligation_id"] == "ART09-OBL-1"
    assert parsed["observation"]["ai_choose"] == "yes"
    # Other obligation NOT in the response
    assert "ART10-OBL-1" not in str(parsed)


def test_cl_get_ai_observation_returns_null_when_obligation_not_in_response(
    tmp_path, monkeypatch,
):
    """obligation_id given but no observation for it → observation:None,
    NOT an error. Lets IDE AI proceed as 'no prior to cross-verify'."""
    _seed_rc(str(tmp_path), with_saas=True)
    _seed_meta(str(tmp_path), "proj-test-missing")

    def _ok(req, timeout=None):
        return _MockHttpResponse(
            status=200,
            body={"project_id": "proj-test-missing", "scan_id": "scan-1", "observations": {}},
        )

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _ok)

    raw = server.cl_get_ai_observation(
        project_path=str(tmp_path),
        obligation_id="ART09-OBL-1",
    )
    parsed = json.loads(raw)
    assert parsed["observation"] is None


def test_cl_get_ai_observation_handles_saas_500_gracefully(tmp_path, monkeypatch):
    _seed_rc(str(tmp_path), with_saas=True)
    _seed_meta(str(tmp_path), "proj-test-err")

    def _raise(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "Server Error", {}, io.BytesIO(b""))

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _raise)

    raw = server.cl_get_ai_observation(project_path=str(tmp_path))
    parsed = json.loads(raw)
    # Returns empty observations map (graceful) rather than raising
    assert parsed["observations"] == {}


# ── Docstring contract — Phase 4 AI-First fetch instructions present ──


def test_cl_update_finding_docstring_instructs_ai_first_url_fetch():
    """Pin: cl_update_finding's docstring must instruct the IDE AI to
    fetch URLs/files itself (Phase 4 AI-First). Catches a git revert
    that would silently re-introduce the wrong behaviour (AI forming
    yes-verdicts on unread URLs)."""
    doc = server.cl_update_finding.__doc__ or ""
    assert "AI-First" in doc, "docstring must mention AI-First principle"
    assert "WebFetch" in doc or "fetch" in doc.lower(), (
        "docstring must instruct AI to fetch URLs itself"
    )
    assert "needs_review" in doc, (
        "docstring must instruct AI to fall back to needs_review on unfetchable URLs"
    )


def test_cl_update_finding_docstring_documents_cross_verify_flow():
    """Pin: docstring must accurately describe the AI-First cross-verify
    flow (use cl_get_ai_observation BEFORE forming judgment, then call
    cl_update_finding). Catches a regression where docstring drifts
    back to falsely claiming 'MCP fetches prior' (which it doesn't)."""
    doc = server.cl_update_finding.__doc__ or ""
    assert "cl_get_ai_observation" in doc, (
        "docstring must point IDE AI at cl_get_ai_observation for prior fetch"
    )
    assert "BEFORE" in doc.upper() or "before forming" in doc.lower(), (
        "docstring must instruct fetch BEFORE judgment forms (pre-write)"
    )


def test_cl_get_ai_observation_docstring_explains_graceful_degradation():
    doc = server.cl_get_ai_observation.__doc__ or ""
    assert "Graceful degradation" in doc or "graceful" in doc.lower(), (
        "docstring must document graceful-absence semantics so IDE AI"
        " doesn't treat absence-of-prior as an error"
    )
