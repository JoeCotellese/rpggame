# ABOUTME: Unit tests for CharacterVault class
# ABOUTME: Tests character storage, retrieval, import/export, cloning, and state management

import json
import uuid
from pathlib import Path
from datetime import datetime
import pytest

from dnd_engine.core.character_vault import CharacterVault, CharacterState, VAULT_VERSION
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.systems.inventory import Inventory, EquipmentSlot
from dnd_engine.systems.currency import Currency
from dnd_engine.systems.resources import ResourcePool


@pytest.fixture
def temp_vault_dir(tmp_path):
    """Create a temporary vault directory"""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    return vault_dir


@pytest.fixture
def vault(temp_vault_dir):
    """Create a CharacterVault instance"""
    return CharacterVault(vault_dir=temp_vault_dir)


@pytest.fixture
def sample_character():
    """Create a sample character for testing"""
    abilities = Abilities(
        strength=16,
        dexterity=14,
        constitution=15,
        intelligence=10,
        wisdom=12,
        charisma=8
    )

    inventory = Inventory()
    inventory.currency.gold = 50

    character = Character(
        name="Test Fighter",
        character_class=CharacterClass.FIGHTER,
        level=3,
        abilities=abilities,
        max_hp=28,
        ac=16,
        current_hp=28,
        xp=900,
        inventory=inventory,
        race="human",
        subclass="champion",
        saving_throw_proficiencies=["str", "con"],
        skill_proficiencies=["athletics", "intimidation"],
        weapon_proficiencies=["simple", "martial"],
        armor_proficiencies=["light", "medium", "heavy", "shields"]
    )

    # Add a resource pool
    pool = ResourcePool(name="Second Wind", current=1, maximum=1, recovery_type="short")
    character.add_resource_pool(pool)

    return character


class TestCharacterVaultInit:
    """Test CharacterVault initialization"""

    def test_init_with_custom_dir(self, temp_vault_dir):
        """Test initialization with custom directory"""
        vault = CharacterVault(vault_dir=temp_vault_dir)
        assert vault.vault_dir == temp_vault_dir
        assert vault.vault_dir.exists()

    def test_init_creates_directory(self, tmp_path):
        """Test that initialization creates the vault directory"""
        vault_dir = tmp_path / "new_vault"
        assert not vault_dir.exists()

        vault = CharacterVault(vault_dir=vault_dir)
        assert vault_dir.exists()

    def test_init_with_default_dir(self, monkeypatch, tmp_path):
        """Test initialization with default directory"""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        vault = CharacterVault()
        expected_dir = tmp_path / ".dnd_terminal" / "characters" / "vault"
        assert vault.vault_dir == expected_dir
        assert vault.vault_dir.exists()


class TestSaveCharacter:
    """Test saving characters to the vault"""

    def test_save_character_generates_uuid(self, vault, sample_character):
        """Test that saving a character generates a valid UUID"""
        character_id = vault.save_character(sample_character)

        # Should be a valid UUID
        assert uuid.UUID(character_id)

        # File should exist
        character_file = vault.vault_dir / f"{character_id}.json"
        assert character_file.exists()

    def test_save_character_with_custom_id(self, vault, sample_character):
        """Test saving a character with a custom UUID"""
        custom_id = str(uuid.uuid4())
        character_id = vault.save_character(sample_character, character_id=custom_id)

        assert character_id == custom_id

        character_file = vault.vault_dir / f"{custom_id}.json"
        assert character_file.exists()

    def test_save_character_invalid_uuid(self, vault, sample_character):
        """Test that saving with invalid UUID raises error"""
        with pytest.raises(ValueError, match="Invalid character ID"):
            vault.save_character(sample_character, character_id="not-a-uuid")

    def test_save_character_default_state(self, vault, sample_character):
        """Test that characters are saved with AVAILABLE state by default"""
        character_id = vault.save_character(sample_character)

        character_file = vault.vault_dir / f"{character_id}.json"
        with open(character_file, 'r') as f:
            data = json.load(f)

        assert data["metadata"]["state"] == CharacterState.AVAILABLE.value
        assert data["metadata"]["campaign_name"] is None

    def test_save_character_active_state(self, vault, sample_character):
        """Test saving a character with ACTIVE state"""
        character_id = vault.save_character(
            sample_character,
            state=CharacterState.ACTIVE,
            campaign_name="Test Campaign"
        )

        character_file = vault.vault_dir / f"{character_id}.json"
        with open(character_file, 'r') as f:
            data = json.load(f)

        assert data["metadata"]["state"] == CharacterState.ACTIVE.value
        assert data["metadata"]["campaign_name"] == "Test Campaign"

    def test_save_character_active_without_campaign(self, vault, sample_character):
        """Test that active state without campaign name raises error"""
        with pytest.raises(ValueError, match="Active characters must have a campaign_name"):
            vault.save_character(sample_character, state=CharacterState.ACTIVE)

    def test_save_character_available_with_campaign(self, vault, sample_character):
        """Test that non-active state with campaign name raises error"""
        with pytest.raises(ValueError, match="Only active characters can have a campaign_name"):
            vault.save_character(
                sample_character,
                state=CharacterState.AVAILABLE,
                campaign_name="Test Campaign"
            )

    def test_save_character_data_structure(self, vault, sample_character):
        """Test the saved character data structure"""
        character_id = vault.save_character(sample_character)

        character_file = vault.vault_dir / f"{character_id}.json"
        with open(character_file, 'r') as f:
            data = json.load(f)

        # Check top-level structure
        assert "version" in data
        assert "metadata" in data
        assert "character" in data

        # Check version
        assert data["version"] == VAULT_VERSION

        # Check metadata
        metadata = data["metadata"]
        assert metadata["character_id"] == character_id
        assert "state" in metadata
        assert "created" in metadata
        assert "last_modified" in metadata

        # Check character data
        char_data = data["character"]
        assert char_data["name"] == "Test Fighter"
        assert char_data["character_class"] == "fighter"
        assert char_data["level"] == 3
        assert char_data["race"] == "human"
        assert char_data["subclass"] == "champion"
        assert char_data["xp"] == 900
        assert char_data["max_hp"] == 28
        assert char_data["current_hp"] == 28
        assert char_data["ac"] == 16

        # Check abilities
        assert char_data["abilities"]["strength"] == 16
        assert char_data["abilities"]["dexterity"] == 14

        # Check inventory
        assert "inventory" in char_data
        assert char_data["inventory"]["currency"]["gold"] == 50

        # Check proficiencies
        assert "str" in char_data["saving_throw_proficiencies"]
        assert "athletics" in char_data["skill_proficiencies"]
        assert "martial" in char_data["weapon_proficiencies"]

        # Check resource pools
        assert len(char_data["resource_pools"]) == 1
        assert char_data["resource_pools"][0]["name"] == "Second Wind"


class TestLoadCharacter:
    """Test loading characters from the vault"""

    def test_load_character_success(self, vault, sample_character):
        """Test loading a saved character"""
        character_id = vault.save_character(sample_character)
        loaded = vault.load_character(character_id)

        assert loaded.name == "Test Fighter"
        assert loaded.character_class == CharacterClass.FIGHTER
        assert loaded.level == 3
        assert loaded.race == "human"
        assert loaded.subclass == "champion"
        assert loaded.xp == 900
        assert loaded.max_hp == 28
        assert loaded.current_hp == 28
        assert loaded.ac == 16

    def test_load_character_abilities(self, vault, sample_character):
        """Test that abilities are correctly loaded"""
        character_id = vault.save_character(sample_character)
        loaded = vault.load_character(character_id)

        assert loaded.abilities.strength == 16
        assert loaded.abilities.dexterity == 14
        assert loaded.abilities.constitution == 15
        assert loaded.abilities.intelligence == 10
        assert loaded.abilities.wisdom == 12
        assert loaded.abilities.charisma == 8

    def test_load_character_inventory(self, vault, sample_character):
        """Test that inventory is correctly loaded"""
        character_id = vault.save_character(sample_character)
        loaded = vault.load_character(character_id)

        assert loaded.inventory.currency.gold == 50

    def test_load_character_resource_pools(self, vault, sample_character):
        """Test that resource pools are correctly loaded"""
        character_id = vault.save_character(sample_character)
        loaded = vault.load_character(character_id)

        assert "Second Wind" in loaded.resource_pools
        pool = loaded.resource_pools["Second Wind"]
        assert pool.current == 1
        assert pool.maximum == 1
        assert pool.recovery_type == "short"

    def test_load_character_proficiencies(self, vault, sample_character):
        """Test that proficiencies are correctly loaded"""
        character_id = vault.save_character(sample_character)
        loaded = vault.load_character(character_id)

        assert "str" in loaded.saving_throw_proficiencies
        assert "con" in loaded.saving_throw_proficiencies
        assert "athletics" in loaded.skill_proficiencies
        assert "intimidation" in loaded.skill_proficiencies
        assert "martial" in loaded.weapon_proficiencies
        assert "heavy" in loaded.armor_proficiencies

    def test_load_character_not_found(self, vault):
        """Test loading a non-existent character"""
        fake_id = str(uuid.uuid4())
        with pytest.raises(FileNotFoundError, match="Character not found"):
            vault.load_character(fake_id)

    def test_load_character_corrupted_json(self, vault, temp_vault_dir):
        """Test loading a corrupted JSON file"""
        character_id = str(uuid.uuid4())
        character_file = temp_vault_dir / f"{character_id}.json"

        # Write invalid JSON
        with open(character_file, 'w') as f:
            f.write("{invalid json")

        with pytest.raises(ValueError, match="Corrupted character file"):
            vault.load_character(character_id)

    def test_load_character_invalid_data(self, vault, temp_vault_dir):
        """Test loading a file with invalid character data"""
        character_id = str(uuid.uuid4())
        character_file = temp_vault_dir / f"{character_id}.json"

        # Write valid JSON but missing required fields
        with open(character_file, 'w') as f:
            json.dump({"version": "1.0.0"}, f)

        with pytest.raises(ValueError, match="Invalid character file"):
            vault.load_character(character_id)


class TestListCharacters:
    """Test listing characters in the vault"""

    def test_list_characters_empty_vault(self, vault):
        """Test listing characters in an empty vault"""
        characters = vault.list_characters()
        assert len(characters) == 0

    def test_list_characters_single(self, vault, sample_character):
        """Test listing a single character"""
        character_id = vault.save_character(sample_character)
        characters = vault.list_characters()

        assert len(characters) == 1
        char = characters[0]
        assert char["id"] == character_id
        assert char["name"] == "Test Fighter"
        assert char["class"] == "fighter"
        assert char["level"] == 3
        assert char["race"] == "human"
        assert char["state"] == CharacterState.AVAILABLE.value
        assert char["campaign"] is None

    def test_list_characters_multiple(self, vault, sample_character):
        """Test listing multiple characters"""
        id1 = vault.save_character(sample_character)

        # Create another character
        sample_character.name = "Test Wizard"
        sample_character.character_class = CharacterClass.WIZARD
        id2 = vault.save_character(sample_character)

        characters = vault.list_characters()
        assert len(characters) == 2

        names = {char["name"] for char in characters}
        assert "Test Fighter" in names
        assert "Test Wizard" in names

    def test_list_characters_excludes_retired_by_default(self, vault, sample_character):
        """Test that retired characters are excluded by default"""
        # Save available character
        vault.save_character(sample_character)

        # Save retired character
        sample_character.name = "Retired Character"
        vault.save_character(sample_character, state=CharacterState.RETIRED)

        characters = vault.list_characters()
        assert len(characters) == 1
        assert characters[0]["name"] == "Test Fighter"

    def test_list_characters_includes_retired_when_requested(self, vault, sample_character):
        """Test that retired characters can be included"""
        # Save available character
        vault.save_character(sample_character)

        # Save retired character
        sample_character.name = "Retired Character"
        vault.save_character(sample_character, state=CharacterState.RETIRED)

        characters = vault.list_characters(include_retired=True)
        assert len(characters) == 2

        names = {char["name"] for char in characters}
        assert "Test Fighter" in names
        assert "Retired Character" in names

    def test_list_characters_active_state(self, vault, sample_character):
        """Test listing characters shows active state and campaign"""
        vault.save_character(
            sample_character,
            state=CharacterState.ACTIVE,
            campaign_name="Epic Quest"
        )

        characters = vault.list_characters()
        assert len(characters) == 1
        assert characters[0]["state"] == CharacterState.ACTIVE.value
        assert characters[0]["campaign"] == "Epic Quest"

    def test_list_characters_skips_corrupted_files(self, vault, sample_character, temp_vault_dir):
        """Test that listing skips corrupted files"""
        # Save valid character
        vault.save_character(sample_character)

        # Create corrupted file
        corrupted_file = temp_vault_dir / "corrupted.json"
        with open(corrupted_file, 'w') as f:
            f.write("{invalid")

        # Should still list the valid character
        characters = vault.list_characters()
        assert len(characters) == 1


class TestExportCharacter:
    """Test exporting characters"""

    def test_export_character_success(self, vault, sample_character, tmp_path):
        """Test exporting a character"""
        character_id = vault.save_character(sample_character)
        export_path = tmp_path / "export" / "fighter.json"

        result_path = vault.export_character(character_id, export_path)

        assert result_path == export_path
        assert export_path.exists()

    def test_export_character_strips_metadata(self, vault, sample_character, tmp_path):
        """Test that export strips internal metadata by default"""
        character_id = vault.save_character(sample_character)
        export_path = tmp_path / "fighter.json"

        vault.export_character(character_id, export_path, strip_metadata=True)

        with open(export_path, 'r') as f:
            data = json.load(f)

        # Should have version and character, but not full metadata
        assert "version" in data
        assert "character" in data
        assert "exported" in data
        assert "metadata" not in data

    def test_export_character_keeps_metadata(self, vault, sample_character, tmp_path):
        """Test that export can keep metadata if requested"""
        character_id = vault.save_character(sample_character)
        export_path = tmp_path / "fighter.json"

        vault.export_character(character_id, export_path, strip_metadata=False)

        with open(export_path, 'r') as f:
            data = json.load(f)

        # Should have full vault format
        assert "version" in data
        assert "metadata" in data
        assert "character" in data

    def test_export_character_creates_directories(self, vault, sample_character, tmp_path):
        """Test that export creates necessary directories"""
        character_id = vault.save_character(sample_character)
        export_path = tmp_path / "nested" / "dirs" / "fighter.json"

        vault.export_character(character_id, export_path)

        assert export_path.exists()
        assert export_path.parent.exists()

    def test_export_character_not_found(self, vault, tmp_path):
        """Test exporting a non-existent character"""
        fake_id = str(uuid.uuid4())
        export_path = tmp_path / "fighter.json"

        with pytest.raises(FileNotFoundError, match="Character not found"):
            vault.export_character(fake_id, export_path)


class TestImportCharacter:
    """Test importing characters"""

    def test_import_character_success(self, vault, sample_character, tmp_path):
        """Test importing a character from a file"""
        # Create an export file
        export_path = tmp_path / "import.json"
        original_id = vault.save_character(sample_character)
        vault.export_character(original_id, export_path)

        # Delete the original
        vault.delete_character(original_id)

        # Import it back
        new_id = vault.import_character(export_path)

        assert new_id != original_id  # Should get a new UUID
        assert uuid.UUID(new_id)  # Should be valid UUID

        # Should be able to load it
        loaded = vault.load_character(new_id)
        assert loaded.name == "Test Fighter"

    def test_import_character_with_custom_id(self, vault, sample_character, tmp_path):
        """Test importing a character with a custom UUID"""
        # Create an export file
        export_path = tmp_path / "import.json"
        original_id = vault.save_character(sample_character)
        vault.export_character(original_id, export_path)

        # Import with custom ID
        custom_id = str(uuid.uuid4())
        new_id = vault.import_character(export_path, character_id=custom_id)

        assert new_id == custom_id

    def test_import_character_file_not_found(self, vault, tmp_path):
        """Test importing from a non-existent file"""
        import_path = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError, match="Import file not found"):
            vault.import_character(import_path)

    def test_import_character_invalid_json(self, vault, tmp_path):
        """Test importing invalid JSON"""
        import_path = tmp_path / "invalid.json"
        with open(import_path, 'w') as f:
            f.write("{invalid json")

        with pytest.raises(ValueError, match="Invalid import file"):
            vault.import_character(import_path)

    def test_import_character_missing_data(self, vault, tmp_path):
        """Test importing file with missing character data"""
        import_path = tmp_path / "incomplete.json"
        with open(import_path, 'w') as f:
            json.dump({"version": "1.0.0"}, f)

        with pytest.raises(ValueError, match="missing 'character' data"):
            vault.import_character(import_path)


class TestCloneCharacter:
    """Test cloning characters"""

    def test_clone_character_success(self, vault, sample_character):
        """Test cloning a character"""
        original_id = vault.save_character(sample_character)
        clone_id = vault.clone_character(original_id)

        # Should have different IDs
        assert clone_id != original_id

        # Both should exist
        original = vault.load_character(original_id)
        clone = vault.load_character(clone_id)

        # Clone should have same stats but different name
        assert clone.name == "Copy of Test Fighter"
        assert clone.character_class == original.character_class
        assert clone.level == original.level
        assert clone.abilities.strength == original.abilities.strength

    def test_clone_character_with_custom_name(self, vault, sample_character):
        """Test cloning with a custom name"""
        original_id = vault.save_character(sample_character)
        clone_id = vault.clone_character(original_id, new_name="Clone Fighter")

        clone = vault.load_character(clone_id)
        assert clone.name == "Clone Fighter"

    def test_clone_character_always_available(self, vault, sample_character):
        """Test that clones are always in AVAILABLE state"""
        # Save an active character
        original_id = vault.save_character(
            sample_character,
            state=CharacterState.ACTIVE,
            campaign_name="Test Campaign"
        )

        # Clone it
        clone_id = vault.clone_character(original_id)

        # Clone should be available
        characters = vault.list_characters()
        clone_info = next(c for c in characters if c["id"] == clone_id)
        assert clone_info["state"] == CharacterState.AVAILABLE.value
        assert clone_info["campaign"] is None

    def test_clone_character_not_found(self, vault):
        """Test cloning a non-existent character"""
        fake_id = str(uuid.uuid4())

        with pytest.raises(FileNotFoundError, match="Character not found"):
            vault.clone_character(fake_id)


class TestDeleteCharacter:
    """Test deleting characters"""

    def test_delete_character_success(self, vault, sample_character):
        """Test deleting a character"""
        character_id = vault.save_character(sample_character)

        # Should exist
        assert vault.load_character(character_id)

        # Delete it
        result = vault.delete_character(character_id)
        assert result is True

        # Should not exist
        with pytest.raises(FileNotFoundError):
            vault.load_character(character_id)

    def test_delete_character_not_found(self, vault):
        """Test deleting a non-existent character"""
        fake_id = str(uuid.uuid4())
        result = vault.delete_character(fake_id)
        assert result is False


class TestUpdateCharacterState:
    """Test updating character state"""

    def test_update_state_to_active(self, vault, sample_character):
        """Test updating state to ACTIVE"""
        character_id = vault.save_character(sample_character)

        vault.update_character_state(
            character_id,
            CharacterState.ACTIVE,
            campaign_name="New Campaign"
        )

        characters = vault.list_characters()
        char = characters[0]
        assert char["state"] == CharacterState.ACTIVE.value
        assert char["campaign"] == "New Campaign"

    def test_update_state_to_retired(self, vault, sample_character):
        """Test updating state to RETIRED"""
        character_id = vault.save_character(sample_character)

        vault.update_character_state(character_id, CharacterState.RETIRED)

        # Should not appear in default listing
        characters = vault.list_characters()
        assert len(characters) == 0

        # Should appear when including retired
        characters = vault.list_characters(include_retired=True)
        assert len(characters) == 1
        assert characters[0]["state"] == CharacterState.RETIRED.value

    def test_update_state_to_available(self, vault, sample_character):
        """Test updating state from ACTIVE to AVAILABLE"""
        character_id = vault.save_character(
            sample_character,
            state=CharacterState.ACTIVE,
            campaign_name="Old Campaign"
        )

        vault.update_character_state(character_id, CharacterState.AVAILABLE)

        characters = vault.list_characters()
        char = characters[0]
        assert char["state"] == CharacterState.AVAILABLE.value
        assert char["campaign"] is None

    def test_update_state_active_without_campaign(self, vault, sample_character):
        """Test that updating to ACTIVE without campaign raises error"""
        character_id = vault.save_character(sample_character)

        with pytest.raises(ValueError, match="Active characters must have a campaign_name"):
            vault.update_character_state(character_id, CharacterState.ACTIVE)

    def test_update_state_available_with_campaign(self, vault, sample_character):
        """Test that updating to non-ACTIVE with campaign raises error"""
        character_id = vault.save_character(sample_character)

        with pytest.raises(ValueError, match="Only active characters can have a campaign_name"):
            vault.update_character_state(
                character_id,
                CharacterState.AVAILABLE,
                campaign_name="Test Campaign"
            )

    def test_update_state_not_found(self, vault):
        """Test updating state of non-existent character"""
        fake_id = str(uuid.uuid4())

        with pytest.raises(FileNotFoundError, match="Character not found"):
            vault.update_character_state(fake_id, CharacterState.RETIRED)

    def test_update_state_updates_timestamp(self, vault, sample_character, temp_vault_dir):
        """Test that updating state updates the last_modified timestamp"""
        character_id = vault.save_character(sample_character)

        # Get original timestamp
        character_file = temp_vault_dir / f"{character_id}.json"
        with open(character_file, 'r') as f:
            original_data = json.load(f)
        original_timestamp = original_data["metadata"]["last_modified"]

        # Wait a tiny bit to ensure timestamp difference
        import time
        time.sleep(0.01)

        # Update state
        vault.update_character_state(character_id, CharacterState.RETIRED)

        # Check new timestamp
        with open(character_file, 'r') as f:
            new_data = json.load(f)
        new_timestamp = new_data["metadata"]["last_modified"]

        assert new_timestamp > original_timestamp
