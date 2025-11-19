# Unit tests for CharacterVaultV2

import pytest
import json
import tempfile
from pathlib import Path

from dnd_engine.core.character_vault_v2 import CharacterVaultV2
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities


@pytest.fixture
def temp_vault_path():
    """Create a temporary path for vault file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "character_vault.json"


@pytest.fixture
def vault(temp_vault_path):
    """Create a CharacterVaultV2 with temporary file."""
    return CharacterVaultV2(vault_path=temp_vault_path)


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
        name="Test Warrior",
        character_class=CharacterClass.FIGHTER,
        level=5,
        abilities=abilities,
        max_hp=45,
        ac=18,
        current_hp=45,
        xp=6500,
        race="Dwarf"
    )


class TestCharacterVaultV2:
    """Test CharacterVaultV2 functionality."""

    def test_initialization_creates_vault_file(self, temp_vault_path, vault):
        """Test that initialization creates vault file with proper structure."""
        assert temp_vault_path.exists()

        with open(temp_vault_path, 'r') as f:
            data = json.load(f)

        assert "version" in data
        assert "created_at" in data
        assert "characters" in data
        assert isinstance(data["characters"], dict)
        assert len(data["characters"]) == 0

    def test_add_character_generates_uuid(self, vault, sample_character):
        """Test adding a character generates a UUID."""
        char_id = vault.add_character(sample_character)

        assert char_id is not None
        assert len(char_id) == 36  # UUID format

    def test_add_character_with_custom_id(self, vault, sample_character):
        """Test adding a character with a custom UUID."""
        custom_id = "12345678-1234-1234-1234-123456789abc"

        char_id = vault.add_character(sample_character, character_id=custom_id)

        assert char_id == custom_id

    def test_add_character_invalid_uuid_raises_error(self, vault, sample_character):
        """Test that invalid UUID raises ValueError."""
        with pytest.raises(ValueError, match="Invalid character ID"):
            vault.add_character(sample_character, character_id="not-a-uuid")

    def test_add_character_duplicate_id_raises_error(self, vault, sample_character):
        """Test that adding duplicate ID raises ValueError."""
        char_id = vault.add_character(sample_character)

        with pytest.raises(ValueError, match="Character ID already exists"):
            vault.add_character(sample_character, character_id=char_id)

    def test_get_character_returns_correct_character(self, vault, sample_character):
        """Test retrieving a character from vault."""
        char_id = vault.add_character(sample_character)

        retrieved = vault.get_character(char_id)

        assert retrieved.name == sample_character.name
        assert retrieved.character_class == sample_character.character_class
        assert retrieved.level == sample_character.level
        assert retrieved.max_hp == sample_character.max_hp
        assert retrieved.race == sample_character.race

    def test_get_character_not_found_raises_error(self, vault):
        """Test that getting non-existent character raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Character not found"):
            vault.get_character("00000000-0000-0000-0000-000000000000")

    def test_update_character_preserves_usage_stats(self, vault, sample_character):
        """Test that updating a character preserves usage statistics."""
        # Add character
        char_id = vault.add_character(sample_character)

        # Record some usage
        vault.record_usage(char_id, slot_number=1)
        vault.record_usage(char_id, slot_number=2)

        # Update character
        sample_character.level = 10
        sample_character.current_hp = 80
        vault.update_character(char_id, sample_character)

        # Get character info
        chars = vault.list_characters()
        char_info = [c for c in chars if c["id"] == char_id][0]

        # Verify character was updated
        retrieved = vault.get_character(char_id)
        assert retrieved.level == 10
        assert retrieved.current_hp == 80

        # Verify usage stats preserved
        assert char_info["times_used"] == 2
        assert set(char_info["save_slots_used"]) == {1, 2}

    def test_record_usage_updates_statistics(self, vault, sample_character):
        """Test that recording usage updates statistics correctly."""
        char_id = vault.add_character(sample_character)

        # Initial state
        chars = vault.list_characters()
        char_info = chars[0]
        assert char_info["times_used"] == 0
        assert char_info["last_used"] is None
        assert char_info["save_slots_used"] == []

        # Record usage
        vault.record_usage(char_id, slot_number=3)

        chars = vault.list_characters()
        char_info = chars[0]
        assert char_info["times_used"] == 1
        assert char_info["last_used"] is not None
        assert char_info["save_slots_used"] == [3]

        # Record more usage
        vault.record_usage(char_id, slot_number=5)
        vault.record_usage(char_id, slot_number=3)  # Duplicate slot

        chars = vault.list_characters()
        char_info = chars[0]
        assert char_info["times_used"] == 3
        assert set(char_info["save_slots_used"]) == {3, 5}  # No duplicates

    def test_list_characters_returns_all(self, vault):
        """Test that list_characters returns all characters."""
        # Add multiple characters
        char1 = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(16, 12, 14, 8, 10, 10),
            max_hp=12,
            ac=16,
            current_hp=12,
            xp=0,
            race="Human"
        )

        char2 = Character(
            name="Wizard",
            character_class=CharacterClass.WIZARD,
            level=2,
            abilities=Abilities(8, 14, 12, 16, 13, 10),
            max_hp=14,
            ac=12,
            current_hp=14,
            xp=300,
            race="Elf"
        )

        vault.add_character(char1)
        vault.add_character(char2)

        chars = vault.list_characters()

        assert len(chars) == 2
        names = {c["name"] for c in chars}
        assert names == {"Fighter", "Wizard"}

    def test_list_characters_sorting(self, vault):
        """Test that list_characters sorts by usage."""
        # Add characters
        id1 = vault.add_character(Character(
            name="Old", character_class=CharacterClass.FIGHTER,
            level=1, abilities=Abilities(10, 10, 10, 10, 10, 10),
            max_hp=10, ac=10, current_hp=10, xp=0, race="Human"
        ))

        id2 = vault.add_character(Character(
            name="Recent", character_class=CharacterClass.WIZARD,
            level=1, abilities=Abilities(10, 10, 10, 10, 10, 10),
            max_hp=8, ac=10, current_hp=8, xp=0, race="Elf"
        ))

        # Record usage for second character
        vault.record_usage(id2, slot_number=1)

        chars = vault.list_characters()

        # Character with recent usage should be first
        assert chars[0]["name"] == "Recent"
        assert chars[1]["name"] == "Old"

    def test_delete_character(self, vault, sample_character):
        """Test deleting a character from vault."""
        char_id = vault.add_character(sample_character)

        # Verify exists
        chars = vault.list_characters()
        assert len(chars) == 1

        # Delete
        result = vault.delete_character(char_id)
        assert result is True

        # Verify deleted
        chars = vault.list_characters()
        assert len(chars) == 0

        # Delete non-existent
        result = vault.delete_character(char_id)
        assert result is False

    def test_clone_character(self, vault, sample_character):
        """Test cloning a character."""
        original_id = vault.add_character(sample_character)

        # Clone with new name
        clone_id = vault.clone_character(original_id, new_name="Cloned Warrior")

        assert clone_id != original_id

        # Verify both exist
        chars = vault.list_characters()
        assert len(chars) == 2

        # Verify clone has new name
        cloned = vault.get_character(clone_id)
        assert cloned.name == "Cloned Warrior"
        assert cloned.level == sample_character.level

    def test_clone_character_default_name(self, vault, sample_character):
        """Test cloning without custom name uses 'Copy of' prefix."""
        original_id = vault.add_character(sample_character)

        clone_id = vault.clone_character(original_id)

        cloned = vault.get_character(clone_id)
        assert cloned.name == f"Copy of {sample_character.name}"

    def test_import_characters_bulk(self, vault):
        """Test bulk import of characters."""
        chars = [
            Character(
                name=f"Hero {i}",
                character_class=CharacterClass.FIGHTER,
                level=i,
                abilities=Abilities(10 + i, 10, 10, 10, 10, 10),
                max_hp=10 + i,
                ac=10,
                current_hp=10 + i,
                xp=0,
                race="Human"
            )
            for i in range(1, 4)
        ]

        char_ids = vault.import_characters_bulk(chars)

        assert len(char_ids) == 3
        assert len(set(char_ids)) == 3  # All unique

        listed = vault.list_characters()
        assert len(listed) == 3

    def test_get_usage_stats(self, vault, sample_character):
        """Test getting overall vault usage statistics."""
        # Empty vault
        stats = vault.get_usage_stats()
        assert stats["total_characters"] == 0
        assert stats["total_uses"] == 0
        assert stats["most_used_character"] is None

        # Add characters and record usage
        id1 = vault.add_character(sample_character)

        char2 = Character(
            name="Popular Hero",
            character_class=CharacterClass.WIZARD,
            level=1,
            abilities=Abilities(10, 10, 10, 16, 10, 10),
            max_hp=8,
            ac=10,
            current_hp=8,
            xp=0,
            race="Elf"
        )
        id2 = vault.add_character(char2)

        # Record usage
        vault.record_usage(id1, 1)
        vault.record_usage(id2, 2)
        vault.record_usage(id2, 3)
        vault.record_usage(id2, 4)

        stats = vault.get_usage_stats()
        assert stats["total_characters"] == 2
        assert stats["total_uses"] == 4
        assert stats["most_used_character"] == "Popular Hero"
        assert stats["most_used_count"] == 3

    def test_vault_persistence(self, temp_vault_path, sample_character):
        """Test that vault data persists across instances."""
        # Create first vault instance and add character
        vault1 = CharacterVaultV2(vault_path=temp_vault_path)
        char_id = vault1.add_character(sample_character)
        vault1.record_usage(char_id, slot_number=1)

        # Create second vault instance (simulating reload)
        vault2 = CharacterVaultV2(vault_path=temp_vault_path)

        # Verify character is still there
        chars = vault2.list_characters()
        assert len(chars) == 1
        assert chars[0]["name"] == sample_character.name
        assert chars[0]["times_used"] == 1

        # Verify can load character
        retrieved = vault2.get_character(char_id)
        assert retrieved.name == sample_character.name
