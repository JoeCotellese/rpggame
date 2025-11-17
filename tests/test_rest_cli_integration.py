# ABOUTME: Integration tests for rest CLI command
# ABOUTME: Tests CLI rest command interaction with game state and event system

import pytest
from unittest.mock import patch, MagicMock

from dnd_engine.core.game_state import GameState
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.utils.events import EventBus, EventType
from dnd_engine.ui.cli import CLI


def create_test_party_with_resources():
    """Create a test party with resources for rest testing."""
    abilities1 = Abilities(
        strength=16, dexterity=14, constitution=15,
        intelligence=10, wisdom=12, charisma=8
    )
    char1 = Character(
        name="Thorin", character_class=CharacterClass.FIGHTER,
        level=2, abilities=abilities1, max_hp=20, ac=16,
        current_hp=10, xp=500, race="human"
    )
    # Add short rest resource
    second_wind = ResourcePool(
        name="second_wind",
        current=0,
        maximum=1,
        recovery_type="short_rest"
    )
    char1.add_resource_pool(second_wind)

    # Add long rest resource
    spell_slots = ResourcePool(
        name="spell_slots",
        current=0,
        maximum=2,
        recovery_type="long_rest"
    )
    char1.add_resource_pool(spell_slots)

    abilities2 = Abilities(
        strength=10, dexterity=16, constitution=12,
        intelligence=14, wisdom=13, charisma=12
    )
    char2 = Character(
        name="Gandalf", character_class=CharacterClass.ROGUE,
        level=2, abilities=abilities2, max_hp=15, ac=12,
        current_hp=5, xp=200, race="human"
    )
    # Add short rest resource
    action_surge = ResourcePool(
        name="action_surge",
        current=0,
        maximum=1,
        recovery_type="short_rest"
    )
    char2.add_resource_pool(action_surge)

    return Party(characters=[char1, char2])


class TestRestCLIIntegration:
    """Integration tests for CLI rest command"""

    def setup_method(self):
        """Set up test fixtures"""
        self.event_bus = EventBus()
        self.loader = DataLoader()

        self.party = create_test_party_with_resources()
        self.game_state = GameState(
            party=self.party,
            dungeon_name="goblin_warren",
            event_bus=self.event_bus,
            data_loader=self.loader
        )
        self.cli = CLI(self.game_state, auto_save_enabled=True)

    def test_rest_command_exists(self):
        """Test that rest command handler exists"""
        assert hasattr(self.cli, 'handle_rest')

    @patch('builtins.input', side_effect=['1'])  # Choose short rest
    def test_short_rest_command_recovers_short_rest_resources(self, mock_input):
        """Test that short rest command recovers short_rest resources"""
        # Verify resources are depleted
        assert self.party.characters[0].resource_pools["second_wind"].current == 0
        assert self.party.characters[1].resource_pools["action_surge"].current == 0

        # Capture initial HP
        initial_hp_0 = self.party.characters[0].current_hp
        initial_hp_1 = self.party.characters[1].current_hp

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_rest()

        # Verify short rest resources recovered
        assert self.party.characters[0].resource_pools["second_wind"].current == 1
        assert self.party.characters[1].resource_pools["action_surge"].current == 1

        # Verify long rest resources NOT recovered
        assert self.party.characters[0].resource_pools["spell_slots"].current == 0

        # Verify HP not recovered (no Hit Dice in MVP)
        assert self.party.characters[0].current_hp == initial_hp_0
        assert self.party.characters[1].current_hp == initial_hp_1

    @patch('builtins.input', side_effect=['2'])  # Choose long rest
    def test_long_rest_command_recovers_all_hp(self, mock_input):
        """Test that long rest command recovers all HP"""
        # Verify HP is damaged
        assert self.party.characters[0].current_hp < self.party.characters[0].max_hp
        assert self.party.characters[1].current_hp < self.party.characters[1].max_hp

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_rest()

        # Verify HP fully recovered
        assert self.party.characters[0].current_hp == self.party.characters[0].max_hp
        assert self.party.characters[1].current_hp == self.party.characters[1].max_hp

    @patch('builtins.input', side_effect=['2'])  # Choose long rest
    def test_long_rest_command_recovers_all_resources(self, mock_input):
        """Test that long rest command recovers both short_rest and long_rest resources"""
        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_rest()

        # Verify all resources recovered
        assert self.party.characters[0].resource_pools["second_wind"].current == 1
        assert self.party.characters[0].resource_pools["spell_slots"].current == 2
        assert self.party.characters[1].resource_pools["action_surge"].current == 1

    @patch('builtins.input', side_effect=['3'])  # Cancel
    def test_rest_command_can_be_cancelled(self, mock_input):
        """Test that rest can be cancelled by the player"""
        # Capture initial state
        initial_hp = self.party.characters[0].current_hp
        initial_resource = self.party.characters[0].resource_pools["second_wind"].current

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_rest()

        # Verify nothing changed
        assert self.party.characters[0].current_hp == initial_hp
        assert self.party.characters[0].resource_pools["second_wind"].current == initial_resource

    @patch('builtins.input', side_effect=['invalid'])  # Invalid choice
    def test_rest_command_handles_invalid_input(self, mock_input):
        """Test that rest command handles invalid input gracefully"""
        initial_hp = self.party.characters[0].current_hp

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_rest()

        # Verify nothing changed
        assert self.party.characters[0].current_hp == initial_hp

    @patch('builtins.input', side_effect=['1'])  # Short rest
    def test_short_rest_emits_event(self, mock_input):
        """Test that short rest emits SHORT_REST event"""
        event_data = None

        def capture_event(event):
            nonlocal event_data
            event_data = event.data

        self.event_bus.subscribe(EventType.SHORT_REST, capture_event)

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_rest()

        # Verify event was emitted
        assert event_data is not None
        assert event_data["rest_type"] == "short"
        assert "Thorin" in event_data["party"]
        assert "Gandalf" in event_data["party"]
        assert "hp_recovered" in event_data
        assert "resources_recovered" in event_data

    @patch('builtins.input', side_effect=['2'])  # Long rest
    def test_long_rest_emits_event(self, mock_input):
        """Test that long rest emits LONG_REST event"""
        event_data = None

        def capture_event(event):
            nonlocal event_data
            event_data = event.data

        self.event_bus.subscribe(EventType.LONG_REST, capture_event)

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_rest()

        # Verify event was emitted
        assert event_data is not None
        assert event_data["rest_type"] == "long"
        assert "Thorin" in event_data["party"]
        assert "Gandalf" in event_data["party"]
        assert event_data["hp_recovered"]["Thorin"] == 10  # From 10 to 20
        assert event_data["hp_recovered"]["Gandalf"] == 10  # From 5 to 15

    @patch('builtins.input', side_effect=['2'])  # Long rest
    def test_rest_results_displayed(self, mock_input):
        """Test that rest results are displayed to the player"""
        with patch('dnd_engine.ui.rich_ui.print_section') as mock_section, \
             patch('dnd_engine.ui.rich_ui.print_message') as mock_message, \
             patch('dnd_engine.ui.rich_ui.print_status_message') as mock_status:
            self.cli.handle_rest()

        # Verify display functions were called
        assert mock_section.called
        assert mock_message.called
        assert mock_status.called

        # Check that character names appear in messages
        all_messages = [str(call[0][0]) for call in mock_message.call_args_list]
        character_messages = [msg for msg in all_messages if "Thorin" in msg or "Gandalf" in msg]
        assert len(character_messages) >= 2  # At least one message per character

    def test_rest_command_in_help(self):
        """Test that rest command appears in help text"""
        with patch('dnd_engine.ui.cli.print_help_section') as mock_print:
            self.cli.display_help_exploration()

        # Verify help was called
        mock_print.assert_called_once()
        title, commands = mock_print.call_args[0]

        # Find rest command in the help text
        rest_commands = [cmd for cmd in commands if "rest" in cmd[0].lower()]
        assert len(rest_commands) >= 1

    @patch('builtins.input', side_effect=['1'])  # Short rest
    def test_multiple_short_rests(self, mock_input):
        """Test taking multiple short rests (resources should stay at max)"""
        # First short rest
        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_rest()

        assert self.party.characters[0].resource_pools["second_wind"].current == 1

        # Use resource
        self.party.characters[0].use_resource("second_wind")
        assert self.party.characters[0].resource_pools["second_wind"].current == 0

        # Second short rest
        with patch('builtins.input', side_effect=['1']), \
             patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_rest()

        # Verify resource recovered again
        assert self.party.characters[0].resource_pools["second_wind"].current == 1

    @patch('builtins.input', side_effect=['2'])  # Long rest
    def test_long_rest_with_full_health_party(self, mock_input):
        """Test long rest when party is already at full health"""
        # Restore full health first
        for character in self.party.characters:
            character.current_hp = character.max_hp

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message') as mock_message, \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_rest()

        # Verify HP stayed at max
        assert self.party.characters[0].current_hp == self.party.characters[0].max_hp
        assert self.party.characters[1].current_hp == self.party.characters[1].max_hp

        # Verify resources still recovered
        assert self.party.characters[0].resource_pools["second_wind"].current == 1
        assert self.party.characters[0].resource_pools["spell_slots"].current == 2

    @patch('builtins.input', side_effect=['1'])  # Short rest
    def test_short_rest_event_data_structure(self, mock_input):
        """Test that short rest event data has correct structure"""
        event_data = None

        def capture_event(event):
            nonlocal event_data
            event_data = event.data

        self.event_bus.subscribe(EventType.SHORT_REST, capture_event)

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_rest()

        # Verify event data structure
        assert "party" in event_data
        assert "rest_type" in event_data
        assert "hp_recovered" in event_data
        assert "resources_recovered" in event_data

        # Verify party data
        assert isinstance(event_data["party"], list)
        assert len(event_data["party"]) == 2

        # Verify hp_recovered data
        assert isinstance(event_data["hp_recovered"], dict)
        assert "Thorin" in event_data["hp_recovered"]
        assert "Gandalf" in event_data["hp_recovered"]

        # Verify resources_recovered data
        assert isinstance(event_data["resources_recovered"], dict)
        assert "Thorin" in event_data["resources_recovered"]
        assert "Gandalf" in event_data["resources_recovered"]
