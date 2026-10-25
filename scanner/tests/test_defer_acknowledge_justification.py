"""Acknowledge and defer keep their justification, and cl_sync sends it (series-2 dry run, 2026-10-24, QA #29).

cl_update_finding(action="defer", justification="Targeted Q3 …") recorded only the status: the justification was
dropped, so cl_sync sent an empty note and the Compliance Pack's "Defer note" stayed empty — the reason, the owner and
the dates of a deferred point were nowhere in the record. rebut always kept its justification; acknowledge and defer
now do too, in the finding's history, which is what cl_sync reads.
"""
import json
import os
import subprocess
import sys

import pytest

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)
sys.path.insert(0, os.path.dirname(__file__))

import server  # noqa: E402
from core.state import load_state, update_finding, update_findings_batch  # noqa: E402
from test_cl_sync import _make_fake_run, _seed_article_state, _seed_rc_with_saas  # noqa: E402

ATTESTER = {"name": "Alex Weber", "email": "alex@example.com", "role": "developer", "source": "config"}
REASON = "Text watermark not offered by the model provider; post-hoc watermark test by 30 November 2026; owner Alex Weber"


def _history(project, oid="ART12-OBL-1"):
    return load_state(project)["articles"]["art12"]["findings"][oid]["history"]


@pytest.mark.parametrize("action", ["defer", "acknowledge"])
def test_update_finding_keeps_the_justification(tmp_path, action):
    project = str(tmp_path)
    _seed_article_state(project)
    result = update_finding(project, "ART12-OBL-1", action, justification=REASON, attester=ATTESTER)
    assert result["status"] == "updated"
    assert _history(project)[-1]["justification"] == REASON


@pytest.mark.parametrize("action", ["defer", "acknowledge"])
def test_batch_keeps_the_justification(tmp_path, action):
    project = str(tmp_path)
    _seed_article_state(project)
    update_findings_batch(project, [{"obligation_id": "ART12-OBL-1", "action": action, "justification": REASON}],
                          attester=ATTESTER)
    assert _history(project)[-1]["justification"] == REASON


def test_without_a_justification_nothing_is_invented(tmp_path):
    project = str(tmp_path)
    _seed_article_state(project)
    update_finding(project, "ART12-OBL-1", "acknowledge", attester=ATTESTER)
    assert "justification" not in _history(project)[-1]


def test_sync_sends_the_defer_note(tmp_path, monkeypatch):
    project = str(tmp_path)
    _seed_rc_with_saas(project)
    _seed_article_state(project)
    update_finding(project, "ART12-OBL-1", "defer", justification=REASON, attester=ATTESTER)
    captured: dict = {}
    fake_scans = {"status": 200, "body": json.dumps({"scan_id": "s", "dashboard_url": "https://dash.test.local/x"})}
    monkeypatch.setattr(subprocess, "run", _make_fake_run(fake_scans, captured))
    server.cl_sync(project, regulation="")
    defers = [r for r in captured["last_payload"]["responses"] if r["action"] == "defer"]
    assert [r["note"] for r in defers] == [REASON]
