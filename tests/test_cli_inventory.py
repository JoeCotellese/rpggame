# ABOUTME: Unit tests for CLI inventory commands with player targeting
# ABOUTME: Tests the new player targeting functionality for equip, unequip, and use commands

import pytest
from unittest.mock import Mock, patch, MagicMock
from dnd_engine.ui.cli import CLI
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.party import Party
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.systems.inventory import Inventory, EquipmentSlot
from dnd_engine.utils.events import EventBus


class TestCLIPlayerTargeting:
    """Test CLI player targeting functionality for inventory commands"""

    def setup_method(self):
        """Set up test fixtures with a multi-character party"""
        # Create three test characters
        abilities = Abilities(16, 14, 15, 10, 12, 8)

        self.char1 = Character(
            name="Gandalf",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=16
        )

        self.char2 = Character(
            name="Aragorn",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=16
        )

        self.char3 = Character(
            name="Legolas",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=16
        )

        # Add items to each character's inventory
        self.char1.inventory.add_item("longsword", "weapons")
        self.char1.inventory.add_item("potion_of_healing", "consumables")

        self.char2.inventory.add_item("greataxe", "weapons")
        self.char2.inventory.add_item("potion_of_healing", "consumables")

        self.char3.inventory.add_item("shortbow", "weapons")
        self.char3.inventory.add_item("potion_of_healing", "consumables")

        # Create party with all three characters
        self.party = Party([self.char1, self.char2, self.char3])

        # Create mock game state
        self.game_state = Mock(spec=GameState)
        self.game_state.party = self.party
        self.game_state.event_bus = Mock(spec=EventBus)
        self.game_state.data_loader = Mock()
        self.game_state.data_loader.load_items.return_value = {
            "weapons": {
                "longsword": {"name": "Longsword", "damage": "1d8"},
                "greataxe": {"name": "Greataxe", "damage": "1d12"},
                "shortbow": {"name": "Shortbow", "damage": "1d6"}
            },
            "armor": {
                "chainmail": {"name": "Chainmail", "ac": 16}
            },
            "consumables": {
                "potion_of_healing": {"name": "Potion of Healing", "effect": "heal", "amount": "2d4+2"}
            }
        }
        self.game_state.dice_roller = Mock()
        self.game_state.dice_roller.roll.return_value = Mock(total=8)

        # Create CLI
        self.cli = CLI(self.game_state, auto_save_enabled=False)

    def test_parse_item_and_player_with_number(self):
        """Test parsing item and player number"""
        item, player = self.cli._parse_item_and_player(["longsword", "2"])
        assert item == "longsword"
        assert player == "2"

    def test_parse_item_and_player_with_name(self):
        """Test parsing item and player name"""
        item, player = self.cli._parse_item_and_player(["longsword", "gandalf"])
        assert item == "longsword"
        assert player == "gandalf"

    def test_parse_item_and_player_multiword_item(self):
        """Test parsing multi-word item name with player number"""
        item, player = self.cli._parse_item_and_player(["potion", "of", "healing", "2"])
        assert item == "potion of healing"
        assert player == "2"

    def test_parse_item_and_player_no_player(self):
        """Test parsing when no player identifier is provided"""
        item, player = self.cli._parse_item_and_player(["longsword"])
        assert item == "longsword"
        assert player is None

    def test_parse_item_and_player_invalid_number(self):
        """Test parsing with invalid player number (treated as item name)"""
        item, player = self.cli._parse_item_and_player(["longsword", "999"])
        assert item == "longsword 999"
        assert player is None

    def test_get_target_player_by_number(self):
        """Test getting player by number (1-based index)"""
        player = self.cli._get_target_player("1")
        assert player == self.char1

        player = self.cli._get_target_player("2")
        assert player == self.char2

        player = self.cli._get_target_player("3")
        assert player == self.char3

    def test_get_target_player_by_name(self):
        """Test getting player by name (case-insensitive)"""
        player = self.cli._get_target_player("gandalf")
        assert player == self.char1

        player = self.cli._get_target_player("ARAGORN")
        assert player == self.char2

        player = self.cli._get_target_player("Legolas")
        assert player == self.char3

    def test_get_target_player_default(self):
        """Test getting default player (first living member)"""
        player = self.cli._get_target_player(None)
        assert player == self.char1

    @patch('dnd_engine.ui.cli.print_error')
    def test_get_target_player_invalid_number(self, mock_print_error):
        """Test getting player with invalid number"""
        player = self.cli._get_target_player("999")
        assert player is None
        mock_print_error.assert_called_once()

    @patch('dnd_engine.ui.cli.print_error')
    def test_get_target_player_dead_character(self, mock_print_error):
        """Test getting dead character by number"""
        self.char2.current_hp = 0
        player = self.cli._get_target_player("2")
        assert player is None
        mock_print_error.assert_called_once()

    @patch('dnd_engine.ui.cli.print_error')
    def test_get_target_player_invalid_name(self, mock_print_error):
        """Test getting player with invalid name"""
        player = self.cli._get_target_player("frodo")
        assert player is None
        mock_print_error.assert_called_once()

    @patch('dnd_engine.ui.cli.print_status_message')
    def test_handle_equip_with_player_number(self, mock_print):
        """Test equipping item on specific player by number"""
        self.cli.handle_equip("longsword", "1")

        # Check that the item was equipped on the correct character
        assert self.char1.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "longsword"
        assert self.char2.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None
        assert self.char3.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None

    @patch('dnd_engine.ui.cli.print_status_message')
    def test_handle_equip_with_player_name(self, mock_print):
        """Test equipping item on specific player by name"""
        self.cli.handle_equip("greataxe", "aragorn")

        # Check that the item was equipped on the correct character
        assert self.char1.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None
        assert self.char2.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "greataxe"
        assert self.char3.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None

    @patch('dnd_engine.ui.cli.print_status_message')
    def test_handle_equip_default_player(self, mock_print):
        """Test equipping item on default player (first living)"""
        self.cli.handle_equip("longsword")

        # Should equip on first living member (char1)
        assert self.char1.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "longsword"

    @patch('dnd_engine.ui.cli.print_error')
    def test_handle_equip_wrong_player(self, mock_print_error):
        """Test equipping item that player doesn't have"""
        self.cli.handle_equip("greataxe", "1")  # char1 doesn't have greataxe

        # Should show error and not equip anything
        mock_print_error.assert_called_once()
        assert self.char1.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None

    @patch('dnd_engine.ui.cli.print_status_message')
    def test_handle_unequip_with_player_number(self, mock_print):
        """Test unequipping item from specific player by number"""
        # First equip something on char2
        self.char2.inventory.equip_item("greataxe", EquipmentSlot.WEAPON)

        # Now unequip from char2
        self.cli.handle_unequip("weapon", "2")

        # Check that the item was unequipped from char2
        assert self.char2.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None

    @patch('dnd_engine.ui.cli.print_status_message')
    def test_handle_unequip_with_player_name(self, mock_print):
        """Test unequipping item from specific player by name"""
        # First equip something on char3
        self.char3.inventory.equip_item("shortbow", EquipmentSlot.WEAPON)

        # Now unequip from char3 by name
        self.cli.handle_unequip("weapon", "legolas")

        # Check that the item was unequipped from char3
        assert self.char3.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None

    @patch('dnd_engine.ui.cli.print_status_message')
    def test_handle_use_item_with_player_number(self, mock_print):
        """Test using item on specific player by number"""
        initial_count = len(self.char2.inventory.get_items_by_category("consumables"))

        self.cli.handle_use_item("potion_of_healing", "2")

        # Check that the item was removed from char2's inventory
        final_count = len(self.char2.inventory.get_items_by_category("consumables"))
        assert final_count == initial_count - 1

    @patch('dnd_engine.ui.cli.print_status_message')
    @patch('dnd_engine.ui.cli.print_message')
    def test_handle_use_item_with_player_name(self, mock_print_msg, mock_print_status):
        """Test using item on specific player by name"""
        initial_count = len(self.char3.inventory.get_items_by_category("consumables"))

        self.cli.handle_use_item("potion_of_healing", "legolas")

        # Check that the item was removed from char3's inventory
        final_count = len(self.char3.inventory.get_items_by_category("consumables"))
        assert final_count == initial_count - 1

    @patch('dnd_engine.ui.cli.print_status_message')
    @patch('dnd_engine.ui.cli.print_message')
    def test_handle_use_item_default_player(self, mock_print_msg, mock_print_status):
        """Test using item on default player (first living)"""
        initial_count = len(self.char1.inventory.get_items_by_category("consumables"))

        self.cli.handle_use_item("potion_of_healing")

        # Should use item from first living member (char1)
        final_count = len(self.char1.inventory.get_items_by_category("consumables"))
        assert final_count == initial_count - 1

    @patch('dnd_engine.ui.cli.print_error')
    def test_handle_use_item_wrong_player(self, mock_print_error):
        """Test using item that player doesn't have"""
        # Remove all consumables from char1
        self.char1.inventory.remove_item("potion_of_healing", 1)

        self.cli.handle_use_item("potion_of_healing", "1")

        # Should show error
        mock_print_error.assert_called_once()

    def test_process_exploration_command_equip_with_number(self):
        """Test processing 'equip longsword 2' command"""
        with patch.object(self.cli, 'handle_equip') as mock_handle:
            self.cli.process_exploration_command("equip longsword 2")
            mock_handle.assert_called_once_with("longsword", "2")

    def test_process_exploration_command_equip_with_name(self):
        """Test processing 'equip longsword gandalf' command"""
        with patch.object(self.cli, 'handle_equip') as mock_handle:
            self.cli.process_exploration_command("equip longsword gandalf")
            mock_handle.assert_called_once_with("longsword", "gandalf")

    def test_process_exploration_command_equip_no_player(self):
        """Test processing 'equip longsword' command (backward compatibility)"""
        with patch.object(self.cli, 'handle_equip') as mock_handle:
            self.cli.process_exploration_command("equip longsword")
            mock_handle.assert_called_once_with("longsword", None)

    def test_process_exploration_command_unequip_with_number(self):
        """Test processing 'unequip weapon 2' command"""
        with patch.object(self.cli, 'handle_unequip') as mock_handle:
            self.cli.process_exploration_command("unequip weapon 2")
            mock_handle.assert_called_once_with("weapon", "2")

    def test_process_exploration_command_use_with_number(self):
        """Test processing 'use potion 3' command"""
        with patch.object(self.cli, 'handle_use_item') as mock_handle:
            self.cli.process_exploration_command("use potion 3")
            mock_handle.assert_called_once_with("potion", "3")

    def test_backward_compatibility_all_commands(self):
        """Test that all commands work without player identifier (backward compatibility)"""
        with patch('dnd_engine.ui.cli.print_status_message'):
            # Equip without player identifier should work
            self.cli.handle_equip("longsword")
            assert self.char1.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "longsword"

            # Unequip without player identifier should work
            self.cli.handle_unequip("weapon")
            assert self.char1.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None

            # Use without player identifier should work
            initial_count = len(self.char1.inventory.get_items_by_category("consumables"))
            with patch('dnd_engine.ui.cli.print_message'):
                self.cli.handle_use_item("potion_of_healing")
            final_count = len(self.char1.inventory.get_items_by_category("consumables"))
            assert final_count == initial_count - 1
