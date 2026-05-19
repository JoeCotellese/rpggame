# ABOUTME: Headless entry point for the 2D client (#362).
# ABOUTME: Runs a GameSession + embedded MCP server without an Arcade window.

"""Headless mode for the D&D 5E 2D client.

``run_headless()`` instantiates a :class:`GameSession` (no Arcade, no
window), starts the embedded MCP HTTP server, and runs a tick loop at
~30 Hz so MCP commands are drained from the bridge queue and the combat
state machine advances. Use this when you want to drive the engine from
Claude / pytest / CI without the visual layer.

CLI:
    uv run dnd-2d --headless --dev --mcp [--mcp-port 8765]
"""

from __future__ import annotations

import signal
import sys
import threading
import time

from client_2d.session import GameSession

# Tick at ~30 Hz so the MCP bridge drains promptly and the combat state
# machine keeps pace with the same ENEMY_TURN_DELAY (1.5s) GameWindow
# uses.
TICK_RATE_HZ = 30.0
TICK_INTERVAL_SECONDS = 1.0 / TICK_RATE_HZ


def run_headless(
    enable_mcp: bool = True,
    mcp_port: int = 8765,
    dev_mode: bool = False,
) -> None:
    """Run the engine in headless mode (no Arcade).

    Args:
        enable_mcp: When True (default), start the embedded MCP HTTP
            server. Headless without MCP isn't very useful but is
            allowed for symmetry with the windowed entry.
        mcp_port: Port for the MCP HTTP server.
        dev_mode: When True, register the --dev spawn / setup MCP tools.
    """
    print("=" * 50)
    print("D&D 5E - 2D Client (HEADLESS)")
    print("=" * 50)
    if enable_mcp:
        print(f"MCP Server: http://127.0.0.1:{mcp_port}/sse")
    if dev_mode:
        print("Dev mode: ENABLED (spawn_monster/spawn_character/... available)")
    print()

    session = GameSession(
        enable_mcp=enable_mcp,
        mcp_port=mcp_port,
        dev_mode=dev_mode,
    )
    session.initialize()
    if enable_mcp:
        session.initialize_mcp_server()

    stop_event = threading.Event()

    def _handle_signal(signum, _frame) -> None:
        """SIGINT / SIGTERM tells the tick loop to exit cleanly."""
        print(f"\nReceived signal {signum}, shutting down...")
        stop_event.set()

    # Register signal handlers so Ctrl-C / kill stops the loop.
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    last_tick = time.monotonic()
    try:
        while not stop_event.is_set():
            now = time.monotonic()
            delta = now - last_tick
            last_tick = now
            session.tick(delta)
            # Sleep until the next tick; cap on tick interval so we
            # don't busy-wait when ticks are cheap.
            time.sleep(TICK_INTERVAL_SECONDS)
    finally:
        # Daemon-thread MCP server will tear down with the process; we
        # call session.shutdown() to flip the shutdown event for the
        # server thread.
        session.shutdown()
        print("Headless session stopped.")
        sys.stdout.flush()
