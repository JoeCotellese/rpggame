# ABOUTME: Unit tests for CampaignManager serialization and deserialization
# ABOUTME: Tests the internal save/load logic that was moved from SaveManager

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from dnd_engine.core.campaign_manager import CampaignManager, SAVE_VERSION
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party
from dnd_engine.core.game_state import GameState
from dnd_engine.systems.inventory import Inventory, EquipmentSlot
from dnd_engine.systems.currency import Currency
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.utils.events import EventBus
from dnd_engine.rules.loader import DataLoader
from dnd_engine.core.dice import DiceRoller


@pytest.fixture
def campaign_manager():
    """Create a CampaignManager with temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield CampaignManager(campaigns_dir=Path(tmpdir))


@pytest.fixture
def sample_character():
    """Create a sample character for testing."""
    abilities = Abilities(
        strength=16,
        dexterity=14,
        constitution=15,
        intelligence=10,
        wisdom=12,
        charisma=8
    )

    character = Character(
        name="Test Warrior",
        character_class=CharacterClass.FIGHTER,
        level=3,
        abilities=abilities,
        max_hp=28,
        ac=17,
        xp=900,
        race="Human",
        subclass="Champion"
    )

    # Add some inventory
    character.inventory.add_item("longsword", "weapon", 1)
    character.inventory.add_item("chain_mail", "armor", 1)
    character.inventory.equip_item("longsword", EquipmentSlot.WEAPON)
    character.inventory.equip_item("chain_mail", EquipmentSlot.ARMOR)
    character.inventory.currency.gold = 50
    character.inventory.currency.silver = 25

    # Add resource pools
    second_wind = ResourcePool(
        name="Second Wind",
        current=1,
        maximum=1,
        recovery_type="short_rest"
    )
    character.add_resource_pool(second_wind)

    action_surge = ResourcePool(
        name="Action Surge",
        current=0,
        maximum=1,
        recovery_type="short_rest"
    )
    character.add_resource_pool(action_surge)

    # Add conditions
    character.add_condition("blessed")

    return character


@pytest.fixture
def wizard_character():
    """Create a wizard character with spells for testing."""
    abilities = Abilities(
        strength=8,
        dexterity=14,
        constitution=12,
        intelligence=16,
        wisdom=13,
        charisma=10
    )

    character = Character(
        name="Test Wizard",
        character_class=CharacterClass.WIZARD,
        level=2,
        abilities=abilities,
        max_hp=13,
        ac=12,
        xp=300,
        race="Elf",
        spellcasting_ability="int",
        known_spells=["fire_bolt", "mage_hand", "magic_missile", "shield", "detect_magic"],
        prepared_spells=["magic_missile", "shield", "detect_magic"]
    )

    # Add spell slots
    spell_slots = ResourcePool(
        name="1st level slots",
        current=2,
        maximum=3,
        recovery_type="long_rest"
    )
    character.add_resource_pool(spell_slots)

    return character


class TestCharacterSerialization:
    """Test character serialization and deserialization."""

    def test_serialize_basic_character(self, campaign_manager, sample_character):
        """Test serializing a basic character."""
        serialized = campaign_manager._serialize_character(sample_character)

        assert serialized["name"] == "Test Warrior"
        assert serialized["character_class"] == "fighter"
        assert serialized["level"] == 3
        assert serialized["race"] == "Human"
        assert serialized["subclass"] == "Champion"
        assert serialized["max_hp"] == 28
        assert serialized["current_hp"] == 28
        assert serialized["ac"] == 17
        assert serialized["xp"] == 900

    def test_serialize_abilities(self, campaign_manager, sample_character):
        """Test that abilities are serialized correctly."""
        serialized = campaign_manager._serialize_character(sample_character)

        abilities = serialized["abilities"]
        assert abilities["strength"] == 16
        assert abilities["dexterity"] == 14
        assert abilities["constitution"] == 15
        assert abilities["intelligence"] == 10
        assert abilities["wisdom"] == 12
        assert abilities["charisma"] == 8

    def test_serialize_inventory(self, campaign_manager, sample_character):
        """Test that inventory is serialized correctly."""
        serialized = campaign_manager._serialize_character(sample_character)

        inventory = serialized["inventory"]
        assert len(inventory["items"]) == 2
        assert inventory["equipped"]["weapon"] == "longsword"
        assert inventory["equipped"]["armor"] == "chain_mail"
        assert inventory["currency"]["gold"] == 50
        assert inventory["currency"]["silver"] == 25

    def test_serialize_resource_pools(self, campaign_manager, sample_character):
        """Test that resource pools are serialized correctly."""
        serialized = campaign_manager._serialize_character(sample_character)

        pools = serialized["resource_pools"]
        assert len(pools) == 2

        # Find Second Wind pool
        second_wind = next(p for p in pools if p["name"] == "Second Wind")
        assert second_wind["current"] == 1
        assert second_wind["maximum"] == 1
        assert second_wind["recovery_type"] == "short_rest"

        # Find Action Surge pool (used)
        action_surge = next(p for p in pools if p["name"] == "Action Surge")
        assert action_surge["current"] == 0
        assert action_surge["maximum"] == 1

    def test_serialize_conditions(self, campaign_manager, sample_character):
        """Test that conditions are serialized correctly."""
        serialized = campaign_manager._serialize_character(sample_character)

        conditions = serialized["conditions"]
        assert "blessed" in conditions

    def test_serialize_wizard_spells(self, campaign_manager, wizard_character):
        """Test that wizard spells are serialized correctly."""
        serialized = campaign_manager._serialize_character(wizard_character)

        assert serialized["spellcasting_ability"] == "int"
        assert len(serialized["known_spells"]) == 5
        assert "magic_missile" in serialized["known_spells"]
        assert len(serialized["prepared_spells"]) == 3
        assert "shield" in serialized["prepared_spells"]

    def test_deserialize_basic_character(self, campaign_manager):
        """Test deserializing a basic character."""
        char_data = {
            "name": "Deserialized Fighter",
            "character_class": "fighter",
            "level": 2,
            "race": "Dwarf",
            "subclass": "Battle Master",
            "xp": 300,
            "max_hp": 18,
            "current_hp": 15,
            "ac": 16,
            "abilities": {
                "strength": 16,
                "dexterity": 12,
                "constitution": 15,
                "intelligence": 10,
                "wisdom": 11,
                "charisma": 8
            },
            "inventory": {
                "items": [],
                "equipped": {"weapon": None, "armor": None},
                "currency": {"copper": 0, "silver": 0, "gold": 0, "platinum": 0}
            },
            "conditions": [],
            "resource_pools": []
        }

        character = campaign_manager._deserialize_character(char_data)

        assert character.name == "Deserialized Fighter"
        assert character.character_class == CharacterClass.FIGHTER
        assert character.level == 2
        assert character.race == "Dwarf"
        assert character.subclass == "Battle Master"
        assert character.xp == 300
        assert character.max_hp == 18
        assert character.current_hp == 15
        assert character.ac == 16

    def test_deserialize_abilities(self, campaign_manager):
        """Test that abilities are deserialized correctly."""
        char_data = {
            "name": "Test",
            "character_class": "wizard",
            "level": 1,
            "race": "Human",
            "max_hp": 6,
            "current_hp": 6,
            "ac": 10,
            "xp": 0,
            "abilities": {
                "strength": 8,
                "dexterity": 14,
                "constitution": 12,
                "intelligence": 16,
                "wisdom": 13,
                "charisma": 10
            },
            "inventory": {
                "items": [],
                "equipped": {"weapon": None, "armor": None},
                "currency": {"copper": 0, "silver": 0, "gold": 0, "platinum": 0}
            },
            "conditions": [],
            "resource_pools": []
        }

        character = campaign_manager._deserialize_character(char_data)

        assert character.abilities.strength == 8
        assert character.abilities.intelligence == 16

    def test_deserialize_resource_pools(self, campaign_manager):
        """Test that resource pools are deserialized correctly."""
        char_data = {
            "name": "Test",
            "character_class": "fighter",
            "level": 2,
            "race": "Human",
            "max_hp": 18,
            "current_hp": 18,
            "ac": 16,
            "xp": 300,
            "abilities": {
                "strength": 16,
                "dexterity": 14,
                "constitution": 14,
                "intelligence": 10,
                "wisdom": 12,
                "charisma": 8
            },
            "inventory": {
                "items": [],
                "equipped": {"weapon": None, "armor": None},
                "currency": {"copper": 0, "silver": 0, "gold": 0, "platinum": 0}
            },
            "conditions": [],
            "resource_pools": [
                {
                    "name": "Second Wind",
                    "current": 0,
                    "maximum": 1,
                    "recovery_type": "short_rest"
                }
            ]
        }

        character = campaign_manager._deserialize_character(char_data)

        pool = character.get_resource_pool("Second Wind")
        assert pool is not None
        assert pool.current == 0
        assert pool.maximum == 1

    def test_roundtrip_character(self, campaign_manager, sample_character):
        """Test serializing and deserializing a character maintains data."""
        serialized = campaign_manager._serialize_character(sample_character)
        deserialized = campaign_manager._deserialize_character(serialized)

        assert deserialized.name == sample_character.name
        assert deserialized.character_class == sample_character.character_class
        assert deserialized.level == sample_character.level
        assert deserialized.max_hp == sample_character.max_hp
        assert deserialized.ac == sample_character.ac

        # Check resource pools preserved
        assert len(deserialized.resource_pools) == len(sample_character.resource_pools)


class TestInventorySerialization:
    """Test inventory serialization and deserialization."""

    def test_serialize_empty_inventory(self, campaign_manager):
        """Test serializing an empty inventory."""
        inventory = Inventory()
        serialized = campaign_manager._serialize_inventory(inventory)

        assert serialized["items"] == []
        assert serialized["equipped"]["weapon"] is None
        assert serialized["equipped"]["armor"] is None
        assert serialized["currency"]["gold"] == 0

    def test_serialize_inventory_with_items(self, campaign_manager):
        """Test serializing inventory with items."""
        inventory = Inventory()
        inventory.add_item("longsword", "weapon", 1)
        inventory.add_item("potion_of_healing", "consumable", 3)

        serialized = campaign_manager._serialize_inventory(inventory)

        assert len(serialized["items"]) == 2
        item_ids = [item["item_id"] for item in serialized["items"]]
        assert "longsword" in item_ids
        assert "potion_of_healing" in item_ids

    def test_serialize_equipped_items(self, campaign_manager):
        """Test serializing equipped items."""
        inventory = Inventory()
        inventory.add_item("longsword", "weapon", 1)
        inventory.add_item("chain_mail", "armor", 1)
        inventory.equip_item("longsword", EquipmentSlot.WEAPON)
        inventory.equip_item("chain_mail", EquipmentSlot.ARMOR)

        serialized = campaign_manager._serialize_inventory(inventory)

        assert serialized["equipped"]["weapon"] == "longsword"
        assert serialized["equipped"]["armor"] == "chain_mail"

    def test_serialize_currency(self, campaign_manager):
        """Test serializing currency."""
        inventory = Inventory()
        inventory.currency.copper = 25
        inventory.currency.silver = 10
        inventory.currency.gold = 100
        inventory.currency.platinum = 5

        serialized = campaign_manager._serialize_inventory(inventory)

        currency = serialized["currency"]
        assert currency["copper"] == 25
        assert currency["silver"] == 10
        assert currency["gold"] == 100
        assert currency["platinum"] == 5

    def test_deserialize_inventory(self, campaign_manager):
        """Test deserializing inventory."""
        inv_data = {
            "items": [
                {"item_id": "longsword", "category": "weapon", "quantity": 1},
                {"item_id": "potion_of_healing", "category": "consumable", "quantity": 2}
            ],
            "equipped": {
                "weapon": "longsword",
                "armor": None
            },
            "currency": {
                "copper": 10,
                "silver": 20,
                "gold": 50,
                "platinum": 1
            }
        }

        inventory = campaign_manager._deserialize_inventory(inv_data)

        assert len(inventory.items) == 2
        assert inventory.has_item("longsword")
        assert inventory.get_item_quantity("potion_of_healing") == 2
        assert inventory.equipped[EquipmentSlot.WEAPON] == "longsword"
        assert inventory.currency.gold == 50


class TestGameStateSerialization:
    """Test game state serialization."""

    def test_serialize_game_state(self, campaign_manager):
        """Test serializing a complete game state."""
        abilities = Abilities(16, 14, 15, 10, 12, 8)
        character = Character(
            name="Hero",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )
        party = Party([character])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=EventBus(),
            data_loader=DataLoader(),
            dice_roller=DiceRoller()
        )

        serialized = campaign_manager._serialize_game_state(game_state, auto_save=True)

        assert serialized["version"] == SAVE_VERSION
        assert serialized["metadata"]["auto_save"] is True
        assert len(serialized["party"]) == 1
        assert serialized["party"][0]["name"] == "Hero"
        assert serialized["game_state"]["dungeon_name"] == "test_dungeon"

    def test_serialize_dungeon_state(self, campaign_manager):
        """Test serializing dungeon state."""
        dungeon = {
            "rooms": {
                "room_1": {
                    "searched": True,
                    "enemies": ["goblin_1"]
                },
                "room_2": {
                    "searched": False,
                    "enemies": []
                }
            }
        }

        serialized = campaign_manager._serialize_dungeon_state(dungeon)

        assert "room_1" in serialized
        assert serialized["room_1"]["searched"] is True
        assert "goblin_1" in serialized["room_1"]["enemies"]


class TestSaveDataValidation:
    """Test save data validation."""

    def test_validate_valid_save_data(self, campaign_manager):
        """Test validation passes for valid save data."""
        save_data = {
            "version": "1.0.0",
            "metadata": {"created": "2024-01-01T00:00:00"},
            "party": [{"name": "Hero"}],
            "game_state": {}
        }

        # Should not raise
        campaign_manager._validate_save_data(save_data)

    def test_validate_missing_version(self, campaign_manager):
        """Test validation fails when version is missing."""
        save_data = {
            "metadata": {},
            "party": [{}],
            "game_state": {}
        }

        with pytest.raises(ValueError, match="missing 'version'"):
            campaign_manager._validate_save_data(save_data)

    def test_validate_missing_party(self, campaign_manager):
        """Test validation fails when party is missing."""
        save_data = {
            "version": "1.0.0",
            "metadata": {},
            "game_state": {}
        }

        with pytest.raises(ValueError, match="missing 'party'"):
            campaign_manager._validate_save_data(save_data)

    def test_validate_empty_party(self, campaign_manager):
        """Test validation fails when party is empty."""
        save_data = {
            "version": "1.0.0",
            "metadata": {},
            "party": [],
            "game_state": {}
        }

        with pytest.raises(ValueError, match="party cannot be empty"):
            campaign_manager._validate_save_data(save_data)

    def test_validate_party_not_list(self, campaign_manager):
        """Test validation fails when party is not a list."""
        save_data = {
            "version": "1.0.0",
            "metadata": {},
            "party": {"character": "data"},
            "game_state": {}
        }

        with pytest.raises(ValueError, match="'party' must be a list"):
            campaign_manager._validate_save_data(save_data)

    def test_is_compatible_version_exact_match(self, campaign_manager):
        """Test version compatibility with exact match."""
        assert campaign_manager._is_compatible_version(SAVE_VERSION) is True

    def test_is_compatible_version_mismatch(self, campaign_manager):
        """Test version compatibility with mismatch."""
        assert campaign_manager._is_compatible_version("0.9.0") is False
        assert campaign_manager._is_compatible_version("2.0.0") is False
