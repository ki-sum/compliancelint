"""OAuth callback simulator for cl_connect device-flow tests.

The cl_connect tool's device-flow path opens a browser to
``GET /api/v1/auth/connect?token=<uuid>`` (creates an empty
``connect_tokens`` row) and then polls
``/api/v1/auth/connect/poll?token=<uuid>`` for up to 90 seconds
waiting for the OAuth callback to fill in ``api_key`` + ``email``.

In an interactive Claude Code session a real human signs in via
GitHub or Google in the browser; the OAuth callback handler fills
the row. In Pool 4 cells we don't have a human-in-the-loop, so this
simulator stands in for that callback:

  1. Capture a baseline of token IDs already in
     ``connect_tokens`` at the start of the test.
  2. After ``cl_connect`` is invoked (and the browser-equivalent
     curl wrapper has hit the ``/api/v1/auth/connect`` endpoint
     to create a fresh empty row), poll the table for any new
     row with ``api_key=''`` whose token wasn't in the baseline.
  3. ``complete(token, api_key, email)`` updates the row so the
     next poll from cl_connect returns ``{status: "complete"}``.
     ``cancel(token)`` deletes the row so the next poll returns
     ``{status: "expired"}`` (mirrors a user closing the browser
     tab without finishing OAuth).

The simulator is read-and-write but uses its own short-lived
sqlite3 connections per call to avoid contending with the
dashboard's WAL writers.

C2 (live :3000) is required because the scanner's webbrowser-
launched curl needs the dashboard to be up — otherwise the
``/api/v1/auth/connect`` GET fails and no row is ever created.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Optional


class OAuthSimulatorError(RuntimeError):
    """Raised when the simulator can't observe expected DB state."""


class OAuthSimulator:
    """Watches the dashboard's ``connect_tokens`` table during a
    cl_connect device-flow test and applies completion / cancel
    actions on newly-created pending rows.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        # Ensure schema; lib/connect-tokens.ts creates it on first
        # touch but Pool 4 cells may run before any production code
        # path opened the table.
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS connect_tokens (
                       token TEXT PRIMARY KEY,
                       api_key TEXT NOT NULL DEFAULT '',
                       email TEXT NOT NULL DEFAULT '',
                       created_at INTEGER NOT NULL
                   )"""
            )
            conn.commit()
        # Time-anchor: only consider rows whose created_at is at or
        # after this simulator's birth time. Anchors at -100ms to
        # tolerate clock skew between this Python process and the
        # node dashboard process. Replaces the older "diff against a
        # baseline token set" approach which was brittle when prior
        # failed runs left stale empty-api_key rows in the DB.
        self.created_at_threshold_ms: int = int(time.time() * 1000) - 100
        # Tokens this simulator has already returned/acted on, so
        # ``wait_for_n_pending_tokens`` calls don't double-count
        # rows that ``wait_for_pending_token`` already consumed.
        self._consumed: set[str] = set()

    def _query_new_pending(self) -> list[tuple[str, int]]:
        """Return (token, created_at_ms) for pending rows newer than
        this simulator's anchor and not yet consumed."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT token, created_at FROM connect_tokens "
                "WHERE api_key = '' AND created_at >= ? "
                "ORDER BY created_at ASC",
                (self.created_at_threshold_ms,),
            ).fetchall()
        return [(r[0], r[1]) for r in rows if r[0] not in self._consumed]

    def wait_for_pending_token(
        self,
        timeout: float = 15.0,
        poll_interval: float = 0.2,
    ) -> str:
        """Poll until exactly one new pending row appears (api_key='',
        created_at >= simulator anchor). Returns the token. Raises
        OAuthSimulatorError on timeout or on more than one new row
        (parallel-test contamination — caller should ensure isolation).
        """
        deadline = time.monotonic() + timeout
        last_seen: list[str] = []
        while time.monotonic() < deadline:
            new = self._query_new_pending()
            if len(new) == 1:
                token = new[0][0]
                self._consumed.add(token)
                return token
            if len(new) > 1:
                raise OAuthSimulatorError(
                    f"more than one new pending token observed "
                    f"({len(new)}); test isolation broken — only one "
                    f"cl_connect should be in flight per simulator. "
                    f"tokens={[t for t, _ in new][:5]}"
                )
            last_seen = [t for t, _ in new]
            time.sleep(poll_interval)
        raise OAuthSimulatorError(
            f"timed out after {timeout}s waiting for new pending "
            f"connect_tokens row (anchor "
            f"created_at>={self.created_at_threshold_ms}). The "
            f"scanner's webbrowser hook may not be GET-ing "
            f"/api/v1/auth/connect. New pending rows seen at "
            f"timeout: {last_seen[:5]}"
        )

    def wait_for_n_pending_tokens(
        self,
        n: int,
        timeout: float = 20.0,
        poll_interval: float = 0.2,
    ) -> list[str]:
        """Wait until exactly N new pending rows appear (api_key='',
        created_at >= simulator anchor). Returns the tokens in
        oldest-first order so caller can pair them with concurrent
        cl_connect invocations deterministically.

        Used by the repo_binding_race cell where two cl_connects fire
        in parallel and both should be observed before either is
        completed.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            new = self._query_new_pending()
            if len(new) == n:
                tokens = [t for t, _ in new]
                self._consumed.update(tokens)
                return tokens
            if len(new) > n:
                raise OAuthSimulatorError(
                    f"observed {len(new)} new tokens, expected {n}. "
                    f"Sibling test bleed-over? "
                    f"tokens={[t for t, _ in new][:6]}"
                )
            time.sleep(poll_interval)
        # Surface what we DID see at timeout for debuggability.
        last = self._query_new_pending()
        raise OAuthSimulatorError(
            f"timed out after {timeout}s waiting for {n} new pending "
            f"connect_tokens rows; got {len(last)} "
            f"(tokens={[t for t, _ in last][:6]})"
        )

    def complete(self, token: str, api_key: str, email: str) -> None:
        """Set api_key + email on the row so the scanner's next poll
        returns ``{status: "complete"}``. UPDATE-based so created_at
        stays the original (the scanner's expiry check uses created_at
        relative to now, and we don't want to extend the window).
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE connect_tokens SET api_key = ?, email = ? "
                "WHERE token = ?",
                (api_key, email, token),
            )
            if cur.rowcount != 1:
                raise OAuthSimulatorError(
                    f"complete() expected to update exactly 1 row, "
                    f"got rowcount={cur.rowcount} for token "
                    f"{token[:12]}..."
                )
            conn.commit()

    def cancel(self, token: str) -> None:
        """Delete the row so the scanner's next poll returns
        ``{status: "expired"}`` — mirrors a user closing the browser
        tab without completing OAuth. The dashboard's
        ``/api/v1/auth/connect/poll`` returns ``expired`` when the
        token is not found.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM connect_tokens WHERE token = ?", (token,),
            )
            conn.commit()


def resolve_curl_path() -> Optional[str]:
    """Locate a curl binary suitable for use as the BROWSER env value.

    Falls back to ``shutil.which("curl")`` when the standard Windows
    System32 path isn't accessible (e.g. test running inside Git Bash
    where PATH is reordered). Returns None if curl can't be found.
    """
    # Prefer System32 curl on Windows so we don't accidentally pick up
    # a Git Bash mintty wrapper that doesn't terminate cleanly when
    # webbrowser.open spawns it without a TTY.
    candidates = [
        os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                     "System32", "curl.exe"),
        shutil.which("curl"),
    ]
    for cand in candidates:
        if cand and os.path.isfile(cand):
            return cand
    return None
