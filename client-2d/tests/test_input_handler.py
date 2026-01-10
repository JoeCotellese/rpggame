# ABOUTME: Unit tests for the input handler system.
# ABOUTME: Tests key bindings, action mapping, and game mode-specific input.

"""Tests for the InputHandler."""


from client_2d.core.constants import Action, Direction, GameMode
from client_2d.input.input_handler import (
    KEY_1,
    KEY_A,
    KEY_C,
    KEY_D,
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_I,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_S,
    KEY_SPACE,
    KEY_TAB,
    KEY_UP,
    KEY_W,
    InputHandler,
)


class TestInputHandlerInitialization:
    """Tests for InputHandler initialization."""

    def test_creates_with_default_exploration_mode(self):
        """InputHandler should start in exploration mode."""
        handler = InputHandler()

        assert handler.current_mode == GameMode.EXPLORATION

    def test_creates_with_default_bindings(self):
        """InputHandler should have default key bindings."""
        handler = InputHandler()

        # Movement should be bound
        assert handler.handle_key_press(KEY_UP) is not None
        assert handler.handle_key_press(KEY_W) is not None


class TestExplorationModeInput:
    """Tests for input handling in exploration mode."""

    def test_arrow_up_moves_north(self):
        """Arrow up should map to MOVE_NORTH in exploration."""
        handler = InputHandler(current_mode=GameMode.EXPLORATION)

        action = handler.handle_key_press(KEY_UP)

        assert action == Action.MOVE_NORTH

    def test_arrow_down_moves_south(self):
        """Arrow down should map to MOVE_SOUTH in exploration."""
        handler = InputHandler(current_mode=GameMode.EXPLORATION)

        action = handler.handle_key_press(KEY_DOWN)

        assert action == Action.MOVE_SOUTH

    def test_arrow_left_moves_west(self):
        """Arrow left should map to MOVE_WEST in exploration."""
        handler = InputHandler(current_mode=GameMode.EXPLORATION)

        action = handler.handle_key_press(KEY_LEFT)

        assert action == Action.MOVE_WEST

    def test_arrow_right_moves_east(self):
        """Arrow right should map to MOVE_EAST in exploration."""
        handler = InputHandler(current_mode=GameMode.EXPLORATION)

        action = handler.handle_key_press(KEY_RIGHT)

        assert action == Action.MOVE_EAST

    def test_wasd_movement(self):
        """WASD keys should map to movement in exploration."""
        handler = InputHandler(current_mode=GameMode.EXPLORATION)

        assert handler.handle_key_press(KEY_W) == Action.MOVE_NORTH
        assert handler.handle_key_press(KEY_A) == Action.MOVE_WEST
        assert handler.handle_key_press(KEY_S) == Action.MOVE_SOUTH
        assert handler.handle_key_press(KEY_D) == Action.MOVE_EAST

    def test_space_interacts(self):
        """Space should map to INTERACT in exploration."""
        handler = InputHandler(current_mode=GameMode.EXPLORATION)

        action = handler.handle_key_press(KEY_SPACE)

        assert action == Action.INTERACT

    def test_escape_cancels(self):
        """Escape should map to CANCEL in exploration."""
        handler = InputHandler(current_mode=GameMode.EXPLORATION)

        action = handler.handle_key_press(KEY_ESCAPE)

        assert action == Action.CANCEL

    def test_inventory_key(self):
        """I should open inventory in exploration."""
        handler = InputHandler(current_mode=GameMode.EXPLORATION)

        action = handler.handle_key_press(KEY_I)

        assert action == Action.INVENTORY

    def test_character_key(self):
        """C should open character sheet in exploration."""
        handler = InputHandler(current_mode=GameMode.EXPLORATION)

        action = handler.handle_key_press(KEY_C)

        assert action == Action.CHARACTER


class TestCombatModeInput:
    """Tests for input handling in combat mode."""

    def test_movement_disabled_in_combat(self):
        """Movement keys should not work in combat mode."""
        handler = InputHandler(current_mode=GameMode.COMBAT)

        assert handler.handle_key_press(KEY_UP) is None
        assert handler.handle_key_press(KEY_W) is None

    def test_tab_cycles_targets(self):
        """Tab should cycle targets in combat."""
        handler = InputHandler(current_mode=GameMode.COMBAT)

        action = handler.handle_key_press(KEY_TAB)

        assert action == Action.NEXT_TARGET

    def test_number_keys_select_actions(self):
        """Number keys should select combat actions."""
        handler = InputHandler(current_mode=GameMode.COMBAT)

        assert handler.handle_key_press(KEY_1) == Action.ATTACK

    def test_enter_confirms_in_combat(self):
        """Enter should confirm action in combat."""
        handler = InputHandler(current_mode=GameMode.COMBAT)

        action = handler.handle_key_press(KEY_ENTER)

        assert action == Action.CONFIRM

    def test_escape_works_in_combat(self):
        """Escape should work in combat (cancel action)."""
        handler = InputHandler(current_mode=GameMode.COMBAT)

        action = handler.handle_key_press(KEY_ESCAPE)

        assert action == Action.CANCEL


class TestModeTransitions:
    """Tests for game mode transitions."""

    def test_set_mode_changes_current_mode(self):
        """set_mode should change the current game mode."""
        handler = InputHandler(current_mode=GameMode.EXPLORATION)

        handler.set_mode(GameMode.COMBAT)

        assert handler.current_mode == GameMode.COMBAT

    def test_mode_change_affects_key_handling(self):
        """Changing mode should affect which keys are valid."""
        handler = InputHandler(current_mode=GameMode.EXPLORATION)

        # Movement works in exploration
        assert handler.handle_key_press(KEY_UP) == Action.MOVE_NORTH

        handler.set_mode(GameMode.COMBAT)

        # Movement doesn't work in combat
        assert handler.handle_key_press(KEY_UP) is None


class TestDirectionMapping:
    """Tests for action to direction conversion."""

    def test_get_direction_from_move_north(self):
        """MOVE_NORTH should map to Direction.NORTH."""
        handler = InputHandler()

        direction = handler.get_direction_from_action(Action.MOVE_NORTH)

        assert direction == Direction.NORTH

    def test_get_direction_from_move_south(self):
        """MOVE_SOUTH should map to Direction.SOUTH."""
        handler = InputHandler()

        direction = handler.get_direction_from_action(Action.MOVE_SOUTH)

        assert direction == Direction.SOUTH

    def test_get_direction_from_move_east(self):
        """MOVE_EAST should map to Direction.EAST."""
        handler = InputHandler()

        direction = handler.get_direction_from_action(Action.MOVE_EAST)

        assert direction == Direction.EAST

    def test_get_direction_from_move_west(self):
        """MOVE_WEST should map to Direction.WEST."""
        handler = InputHandler()

        direction = handler.get_direction_from_action(Action.MOVE_WEST)

        assert direction == Direction.WEST

    def test_get_direction_from_non_movement_returns_none(self):
        """Non-movement actions should return None."""
        handler = InputHandler()

        direction = handler.get_direction_from_action(Action.ATTACK)

        assert direction is None


class TestCustomBindings:
    """Tests for custom key binding management."""

    def test_add_custom_binding(self):
        """Should be able to add custom key bindings."""
        handler = InputHandler(current_mode=GameMode.EXPLORATION)

        # Bind a non-standard key to interact
        handler.add_binding(ord('e'), Action.INTERACT)

        action = handler.handle_key_press(ord('e'))
        assert action == Action.INTERACT

    def test_remove_binding(self):
        """Should be able to remove key bindings."""
        handler = InputHandler(current_mode=GameMode.EXPLORATION)

        handler.remove_binding(KEY_SPACE, Action.INTERACT)

        # Space should no longer work
        action = handler.handle_key_press(KEY_SPACE)
        assert action is None


class TestUnboundKeys:
    """Tests for handling unbound keys."""

    def test_unbound_key_returns_none(self):
        """Pressing an unbound key should return None."""
        handler = InputHandler()

        action = handler.handle_key_press(ord('z'))

        assert action is None

    def test_modifier_without_binding_returns_none(self):
        """Keys with modifiers but no binding should return None."""
        handler = InputHandler()

        # Shift+W without a binding
        action = handler.handle_key_press(KEY_W, modifiers=1)  # 1 = SHIFT

        # Should still match non-shift binding
        assert action == Action.MOVE_NORTH


class TestDirectionDeltas:
    """Tests for Direction delta properties."""

    def test_north_delta(self):
        """North should move up (negative y)."""
        assert Direction.NORTH.delta == (0, -1)

    def test_south_delta(self):
        """South should move down (positive y)."""
        assert Direction.SOUTH.delta == (0, 1)

    def test_east_delta(self):
        """East should move right (positive x)."""
        assert Direction.EAST.delta == (1, 0)

    def test_west_delta(self):
        """West should move left (negative x)."""
        assert Direction.WEST.delta == (-1, 0)

    def test_opposite_directions(self):
        """Opposite directions should be correct."""
        assert Direction.NORTH.opposite == Direction.SOUTH
        assert Direction.SOUTH.opposite == Direction.NORTH
        assert Direction.EAST.opposite == Direction.WEST
        assert Direction.WEST.opposite == Direction.EAST
