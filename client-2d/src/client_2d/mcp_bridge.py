# ABOUTME: Thread-safe command queue bridge between HTTP server and game window.
# ABOUTME: Enables MCP tools to safely interact with Arcade's single-threaded game loop.

"""Thread-safe bridge for MCP server to GameWindow communication.

The MCPBridge provides a command queue that allows the HTTP MCP server
(running in a background thread) to safely send commands to the GameWindow
(running in the main Arcade thread). Commands are queued and processed
during on_update() to maintain thread safety.
"""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass, field
from enum import Enum, auto
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from client_2d.game import GameWindow
    from client_2d.session import GameSession


class CommandType(Enum):
    """Types of commands that can be sent to the game window."""

    GET_STATE = auto()
    MOVE = auto()
    ATTACK = auto()
    WAIT = auto()

    # Dev-mode commands (only dispatched when EmbeddedMCPServer was started
    # with dev_mode=True, gated upstream by --dev or DND_DEBUG=1).
    SPAWN_MONSTER = auto()
    SPAWN_CHARACTER = auto()
    SET_POSITION = auto()
    CLEAR_ENEMIES = auto()
    SET_SEED = auto()
    LOAD_SCENARIO = auto()
    RESET_GAME = auto()


@dataclass
class CommandRequest:
    """Thread-safe command request from HTTP server to game window.

    The HTTP server creates these requests and puts them in the command queue.
    The game window processes them in on_update() and sets the result on
    the response_future.

    Attributes:
        command_type: The type of command to execute.
        args: Dictionary of arguments for the command.
        response_future: Future that will be set with the command result.
    """

    command_type: CommandType
    args: dict[str, Any] = field(default_factory=dict)
    response_future: Future[str] = field(default_factory=Future)


class MCPBridge:
    """Bridge connecting HTTP MCP server to GameWindow.

    Provides thread-safe communication via a command queue.
    HTTP handlers put commands, game window polls and processes them.

    Thread Safety:
        - submit_command() is called from HTTP thread, blocks until result
        - poll_commands() is called from game thread in on_update()
        - Queue handles synchronization between threads
    """

    def __init__(self, max_queue_size: int = 100) -> None:
        """Initialize the MCP bridge.

        Args:
            max_queue_size: Maximum pending commands before blocking.
        """
        self._command_queue: Queue[CommandRequest] = Queue(maxsize=max_queue_size)
        self._game_window: GameWindow | None = None
        self._session: GameSession | None = None

    def set_game_window(self, window: GameWindow) -> None:
        """Set reference to GameWindow (called from main thread).

        Args:
            window: The GameWindow instance to control.
        """
        self._game_window = window

    def set_session(self, session: GameSession) -> None:
        """Set reference to the owning GameSession.

        The session is the authoritative reference now that headless
        mode can run without a window. ``set_game_window`` is kept for
        backwards compatibility with windowed-only code paths.
        """
        self._session = session

    @property
    def game_window(self) -> GameWindow | None:
        """Get the connected GameWindow (windowed mode only)."""
        return self._game_window

    @property
    def session(self) -> GameSession | None:
        """Get the connected GameSession (both modes)."""
        return self._session

    def submit_command(self, cmd: CommandRequest, timeout: float = 5.0) -> str:
        """Submit command and wait for result (called from HTTP thread).

        Thread-safe. Blocks until game window processes the command
        or timeout expires.

        Args:
            cmd: The command request to submit.
            timeout: Maximum seconds to wait for response.

        Returns:
            The result string from the game window.

        Raises:
            TimeoutError: If game window doesn't respond in time.
            Exception: If command processing raised an exception.
        """
        self._command_queue.put(cmd)
        return cmd.response_future.result(timeout=timeout)

    def poll_commands(self) -> CommandRequest | None:
        """Poll for pending command (called from game thread in on_update).

        Non-blocking. Returns immediately if no command is pending.

        Returns:
            A CommandRequest if one is pending, None otherwise.
        """
        try:
            return self._command_queue.get_nowait()
        except Empty:
            return None

    def queue_size(self) -> int:
        """Get the current number of pending commands."""
        return self._command_queue.qsize()
