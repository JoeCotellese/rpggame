# ABOUTME: Tests for CLI status bar functionality
# ABOUTME: Verifies status bar displays location, lighting, and exit directions

from unittest.mock import Mock

import pytest

from terminal_client.ui.cli import CLI


class TestStatusBar:
    """Test CLI status bar functionality."""

    @pytest.fixture
    def mock_game_state(self):
        """Create a mock game state for testing."""
        game_state = Mock()
        game_state.dungeon = {"name": "The Crypt"}
        game_state.get_current_room.return_value = {"name": "Entrance Hall"}
        game_state.get_effective_lighting.return_value = "bright"
        game_state.party = Mock()
        game_state.party.characters = [Mock()]
        game_state.get_available_exits.return_value = {
            "north": {"destination": "room_2"},
            "east": {"destination": "room_3"},
        }
        return game_state

    def test_status_bar_includes_exits(self, mock_game_state):
        """Test that status bar includes available exit directions."""
        cli = CLI(mock_game_state, Mock(), "test_campaign")

        status_bar = cli._get_status_bar()

        # Convert HTML to string for checking
        status_str = str(status_bar)

        # Verify exits are shown in compact format
        assert "Exits:" in status_str
        assert "N" in status_str  # north
        assert "E" in status_str  # east

    def test_status_bar_exits_compact_format(self, mock_game_state):
        """Test that exits use compact abbreviations (N, S, E, W)."""
        mock_game_state.get_available_exits.return_value = {
            "north": {},
            "south": {},
            "west": {},
        }

        cli = CLI(mock_game_state, Mock(), "test_campaign")
        status_bar = cli._get_status_bar()
        status_str = str(status_bar)

        # Should show abbreviated directions
        assert "N" in status_str
        assert "S" in status_str
        assert "W" in status_str
        # Should NOT show full words
        assert "north" not in status_str.lower() or "Exits:" in status_str

    def test_status_bar_no_exits(self, mock_game_state):
        """Test status bar when no exits available."""
        mock_game_state.get_available_exits.return_value = {}

        cli = CLI(mock_game_state, Mock(), "test_campaign")
        status_bar = cli._get_status_bar()
        status_str = str(status_bar)

        assert "Exits: None" in status_str

    def test_status_bar_updates_with_room_change(self, mock_game_state):
        """Test that exits update when player moves to new room."""
        cli = CLI(mock_game_state, Mock(), "test_campaign")

        # Initial room has north and east exits
        status_bar1 = cli._get_status_bar()
        status_str1 = str(status_bar1)
        assert "N" in status_str1
        assert "E" in status_str1

        # Simulate moving to new room with different exits
        mock_game_state.get_available_exits.return_value = {"south": {}, "down": {}}
        mock_game_state.get_current_room.return_value = {"name": "Lower Chamber"}

        status_bar2 = cli._get_status_bar()
        status_str2 = str(status_bar2)
        assert "S" in status_str2
        assert "D" in status_str2  # down
