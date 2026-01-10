# ABOUTME: Real-time single-key input handler for 2D grid mode
# ABOUTME: Processes keypresses without requiring Enter for roguelike feel

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Callable

import readchar

from dnd_engine.spatial.position import Direction
from dnd_engine.spatial.movement import KEY_TO_DIRECTION

if TYPE_CHECKING:
    from dnd_engine.ui.cli import CLI

logger = logging.getLogger(__name__)


class GridAction(Enum):
    """Actions available in grid mode."""

    MOVE = "move"
    ATTACK = "attack"
    PICKUP = "pickup"
    TALK = "talk"
    INVENTORY = "inventory"
    CAST = "cast"
    LOOK = "look"
    WAIT = "wait"
    HELP = "help"
    OPEN_DOOR = "open_door"
    QUIT = "quit"
    TEXT_MODE = "text_mode"
    NONE = "none"


@dataclass
class GridInputResult:
    """
    Result of processing a grid mode keypress.

    Carries information about what action to take based on input.
    """

    action: GridAction = GridAction.NONE
    direction: Direction | None = None
    target_id: str | None = None
    switch_to_text_mode: bool = False
    message: str = ""


# Special key sequences from readchar
ARROW_UP = "\x1b[A"
ARROW_DOWN = "\x1b[B"
ARROW_RIGHT = "\x1b[C"
ARROW_LEFT = "\x1b[D"


# Map arrow key sequences to direction keys
ARROW_KEY_MAP = {
    ARROW_UP: "w",
    ARROW_DOWN: "s",
    ARROW_LEFT: "a",
    ARROW_RIGHT: "d",
}


class GridInputHandler:
    """
    Handles real-time single-key input for 2D grid navigation.

    Keybindings:
    - WASD / Arrows / Vi keys / Numpad: Movement
    - g or ,: Pickup item
    - a: Attack (shows target selection)
    - t: Talk to NPC
    - i: Inventory
    - c: Cast spell
    - l: Look/examine tile
    - o: Open/close door
    - . or Space: Wait/pass turn
    - ?: Show help
    - :: Enter text command mode
    - Esc or q: Quit/menu
    """

    def __init__(self, cli: CLI):
        """
        Initialize the input handler.

        Args:
            cli: Reference to the CLI for accessing game state
        """
        self.cli = cli
        self.pending_targets: list[str] = []

    def read_key(self) -> str:
        """
        Read a single keypress without requiring Enter.

        Returns:
            The key pressed as a string. Arrow keys return escape sequences.
        """
        try:
            key = readchar.readkey()
            return key
        except KeyboardInterrupt:
            return "\x03"  # Ctrl+C

    def handle_key(self, key: str) -> GridInputResult:
        """
        Process a keypress and return the appropriate action.

        Action keys (a, g, t, etc.) take priority over movement keys.
        Arrow keys and numpad are for movement.

        Args:
            key: The key that was pressed

        Returns:
            GridInputResult describing the action to take
        """
        # Check for target selection (when we have pending targets)
        if self.pending_targets and key.isdigit():
            idx = int(key) - 1  # 1-indexed for user
            if 0 <= idx < len(self.pending_targets):
                target = self.pending_targets[idx]
                self.pending_targets = []
                return GridInputResult(
                    action=GridAction.ATTACK,
                    target_id=target,
                )
            else:
                return GridInputResult(
                    action=GridAction.NONE,
                    message="Invalid target number",
                )

        # Clear pending targets on any non-digit key
        self.pending_targets = []

        key_lower = key.lower()

        # Check quit keys first (they override everything)
        if key_lower == "q" or key == "\x1b":  # q or Escape
            return GridInputResult(action=GridAction.QUIT)

        if key == "\x03":  # Ctrl+C
            return GridInputResult(action=GridAction.QUIT)

        # Check action keys BEFORE movement keys
        # (so 'a' is attack, not west movement)
        if key_lower == "a":
            return GridInputResult(action=GridAction.ATTACK)

        if key_lower in ("g", ","):
            return GridInputResult(action=GridAction.PICKUP)

        if key_lower == "t":
            return GridInputResult(action=GridAction.TALK)

        if key_lower == "i":
            return GridInputResult(action=GridAction.INVENTORY)

        if key_lower == "c":
            return GridInputResult(action=GridAction.CAST)

        if key_lower == "l":
            return GridInputResult(action=GridAction.LOOK)

        if key_lower == "o":
            return GridInputResult(action=GridAction.OPEN_DOOR)

        if key in (".", " "):
            return GridInputResult(action=GridAction.WAIT)

        if key == "?":
            return GridInputResult(action=GridAction.HELP)

        if key == ":":
            return GridInputResult(
                action=GridAction.TEXT_MODE,
                switch_to_text_mode=True,
            )

        # Now check movement keys (arrows, WASD except 'a', numpad, vi)
        # Normalize arrow keys to WASD first
        normalized_key = key
        if key in ARROW_KEY_MAP:
            normalized_key = ARROW_KEY_MAP[key]

        direction = KEY_TO_DIRECTION.get(normalized_key.lower())
        if direction is not None:
            return GridInputResult(
                action=GridAction.MOVE,
                direction=direction,
            )

        return GridInputResult(
            action=GridAction.NONE,
            message=f"Unknown key: {repr(key)}",
        )

    def set_pending_targets(self, targets: list[str]) -> None:
        """
        Set targets for numbered selection.

        Args:
            targets: List of target IDs that can be selected
        """
        self.pending_targets = targets[:9]  # Max 9 targets (keys 1-9)

    def clear_pending_targets(self) -> None:
        """Clear any pending target selection."""
        self.pending_targets = []

    def get_help_text(self) -> str:
        """Return help text showing keybindings."""
        return """
Grid Mode Controls:
-------------------
Movement:
  WASD / Arrow keys  - Move in direction
  Numpad 1-9         - Move (including diagonals)
  hjkl (vi keys)     - Move (yubn for diagonals)

Actions:
  g or ,  - Pickup item on current tile
  a       - Attack (select target 1-9)
  t       - Talk to adjacent NPC
  c       - Cast spell
  i       - Open inventory
  l       - Look at current tile
  o       - Open/close adjacent door
  . or Space - Wait/pass turn

Other:
  ?   - Show this help
  :   - Enter text command mode
  q or Esc - Quit/menu
"""
