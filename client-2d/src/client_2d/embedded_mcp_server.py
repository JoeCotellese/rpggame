# ABOUTME: HTTP MCP server embedded in the Arcade game window.
# ABOUTME: Runs uvicorn in background thread, bridges to game via command queue.

"""Embedded MCP server for the 2D game client.

This server runs alongside the Arcade window in a background thread,
exposing game controls as MCP tools over HTTP/SSE. Commands are submitted
to the MCPBridge queue and processed by the GameWindow in on_update().

Architecture:
    Claude (HTTP) --> EmbeddedMCPServer --> MCPBridge --> GameWindow
                          |                    |
                     background thread     main thread (Arcade)

Usage:
    # GameWindow creates and starts the server
    bridge = MCPBridge()
    server = EmbeddedMCPServer(bridge, port=8765)
    server.start()

    # In on_update(), GameWindow processes commands from bridge
    request = bridge.poll_commands()
    if request:
        result = process_command(request)
        request.response_future.set_result(result)
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

from client_2d.mcp_bridge import CommandRequest, CommandType, MCPBridge

if TYPE_CHECKING:
    pass


class EmbeddedMCPServer:
    """HTTP MCP server that runs alongside the Arcade window.

    Starts uvicorn in a background thread and communicates with
    the GameWindow via a thread-safe command queue.

    The server exposes these tools:
        - game_state: Get current state (ASCII map + JSON)
        - game_move: Move party north/south/east/west
        - game_attack: Attack enemy by index in combat
        - game_wait: Pass turn in combat

    Note: Unlike the standalone mcp_server.py, this server does NOT
    have a game_new tool since the game is already running.
    """

    def __init__(
        self,
        bridge: MCPBridge,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        """Initialize the embedded MCP server.

        Args:
            bridge: MCPBridge for communication with GameWindow.
            host: Host to bind to (default localhost only).
            port: Port to listen on.
        """
        self._bridge = bridge
        self._host = host
        self._port = port
        self._server_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()
        self._mcp = self._create_mcp_server()

    def _create_mcp_server(self) -> FastMCP:
        """Create FastMCP server with tool definitions."""
        mcp = FastMCP("dnd-game-embedded")

        # Capture bridge reference for closures
        bridge = self._bridge

        @mcp.tool()
        def game_state() -> str:
            """Get current game state with ASCII map and entity info.

            Returns ASCII map with fog of war, party HP, combat status, and
            available actions. Call this first to understand the situation.

            Example:
                game_state()
                # Returns map showing @ (player), A-Z (entities), # (walls)
                # Plus party HP, visible enemies, and suggested actions

            Returns:
                Formatted string with map, legend, party status, available actions.
            """
            request = CommandRequest(command_type=CommandType.GET_STATE)
            return bridge.submit_command(request, timeout=5.0)

        @mcp.tool()
        def game_move(direction: str) -> str:
            """Move the party in a direction. May trigger room transitions or combat.

            Use during exploration (not combat). Moving into a room with enemies
            starts combat automatically.

            Examples:
                game_move("north")  # Move north, may enter new room
                game_move("east")   # Move east within current room
                game_move("SOUTH")  # Case insensitive

            Args:
                direction: One of 'north', 'south', 'east', 'west' (case insensitive)

            Returns:
                Updated game state after movement, or error if blocked/in combat.
            """
            request = CommandRequest(
                command_type=CommandType.MOVE,
                args={"direction": direction.lower()},
            )
            return bridge.submit_command(request, timeout=5.0)

        @mcp.tool()
        def game_attack(target: int | str) -> str:
            """Attack an enemy in combat using real D&D 5E combat rules.

            Only works during combat when it's a player's turn. Target can be
            specified by index or entity ID.

            Examples:
                game_attack(0)            # Attack first enemy by index
                game_attack("goblin_0")   # Attack by entity ID
                game_attack("giant_rat_1") # Attack specific enemy by ID

            Args:
                target: Either 0-based index (int) or entity ID string
                       (see Visible Entities in game_state output)

            Returns:
                Attack result (hit/miss, damage) and updated game state.
            """
            request = CommandRequest(
                command_type=CommandType.ATTACK,
                args={"target": target},
            )
            return bridge.submit_command(request, timeout=10.0)

        @mcp.tool()
        def game_wait() -> str:
            """Wait/pass your turn in combat, letting enemies act.

            Use when you want to skip a player's turn or let enemy turns resolve.
            Processes all enemy turns until a player can act again.

            Example:
                game_wait()  # Pass turn, enemies will attack, returns new state

            Returns:
                Updated game state after all enemy turns complete.
            """
            request = CommandRequest(command_type=CommandType.WAIT)
            return bridge.submit_command(request, timeout=10.0)

        return mcp

    def start(self) -> None:
        """Start HTTP server in background thread."""
        self._shutdown_event.clear()
        self._server_thread = threading.Thread(
            target=self._run_server,
            daemon=True,
            name="MCP-HTTP-Server",
        )
        self._server_thread.start()
        print(f"MCP server started at http://{self._host}:{self._port}/sse")

    def _run_server(self) -> None:
        """Run uvicorn server (called in background thread)."""
        import uvicorn

        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Get SSE app from FastMCP
        app = self._mcp.sse_app()

        config = uvicorn.Config(
            app,
            host=self._host,
            port=self._port,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)

        # Run until shutdown
        try:
            loop.run_until_complete(server.serve())
        except Exception as e:
            if not self._shutdown_event.is_set():
                print(f"MCP server error: {e}")
        finally:
            loop.close()

    def stop(self) -> None:
        """Signal server to stop."""
        self._shutdown_event.set()
        # Daemon thread will terminate when main process exits

    @property
    def port(self) -> int:
        """Get the port the server is listening on."""
        return self._port

    @property
    def host(self) -> str:
        """Get the host the server is bound to."""
        return self._host
