"""MCP stdio client for Pool 4 real-flow tests.

Spawns ``python -m scanner.server`` as a subprocess, handshakes the
MCP protocol, and dispatches ``tools/call`` requests over the same
JSON-RPC stdio channel a real Claude Code session uses. Returns the
inner tool response (the JSON string the @mcp.tool function returned).

Why this matters: Pool 4 hard constraint C1 forbids
``from scanner.server import cl_*`` in test code. Direct imports skip
the JSON-RPC encode/decode round trip, the subprocess startup, and the
MCP framework's argument validation — exactly the layers where the
production failure modes (cl_sync git-regression hang, normalize
bypass, enum drift) surface. Real subprocess transport reproduces them.

Usage::

    with McpStdioClient.spawn() as client:
        raw = client.call_tool("cl_version", {})
        # raw is the JSON string the cl_version tool returned

The context-manager form ensures the subprocess is reaped even if the
test raises. For matrix runs that invoke many cells, prefer one client
per cell (cell isolation > startup cost) — server startup is ~0.5-1s
on Windows, well under the 5-10 min daily-cron budget for ~330 cells.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]


def parse_first_json(raw: str) -> dict:
    """Decode the leading JSON object from a tool response and discard
    any trailing text.

    Some scanner tools (cl_scan / cl_scan_all observed 2026-05-04)
    append a marketing/hint footer ("--- Compliance Tracking ---..."
    + "💡 hint...") AFTER the JSON envelope. ``json.loads`` rejects
    that with ``Extra data`` because the response is JSON + plain
    text concatenated, not pure JSON.

    Use this when you know the tool may emit extra text. For tools
    that return pure JSON (cl_version / cl_explain / cl_sync / etc.)
    keep using ``json.loads(raw)`` so unexpected garbage still fails.
    """
    decoder = json.JSONDecoder()
    obj, _end = decoder.raw_decode(raw.lstrip())
    if not isinstance(obj, dict):
        raise McpClientError(
            f"parse_first_json: leading value is {type(obj).__name__}, "
            f"expected dict"
        )
    return obj


class McpClientError(RuntimeError):
    """Raised when the MCP subprocess misbehaves (handshake fail, no
    response, JSON-RPC error envelope, dead pipe, etc.).

    Distinct from ``DispatchError`` (cell-level) so callers can
    distinguish "the test cell is broken" from "the MCP framework
    transport is broken".
    """


class McpStdioClient:
    """Synchronous MCP client over a single subprocess stdio pipe.

    Lifecycle:
      1. ``spawn()`` starts ``python -m scanner.server`` and runs the
         initialize / initialized handshake.
      2. ``call_tool(name, args)`` sends one ``tools/call`` request and
         blocks until the response arrives. Inner tool response (the
         scanner-side JSON string) is unwrapped from the MCP content
         envelope before return.
      3. ``close()`` closes stdin, waits ~2s for graceful exit, then
         terminates if the subprocess is still alive.

    Thread safety: NOT thread-safe. Each client wraps one subprocess;
    spawn separate clients for parallel calls.
    """

    PROTOCOL_VERSION = "2024-11-05"
    DEFAULT_HANDSHAKE_TIMEOUT = 10.0
    DEFAULT_CALL_TIMEOUT = 30.0

    def __init__(self, proc: subprocess.Popen[str]) -> None:
        self._proc = proc
        self._next_id = 1
        self._stderr_lines: list[str] = []
        self._stderr_lock = threading.Lock()
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr, daemon=True,
        )
        self._stderr_thread.start()

    @classmethod
    def spawn(
        cls,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        handshake_timeout: float = DEFAULT_HANDSHAKE_TIMEOUT,
    ) -> "McpStdioClient":
        """Start the MCP subprocess and complete the handshake.

        ``cwd`` defaults to the repo root (where ``scanner/`` lives).
        ``env`` extends os.environ; pass values to override (e.g.
        ``PYTHONPATH``). Handshake failure raises ``McpClientError``
        with the captured stderr for diagnosis.
        """
        run_cwd = cwd if cwd is not None else REPO_ROOT
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        proc = subprocess.Popen(
            [sys.executable, "-m", "scanner.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(run_cwd),
            env=run_env,
            text=True,
            encoding="utf-8",
            bufsize=0,
        )
        client = cls(proc)
        try:
            client._handshake(handshake_timeout)
        except Exception:
            client.close()
            raise
        return client

    def __enter__(self) -> "McpStdioClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = DEFAULT_CALL_TIMEOUT,
    ) -> str:
        """Send tools/call and return the inner JSON string.

        The MCP framework wraps tool responses in a content array:
        ``{"result":{"content":[{"type":"text","text":"<json>"}]}}``.
        This method unwraps that envelope and returns the inner
        ``text`` field, which is what the scanner ``@mcp.tool`` function
        actually returned. Callers parse it as JSON themselves to keep
        compatibility with the legacy in-process dispatcher signature.

        Raises ``McpClientError`` on JSON-RPC error envelope, missing
        content, or timeout.
        """
        request_id = self._allocate_id()
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments or {},
            },
        }
        envelope = self._send_and_receive(request, request_id, timeout)
        result = envelope.get("result")
        if result is None:
            raise McpClientError(
                f"call_tool({name}): no 'result' in response. "
                f"envelope={envelope}; stderr={self._stderr_snapshot()}"
            )
        is_error = result.get("isError")
        content = result.get("content") or []
        if not content or not isinstance(content, list):
            raise McpClientError(
                f"call_tool({name}): result.content is empty or non-list. "
                f"result={result}"
            )
        first = content[0]
        if not isinstance(first, dict) or first.get("type") != "text":
            raise McpClientError(
                f"call_tool({name}): result.content[0] not text. got={first}"
            )
        text = first.get("text")
        if not isinstance(text, str):
            raise McpClientError(
                f"call_tool({name}): result.content[0].text not a string. "
                f"got type={type(text).__name__}"
            )
        if is_error:
            # MCP marked this as an error envelope — but the inner JSON
            # is still the scanner's structured error response. Pass
            # through; cell-level asserter decides how to interpret.
            pass
        return text

    def close(self) -> None:
        """Best-effort subprocess shutdown."""
        if self._proc.poll() is not None:
            return
        try:
            if self._proc.stdin and not self._proc.stdin.closed:
                self._proc.stdin.close()
        except OSError:
            pass
        try:
            self._proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def _handshake(self, timeout: float) -> None:
        init_id = self._allocate_id()
        init_req = {
            "jsonrpc": "2.0",
            "id": init_id,
            "method": "initialize",
            "params": {
                "protocolVersion": self.PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "pool4-mcp-client", "version": "1.0"},
            },
        }
        envelope = self._send_and_receive(init_req, init_id, timeout)
        result = envelope.get("result")
        if not isinstance(result, dict) or "protocolVersion" not in result:
            raise McpClientError(
                f"initialize handshake malformed: {envelope}; "
                f"stderr={self._stderr_snapshot()}"
            )
        notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        self._write_message(notif)

    def _send_and_receive(
        self,
        request: dict[str, Any],
        expected_id: int,
        timeout: float,
    ) -> dict[str, Any]:
        self._write_message(request)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self._read_line(timeout=max(0.1, deadline - time.monotonic()))
            if line is None:
                continue
            try:
                envelope = json.loads(line)
            except json.JSONDecodeError as e:
                raise McpClientError(
                    f"non-JSON line on stdout: {line[:200]!r} ({e}); "
                    f"stderr={self._stderr_snapshot()}"
                ) from e
            if "error" in envelope and envelope.get("id") == expected_id:
                err = envelope["error"]
                raise McpClientError(
                    f"JSON-RPC error id={expected_id}: code={err.get('code')} "
                    f"message={err.get('message')!r}"
                )
            if envelope.get("id") == expected_id and "result" in envelope:
                return envelope
            # Other messages (notifications, unrelated ids) — drop and keep reading.
        raise McpClientError(
            f"no response for id={expected_id} within {timeout}s; "
            f"stderr={self._stderr_snapshot()}"
        )

    def _write_message(self, message: dict[str, Any]) -> None:
        if self._proc.stdin is None or self._proc.stdin.closed:
            raise McpClientError(
                "stdin closed before message could be written; "
                f"stderr={self._stderr_snapshot()}"
            )
        try:
            self._proc.stdin.write(json.dumps(message) + "\n")
            self._proc.stdin.flush()
        except (OSError, BrokenPipeError) as e:
            raise McpClientError(
                f"stdin write failed: {e}; stderr={self._stderr_snapshot()}"
            ) from e

    def _read_line(self, timeout: float) -> str | None:
        """Read one stdout line with a soft timeout.

        Python's ``readline`` blocks; for cross-platform compatibility
        we poll the subprocess and use a short busy-wait when no data
        is available. Acceptable for test code (called at most a few
        times per cell). Returns None on timeout, empty string when
        the pipe closes, or the line contents (without trailing newline).
        """
        if self._proc.stdout is None:
            return None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None and self._stdout_drained():
                return ""
            line = self._proc.stdout.readline()
            if line:
                return line.rstrip("\r\n")
            time.sleep(0.01)
        return None

    def _stdout_drained(self) -> bool:
        if self._proc.stdout is None:
            return True
        try:
            return self._proc.stdout.peek() == b"" if hasattr(
                self._proc.stdout, "peek"
            ) else False
        except (OSError, ValueError):
            return True

    def _drain_stderr(self) -> None:
        if self._proc.stderr is None:
            return
        try:
            for line in self._proc.stderr:
                with self._stderr_lock:
                    self._stderr_lines.append(line.rstrip("\r\n"))
        except (OSError, ValueError):
            pass

    def _stderr_snapshot(self) -> str:
        with self._stderr_lock:
            tail = self._stderr_lines[-20:]
        return "\n".join(tail)

    def _allocate_id(self) -> int:
        i = self._next_id
        self._next_id += 1
        return i
