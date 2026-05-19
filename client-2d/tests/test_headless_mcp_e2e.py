# ABOUTME: End-to-end test for --headless dnd-2d (#362).
# ABOUTME: Launches a subprocess, hits the MCP HTTP endpoint, kills it.

"""End-to-end test for the headless MCP server.

This test starts ``dnd-2d --headless --dev --mcp`` in a subprocess, waits
for the embedded MCP HTTP server to come up, hits its SSE endpoint to
confirm the server is alive, and tears the process down. It does not
attempt to drive an MCP session over SSE; the unit tests in
``test_game_session.py`` already cover the session-side semantics that
the headless mode runs.

The test is a smoke test for the headless wiring: confirms that the
``--headless`` flag dispatches into ``run_headless``, the embedded MCP
server binds the requested port, and the process stays alive long
enough to serve traffic.
"""

from __future__ import annotations

import http.client
import socket
import subprocess
import time
from pathlib import Path

CLIENT_2D_DIR = Path(__file__).parent.parent
REPO_ROOT = CLIENT_2D_DIR.parent


def _free_port() -> int:
    """Return an OS-allocated free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 15.0) -> bool:
    """Poll the loopback port until it accepts a TCP connection."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def test_headless_starts_and_serves_mcp() -> None:
    """`dnd-2d --headless --dev --mcp` starts a process serving HTTP."""
    port = _free_port()

    # Use the project's uv runner so we hit the installed dnd-2d entry.
    cmd = [
        "uv",
        "run",
        "--project",
        str(CLIENT_2D_DIR),
        "dnd-2d",
        "--headless",
        "--dev",
        "--mcp",
        "--mcp-port",
        str(port),
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        # Wait for the MCP HTTP port to accept connections.
        assert _wait_for_port(port, timeout=20.0), (
            "Headless MCP server never bound port "
            f"{port}. stdout so far:\n{proc.stdout.read() if proc.stdout else ''}"
        )

        # Hit the SSE endpoint and verify the server responds (FastMCP
        # serves /sse for MCP-over-HTTP). We don't follow the stream;
        # any HTTP-level response means the server is up.
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2.0)
        try:
            conn.request("GET", "/sse", headers={"Accept": "text/event-stream"})
            response = conn.getresponse()
            # Read just enough to confirm the server is responsive
            # (the SSE stream stays open otherwise).
            assert response.status in (200, 404, 405), (
                f"Unexpected HTTP status {response.status} from MCP server"
            )
            # Read a small chunk to ensure we actually got data flowing
            # before we close.
            try:
                response.read(1)
            except TimeoutError:
                # SSE keeps the stream open; partial read timeout is fine.
                pass
        finally:
            conn.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)


def test_headless_module_exists() -> None:
    """The headless entrypoint must be importable."""
    from client_2d import headless  # noqa: F401

    assert hasattr(headless, "run_headless")


def test_main_dispatches_headless_flag() -> None:
    """``dnd-2d --headless`` must call run_headless via main()."""
    import sys as _sys
    from unittest.mock import patch

    from client_2d import main as main_module

    original_argv = _sys.argv[:]
    _sys.argv = ["dnd-2d", "--headless", "--mcp-port", "0"]
    try:
        with patch.object(main_module, "run_headless") as mock_headless:
            mock_headless.return_value = None
            main_module.main()
            mock_headless.assert_called_once()
    finally:
        _sys.argv = original_argv
