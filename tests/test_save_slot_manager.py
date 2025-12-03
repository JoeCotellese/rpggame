# Unit tests for SaveSlotManager

import json
import tempfile
from pathlib import Path

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.save_slot import SaveSlot
from dnd_engine.core.save_slot_manager import SaveSlotManager
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
        strength=16, dexterity=14, constitution=15, intelligence=8, wisdom=10, charisma=12
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
        race="Human",
    )


@pytest.fixture
def sample_game_state(sample_character):
    """Create a sample game state for testing."""
    party = Party([sample_character])
    data_loader = DataLoader()

    game_state = GameState(party=party, dungeon_name="test_dungeon", data_loader=data_loader)

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
            slot_number=1, game_state=sample_game_state, playtime_delta=120
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
        save_manager.save_game(slot_number=2, game_state=sample_game_state, playtime_delta=300)

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
        save_manager.save_game(slot_number=4, game_state=sample_game_state, playtime_delta=60)

        # Load - now returns tuple of (game_state, campaign_progress)
        loaded_state, campaign_progress = save_manager.load_game(slot_number=4)

        assert loaded_state is not None
        assert len(loaded_state.party.characters) == 1
        assert loaded_state.party.characters[0].name == "Test Hero"
        assert loaded_state.party.characters[0].level == 3
        assert loaded_state.party.characters[0].current_hp == 25
        assert loaded_state.dungeon_name == "test_dungeon"
        # No campaign progress saved, so should be None
        assert campaign_progress is None

    def test_load_game_from_empty_slot_raises_error(self, save_manager):
        """Test that loading from empty slot raises ValueError."""
        with pytest.raises(ValueError, match="Slot 5 is empty"):
            save_manager.load_game(slot_number=5)

    def test_clear_slot(self, save_manager, sample_game_state):
        """Test clearing a slot resets it to empty."""
        # Save first
        save_manager.save_game(slot_number=6, game_state=sample_game_state, playtime_delta=100)

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
        save_manager.save_game(slot_number=7, game_state=sample_game_state, playtime_delta=50)

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
        save_manager.save_game(slot_number=8, game_state=sample_game_state, playtime_delta=75)

        slot_path = temp_saves_dir / "slot_08.json"

        with open(slot_path) as f:
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
        with open(slot_path, "w") as f:
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
            race="Elf",
        )

        party = Party([sample_character, char2])
        data_loader = DataLoader()
        game_state = GameState(
            party=party, dungeon_name="multi_char_dungeon", data_loader=data_loader
        )

        # Save
        save_manager.save_game(slot_number=10, game_state=game_state, playtime_delta=200)

        # Check metadata
        slot = save_manager.get_slot(10)
        assert slot.party_composition == ["Test Hero", "Wizard Friend"]
        assert slot.party_levels == [3, 3]

        # Load - returns tuple of (game_state, campaign_progress)
        loaded_state, _ = save_manager.load_game(slot_number=10)
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


class TestVaultSync:
    """Test vault sync functionality during save_game()."""

    @pytest.fixture
    def temp_vault_path(self, temp_saves_dir):
        """Create a temporary path for vault file alongside saves."""
        return temp_saves_dir.parent / "character_vault.json"

    @pytest.fixture
    def vault(self, temp_vault_path):
        """Create a CharacterVaultV2 with temporary file."""
        from dnd_engine.core.character_vault_v2 import CharacterVaultV2

        return CharacterVaultV2(vault_path=temp_vault_path)

    def test_save_game_syncs_characters_with_vault_id(self, save_manager, vault, sample_character):
        """Test that save_game syncs characters with vault_id to the vault."""
        # Add character to vault and get the vault_id
        char_id = vault.add_character(sample_character)
        retrieved = vault.get_character(char_id)

        # Create game state with the vault-linked character
        party = Party([retrieved])
        data_loader = DataLoader()
        game_state = GameState(party=party, dungeon_name="test_dungeon", data_loader=data_loader)

        # Modify character in game
        game_state.party.characters[0].level = 10
        game_state.party.characters[0].xp = 50000

        # Save with vault sync
        save_manager.save_game(slot_number=1, game_state=game_state, character_vault=vault)

        # Verify vault was updated
        vault_char = vault.get_character(char_id)
        assert vault_char.level == 10
        assert vault_char.xp == 50000

    def test_save_game_without_vault_skips_sync(self, save_manager, sample_character):
        """Test that save_game works without vault (no sync)."""
        party = Party([sample_character])
        data_loader = DataLoader()
        game_state = GameState(party=party, dungeon_name="test_dungeon", data_loader=data_loader)

        # Save without vault - should not raise
        slot_path = save_manager.save_game(slot_number=2, game_state=game_state)

        assert slot_path.exists()

    def test_save_game_ignores_characters_without_vault_id(
        self, save_manager, vault, sample_character
    ):
        """Test that characters without vault_id are not synced."""
        # Add one character to vault
        char_id = vault.add_character(sample_character)
        vault_char = vault.get_character(char_id)

        # Create a new character not in vault
        new_char = Character(
            name="New Hero",
            character_class=CharacterClass.ROGUE,
            level=5,
            abilities=Abilities(10, 18, 12, 14, 10, 12),
            max_hp=35,
            ac=15,
            current_hp=35,
            xp=6500,
            race="Halfling",
        )

        # Create party with both
        party = Party([vault_char, new_char])
        data_loader = DataLoader()
        game_state = GameState(party=party, dungeon_name="test_dungeon", data_loader=data_loader)

        # Save with vault sync
        save_manager.save_game(slot_number=3, game_state=game_state, character_vault=vault)

        # Vault should still only have one character
        chars = vault.list_characters()
        assert len(chars) == 1

    def test_save_game_handles_deleted_vault_character(self, save_manager, vault, sample_character):
        """Test that sync handles characters deleted from vault gracefully."""
        # Add and get character with vault_id
        char_id = vault.add_character(sample_character)
        retrieved = vault.get_character(char_id)

        # Create game state
        party = Party([retrieved])
        data_loader = DataLoader()
        game_state = GameState(party=party, dungeon_name="test_dungeon", data_loader=data_loader)

        # Delete character from vault
        vault.delete_character(char_id)

        # Save should not raise error even though vault char is deleted
        save_manager.save_game(slot_number=4, game_state=game_state, character_vault=vault)

        # Slot should still be saved
        slot = save_manager.get_slot(4)
        assert not slot.is_empty()

    def test_save_game_syncs_inventory_changes(self, save_manager, vault, sample_character):
        """Test that inventory changes are synced to vault."""
        char_id = vault.add_character(sample_character)
        retrieved = vault.get_character(char_id)

        party = Party([retrieved])
        data_loader = DataLoader()
        game_state = GameState(party=party, dungeon_name="test_dungeon", data_loader=data_loader)

        # Add items to character's inventory
        game_state.party.characters[0].inventory.add_item("longsword", "weapons", 1)
        game_state.party.characters[0].inventory.add_gold(500)

        save_manager.save_game(slot_number=5, game_state=game_state, character_vault=vault)

        # Verify vault character has the items
        vault_char = vault.get_character(char_id)
        assert vault_char.inventory.has_item("longsword")
        assert vault_char.inventory.gold == 500


class TestProficiencySerialization:
    """Test that character proficiencies are correctly saved and loaded."""

    @pytest.fixture
    def character_with_proficiencies(self):
        """Create a character with full proficiency data."""
        abilities = Abilities(
            strength=17, dexterity=16, constitution=15, intelligence=13, wisdom=14, charisma=12
        )

        char = Character(
            name="Larry the Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16,
            current_hp=12,
            xp=0,
            race="Human",
            weapon_proficiencies=["simple", "martial"],
            armor_proficiencies=["light", "medium", "heavy", "shields"],
            skill_proficiencies=["athletics", "perception"],
            expertise_skills=[],
            saving_throw_proficiencies=["strength", "constitution"],
        )
        char.darkvision_range = 60
        return char

    def test_serialize_character_includes_proficiencies(
        self, save_manager, character_with_proficiencies
    ):
        """Test that _serialize_character includes all proficiency fields."""
        serialized = save_manager._serialize_character(character_with_proficiencies)

        assert serialized["weapon_proficiencies"] == ["simple", "martial"]
        assert serialized["armor_proficiencies"] == ["light", "medium", "heavy", "shields"]
        assert serialized["skill_proficiencies"] == ["athletics", "perception"]
        assert serialized["expertise_skills"] == []
        assert serialized["saving_throw_proficiencies"] == ["strength", "constitution"]
        assert serialized["darkvision_range"] == 60

    def test_deserialize_character_restores_proficiencies(
        self, save_manager, character_with_proficiencies
    ):
        """Test that _deserialize_character restores all proficiency fields."""
        serialized = save_manager._serialize_character(character_with_proficiencies)
        deserialized = save_manager._deserialize_character(serialized)

        assert deserialized.weapon_proficiencies == ["simple", "martial"]
        assert deserialized.armor_proficiencies == ["light", "medium", "heavy", "shields"]
        assert deserialized.skill_proficiencies == ["athletics", "perception"]
        assert deserialized.expertise_skills == []
        assert deserialized.saving_throw_proficiencies == ["strength", "constitution"]
        assert deserialized.darkvision_range == 60

    def test_save_and_load_preserves_proficiencies(
        self, save_manager, character_with_proficiencies
    ):
        """Test full save/load cycle preserves proficiencies."""
        party = Party([character_with_proficiencies])
        data_loader = DataLoader()
        game_state = GameState(party=party, dungeon_name="test_dungeon", data_loader=data_loader)

        # Save
        save_manager.save_game(slot_number=1, game_state=game_state)

        # Load
        loaded_state, _ = save_manager.load_game(slot_number=1)
        loaded_char = loaded_state.party.characters[0]

        # Verify all proficiencies preserved
        assert loaded_char.weapon_proficiencies == ["simple", "martial"]
        assert loaded_char.armor_proficiencies == ["light", "medium", "heavy", "shields"]
        assert loaded_char.skill_proficiencies == ["athletics", "perception"]
        assert loaded_char.expertise_skills == []
        assert loaded_char.saving_throw_proficiencies == ["strength", "constitution"]
        assert loaded_char.darkvision_range == 60

    def test_deserialize_handles_missing_proficiencies_gracefully(self, save_manager):
        """Test that loading old saves without proficiencies uses defaults."""
        # Simulate an old save format without proficiency fields
        old_format_char = {
            "name": "Old Character",
            "character_class": "fighter",
            "level": 1,
            "race": "Human",
            "subclass": None,
            "xp": 0,
            "max_hp": 10,
            "current_hp": 10,
            "ac": 16,
            "abilities": {
                "strength": 15,
                "dexterity": 14,
                "constitution": 13,
                "intelligence": 12,
                "wisdom": 10,
                "charisma": 8,
            },
            "inventory": {
                "items": [],
                "equipped": {"weapon": None, "armor": None},
                "currency": {"gold": 0, "silver": 0, "copper": 0, "electrum": 0, "platinum": 0},
            },
            "conditions": [],
            "resource_pools": [],
            "spellcasting_ability": None,
            "known_spells": [],
            "prepared_spells": [],
            "vault_id": None,
            # Note: No proficiency fields - simulating old save format
        }

        deserialized = save_manager._deserialize_character(old_format_char)

        # Should have empty defaults, not crash
        assert deserialized.weapon_proficiencies == []
        assert deserialized.armor_proficiencies == []
        assert deserialized.skill_proficiencies == []
        assert deserialized.expertise_skills == []
        assert deserialized.saving_throw_proficiencies == []
        assert deserialized.darkvision_range == 0

    def test_rogue_expertise_skills_preserved(self, save_manager):
        """Test that Rogue expertise skills are correctly saved and loaded."""
        abilities = Abilities(10, 18, 12, 14, 10, 12)
        rogue = Character(
            name="Sneaky Pete",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=14,
            race="Halfling",
            weapon_proficiencies=["simple"],
            armor_proficiencies=["light"],
            skill_proficiencies=["stealth", "sleight_of_hand", "acrobatics", "perception"],
            expertise_skills=["stealth", "sleight_of_hand"],
            saving_throw_proficiencies=["dexterity", "intelligence"],
        )

        party = Party([rogue])
        data_loader = DataLoader()
        game_state = GameState(party=party, dungeon_name="test_dungeon", data_loader=data_loader)

        save_manager.save_game(slot_number=2, game_state=game_state)
        loaded_state, _ = save_manager.load_game(slot_number=2)
        loaded_rogue = loaded_state.party.characters[0]

        assert loaded_rogue.expertise_skills == ["stealth", "sleight_of_hand"]
        assert loaded_rogue.skill_proficiencies == [
            "stealth",
            "sleight_of_hand",
            "acrobatics",
            "perception",
        ]

    def test_slot_file_contains_proficiencies(
        self, save_manager, character_with_proficiencies, temp_saves_dir
    ):
        """Test that the JSON save file contains proficiency data."""
        party = Party([character_with_proficiencies])
        data_loader = DataLoader()
        game_state = GameState(party=party, dungeon_name="test_dungeon", data_loader=data_loader)

        save_manager.save_game(slot_number=3, game_state=game_state)

        # Read the raw JSON file
        slot_path = temp_saves_dir / "slot_03.json"
        with open(slot_path) as f:
            data = json.load(f)

        char_data = data["party"][0]
        assert char_data["weapon_proficiencies"] == ["simple", "martial"]
        assert char_data["armor_proficiencies"] == ["light", "medium", "heavy", "shields"]
        assert char_data["skill_proficiencies"] == ["athletics", "perception"]
        assert char_data["saving_throw_proficiencies"] == ["strength", "constitution"]
        assert char_data["darkvision_range"] == 60
