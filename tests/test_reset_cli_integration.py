# ABOUTME: Integration tests for reset CLI command
# ABOUTME: Tests CLI reset command interaction with game state and save system

import pytest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

from dnd_engine.core.game_state import GameState
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party
from dnd_engine.core.save_manager import SaveManager
from dnd_engine.systems.inventory import EquipmentSlot
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus
from dnd_engine.ui.cli import CLI


@pytest.fixture
def temp_saves_dir():
    """Create a temporary directory for save files."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def save_manager(temp_saves_dir):
    """Create a SaveManager with temporary directory."""
    return SaveManager(saves_dir=temp_saves_dir)


def create_test_party():
    """Create a test party with equipment and inventory."""
    abilities1 = Abilities(
        strength=16, dexterity=14, constitution=15,
        intelligence=10, wisdom=12, charisma=8
    )
    char1 = Character(
        name="Thorin", character_class=CharacterClass.FIGHTER,
        level=3, abilities=abilities1, max_hp=20, ac=16,
        current_hp=20, xp=500, race="human"
    )
    char1.inventory.add_item("longsword", "weapons")
    char1.inventory.equip_item("longsword", EquipmentSlot.WEAPON)
    char1.inventory.add_gold(150)

    abilities2 = Abilities(
        strength=10, dexterity=16, constitution=12,
        intelligence=14, wisdom=13, charisma=12
    )
    char2 = Character(
        name="Gandalf", character_class=CharacterClass.ROGUE,
        level=2, abilities=abilities2, max_hp=12, ac=12,
        current_hp=12, xp=200, race="human"
    )
    char2.inventory.add_item("staff", "weapons")
    char2.inventory.equip_item("staff", EquipmentSlot.WEAPON)
    char2.inventory.add_gold(75)

    return Party(characters=[char1, char2])


class TestResetCLIIntegration:
    """Integration tests for CLI reset command"""

    def setup_method(self):
        """Set up test fixtures"""
        self.event_bus = EventBus()
        self.loader = DataLoader()

        self.party = create_test_party()
        self.game_state = GameState(
            party=self.party,
            dungeon_name="goblin_warren",
            event_bus=self.event_bus,
            data_loader=self.loader
        )
        self.cli = CLI(self.game_state, auto_save_enabled=True)

    def test_reset_command_parsed_correctly(self):
        """Test that reset command is parsed correctly"""
        # Verify command is recognized
        assert hasattr(self.cli, 'handle_reset')

    @patch('builtins.input', side_effect=['y'])
    def test_reset_command_resets_dungeon(self, mock_input):
        """Test that reset command resets the dungeon"""
        # Move around first
        current_room = self.game_state.get_current_room()
        if current_room["exits"]:
            direction = list(current_room["exits"].keys())[0]
            self.game_state.move(direction)

        initial_room = self.game_state.current_room_id
        assert initial_room != self.game_state.dungeon["start_room"]

        # Execute reset command
        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_reset("reset")

        # Verify dungeon was reset
        assert self.game_state.current_room_id == self.game_state.dungeon["start_room"]

    @patch('builtins.input', side_effect=['y'])
    def test_reset_command_preserves_party_data(self, mock_input):
        """Test that reset preserves party data"""
        original_level = self.party.characters[0].level
        original_xp = self.party.characters[0].xp
        original_gold = self.party.characters[0].inventory.currency.gold
        original_equipment = self.party.characters[0].inventory.get_equipped_item(EquipmentSlot.WEAPON)

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_reset("reset")

        # Verify party data was preserved
        assert self.party.characters[0].level == original_level
        assert self.party.characters[0].xp == original_xp
        assert self.party.characters[0].inventory.currency.gold == original_gold
        assert self.party.characters[0].inventory.get_equipped_item(EquipmentSlot.WEAPON) == original_equipment

    @patch('builtins.input', side_effect=['y'])
    def test_reset_command_clears_action_history(self, mock_input):
        """Test that reset clears action history"""
        # Add some action history
        self.game_state.action_history = ["moved north", "searched room"]
        assert len(self.game_state.action_history) > 0

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_reset("reset")

        # Verify action history was cleared
        assert self.game_state.action_history == []

    @patch('builtins.input', side_effect=['y'])
    def test_reset_command_resets_hp(self, mock_input):
        """Test that reset restores all party members to full HP"""
        # Damage party members
        self.game_state.party.characters[0].current_hp = 5
        self.game_state.party.characters[1].current_hp = 3

        max_hp_0 = self.game_state.party.characters[0].max_hp
        max_hp_1 = self.game_state.party.characters[1].max_hp

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_reset("reset")

        # Verify HP was restored
        assert self.game_state.party.characters[0].current_hp == max_hp_0
        assert self.game_state.party.characters[1].current_hp == max_hp_1

    @patch('builtins.input', side_effect=['y'])
    def test_reset_command_clears_conditions(self, mock_input):
        """Test that reset clears all conditions"""
        # Add conditions
        self.game_state.party.characters[0].add_condition("poisoned")
        self.game_state.party.characters[1].add_condition("stunned")

        assert len(self.game_state.party.characters[0].conditions) > 0
        assert len(self.game_state.party.characters[1].conditions) > 0

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_reset("reset")

        # Verify conditions were cleared
        assert len(self.game_state.party.characters[0].conditions) == 0
        assert len(self.game_state.party.characters[1].conditions) == 0

    @patch('builtins.input', side_effect=['n'])
    def test_reset_command_can_be_cancelled(self, mock_input):
        """Test that reset can be cancelled by the player"""
        # Move to a different room
        current_room = self.game_state.get_current_room()
        if current_room["exits"]:
            direction = list(current_room["exits"].keys())[0]
            self.game_state.move(direction)

        position_before = self.game_state.current_room_id

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_reset("reset")

        # Verify position didn't change (reset was cancelled)
        assert self.game_state.current_room_id == position_before

    @patch('builtins.input', side_effect=['y'])
    def test_reset_with_dungeon_option(self, mock_input):
        """Test reset with --dungeon option to switch dungeons"""
        original_dungeon = self.game_state.dungeon_name
        new_dungeon = "dragon_lair"

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_reset(f"reset --dungeon {new_dungeon}")

        # Verify dungeon switched
        assert self.game_state.dungeon_name == new_dungeon
        assert self.game_state.dungeon_name != original_dungeon

    @patch('builtins.input', side_effect=['y'])
    def test_reset_with_dungeon_option_preserves_party(self, mock_input):
        """Test that switching dungeons preserves party data"""
        original_level = self.party.characters[0].level
        original_xp = self.party.characters[0].xp
        original_count = len(self.party.characters)

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_reset("reset --dungeon dragon_lair")

        # Verify party data was preserved
        assert len(self.party.characters) == original_count
        assert self.party.characters[0].level == original_level
        assert self.party.characters[0].xp == original_xp

    @patch('builtins.input', side_effect=['y'])
    def test_reset_updates_save_state(self, mock_input, temp_saves_dir):
        """Test that reset updates the save state"""
        save_manager = SaveManager(saves_dir=temp_saves_dir)
        self.game_state.save_manager = save_manager

        # Save initial state
        save_manager.save_game(self.game_state, "test_save")

        # Move around and reset
        current_room = self.game_state.get_current_room()
        if current_room["exits"]:
            direction = list(current_room["exits"].keys())[0]
            self.game_state.move(direction)

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_reset("reset")

        # Verify autosave was created
        saves = save_manager.list_saves()
        assert any(save["name"] == "reset_autosave" for save in saves)

    @patch('builtins.input', side_effect=['y'])
    def test_reset_clears_combat_state(self, mock_input):
        """Test that reset clears combat state"""
        # Simulate combat
        self.game_state.in_combat = True
        self.game_state.active_enemies = [MagicMock()]

        assert self.game_state.in_combat
        assert len(self.game_state.active_enemies) > 0

        with patch('dnd_engine.ui.cli.print_section'), \
             patch('dnd_engine.ui.cli.print_message'), \
             patch('dnd_engine.ui.cli.print_status_message'):
            self.cli.handle_reset("reset")

        # Verify combat state was cleared
        assert not self.game_state.in_combat
        assert self.game_state.active_enemies == []

    def test_reset_command_in_help(self):
        """Test that reset command appears in help text"""
        # Capture help output
        with patch('dnd_engine.ui.cli.print_help_section') as mock_print:
            self.cli.display_help_exploration()

        # Verify help was called and check the arguments
        mock_print.assert_called_once()
        title, commands = mock_print.call_args[0]

        # Find reset commands in the help text
        reset_commands = [cmd for cmd in commands if "reset" in cmd[0].lower()]
        assert len(reset_commands) >= 2  # reset and reset --dungeon
