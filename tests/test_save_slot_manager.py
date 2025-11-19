# Unit tests for SaveSlotManager

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

from dnd_engine.core.save_slot_manager import SaveSlotManager
from dnd_engine.core.save_slot import SaveSlot
from dnd_engine.core.party import Party
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.rules.loader import DataLoader


@pytest.fixture
def temp_saves_dir():
    """Create a temporary directory for saves."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "saves"


@pytest.fixture
def save_manager(temp_saves_dir):
    """Create a SaveSlotManager with temporary directory."""
    return SaveSlotManager(saves_dir=temp_saves_dir)


@pytest.fixture
def sample_character():
    """Create a sample character for testing."""
    abilities = Abilities(
        strength=16,
        dexterity=14,
        constitution=15,
        intelligence=8,
        wisdom=10,
        charisma=12
    )

    return Character(
        name="Test Hero",
        character_class=CharacterClass.FIGHTER,
        level=3,
        abilities=abilities,
        max_hp=30,
        ac=16,
        current_hp=25,
        xp=900,
        race="Human"
    )


@pytest.fixture
def sample_game_state(sample_character):
    """Create a sample game state for testing."""
    party = Party([sample_character])
    data_loader = DataLoader()

    game_state = GameState(
        party=party,
        dungeon_name="test_dungeon",
        data_loader=data_loader
    )

    return game_state


class TestSaveSlotManager:
    """Test SaveSlotManager functionality."""

    def test_initialization_creates_10_slots(self, save_manager, temp_saves_dir):
        """Test that initialization creates all 10 slot files."""
        # Check that directory exists
        assert temp_saves_dir.exists()

        # Check that all 10 slot files exist
        for i in range(1, 11):
            slot_path = temp_saves_dir / f"slot_{i:02d}.json"
            assert slot_path.exists()

    def test_list_slots_returns_10_slots(self, save_manager):
        """Test that list_slots returns exactly 10 slots."""
        slots = save_manager.list_slots()

        assert len(slots) == 10
        assert all(isinstance(slot, SaveSlot) for slot in slots)
        assert [slot.slot_number for slot in slots] == list(range(1, 11))

    def test_get_slot_valid_range(self, save_manager):
        """Test getting slots in valid range."""
        for i in range(1, 11):
            slot = save_manager.get_slot(i)
            assert slot.slot_number == i
            assert slot.is_empty()  # Initially empty

    def test_get_slot_invalid_range(self, save_manager):
        """Test that invalid slot numbers raise ValueError."""
        with pytest.raises(ValueError, match="Slot number must be between 1 and 10"):
            save_manager.get_slot(0)

        with pytest.raises(ValueError, match="Slot number must be between 1 and 10"):
            save_manager.get_slot(11)

        with pytest.raises(ValueError, match="Slot number must be between 1 and 10"):
            save_manager.get_slot(-1)

    def test_save_game_creates_slot_file(self, save_manager, sample_game_state, temp_saves_dir):
        """Test that saving a game creates/updates a slot file."""
        slot_path = save_manager.save_game(
            slot_number=1,
            game_state=sample_game_state,
            playtime_delta=120
        )

        assert slot_path.exists()
        assert slot_path == temp_saves_dir / "slot_01.json"

        # Verify slot is no longer empty
        slot = save_manager.get_slot(1)
        assert not slot.is_empty()
        assert slot.playtime_seconds == 120
        assert slot.adventure_name == "Test Dungeon"  # Converted from test_dungeon

    def test_save_game_updates_metadata(self, save_manager, sample_game_state):
        """Test that saving updates slot metadata correctly."""
        save_manager.save_game(
            slot_number=2,
            game_state=sample_game_state,
            playtime_delta=300
        )

        slot = save_manager.get_slot(2)

        assert slot.adventure_name == "Test Dungeon"
        assert slot.party_composition == ["Test Hero"]
        assert slot.party_levels == [3]
        assert slot.playtime_seconds == 300

    def test_save_game_accumulates_playtime(self, save_manager, sample_game_state):
        """Test that multiple saves accumulate playtime."""
        # First save
        save_manager.save_game(slot_number=3, game_state=sample_game_state, playtime_delta=100)
        slot = save_manager.get_slot(3)
        assert slot.playtime_seconds == 100

        # Second save
        save_manager.save_game(slot_number=3, game_state=sample_game_state, playtime_delta=200)
        slot = save_manager.get_slot(3)
        assert slot.playtime_seconds == 300  # 100 + 200

        # Third save
        save_manager.save_game(slot_number=3, game_state=sample_game_state, playtime_delta=150)
        slot = save_manager.get_slot(3)
        assert slot.playtime_seconds == 450  # 100 + 200 + 150

    def test_load_game_from_saved_slot(self, save_manager, sample_game_state):
        """Test loading a game from a saved slot."""
        # Save first
        save_manager.save_game(
            slot_number=4,
            game_state=sample_game_state,
            playtime_delta=60
        )

        # Load
        loaded_state = save_manager.load_game(slot_number=4)

        assert loaded_state is not None
        assert len(loaded_state.party.characters) == 1
        assert loaded_state.party.characters[0].name == "Test Hero"
        assert loaded_state.party.characters[0].level == 3
        assert loaded_state.party.characters[0].current_hp == 25
        assert loaded_state.dungeon_name == "test_dungeon"

    def test_load_game_from_empty_slot_raises_error(self, save_manager):
        """Test that loading from empty slot raises ValueError."""
        with pytest.raises(ValueError, match="Slot 5 is empty"):
            save_manager.load_game(slot_number=5)

    def test_clear_slot(self, save_manager, sample_game_state):
        """Test clearing a slot resets it to empty."""
        # Save first
        save_manager.save_game(
            slot_number=6,
            game_state=sample_game_state,
            playtime_delta=100
        )

        slot = save_manager.get_slot(6)
        assert not slot.is_empty()

        # Clear
        save_manager.clear_slot(6)

        slot = save_manager.get_slot(6)
        assert slot.is_empty()
        assert slot.adventure_name is None
        assert slot.party_composition == []
        assert slot.playtime_seconds == 0

    def test_rename_slot(self, save_manager, sample_game_state):
        """Test renaming a slot with custom name."""
        # Save first
        save_manager.save_game(
            slot_number=7,
            game_state=sample_game_state,
            playtime_delta=50
        )

        # Rename
        save_manager.rename_slot(7, "My Epic Quest")

        slot = save_manager.get_slot(7)
        assert slot.custom_name == "My Epic Quest"
        assert slot.get_display_name() == "My Epic Quest"

        # Clear custom name
        save_manager.rename_slot(7, "")

        slot = save_manager.get_slot(7)
        assert slot.custom_name is None
        assert "Test Dungeon" in slot.get_display_name()

    def test_slot_file_format(self, save_manager, sample_game_state, temp_saves_dir):
        """Test that slot files have correct JSON structure."""
        save_manager.save_game(
            slot_number=8,
            game_state=sample_game_state,
            playtime_delta=75
        )

        slot_path = temp_saves_dir / "slot_08.json"

        with open(slot_path, 'r') as f:
            data = json.load(f)

        # Check required top-level keys
        assert "version" in data
        assert "metadata" in data
        assert "party" in data
        assert "game_state" in data

        # Check metadata
        assert data["metadata"]["slot_number"] == 8
        assert data["metadata"]["adventure_name"] == "Test Dungeon"
        assert data["metadata"]["playtime_seconds"] == 75

        # Check party
        assert isinstance(data["party"], list)
        assert len(data["party"]) == 1
        assert data["party"][0]["name"] == "Test Hero"

        # Check game state
        assert data["game_state"]["dungeon_name"] == "test_dungeon"

    def test_corrupted_slot_treated_as_empty(self, save_manager, temp_saves_dir):
        """Test that corrupted slot files are treated as empty."""
        # Create a corrupted slot file
        slot_path = temp_saves_dir / "slot_09.json"
        with open(slot_path, 'w') as f:
            f.write("{ invalid json }")

        # Should return empty slot instead of crashing
        slot = save_manager.get_slot(9)
        assert slot.is_empty()
        assert slot.slot_number == 9

    def test_multiple_characters_in_party(self, save_manager, sample_character):
        """Test saving and loading with multiple characters."""
        char2 = Character(
            name="Wizard Friend",
            character_class=CharacterClass.WIZARD,
            level=3,
            abilities=Abilities(8, 14, 12, 16, 13, 10),
            max_hp=18,
            ac=12,
            current_hp=18,
            xp=900,
            race="Elf"
        )

        party = Party([sample_character, char2])
        data_loader = DataLoader()
        game_state = GameState(
            party=party,
            dungeon_name="multi_char_dungeon",
            data_loader=data_loader
        )

        # Save
        save_manager.save_game(
            slot_number=10,
            game_state=game_state,
            playtime_delta=200
        )

        # Check metadata
        slot = save_manager.get_slot(10)
        assert slot.party_composition == ["Test Hero", "Wizard Friend"]
        assert slot.party_levels == [3, 3]

        # Load
        loaded_state = save_manager.load_game(slot_number=10)
        assert len(loaded_state.party.characters) == 2
        assert loaded_state.party.characters[0].name == "Test Hero"
        assert loaded_state.party.characters[1].name == "Wizard Friend"

    def test_adventure_name_conversion(self, save_manager):
        """Test that dungeon filenames are converted to display names."""
        test_cases = [
            ("tomb_of_horrors", "Tomb Of Horrors"),
            ("lost_mine_of_phandelver", "Lost Mine Of Phandelver"),
            ("simple", "Simple"),
            ("multi_word_dungeon_name", "Multi Word Dungeon Name"),
        ]

        for filename, expected in test_cases:
            result = save_manager._get_adventure_display_name(filename)
            assert result == expected
