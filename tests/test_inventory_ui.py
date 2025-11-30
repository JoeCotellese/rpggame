# ABOUTME: Unit tests for InventoryUI class
# ABOUTME: Tests character selection, equipment management, and inventory display logic

from unittest.mock import Mock, patch

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.systems.inventory import EquipmentSlot, Inventory
from dnd_engine.ui.inventory_ui import InventoryUI


@pytest.fixture
def mock_items_data():
    """Sample items data for testing."""
    return {
        "weapons": {
            "longsword": {
                "name": "Longsword",
                "type": "weapon",
                "weapon_type": "martial",
                "damage": "1d8",
                "damage_type": "slashing"
            },
            "dagger": {
                "name": "Dagger",
                "type": "weapon",
                "weapon_type": "simple",
                "damage": "1d4",
                "damage_type": "piercing"
            }
        },
        "armor": {
            "chain_mail": {
                "name": "Chain Mail",
                "type": "armor",
                "armor_type": "heavy",
                "ac_base": 16
            },
            "leather_armor": {
                "name": "Leather Armor",
                "type": "armor",
                "armor_type": "light",
                "ac_base": 11
            }
        },
        "consumables": {
            "healing_potion": {
                "name": "Healing Potion",
                "type": "consumable",
                "effect": "heal"
            }
        }
    }


@pytest.fixture
def mock_character():
    """Create a mock character with inventory."""
    char = Mock(spec=Character)
    char.name = "TestHero"
    char.character_class = CharacterClass.FIGHTER
    char.level = 3
    char.is_alive = True
    char.current_hp = 25
    char.max_hp = 30
    char.weapon_proficiencies = {"martial", "simple"}
    char.armor_proficiencies = {"light", "medium", "heavy"}

    # Mock inventory
    char.inventory = Mock(spec=Inventory)
    char.inventory.gold = 50
    char.inventory.item_count.return_value = 5
    char.inventory.get_equipped_item.return_value = None
    char.inventory.get_items_by_category.return_value = []
    char.inventory.get_all_items.return_value = []

    return char


@pytest.fixture
def mock_rogue():
    """Create a mock rogue character (limited proficiencies)."""
    char = Mock(spec=Character)
    char.name = "Sneaky"
    char.character_class = CharacterClass.ROGUE
    char.level = 2
    char.is_alive = True
    char.current_hp = 15
    char.max_hp = 18
    char.weapon_proficiencies = {"simple", "rapier", "shortsword"}
    char.armor_proficiencies = {"light"}

    char.inventory = Mock(spec=Inventory)
    char.inventory.gold = 30
    char.inventory.item_count.return_value = 3
    char.inventory.get_equipped_item.return_value = None
    char.inventory.get_items_by_category.return_value = []
    char.inventory.get_all_items.return_value = []

    return char


@pytest.fixture
def mock_data_loader(mock_items_data):
    """Create a mock data loader."""
    loader = Mock()
    loader.load_items.return_value = mock_items_data
    return loader


class TestInventoryUIInit:
    """Test InventoryUI initialization."""

    def test_init_with_party_and_loader(self, mock_character, mock_data_loader):
        """Test initialization with provided party and loader."""
        party = [mock_character]
        ui = InventoryUI(party=party, data_loader=mock_data_loader)

        assert ui.party == party
        assert ui.loader == mock_data_loader
        assert ui.active_character is None

    def test_init_creates_default_loader(self, mock_character):
        """Test that initialization creates default loader if not provided."""
        with patch('dnd_engine.ui.inventory_ui.DataLoader') as mock_loader_class:
            mock_loader_instance = Mock()
            mock_loader_instance.load_items.return_value = {}
            mock_loader_class.return_value = mock_loader_instance

            InventoryUI(party=[mock_character])

            mock_loader_class.assert_called_once()


class TestCharacterSelection:
    """Test character selection functionality."""

    @patch('dnd_engine.ui.inventory_ui.questionary')
    def test_select_character_shows_all_living_members(
        self, mock_questionary, mock_character, mock_rogue, mock_data_loader
    ):
        """Test that character selection shows all living party members."""
        party = [mock_character, mock_rogue]
        ui = InventoryUI(party=party, data_loader=mock_data_loader)

        mock_questionary.select.return_value.ask.return_value = mock_character

        result = ui._select_character(party)

        assert result == mock_character
        mock_questionary.select.assert_called_once()
        # Verify choices were built for both characters
        call_kwargs = mock_questionary.select.call_args
        assert "Select a character:" in str(call_kwargs)

    @patch('dnd_engine.ui.inventory_ui.questionary')
    def test_select_character_returns_none_on_back(
        self, mock_questionary, mock_character, mock_data_loader
    ):
        """Test that selecting back returns None."""
        party = [mock_character]
        ui = InventoryUI(party=party, data_loader=mock_data_loader)

        mock_questionary.select.return_value.ask.return_value = None

        result = ui._select_character(party)

        assert result is None

    @patch('dnd_engine.ui.inventory_ui.questionary')
    def test_select_character_handles_keyboard_interrupt(
        self, mock_questionary, mock_character, mock_data_loader
    ):
        """Test that keyboard interrupt returns None."""
        party = [mock_character]
        ui = InventoryUI(party=party, data_loader=mock_data_loader)

        mock_questionary.select.return_value.ask.side_effect = KeyboardInterrupt

        result = ui._select_character(party)

        assert result is None


class TestMainMenu:
    """Test main menu functionality."""

    @patch('dnd_engine.ui.inventory_ui.questionary')
    def test_show_main_menu_with_character(
        self, mock_questionary, mock_character, mock_data_loader
    ):
        """Test main menu shows character info in prompt."""
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)
        ui.active_character = mock_character

        mock_questionary.select.return_value.ask.return_value = "view"

        result = ui._show_main_menu()

        assert result == "view"
        # Verify prompt contains character name and gold
        call_args = mock_questionary.select.call_args
        prompt = call_args[0][0]
        assert "TestHero" in prompt
        assert "50 GP" in prompt

    @patch('dnd_engine.ui.inventory_ui.questionary')
    def test_show_main_menu_returns_exit_without_character(
        self, mock_questionary, mock_character, mock_data_loader
    ):
        """Test main menu returns exit if no active character."""
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)
        ui.active_character = None

        result = ui._show_main_menu()

        assert result == "exit"


class TestEquipmentManagement:
    """Test equipment management functionality."""

    @patch('dnd_engine.ui.inventory_ui.questionary')
    def test_change_equipment_shows_available_weapons(
        self, mock_questionary, mock_character, mock_data_loader, mock_items_data
    ):
        """Test that change equipment shows available weapons."""
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)
        ui.active_character = mock_character

        # Setup inventory with weapons
        inv_item = Mock()
        inv_item.item_id = "longsword"
        inv_item.quantity = 1
        mock_character.inventory.get_items_by_category.return_value = [inv_item]
        mock_character.inventory.get_equipped_item.return_value = None

        mock_questionary.select.return_value.ask.return_value = None  # Cancel

        ui._change_equipment(EquipmentSlot.WEAPON)

        mock_questionary.select.assert_called_once()
        # Verify weapons were included in choices
        call_args = mock_questionary.select.call_args
        assert "weapon" in call_args[0][0].lower()

    @patch('dnd_engine.ui.inventory_ui.questionary')
    @patch('dnd_engine.ui.inventory_ui.print_status_message')
    def test_change_equipment_equips_selected_item(
        self, mock_print, mock_questionary, mock_character, mock_data_loader
    ):
        """Test that selecting an item equips it."""
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)
        ui.active_character = mock_character

        inv_item = Mock()
        inv_item.item_id = "longsword"
        inv_item.quantity = 1
        mock_character.inventory.get_items_by_category.return_value = [inv_item]
        mock_character.inventory.get_equipped_item.return_value = None

        mock_questionary.select.return_value.ask.return_value = "longsword"

        ui._change_equipment(EquipmentSlot.WEAPON)

        mock_character.inventory.equip_item.assert_called_once_with(
            "longsword", EquipmentSlot.WEAPON
        )

    @patch('dnd_engine.ui.inventory_ui.questionary')
    @patch('dnd_engine.ui.inventory_ui.print_status_message')
    def test_change_equipment_unequips_on_unequip_selection(
        self, mock_print, mock_questionary, mock_character, mock_data_loader
    ):
        """Test that selecting unequip removes current equipment."""
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)
        ui.active_character = mock_character

        inv_item = Mock()
        inv_item.item_id = "longsword"
        inv_item.quantity = 1
        mock_character.inventory.get_items_by_category.return_value = [inv_item]
        mock_character.inventory.get_equipped_item.return_value = "longsword"
        mock_character.inventory.unequip_item.return_value = "longsword"

        mock_questionary.select.return_value.ask.return_value = "__UNEQUIP__"

        ui._change_equipment(EquipmentSlot.WEAPON)

        mock_character.inventory.unequip_item.assert_called_once_with(
            EquipmentSlot.WEAPON
        )


class TestProficiencyMarkers:
    """Test proficiency marker functionality."""

    def test_proficiency_marker_proficient_weapon(
        self, mock_character, mock_data_loader, mock_items_data
    ):
        """Test proficiency marker shows checkmark for proficient weapon."""
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)

        weapon_data = mock_items_data["weapons"]["longsword"]
        result = ui._get_proficiency_marker(mock_character, weapon_data, "weapon")

        assert "✓" in result
        assert "not proficient" not in result

    def test_proficiency_marker_not_proficient_weapon(
        self, mock_rogue, mock_data_loader, mock_items_data
    ):
        """Test proficiency marker shows warning for non-proficient weapon."""
        ui = InventoryUI(party=[mock_rogue], data_loader=mock_data_loader)

        weapon_data = mock_items_data["weapons"]["longsword"]
        result = ui._get_proficiency_marker(mock_rogue, weapon_data, "weapon")

        assert "not proficient" in result

    def test_proficiency_marker_proficient_armor(
        self, mock_character, mock_data_loader, mock_items_data
    ):
        """Test proficiency marker shows checkmark for proficient armor."""
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)

        armor_data = mock_items_data["armor"]["chain_mail"]
        result = ui._get_proficiency_marker(mock_character, armor_data, "armor")

        assert "✓" in result

    def test_proficiency_marker_not_proficient_armor(
        self, mock_rogue, mock_data_loader, mock_items_data
    ):
        """Test proficiency marker shows warning for non-proficient armor."""
        ui = InventoryUI(party=[mock_rogue], data_loader=mock_data_loader)

        armor_data = mock_items_data["armor"]["chain_mail"]
        result = ui._get_proficiency_marker(mock_rogue, armor_data, "armor")

        assert "not proficient" in result


class TestItemDataLookup:
    """Test item data lookup functionality."""

    def test_get_item_data_found(self, mock_character, mock_data_loader, mock_items_data):
        """Test that item data is returned when found."""
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)

        result = ui._get_item_data("longsword", "weapons")

        assert result is not None
        assert result["name"] == "Longsword"

    def test_get_item_data_not_found(self, mock_character, mock_data_loader):
        """Test that None is returned when item not found."""
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)

        result = ui._get_item_data("nonexistent_item", "weapons")

        assert result is None

    def test_get_item_data_wrong_category(
        self, mock_character, mock_data_loader, mock_items_data
    ):
        """Test that None is returned when looking in wrong category."""
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)

        result = ui._get_item_data("longsword", "armor")

        assert result is None


class TestWeaponArmorInfo:
    """Test weapon and armor info display helpers."""

    def test_get_weapon_info_with_damage(
        self, mock_character, mock_data_loader, mock_items_data
    ):
        """Test weapon info includes damage."""
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)

        weapon_data = mock_items_data["weapons"]["longsword"]
        result = ui._get_weapon_info(weapon_data)

        assert "1d8" in result
        assert "slashing" in result

    def test_get_weapon_info_none_data(self, mock_character, mock_data_loader):
        """Test weapon info returns empty for None."""
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)

        result = ui._get_weapon_info(None)

        assert result == ""

    def test_get_armor_info_with_ac(
        self, mock_character, mock_data_loader, mock_items_data
    ):
        """Test armor info includes AC."""
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)

        armor_data = mock_items_data["armor"]["chain_mail"]
        result = ui._get_armor_info(armor_data)

        assert "AC 16" in result

    def test_get_armor_info_none_data(self, mock_character, mock_data_loader):
        """Test armor info returns empty for None."""
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)

        result = ui._get_armor_info(None)

        assert result == ""


class TestRunMethod:
    """Test the main run method."""

    @patch('dnd_engine.ui.inventory_ui.print_status_message')
    def test_run_with_empty_party(self, mock_print, mock_data_loader):
        """Test run exits early with empty party."""
        ui = InventoryUI(party=[], data_loader=mock_data_loader)

        ui.run()

        mock_print.assert_called_with("No party members available.", "warning")

    @patch('dnd_engine.ui.inventory_ui.print_status_message')
    def test_run_with_all_dead_party(self, mock_print, mock_character, mock_data_loader):
        """Test run exits early with all dead party members."""
        mock_character.is_alive = False
        ui = InventoryUI(party=[mock_character], data_loader=mock_data_loader)

        ui.run()

        mock_print.assert_called_with("No living party members.", "warning")
