# ABOUTME: Unit tests for save/load game state functionality
# ABOUTME: Tests SaveManager serialization, validation, and file operations

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from dnd_engine.core.save_manager import SaveManager, SAVE_VERSION
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party
from dnd_engine.core.game_state import GameState
from dnd_engine.systems.inventory import Inventory, EquipmentSlot
from dnd_engine.systems.currency import Currency
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus


@pytest.fixture
def temp_saves_dir():
    """Create a temporary directory for save files."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def save_manager(temp_saves_dir):
    """Create a SaveManager with temporary directory."""
    return SaveManager(saves_dir=temp_saves_dir)


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
        name="Test Hero",
        character_class=CharacterClass.FIGHTER,
        level=2,
        abilities=abilities,
        max_hp=20,
        ac=16,
        current_hp=15,
        xp=350,
        race="human"
    )

    # Add some inventory items
    character.inventory.add_item("longsword", "weapons", 1)
    character.inventory.add_item("chainmail", "armor", 1)
    character.inventory.add_item("potion_healing", "consumables", 2)
    character.inventory.equip_item("longsword", EquipmentSlot.WEAPON)
    character.inventory.equip_item("chainmail", EquipmentSlot.ARMOR)
    character.inventory.add_gold(50)

    # Add a condition
    character.add_condition("inspired")

    return character


@pytest.fixture
def sample_party(sample_character):
    """Create a sample party for testing."""
    abilities2 = Abilities(
        strength=12,
        dexterity=16,
        constitution=14,
        intelligence=13,
        wisdom=15,
        charisma=10
    )

    character2 = Character(
        name="Test Companion",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities2,
        max_hp=12,
        ac=15,
        current_hp=12,
        xp=100,
        race="high_elf"
    )

    return Party(characters=[sample_character, character2])


@pytest.fixture
def sample_game_state(sample_party):
    """Create a sample game state for testing."""
    event_bus = EventBus()
    data_loader = DataLoader()

    game_state = GameState(
        party=sample_party,
        dungeon_name="goblin_warren",
        event_bus=event_bus,
        data_loader=data_loader
    )

    # Add some action history
    game_state.action_history = [
        "Entered the dungeon",
        "Fought a goblin"
    ]

    return game_state


class TestSaveManager:
    """Test SaveManager functionality."""

    def test_init_creates_saves_directory(self, temp_saves_dir):
        """Test that SaveManager creates saves directory if it doesn't exist."""
        saves_path = temp_saves_dir / "new_saves"
        assert not saves_path.exists()

        manager = SaveManager(saves_dir=saves_path)
        assert saves_path.exists()
        assert saves_path.is_dir()

    def test_save_game_creates_file(self, save_manager, sample_game_state, temp_saves_dir):
        """Test that save_game creates a JSON file."""
        save_path = save_manager.save_game(sample_game_state, "test_save")

        assert save_path.exists()
        assert save_path.suffix == ".json"
        assert save_path.stem == "test_save"
        assert save_path.parent == temp_saves_dir

    def test_save_game_structure(self, save_manager, sample_game_state):
        """Test that saved game has correct structure."""
        save_path = save_manager.save_game(sample_game_state, "test_save")

        with open(save_path, 'r') as f:
            save_data = json.load(f)

        # Check top-level structure
        assert "version" in save_data
        assert "metadata" in save_data
        assert "party" in save_data
        assert "game_state" in save_data

        # Check version
        assert save_data["version"] == SAVE_VERSION

        # Check metadata
        assert "created" in save_data["metadata"]
        assert "last_played" in save_data["metadata"]
        assert "auto_save" in save_data["metadata"]
        assert save_data["metadata"]["auto_save"] is False

        # Check party
        assert isinstance(save_data["party"], list)
        assert len(save_data["party"]) == 2

        # Check game state
        assert "dungeon_name" in save_data["game_state"]
        assert "current_room_id" in save_data["game_state"]
        assert "dungeon_state" in save_data["game_state"]

    def test_save_character_data(self, save_manager, sample_game_state):
        """Test that character data is correctly serialized."""
        save_path = save_manager.save_game(sample_game_state, "test_save")

        with open(save_path, 'r') as f:
            save_data = json.load(f)

        char_data = save_data["party"][0]

        assert char_data["name"] == "Test Hero"
        assert char_data["character_class"] == "fighter"
        assert char_data["level"] == 2
        assert char_data["race"] == "human"
        assert char_data["xp"] == 350
        assert char_data["max_hp"] == 20
        assert char_data["current_hp"] == 15
        assert char_data["ac"] == 16

        # Check abilities
        assert "abilities" in char_data
        assert char_data["abilities"]["strength"] == 16
        assert char_data["abilities"]["dexterity"] == 14

        # Check inventory
        assert "inventory" in char_data
        assert "items" in char_data["inventory"]
        assert "equipped" in char_data["inventory"]
        assert "currency" in char_data["inventory"]

        # Check conditions
        assert "conditions" in char_data
        assert "inspired" in char_data["conditions"]

    def test_save_inventory_data(self, save_manager, sample_game_state):
        """Test that inventory data is correctly serialized."""
        save_path = save_manager.save_game(sample_game_state, "test_save")

        with open(save_path, 'r') as f:
            save_data = json.load(f)

        inv_data = save_data["party"][0]["inventory"]

        # Check items
        assert len(inv_data["items"]) == 3
        item_ids = [item["item_id"] for item in inv_data["items"]]
        assert "longsword" in item_ids
        assert "chainmail" in item_ids
        assert "potion_healing" in item_ids

        # Check equipped
        assert inv_data["equipped"]["weapon"] == "longsword"
        assert inv_data["equipped"]["armor"] == "chainmail"

        # Check currency
        assert inv_data["currency"]["gold"] == 50

    def test_load_game_restores_state(self, save_manager, sample_game_state):
        """Test that load_game correctly restores game state."""
        # Save the game
        save_manager.save_game(sample_game_state, "test_save")

        # Load the game
        loaded_state = save_manager.load_game("test_save")

        # Check party
        assert len(loaded_state.party.characters) == 2
        assert loaded_state.party.characters[0].name == "Test Hero"
        assert loaded_state.party.characters[1].name == "Test Companion"

        # Check dungeon
        assert loaded_state.dungeon_name == "goblin_warren"
        assert loaded_state.dungeon["name"] == "Goblin Warren"

        # Check action history
        assert loaded_state.action_history == ["Entered the dungeon", "Fought a goblin"]

    def test_load_game_restores_character(self, save_manager, sample_game_state):
        """Test that character data is correctly restored."""
        save_manager.save_game(sample_game_state, "test_save")
        loaded_state = save_manager.load_game("test_save")

        char = loaded_state.party.characters[0]

        assert char.name == "Test Hero"
        assert char.character_class == CharacterClass.FIGHTER
        assert char.level == 2
        assert char.race == "human"
        assert char.xp == 350
        assert char.max_hp == 20
        assert char.current_hp == 15
        assert char.ac == 16

        # Check abilities
        assert char.abilities.strength == 16
        assert char.abilities.dexterity == 14
        assert char.abilities.constitution == 15

        # Check conditions
        assert char.has_condition("inspired")

    def test_load_game_restores_inventory(self, save_manager, sample_game_state):
        """Test that inventory is correctly restored."""
        save_manager.save_game(sample_game_state, "test_save")
        loaded_state = save_manager.load_game("test_save")

        inv = loaded_state.party.characters[0].inventory

        # Check items
        assert inv.has_item("longsword")
        assert inv.has_item("chainmail")
        assert inv.has_item("potion_healing")
        assert inv.get_item_quantity("potion_healing") == 2

        # Check equipped
        assert inv.get_equipped_item(EquipmentSlot.WEAPON) == "longsword"
        assert inv.get_equipped_item(EquipmentSlot.ARMOR) == "chainmail"

        # Check currency
        assert inv.gold == 50

    def test_list_saves_empty(self, save_manager):
        """Test list_saves when no saves exist."""
        saves = save_manager.list_saves()
        assert saves == []

    def test_list_saves_returns_metadata(self, save_manager, sample_game_state):
        """Test that list_saves returns correct metadata."""
        save_manager.save_game(sample_game_state, "save1")
        save_manager.save_game(sample_game_state, "save2")

        saves = save_manager.list_saves()

        assert len(saves) == 2
        assert all("name" in save for save in saves)
        assert all("created" in save for save in saves)
        assert all("last_played" in save for save in saves)
        assert all("party_size" in save for save in saves)
        assert all("party_names" in save for save in saves)
        assert all("dungeon" in save for save in saves)

    def test_list_saves_sorted_by_last_played(self, save_manager, sample_game_state):
        """Test that list_saves returns saves sorted by last played."""
        # Create multiple saves
        save_manager.save_game(sample_game_state, "old_save")
        save_manager.save_game(sample_game_state, "new_save")

        # Load old_save to update its last_played
        import time
        time.sleep(0.1)  # Small delay to ensure different timestamps
        save_manager.load_game("old_save")

        saves = save_manager.list_saves()

        # old_save should be first (most recently played)
        assert saves[0]["name"] == "old_save"
        assert saves[1]["name"] == "new_save"

    def test_delete_save(self, save_manager, sample_game_state, temp_saves_dir):
        """Test deleting a save file."""
        save_manager.save_game(sample_game_state, "test_save")

        save_path = temp_saves_dir / "test_save.json"
        assert save_path.exists()

        result = save_manager.delete_save("test_save")
        assert result is True
        assert not save_path.exists()

    def test_delete_nonexistent_save(self, save_manager):
        """Test deleting a save that doesn't exist."""
        result = save_manager.delete_save("nonexistent")
        assert result is False

    def test_save_name_sanitization(self, save_manager, sample_game_state, temp_saves_dir):
        """Test that invalid characters in save names are sanitized."""
        save_path = save_manager.save_game(sample_game_state, "test/save:name")

        # Should replace invalid characters with underscores
        assert save_path.stem == "test_save_name"
        assert save_path.exists()

    def test_empty_save_name_raises_error(self, save_manager, sample_game_state):
        """Test that empty save name raises ValueError."""
        with pytest.raises(ValueError, match="Save name cannot be empty"):
            save_manager.save_game(sample_game_state, "")

    def test_load_nonexistent_save_raises_error(self, save_manager):
        """Test that loading nonexistent save raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            save_manager.load_game("nonexistent")

    def test_auto_save_flag(self, save_manager, sample_game_state):
        """Test that auto_save flag is correctly saved."""
        save_path = save_manager.save_game(sample_game_state, "manual_save", auto_save=False)

        with open(save_path, 'r') as f:
            save_data = json.load(f)

        assert save_data["metadata"]["auto_save"] is False

        save_path = save_manager.save_game(sample_game_state, "auto_save", auto_save=True)

        with open(save_path, 'r') as f:
            save_data = json.load(f)

        assert save_data["metadata"]["auto_save"] is True

    def test_overwrite_existing_save(self, save_manager, sample_game_state):
        """Test that saving with same name overwrites existing save."""
        # Save first version
        sample_game_state.party.characters[0].current_hp = 10
        save_manager.save_game(sample_game_state, "test_save")

        # Modify and save again
        sample_game_state.party.characters[0].current_hp = 5
        save_manager.save_game(sample_game_state, "test_save")

        # Load and check it has the new value
        loaded_state = save_manager.load_game("test_save")
        assert loaded_state.party.characters[0].current_hp == 5


class TestSaveValidation:
    """Test save file validation and error handling."""

    def test_load_corrupted_json(self, save_manager, temp_saves_dir):
        """Test loading a corrupted JSON file."""
        # Create a corrupted save file
        corrupt_file = temp_saves_dir / "corrupt.json"
        with open(corrupt_file, 'w') as f:
            f.write("{invalid json")

        with pytest.raises(ValueError, match="Corrupted save file"):
            save_manager.load_game("corrupt")

    def test_load_missing_required_keys(self, save_manager, temp_saves_dir):
        """Test loading save file missing required keys."""
        # Create invalid save file
        invalid_file = temp_saves_dir / "invalid.json"
        with open(invalid_file, 'w') as f:
            json.dump({"version": "1.0.0"}, f)

        with pytest.raises(ValueError, match="Invalid save file"):
            save_manager.load_game("invalid")

    def test_load_empty_party(self, save_manager, temp_saves_dir):
        """Test loading save file with empty party."""
        # Create save with empty party
        invalid_file = temp_saves_dir / "empty_party.json"
        save_data = {
            "version": SAVE_VERSION,
            "metadata": {"created": "2024-01-01", "last_played": "2024-01-01", "auto_save": False},
            "party": [],
            "game_state": {}
        }
        with open(invalid_file, 'w') as f:
            json.dump(save_data, f)

        with pytest.raises(ValueError, match="party cannot be empty"):
            save_manager.load_game("empty_party")

    def test_incompatible_version(self, save_manager, temp_saves_dir):
        """Test loading save with incompatible version."""
        # Create save with old version
        old_version_file = temp_saves_dir / "old_version.json"
        save_data = {
            "version": "0.0.1",
            "metadata": {"created": "2024-01-01", "last_played": "2024-01-01", "auto_save": False},
            "party": [
                {
                    "name": "Test",
                    "character_class": "fighter",
                    "level": 1,
                    "race": "human",
                    "xp": 0,
                    "max_hp": 10,
                    "current_hp": 10,
                    "ac": 10,
                    "abilities": {
                        "strength": 10,
                        "dexterity": 10,
                        "constitution": 10,
                        "intelligence": 10,
                        "wisdom": 10,
                        "charisma": 10
                    },
                    "inventory": {"items": [], "equipped": {"weapon": None, "armor": None}, "currency": {"gold": 0}},
                    "conditions": []
                }
            ],
            "game_state": {
                "dungeon_name": "goblin_warren",
                "current_room_id": "entrance",
                "dungeon_state": {},
                "in_combat": False,
                "action_history": []
            }
        }
        with open(old_version_file, 'w') as f:
            json.dump(save_data, f)

        with pytest.raises(ValueError, match="Incompatible save version"):
            save_manager.load_game("old_version")

    def test_list_saves_ignores_corrupted_files(self, save_manager, sample_game_state, temp_saves_dir):
        """Test that list_saves skips corrupted save files."""
        # Create a valid save
        save_manager.save_game(sample_game_state, "valid_save")

        # Create a corrupted save
        corrupt_file = temp_saves_dir / "corrupt.json"
        with open(corrupt_file, 'w') as f:
            f.write("{invalid json")

        # list_saves should only return the valid save
        saves = save_manager.list_saves()
        assert len(saves) == 1
        assert saves[0]["name"] == "valid_save"


class TestRoomStatePersistence:
    """Test that room state (searched, enemies) is correctly saved and loaded."""

    def test_save_searched_rooms(self, save_manager, sample_game_state):
        """Test that searched room state is saved."""
        # Mark current room as searched
        room = sample_game_state.get_current_room()
        room["searched"] = True

        # Save and load
        save_manager.save_game(sample_game_state, "test_save")
        loaded_state = save_manager.load_game("test_save")

        # Check that room is still marked as searched
        loaded_room = loaded_state.get_current_room()
        assert loaded_room.get("searched") is True

    def test_save_cleared_enemies(self, save_manager, sample_game_state):
        """Test that cleared enemy rooms are saved."""
        # Clear enemies from a room
        room = sample_game_state.get_current_room()
        original_enemies = room.get("enemies", []).copy()
        room["enemies"] = []

        # Save and load
        save_manager.save_game(sample_game_state, "test_save")
        loaded_state = save_manager.load_game("test_save")

        # Check that room has no enemies
        loaded_room = loaded_state.get_current_room()
        assert loaded_room.get("enemies", []) == []
