# ABOUTME: Integration tests for rest display UI in CLI
# ABOUTME: Tests that unconscious characters are correctly reported in rest summaries

import pytest
from unittest.mock import Mock, patch
from dnd_engine.ui.cli import CLI
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party
from dnd_engine.systems.resources import ResourcePool


class TestRestDisplayIntegration:
    """Integration tests for rest display output"""

    @pytest.fixture
    def mock_game_state(self):
        """Create a mock game state with party"""
        game_state = Mock()
        game_state.data_loader = Mock()
        game_state.event_bus = Mock()
        game_state.time_manager = Mock()
        return game_state

    @pytest.fixture
    def healthy_character(self):
        """Create a healthy character at full HP"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        character = Character(
            name="Bob",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16,
            current_hp=12  # Full HP
        )

        # Add a short rest resource
        second_wind = ResourcePool(
            name="second_wind",
            current=0,
            maximum=1,
            recovery_type="short_rest"
        )
        character.add_resource_pool(second_wind)

        return character

    @pytest.fixture
    def unconscious_character(self):
        """Create an unconscious character at 0 HP"""
        abilities = Abilities(
            strength=10,
            dexterity=14,
            constitution=12,
            intelligence=14,
            wisdom=10,
            charisma=10
        )
        character = Character(
            name="Tim",
            character_class=CharacterClass.WIZARD,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=12,
            current_hp=0  # Unconscious!
        )
        return character

    def test_short_rest_displays_unconscious_warning_for_zero_hp_character(
        self, mock_game_state, healthy_character, unconscious_character
    ):
        """Test that short rest correctly displays warning for unconscious character"""
        # Setup party with both characters
        party = Party()
        party.add_character(healthy_character)
        party.add_character(unconscious_character)
        mock_game_state.party = party

        cli = CLI(mock_game_state, Mock(), "test_campaign")

        # Capture printed output
        printed_messages = []

        def capture_print(message):
            printed_messages.append(str(message))

        # Mock the print functions to capture output and mock user input for short rest choice
        with patch('dnd_engine.ui.rich_ui.print_message', side_effect=capture_print):
            with patch('dnd_engine.ui.rich_ui.print_section', side_effect=capture_print):
                with patch('dnd_engine.ui.rich_ui.print_status_message', side_effect=lambda msg, status: capture_print(msg)):
                    with patch('builtins.input', return_value='1'):  # Choose short rest
                        cli.handle_rest()

        # Join all messages for easier assertion
        full_output = "\n".join(printed_messages)

        # Verify the unconscious character gets the warning
        assert "Tim" in full_output
        assert "Still unconscious (0 HP)" in full_output or "⚠️  Still unconscious (0 HP)" in full_output

        # Verify the healthy character gets appropriate message
        assert "Bob" in full_output
        assert "Second Wind" in full_output or "Recovered" in full_output

    def test_short_rest_displays_full_health_for_healthy_character_without_resources(
        self, mock_game_state
    ):
        """Test that healthy character with no resources to recover shows 'Already at full health'"""
        # Create a character at full HP with no resources
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        character = Character(
            name="Alice",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16,
            current_hp=12  # Full HP
        )
        # Don't add any resource pools

        party = Party()
        party.add_character(character)
        mock_game_state.party = party

        cli = CLI(mock_game_state, Mock(), "test_campaign")

        # Capture printed output
        printed_messages = []

        def capture_print(message):
            printed_messages.append(str(message))

        with patch('dnd_engine.ui.rich_ui.print_message', side_effect=capture_print):
            with patch('dnd_engine.ui.rich_ui.print_section', side_effect=capture_print):
                with patch('dnd_engine.ui.rich_ui.print_status_message', side_effect=lambda msg, status: capture_print(msg)):
                    with patch('builtins.input', return_value='1'):  # Choose short rest
                        cli.handle_rest()

        full_output = "\n".join(printed_messages)

        # Verify healthy character shows the correct message
        assert "Alice" in full_output
        assert "Already at full health and resources" in full_output

    def test_long_rest_heals_unconscious_character_and_displays_hp_recovered(
        self, mock_game_state, unconscious_character
    ):
        """Test that long rest heals unconscious character and shows HP recovery"""
        party = Party()
        party.add_character(unconscious_character)
        mock_game_state.party = party

        cli = CLI(mock_game_state, Mock(), "test_campaign")

        # Capture printed output
        printed_messages = []

        def capture_print(message):
            printed_messages.append(str(message))

        with patch('dnd_engine.ui.rich_ui.print_message', side_effect=capture_print):
            with patch('dnd_engine.ui.rich_ui.print_section', side_effect=capture_print):
                with patch('dnd_engine.ui.rich_ui.print_status_message', side_effect=lambda msg, status: capture_print(msg)):
                    with patch('builtins.input', return_value='2'):  # Choose long rest
                        cli.handle_rest()

        full_output = "\n".join(printed_messages)

        # Verify the character's HP was recovered
        assert unconscious_character.current_hp == 8
        assert unconscious_character.current_hp == unconscious_character.max_hp

        # Verify the output shows HP recovery
        assert "Tim" in full_output
        assert "HP recovered: 8" in full_output or "❤️  HP recovered: 8" in full_output

        # Should NOT show the unconscious warning after long rest
        assert "Still unconscious" not in full_output

    def test_mixed_party_displays_all_statuses_correctly(
        self, mock_game_state, healthy_character, unconscious_character
    ):
        """Test that a party with mixed health statuses displays correctly"""
        # Damage the healthy character a bit so they recover HP on long rest
        healthy_character.current_hp = 6

        party = Party()
        party.add_character(healthy_character)
        party.add_character(unconscious_character)
        mock_game_state.party = party

        cli = CLI(mock_game_state, Mock(), "test_campaign")

        # Capture printed output
        printed_messages = []

        def capture_print(message):
            printed_messages.append(str(message))

        with patch('dnd_engine.ui.rich_ui.print_message', side_effect=capture_print):
            with patch('dnd_engine.ui.rich_ui.print_section', side_effect=capture_print):
                with patch('dnd_engine.ui.rich_ui.print_status_message', side_effect=lambda msg, status: capture_print(msg)):
                    with patch('builtins.input', return_value='2'):  # Choose long rest
                        cli.handle_rest()

        full_output = "\n".join(printed_messages)

        # Verify Bob shows HP recovery
        assert "Bob" in full_output
        # Bob should recover 6 HP (from 6 to 12)
        assert "6" in full_output

        # Verify Tim shows HP recovery
        assert "Tim" in full_output
        # Tim should recover 8 HP (from 0 to 8)
        assert "8" in full_output

        # Both should be healed now
        assert healthy_character.current_hp == 12
        assert unconscious_character.current_hp == 8
