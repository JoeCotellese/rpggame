# ABOUTME: Always-running MCP proxy server that manages game lifecycle.
# ABOUTME: Forwards tool calls to the game's embedded MCP server via MCP client.

"""MCP Proxy Server for D&D 5E Game.

This server runs continuously and manages the game process lifecycle,
solving the "disconnected MCP" problem when Claude Code starts before
the game is running.

Architecture:
    Claude Code <--MCP/stdio--> Proxy <--MCP/SSE--> Game (embedded MCP)
                                  |
                           manages subprocess

Usage:
    # Start proxy (stays running)
    uv run python -m client_2d.mcp_proxy

    # In Claude Code .mcp.json, point to this proxy instead of the game
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import httpx
from fastmcp import Client
from fastmcp.client.transports import SSETransport
from mcp.server.fastmcp import FastMCP

# Game configuration
GAME_COMMAND = [sys.executable, "-m", "client_2d.main", "--mcp"]
GAME_MCP_URL = "http://127.0.0.1:8765"
GAME_STARTUP_TIMEOUT = 10.0  # seconds to wait for game to start
GAME_HEALTH_CHECK_INTERVAL = 0.5  # seconds between health checks


class GameProcessManager:
    """Manages the game subprocess lifecycle."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._working_dir = Path(__file__).parent.parent.parent  # client-2d/

    @property
    def is_running(self) -> bool:
        """Check if game process is running."""
        if self._process is None:
            return False
        return self._process.poll() is None

    def start(self) -> str:
        """Start the game process.

        Returns:
            Status message.
        """
        if self.is_running:
            return "Game is already running."

        try:
            self._process = subprocess.Popen(
                GAME_COMMAND,
                cwd=self._working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Wait for game to start and MCP server to be ready
            if self._wait_for_mcp_ready():
                return f"Game started (PID: {self._process.pid}). MCP server ready."
            else:
                return "Game started but MCP server not responding. Try game_state()."

        except Exception as e:
            return f"Failed to start game: {e}"

    def stop(self) -> str:
        """Stop the game process.

        Returns:
            Status message.
        """
        if not self.is_running:
            return "Game is not running."

        try:
            pid = self._process.pid
            self._process.terminate()
            self._process.wait(timeout=5.0)
            self._process = None
            return f"Game stopped (was PID: {pid})."
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process = None
            return "Game force-killed after timeout."
        except Exception as e:
            return f"Error stopping game: {e}"

    def restart(self) -> str:
        """Restart the game process (picks up code changes).

        Returns:
            Status message.
        """
        stop_msg = self.stop() if self.is_running else "Game was not running."
        time.sleep(0.5)  # Brief pause to ensure clean shutdown
        start_msg = self.start()
        return f"{stop_msg} {start_msg}"

    def _wait_for_mcp_ready(self) -> bool:
        """Wait for the game's MCP server to be ready.

        Returns:
            True if MCP server is responding, False if timeout.
        """
        start_time = time.time()
        while time.time() - start_time < GAME_STARTUP_TIMEOUT:
            try:
                # Try to hit the SSE endpoint
                with httpx.Client(timeout=1.0) as client:
                    response = client.get(f"{GAME_MCP_URL}/sse")
                    if response.status_code in (200, 307):
                        return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            time.sleep(GAME_HEALTH_CHECK_INTERVAL)
        return False


class MCPProxy:
    """Forwards MCP tool calls to the game's MCP server via SSE transport."""

    def __init__(self, game_url: str = GAME_MCP_URL) -> None:
        self._game_url = f"{game_url}/sse"

    async def call_tool_async(self, tool_name: str, **kwargs) -> str:
        """Call a tool on the game's MCP server.

        Args:
            tool_name: Name of the tool (e.g., 'game_state').
            **kwargs: Tool arguments.

        Returns:
            Tool result or error message.
        """
        try:
            transport = SSETransport(url=self._game_url)
            async with Client(transport=transport) as client:
                result = await client.call_tool(tool_name, kwargs)
                # Extract text from result
                if hasattr(result, "content"):
                    for item in result.content:
                        if hasattr(item, "text"):
                            return item.text
                return str(result)
        except Exception as e:
            error_msg = str(e)
            if "connect" in error_msg.lower() or "refused" in error_msg.lower():
                return "Game not running. Use game_start() first."
            return f"Error calling game: {e}"


def create_proxy_server() -> FastMCP:
    """Create the proxy MCP server with lifecycle + forwarded tools."""
    mcp = FastMCP("dnd-game-proxy")

    # Shared instances
    game_manager = GameProcessManager()
    proxy = MCPProxy()

    # === Lifecycle Tools ===

    @mcp.tool()
    def game_start() -> str:
        """Start the game process.

        Launches the 2D game client with embedded MCP server.
        Call this before using other game_* tools.

        Returns:
            Status message indicating success or failure.
        """
        return game_manager.start()

    @mcp.tool()
    def game_stop() -> str:
        """Stop the game process.

        Terminates the running game. Use game_start() to launch again.

        Returns:
            Status message.
        """
        return game_manager.stop()

    @mcp.tool()
    def game_restart() -> str:
        """Restart the game process.

        Stops and restarts the game, picking up any code changes.
        Use this after modifying game code to test changes.

        Returns:
            Status message.
        """
        return game_manager.restart()

    @mcp.tool()
    def game_status() -> str:
        """Check if the game is running.

        Returns:
            Status message with process info.
        """
        if game_manager.is_running:
            return f"Game is running (PID: {game_manager._process.pid})."
        return "Game is not running. Use game_start() to launch."

    # === Forwarded Game Tools ===

    @mcp.tool()
    async def game_state() -> str:
        """Get current game state with ASCII map and entity info.

        Returns ASCII map with fog of war, party HP, combat status, and
        available actions. Call this first to understand the situation.

        Returns:
            Formatted string with map, legend, party status, available actions.
        """
        if not game_manager.is_running:
            return "Game not running. Use game_start() first."
        return await proxy.call_tool_async("game_state")

    @mcp.tool()
    async def game_move(direction: str) -> str:
        """Move the party in a direction. May trigger combat.

        Args:
            direction: One of 'north', 'south', 'east', 'west'

        Returns:
            Updated game state or error message.
        """
        if not game_manager.is_running:
            return "Game not running. Use game_start() first."
        return await proxy.call_tool_async("game_move", direction=direction)

    @mcp.tool()
    async def game_attack(target: int | str) -> str:
        """Attack an enemy in combat.

        Args:
            target: Either 0-based index (int) or entity ID string
                   (e.g., "giant_rat_0", "goblin_1")

        Returns:
            Attack result and updated game state.
        """
        if not game_manager.is_running:
            return "Game not running. Use game_start() first."
        return await proxy.call_tool_async("game_attack", target=target)

    @mcp.tool()
    async def game_wait() -> str:
        """Wait/pass your turn in combat.

        Returns:
            Updated game state after enemy turns.
        """
        if not game_manager.is_running:
            return "Game not running. Use game_start() first."
        return await proxy.call_tool_async("game_wait")

    return mcp


# Entry point for running as MCP server
mcp = create_proxy_server()

if __name__ == "__main__":
    # Run as stdio MCP server (for Claude Code)
    mcp.run()
