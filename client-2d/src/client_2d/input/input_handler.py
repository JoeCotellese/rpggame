# ABOUTME: Input handler mapping keyboard events to game actions.
# ABOUTME: Supports configurable key bindings and game mode-specific input.

"""Input handler for keyboard-based game control."""

from dataclasses import dataclass, field
from typing import Optional

from client_2d.core.constants import Action, Direction, GameMode


# Key code constants (matching arcade.key values for testing without arcade)
# These match arcade.key.* constants
KEY_UP = 65362
KEY_DOWN = 65364
KEY_LEFT = 65361
KEY_RIGHT = 65363
KEY_W = 119
KEY_A = 97
KEY_S = 115
KEY_D = 100
KEY_SPACE = 32
KEY_ENTER = 65293
KEY_ESCAPE = 65307
KEY_TAB = 65289
KEY_I = 105
KEY_C = 99
KEY_1 = 49
KEY_2 = 50
KEY_3 = 51
KEY_4 = 52
KEY_5 = 53


@dataclass
class KeyBinding:
    """A key binding mapping a key code to an action."""

    key: int
    action: Action
    requires_shift: bool = False
    requires_ctrl: bool = False


@dataclass
class InputHandler:
    """Handles keyboard input and maps to game actions.

    The input handler:
    1. Receives raw key press events
    2. Maps keys to actions based on current game mode
    3. Returns appropriate game actions for the game controller

    Key bindings are configurable but have sensible defaults:
    - Arrow keys / WASD: Movement
    - Space: Interact
    - Enter: Confirm
    - Escape: Cancel / Menu
    - Tab: Cycle targets
    - I: Inventory
    - C: Character sheet

    Attributes:
        current_mode: Current game mode affecting key interpretation
    """

    current_mode: GameMode = GameMode.EXPLORATION
    _bindings: dict[int, list[KeyBinding]] = field(default_factory=dict)

    def __post_init__(self):
        """Set up default key bindings."""
        self._setup_default_bindings()

    def _setup_default_bindings(self) -> None:
        """Configure default key bindings."""
        # Movement keys (work in exploration mode)
        movement_bindings = [
            KeyBinding(KEY_UP, Action.MOVE_NORTH),
            KeyBinding(KEY_W, Action.MOVE_NORTH),
            KeyBinding(KEY_DOWN, Action.MOVE_SOUTH),
            KeyBinding(KEY_S, Action.MOVE_SOUTH),
            KeyBinding(KEY_LEFT, Action.MOVE_WEST),
            KeyBinding(KEY_A, Action.MOVE_WEST),
            KeyBinding(KEY_RIGHT, Action.MOVE_EAST),
            KeyBinding(KEY_D, Action.MOVE_EAST),
        ]

        # General action keys
        action_bindings = [
            KeyBinding(KEY_SPACE, Action.INTERACT),
            KeyBinding(KEY_ENTER, Action.CONFIRM),
            KeyBinding(KEY_ESCAPE, Action.CANCEL),
            KeyBinding(KEY_TAB, Action.NEXT_TARGET),
            KeyBinding(KEY_I, Action.INVENTORY),
            KeyBinding(KEY_C, Action.CHARACTER),
        ]

        # Combat number keys
        combat_bindings = [
            KeyBinding(KEY_1, Action.ATTACK),
            KeyBinding(KEY_2, Action.SPELL),
            KeyBinding(KEY_3, Action.ITEM),
            KeyBinding(KEY_4, Action.WAIT),
        ]

        # Store all bindings
        all_bindings = movement_bindings + action_bindings + combat_bindings
        for binding in all_bindings:
            if binding.key not in self._bindings:
                self._bindings[binding.key] = []
            self._bindings[binding.key].append(binding)

    def handle_key_press(
        self, key: int, modifiers: int = 0
    ) -> Optional[Action]:
        """Convert a key press to a game action.

        Args:
            key: The key code that was pressed
            modifiers: Bit flags for modifier keys (shift, ctrl, alt)

        Returns:
            The corresponding Action, or None if no mapping exists
        """
        if key not in self._bindings:
            return None

        shift_pressed = bool(modifiers & 1)  # SHIFT modifier flag
        ctrl_pressed = bool(modifiers & 2)  # CTRL modifier flag

        for binding in self._bindings[key]:
            # Check modifier requirements
            if binding.requires_shift and not shift_pressed:
                continue
            if binding.requires_ctrl and not ctrl_pressed:
                continue

            # Check if action is valid for current mode
            if self._is_action_valid(binding.action):
                return binding.action

        return None

    def _is_action_valid(self, action: Action) -> bool:
        """Check if an action is valid in the current game mode.

        Args:
            action: The action to check

        Returns:
            True if the action is valid in current mode
        """
        # Movement actions
        movement_actions = {
            Action.MOVE_NORTH,
            Action.MOVE_SOUTH,
            Action.MOVE_EAST,
            Action.MOVE_WEST,
        }

        # Combat-only actions
        combat_actions = {
            Action.ATTACK,
            Action.SPELL,
            Action.ITEM,
            Action.WAIT,
            Action.NEXT_TARGET,
            Action.PREV_TARGET,
        }

        # Actions valid everywhere
        universal_actions = {
            Action.CANCEL,
            Action.INVENTORY,
            Action.CHARACTER,
        }

        if action in universal_actions:
            return True

        if self.current_mode == GameMode.EXPLORATION:
            return action in movement_actions or action == Action.INTERACT

        if self.current_mode == GameMode.COMBAT:
            return action in combat_actions or action == Action.CONFIRM

        if self.current_mode == GameMode.INVENTORY:
            return action == Action.CONFIRM

        if self.current_mode == GameMode.MENU:
            return action == Action.CONFIRM

        return False

    def set_mode(self, mode: GameMode) -> None:
        """Set the current game mode.

        Args:
            mode: The new game mode
        """
        self.current_mode = mode

    def get_direction_from_action(self, action: Action) -> Optional[Direction]:
        """Convert a movement action to a direction.

        Args:
            action: A movement action

        Returns:
            The corresponding Direction, or None if not a movement action
        """
        mapping = {
            Action.MOVE_NORTH: Direction.NORTH,
            Action.MOVE_SOUTH: Direction.SOUTH,
            Action.MOVE_EAST: Direction.EAST,
            Action.MOVE_WEST: Direction.WEST,
        }
        return mapping.get(action)

    def add_binding(self, key: int, action: Action, **kwargs) -> None:
        """Add a custom key binding.

        Args:
            key: The key code to bind
            action: The action to trigger
            **kwargs: Additional KeyBinding parameters
        """
        binding = KeyBinding(key=key, action=action, **kwargs)
        if key not in self._bindings:
            self._bindings[key] = []
        self._bindings[key].append(binding)

    def remove_binding(self, key: int, action: Action) -> None:
        """Remove a key binding.

        Args:
            key: The key code
            action: The action to unbind
        """
        if key in self._bindings:
            self._bindings[key] = [
                b for b in self._bindings[key] if b.action != action
            ]
