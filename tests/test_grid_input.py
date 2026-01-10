# ABOUTME: Unit tests for the GridInputHandler class
# ABOUTME: Tests key mapping, target selection, and action generation

import pytest
from unittest.mock import Mock, patch

from dnd_engine.ui.grid_input import (
    GridAction,
    GridInputHandler,
    GridInputResult,
    ARROW_KEY_MAP,
    ARROW_UP,
    ARROW_DOWN,
    ARROW_LEFT,
    ARROW_RIGHT,
)
from dnd_engine.spatial.position import Direction


class TestGridInputHandler:
    """Tests for GridInputHandler key processing."""

    @pytest.fixture
    def mock_cli(self):
        """Create a mock CLI for testing."""
        cli = Mock()
        return cli

    @pytest.fixture
    def handler(self, mock_cli):
        """Create a GridInputHandler with mocked CLI."""
        return GridInputHandler(mock_cli)

    def test_wsd_movement_keys(self, handler):
        """Test WSD keys map to correct directions.

        Note: 'a' is reserved for attack action, so we use arrows for west.
        """
        assert handler.handle_key("w").action == GridAction.MOVE
        assert handler.handle_key("w").direction == Direction.NORTH

        assert handler.handle_key("s").action == GridAction.MOVE
        assert handler.handle_key("s").direction == Direction.SOUTH

        assert handler.handle_key("d").action == GridAction.MOVE
        assert handler.handle_key("d").direction == Direction.EAST

        # 'a' is attack, not west movement
        assert handler.handle_key("a").action == GridAction.ATTACK

    def test_wsd_case_insensitive(self, handler):
        """Test WSD works with uppercase.

        Note: 'a' is reserved for attack action.
        """
        assert handler.handle_key("W").direction == Direction.NORTH
        assert handler.handle_key("S").direction == Direction.SOUTH
        assert handler.handle_key("D").direction == Direction.EAST
        # 'A' is attack, not west movement
        assert handler.handle_key("A").action == GridAction.ATTACK

    def test_arrow_keys_normalized(self, handler):
        """Test arrow key escape sequences are normalized."""
        assert handler.handle_key(ARROW_UP).direction == Direction.NORTH
        assert handler.handle_key(ARROW_DOWN).direction == Direction.SOUTH
        assert handler.handle_key(ARROW_LEFT).direction == Direction.WEST
        assert handler.handle_key(ARROW_RIGHT).direction == Direction.EAST

    def test_vi_movement_keys(self, handler):
        """Test vi-style hjk movement keys.

        Note: 'l' is reserved for look action, so we use arrows for east.
        """
        assert handler.handle_key("h").direction == Direction.WEST
        assert handler.handle_key("j").direction == Direction.SOUTH
        assert handler.handle_key("k").direction == Direction.NORTH
        # 'l' is look, not east movement
        assert handler.handle_key("l").action == GridAction.LOOK

    def test_numpad_movement(self, handler):
        """Test numpad movement keys including diagonals."""
        assert handler.handle_key("8").direction == Direction.NORTH
        assert handler.handle_key("2").direction == Direction.SOUTH
        assert handler.handle_key("4").direction == Direction.WEST
        assert handler.handle_key("6").direction == Direction.EAST
        assert handler.handle_key("7").direction == Direction.NORTHWEST
        assert handler.handle_key("9").direction == Direction.NORTHEAST
        assert handler.handle_key("1").direction == Direction.SOUTHWEST
        assert handler.handle_key("3").direction == Direction.SOUTHEAST

    def test_action_keys(self, handler):
        """Test action keys map to correct actions."""
        assert handler.handle_key("g").action == GridAction.PICKUP
        assert handler.handle_key(",").action == GridAction.PICKUP
        assert handler.handle_key("a").action == GridAction.ATTACK
        assert handler.handle_key("t").action == GridAction.TALK
        assert handler.handle_key("i").action == GridAction.INVENTORY
        assert handler.handle_key("c").action == GridAction.CAST
        assert handler.handle_key("l").action == GridAction.LOOK
        assert handler.handle_key("o").action == GridAction.OPEN_DOOR

    def test_wait_keys(self, handler):
        """Test wait/pass turn keys."""
        assert handler.handle_key(".").action == GridAction.WAIT
        assert handler.handle_key(" ").action == GridAction.WAIT

    def test_help_key(self, handler):
        """Test help key."""
        assert handler.handle_key("?").action == GridAction.HELP

    def test_text_mode_key(self, handler):
        """Test colon enters text mode."""
        result = handler.handle_key(":")
        assert result.action == GridAction.TEXT_MODE
        assert result.switch_to_text_mode is True

    def test_quit_keys(self, handler):
        """Test quit/escape keys."""
        assert handler.handle_key("q").action == GridAction.QUIT
        assert handler.handle_key("\x1b").action == GridAction.QUIT
        assert handler.handle_key("\x03").action == GridAction.QUIT  # Ctrl+C

    def test_unknown_key(self, handler):
        """Test unknown keys return NONE action."""
        result = handler.handle_key("x")
        assert result.action == GridAction.NONE
        assert "Unknown key" in result.message

    def test_target_selection(self, handler):
        """Test numbered target selection."""
        handler.set_pending_targets(["enemy1", "enemy2", "enemy3"])

        result = handler.handle_key("2")
        assert result.action == GridAction.ATTACK
        assert result.target_id == "enemy2"
        assert handler.pending_targets == []  # Cleared after selection

    def test_target_selection_invalid_number(self, handler):
        """Test invalid target number returns NONE."""
        handler.set_pending_targets(["enemy1", "enemy2"])

        result = handler.handle_key("5")
        assert result.action == GridAction.NONE
        assert "Invalid target" in result.message

    def test_target_selection_cleared_on_other_key(self, handler):
        """Test pending targets cleared on non-digit key."""
        handler.set_pending_targets(["enemy1", "enemy2"])

        result = handler.handle_key("w")
        assert result.action == GridAction.MOVE
        assert handler.pending_targets == []

    def test_clear_pending_targets(self, handler):
        """Test explicitly clearing pending targets."""
        handler.set_pending_targets(["enemy1"])
        handler.clear_pending_targets()
        assert handler.pending_targets == []

    def test_max_nine_targets(self, handler):
        """Test only first 9 targets are kept."""
        targets = [f"enemy{i}" for i in range(15)]
        handler.set_pending_targets(targets)
        assert len(handler.pending_targets) == 9

    def test_help_text_contains_keybindings(self, handler):
        """Test help text contains key binding information."""
        help_text = handler.get_help_text()
        assert "WASD" in help_text
        assert "Arrow keys" in help_text
        assert "Movement" in help_text
        assert "Pickup" in help_text


class TestArrowKeyMapping:
    """Tests for arrow key escape sequence mapping."""

    def test_arrow_key_constants(self):
        """Test arrow key constants are correct escape sequences."""
        assert ARROW_UP == "\x1b[A"
        assert ARROW_DOWN == "\x1b[B"
        assert ARROW_RIGHT == "\x1b[C"
        assert ARROW_LEFT == "\x1b[D"

    def test_arrow_key_map(self):
        """Test arrow keys map to WASD equivalents."""
        assert ARROW_KEY_MAP[ARROW_UP] == "w"
        assert ARROW_KEY_MAP[ARROW_DOWN] == "s"
        assert ARROW_KEY_MAP[ARROW_LEFT] == "a"
        assert ARROW_KEY_MAP[ARROW_RIGHT] == "d"
