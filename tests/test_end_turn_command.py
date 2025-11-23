# ABOUTME: Unit tests for the end turn command in combat
# ABOUTME: Tests that players can explicitly end their turn when actions remain

import pytest
from unittest.mock import Mock, MagicMock, patch
from dnd_engine.ui.cli import CLI
from dnd_engine.core.game_state import GameState
from dnd_engine.core.character import Character
from dnd_engine.systems.initiative import InitiativeTracker, Combatant
from dnd_engine.core.creature import Creature, Abilities


class TestEndTurnCommand:
    """Test the end turn command functionality"""

    @pytest.fixture
    def mock_game_state(self):
        """Create a mock game state with combat active"""
        game_state = Mock(spec=GameState)
        game_state.in_combat = True
        game_state.initiative_tracker = Mock(spec=InitiativeTracker)
        game_state.party = Mock()
        game_state.active_enemies = []
        game_state.event_bus = Mock()
        return game_state

    @pytest.fixture
    def mock_character(self):
        """Create a mock character"""
        char = Mock(spec=Character)
        char.name = "TestCharacter"
        char.is_alive = True
        return char

    @pytest.fixture
    def cli(self, mock_game_state):
        """Create a CLI instance with mocked game state"""
        with patch('dnd_engine.ui.cli.GameState', return_value=mock_game_state):
            cli_instance = CLI()
            cli_instance.game_state = mock_game_state
            cli_instance.running = True
            return cli_instance

    def test_end_turn_command_variants(self, cli, mock_game_state, mock_character):
        """Test that all end turn command variants work"""
        # Setup: create a combatant for the current turn
        combatant = Mock(spec=Combatant)
        combatant.creature = mock_character
        mock_game_state.initiative_tracker.get_current_combatant.return_value = combatant
        mock_game_state.party.characters = [mock_character]

        # Mock process_enemy_turns to prevent it from running
        cli.process_enemy_turns = Mock()

        # Test all command variants
        commands = ["end turn", "end", "done", "pass", "skip"]
        for command in commands:
            # Reset mocks
            mock_game_state.initiative_tracker.next_turn.reset_mock()
            mock_game_state._check_combat_end.reset_mock()

            # Execute command
            cli.process_combat_command(command)

            # Verify turn was advanced
            mock_game_state.initiative_tracker.next_turn.assert_called_once()
            mock_game_state._check_combat_end.assert_called_once()

    def test_end_turn_advances_to_enemy_turns(self, cli, mock_game_state, mock_character):
        """Test that ending turn processes enemy turns"""
        # Setup
        combatant = Mock(spec=Combatant)
        combatant.creature = mock_character
        mock_game_state.initiative_tracker.get_current_combatant.return_value = combatant
        mock_game_state.party.characters = [mock_character]
        cli.process_enemy_turns = Mock()

        # Execute
        cli.handle_end_turn()

        # Verify enemy turns are processed
        cli.process_enemy_turns.assert_called_once()

    def test_end_turn_not_in_combat(self, cli, mock_game_state):
        """Test that end turn fails when not in combat"""
        mock_game_state.in_combat = False

        with patch('dnd_engine.ui.cli.print_error') as mock_error:
            cli.handle_end_turn()
            mock_error.assert_called_with("You're not in combat!")

        # Verify turn was NOT advanced
        mock_game_state.initiative_tracker.next_turn.assert_not_called()

    def test_end_turn_no_initiative_tracker(self, cli, mock_game_state):
        """Test that end turn fails when no initiative tracker exists"""
        mock_game_state.initiative_tracker = None

        with patch('dnd_engine.ui.cli.print_error') as mock_error:
            cli.handle_end_turn()
            mock_error.assert_called_with("No initiative tracker!")

    def test_end_turn_no_current_combatant(self, cli, mock_game_state):
        """Test that end turn fails when no current combatant"""
        mock_game_state.initiative_tracker.get_current_combatant.return_value = None

        with patch('dnd_engine.ui.cli.print_error') as mock_error:
            cli.handle_end_turn()
            mock_error.assert_called_with("No current combatant!")

    def test_end_turn_not_player_turn(self, cli, mock_game_state, mock_character):
        """Test that end turn fails when it's not a player character's turn"""
        # Setup: enemy turn
        enemy = Mock(spec=Creature)
        enemy.name = "Goblin"
        combatant = Mock(spec=Combatant)
        combatant.creature = enemy
        mock_game_state.initiative_tracker.get_current_combatant.return_value = combatant
        mock_game_state.party.characters = [mock_character]  # Enemy not in party

        with patch('dnd_engine.ui.cli.print_error') as mock_error:
            cli.handle_end_turn()
            mock_error.assert_called_with("It's not a party member's turn!")

        # Verify turn was NOT advanced
        mock_game_state.initiative_tracker.next_turn.assert_not_called()

    def test_end_turn_shows_message(self, cli, mock_game_state, mock_character):
        """Test that ending turn shows appropriate message"""
        combatant = Mock(spec=Combatant)
        combatant.creature = mock_character
        mock_game_state.initiative_tracker.get_current_combatant.return_value = combatant
        mock_game_state.party.characters = [mock_character]
        cli.process_enemy_turns = Mock()

        with patch('dnd_engine.ui.cli.print_status_message') as mock_status:
            cli.handle_end_turn()
            mock_status.assert_called_with(f"{mock_character.name} ends their turn.", "info")

    def test_end_turn_stops_if_combat_ends(self, cli, mock_game_state, mock_character):
        """Test that enemy turns are not processed if combat ends"""
        combatant = Mock(spec=Combatant)
        combatant.creature = mock_character
        mock_game_state.initiative_tracker.get_current_combatant.return_value = combatant
        mock_game_state.party.characters = [mock_character]

        # Combat ends after checking
        mock_game_state.in_combat = False
        cli.process_enemy_turns = Mock()

        cli.handle_end_turn()

        # Verify enemy turns were NOT processed
        cli.process_enemy_turns.assert_not_called()


class TestEndTurnIntegration:
    """Integration tests for end turn in combat flow"""

    def test_end_turn_in_help_text(self):
        """Test that end turn command appears in combat help"""
        with patch('dnd_engine.ui.cli.GameState'):
            cli = CLI()

            # Capture help output
            with patch('dnd_engine.ui.cli.print_help_section') as mock_help:
                cli.display_help_combat()

                # Verify help was called
                assert mock_help.called

                # Get the commands list that was passed
                call_args = mock_help.call_args
                commands = call_args[0][1]  # Second argument is the commands list

                # Verify end turn command is in the list
                command_texts = [cmd[0] for cmd in commands]
                assert any("end turn" in cmd or "done" in cmd or "pass" in cmd for cmd in command_texts)
