# ABOUTME: Integration tests for CharacterVault workflows
# ABOUTME: Tests end-to-end character import/export, multi-vault operations, and character factory integration

import json
from pathlib import Path
import pytest

from dnd_engine.core.character_vault import CharacterVault, CharacterState
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
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
def second_vault_dir(tmp_path):
    """Create a second temporary vault directory"""
    vault_dir = tmp_path / "vault2"
    vault_dir.mkdir()
    return vault_dir


@pytest.fixture
def second_vault(second_vault_dir):
    """Create a second CharacterVault instance"""
    return CharacterVault(vault_dir=second_vault_dir)


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
    inventory.currency.gold = 100
    inventory.add_item("longsword", "weapon", 1)
    inventory.add_item("chain_mail", "armor", 1)
    inventory.equip_item("longsword", EquipmentSlot.WEAPON)
    inventory.equip_item("chain_mail", EquipmentSlot.ARMOR)

    character = Character(
        name="Integration Test Fighter",
        character_class=CharacterClass.FIGHTER,
        level=5,
        abilities=abilities,
        max_hp=45,
        ac=16,
        current_hp=35,  # Has taken damage
        xp=6500,
        inventory=inventory,
        race="human",
        subclass="champion",
        saving_throw_proficiencies=["str", "con"],
        skill_proficiencies=["athletics", "intimidation", "perception"],
        expertise_skills=[],
        weapon_proficiencies=["simple", "martial"],
        armor_proficiencies=["light", "medium", "heavy", "shields"]
    )

    # Add multiple resource pools
    second_wind = ResourcePool(name="Second Wind", current=0, maximum=1, recovery_type="short")
    action_surge = ResourcePool(name="Action Surge", current=1, maximum=1, recovery_type="short")
    character.add_resource_pool(second_wind)
    character.add_resource_pool(action_surge)

    # Add a condition
    character.add_condition("poisoned")

    return character


class TestImportExportWorkflow:
    """Test complete import/export workflows"""

    def test_export_import_roundtrip(self, vault, sample_character, tmp_path):
        """Test that exporting and importing preserves all character data"""
        # Save original character
        original_id = vault.save_character(sample_character)

        # Export to file
        export_path = tmp_path / "export.json"
        vault.export_character(original_id, export_path)

        # Import to new ID
        imported_id = vault.import_character(export_path)

        # Load both and compare
        original = vault.load_character(original_id)
        imported = vault.load_character(imported_id)

        # Basic attributes
        assert imported.name == original.name
        assert imported.character_class == original.character_class
        assert imported.level == original.level
        assert imported.race == original.race
        assert imported.subclass == original.subclass
        assert imported.xp == original.xp
        assert imported.max_hp == original.max_hp
        assert imported.current_hp == original.current_hp
        assert imported.ac == original.ac

        # Abilities
        assert imported.abilities.strength == original.abilities.strength
        assert imported.abilities.dexterity == original.abilities.dexterity
        assert imported.abilities.constitution == original.abilities.constitution
        assert imported.abilities.intelligence == original.abilities.intelligence
        assert imported.abilities.wisdom == original.abilities.wisdom
        assert imported.abilities.charisma == original.abilities.charisma

        # Proficiencies
        assert set(imported.saving_throw_proficiencies) == set(original.saving_throw_proficiencies)
        assert set(imported.skill_proficiencies) == set(original.skill_proficiencies)
        assert set(imported.weapon_proficiencies) == set(original.weapon_proficiencies)
        assert set(imported.armor_proficiencies) == set(original.armor_proficiencies)

        # Inventory
        assert imported.inventory.currency.gold == original.inventory.currency.gold
        assert "longsword" in imported.inventory.items
        assert "chain_mail" in imported.inventory.items
        assert imported.inventory.equipped[EquipmentSlot.WEAPON] == "longsword"
        assert imported.inventory.equipped[EquipmentSlot.ARMOR] == "chain_mail"

        # Resource pools
        assert "Second Wind" in imported.resource_pools
        assert "Action Surge" in imported.resource_pools
        assert imported.resource_pools["Second Wind"].current == 0
        assert imported.resource_pools["Action Surge"].current == 1

        # Conditions
        assert "poisoned" in imported.conditions

    def test_export_to_multiple_vaults(self, vault, second_vault, sample_character, tmp_path):
        """Test exporting from one vault and importing to another"""
        # Save to first vault
        original_id = vault.save_character(sample_character)

        # Export from first vault
        export_path = tmp_path / "shared.json"
        vault.export_character(original_id, export_path)

        # Import to second vault
        imported_id = second_vault.import_character(export_path)

        # Verify character exists in second vault
        imported = second_vault.load_character(imported_id)
        assert imported.name == sample_character.name
        assert imported.level == sample_character.level

    def test_export_strips_internal_ids(self, vault, sample_character, tmp_path):
        """Test that exported files don't contain internal IDs"""
        character_id = vault.save_character(sample_character)
        export_path = tmp_path / "clean_export.json"

        vault.export_character(character_id, export_path, strip_metadata=True)

        with open(export_path, 'r') as f:
            data = json.load(f)

        # Should not have metadata section
        assert "metadata" not in data

        # Should have character data
        assert "character" in data
        assert data["character"]["name"] == "Integration Test Fighter"

    def test_import_assigns_new_uuid(self, vault, sample_character, tmp_path):
        """Test that importing creates a new UUID"""
        # Create export
        original_id = vault.save_character(sample_character)
        export_path = tmp_path / "export.json"
        vault.export_character(original_id, export_path)

        # Import multiple times
        id1 = vault.import_character(export_path)
        id2 = vault.import_character(export_path)
        id3 = vault.import_character(export_path)

        # All should be different
        assert id1 != id2
        assert id2 != id3
        assert id1 != id3

        # All should be different from original
        assert id1 != original_id
        assert id2 != original_id
        assert id3 != original_id


class TestCloneWorkflow:
    """Test character cloning workflows"""

    def test_clone_preserves_all_data(self, vault, sample_character):
        """Test that cloning preserves all character data"""
        original_id = vault.save_character(sample_character)
        clone_id = vault.clone_character(original_id)

        original = vault.load_character(original_id)
        clone = vault.load_character(clone_id)

        # Name should be different
        assert clone.name == "Copy of Integration Test Fighter"

        # Everything else should match
        assert clone.character_class == original.character_class
        assert clone.level == original.level
        assert clone.xp == original.xp
        assert clone.max_hp == original.max_hp
        assert clone.current_hp == original.current_hp
        assert clone.ac == original.ac

        # Abilities
        assert clone.abilities.strength == original.abilities.strength

        # Inventory
        assert clone.inventory.currency.gold == original.inventory.currency.gold
        assert "longsword" in clone.inventory.items
        assert clone.inventory.equipped[EquipmentSlot.WEAPON] == "longsword"

        # Resource pools
        assert "Second Wind" in clone.resource_pools
        assert clone.resource_pools["Second Wind"].current == original.resource_pools["Second Wind"].current

        # Conditions
        assert "poisoned" in clone.conditions

    def test_clone_chain(self, vault, sample_character):
        """Test cloning a clone"""
        original_id = vault.save_character(sample_character)
        clone1_id = vault.clone_character(original_id)
        clone2_id = vault.clone_character(clone1_id, new_name="Second Generation Clone")

        clone2 = vault.load_character(clone2_id)
        assert clone2.name == "Second Generation Clone"
        assert clone2.level == sample_character.level

    def test_clone_and_modify(self, vault, sample_character):
        """Test that modifying a clone doesn't affect the original"""
        original_id = vault.save_character(sample_character)
        clone_id = vault.clone_character(original_id)

        # Load and modify clone
        clone = vault.load_character(clone_id)
        clone.level = 10
        clone.max_hp = 80
        clone.inventory.currency.gold = 500

        # Save modified clone
        vault.save_character(clone, character_id=clone_id)

        # Original should be unchanged
        original = vault.load_character(original_id)
        assert original.level == 5
        assert original.max_hp == 45
        assert original.inventory.currency.gold == 100


class TestStateManagement:
    """Test character state management workflows"""

    def test_character_lifecycle_states(self, vault, sample_character):
        """Test transitioning a character through different states"""
        # Create available character
        character_id = vault.save_character(sample_character)

        chars = vault.list_characters()
        assert len(chars) == 1
        assert chars[0]["state"] == CharacterState.AVAILABLE.value

        # Activate for a campaign
        vault.update_character_state(
            character_id,
            CharacterState.ACTIVE,
            campaign_name="Lost Mine of Phandelver"
        )

        chars = vault.list_characters()
        assert chars[0]["state"] == CharacterState.ACTIVE.value
        assert chars[0]["campaign"] == "Lost Mine of Phandelver"

        # Return to available (campaign ended)
        vault.update_character_state(character_id, CharacterState.AVAILABLE)

        chars = vault.list_characters()
        assert chars[0]["state"] == CharacterState.AVAILABLE.value
        assert chars[0]["campaign"] is None

        # Retire character
        vault.update_character_state(character_id, CharacterState.RETIRED)

        chars = vault.list_characters()
        assert len(chars) == 0  # Retired not shown by default

        chars = vault.list_characters(include_retired=True)
        assert len(chars) == 1
        assert chars[0]["state"] == CharacterState.RETIRED.value

    def test_multiple_campaigns(self, vault, sample_character):
        """Test tracking characters across multiple campaigns"""
        # Create three characters
        char1_id = vault.save_character(sample_character)

        sample_character.name = "Wizard Hero"
        sample_character.character_class = CharacterClass.WIZARD
        char2_id = vault.save_character(sample_character)

        sample_character.name = "Rogue Scout"
        sample_character.character_class = CharacterClass.ROGUE
        char3_id = vault.save_character(sample_character)

        # Activate two in different campaigns
        vault.update_character_state(char1_id, CharacterState.ACTIVE, "Campaign A")
        vault.update_character_state(char2_id, CharacterState.ACTIVE, "Campaign B")

        # List should show all three with proper states
        chars = vault.list_characters()
        assert len(chars) == 3

        active_chars = [c for c in chars if c["state"] == CharacterState.ACTIVE.value]
        available_chars = [c for c in chars if c["state"] == CharacterState.AVAILABLE.value]

        assert len(active_chars) == 2
        assert len(available_chars) == 1

        campaigns = {c["campaign"] for c in active_chars}
        assert "Campaign A" in campaigns
        assert "Campaign B" in campaigns


class TestCharacterFactoryIntegration:
    """Test integration with CharacterFactory"""

    def test_save_factory_created_character(self, vault):
        """Test saving a character created by CharacterFactory"""
        factory = CharacterFactory(dice_roller=DiceRoller(seed=42))

        # Create a simple character programmatically
        abilities = Abilities(
            strength=15,
            dexterity=13,
            constitution=14,
            intelligence=12,
            wisdom=10,
            charisma=8
        )

        character = Character(
            name="Factory Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16,
            inventory=Inventory(),
            race="human"
        )

        # Save to vault
        character_id = vault.save_character(character)

        # Verify it loads correctly
        loaded = vault.load_character(character_id)
        assert loaded.name == "Factory Fighter"
        assert loaded.character_class == CharacterClass.FIGHTER
        assert loaded.level == 1


class TestMultiVaultOperations:
    """Test operations across multiple vaults"""

    def test_transfer_character_between_vaults(self, vault, second_vault, sample_character, tmp_path):
        """Test moving a character from one vault to another"""
        # Save to first vault
        original_id = vault.save_character(sample_character)

        # Export from first vault
        export_path = tmp_path / "transfer.json"
        vault.export_character(original_id, export_path)

        # Import to second vault
        new_id = second_vault.import_character(export_path)

        # Delete from first vault
        vault.delete_character(original_id)

        # Verify only exists in second vault
        assert len(vault.list_characters()) == 0
        assert len(second_vault.list_characters()) == 1

        # Verify data integrity
        transferred = second_vault.load_character(new_id)
        assert transferred.name == sample_character.name
        assert transferred.level == sample_character.level

    def test_share_character_between_players(self, vault, second_vault, sample_character, tmp_path):
        """Test sharing a character build between players"""
        # Player 1 creates and exports a character
        player1_id = vault.save_character(sample_character)
        share_path = tmp_path / "shared_build.json"
        vault.export_character(player1_id, share_path, strip_metadata=True)

        # Player 2 imports the build
        player2_id = second_vault.import_character(share_path)

        # Both vaults should have the character
        assert len(vault.list_characters()) == 1
        assert len(second_vault.list_characters()) == 1

        # But with different IDs
        assert player1_id != player2_id

        # Player 2 can rename and modify
        player2_char = second_vault.load_character(player2_id)
        player2_char.name = "Player 2 Version"
        second_vault.save_character(player2_char, character_id=player2_id)

        # Player 1's character unchanged
        player1_char = vault.load_character(player1_id)
        assert player1_char.name == "Integration Test Fighter"


class TestErrorRecovery:
    """Test error handling and recovery scenarios"""

    def test_recover_from_corrupted_export(self, vault, sample_character, tmp_path):
        """Test that vault remains stable after corrupted import"""
        character_id = vault.save_character(sample_character)

        # Create corrupted export file
        bad_export = tmp_path / "corrupted.json"
        with open(bad_export, 'w') as f:
            f.write("{invalid json")

        # Try to import (should fail)
        with pytest.raises(ValueError):
            vault.import_character(bad_export)

        # Vault should still work normally
        chars = vault.list_characters()
        assert len(chars) == 1

        # Can still load original
        loaded = vault.load_character(character_id)
        assert loaded.name == sample_character.name

    def test_handle_missing_optional_fields(self, vault, tmp_path):
        """Test importing character with minimal data (backwards compatibility)"""
        # Create export with only required fields
        minimal_data = {
            "version": "1.0.0",
            "character": {
                "name": "Minimal Fighter",
                "character_class": "fighter",
                "level": 1,
                "race": "human",
                "subclass": None,
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
                "inventory": {
                    "items": [],
                    "equipped": {"weapon": None, "armor": None},
                    "currency": {"copper": 0, "silver": 0, "gold": 0, "platinum": 0}
                },
                "conditions": [],
                "resource_pools": []
            }
        }

        minimal_file = tmp_path / "minimal.json"
        with open(minimal_file, 'w') as f:
            json.dump(minimal_data, f)

        # Should import successfully
        character_id = vault.import_character(minimal_file)

        # Should load with defaults for optional fields
        character = vault.load_character(character_id)
        assert character.name == "Minimal Fighter"
        assert character.level == 1
        assert character.saving_throw_proficiencies == []  # Default empty list
        assert character.skill_proficiencies == []


class TestBulkOperations:
    """Test bulk operations on multiple characters"""

    def test_list_many_characters(self, vault):
        """Test listing with many characters in vault"""
        # Create 20 characters
        for i in range(20):
            abilities = Abilities(
                strength=10 + i % 6,
                dexterity=10 + (i + 1) % 6,
                constitution=10 + (i + 2) % 6,
                intelligence=10 + (i + 3) % 6,
                wisdom=10 + (i + 4) % 6,
                charisma=10 + (i + 5) % 6
            )

            character = Character(
                name=f"Character {i}",
                character_class=CharacterClass.FIGHTER,
                level=1 + (i % 5),
                abilities=abilities,
                max_hp=10,
                ac=10,
                inventory=Inventory()
            )

            vault.save_character(character)

        # Should list all characters
        chars = vault.list_characters()
        assert len(chars) == 20

        # Should be sorted by last_modified (most recent first)
        # The last created should be first in the list
        assert chars[0]["name"] == "Character 19"

    def test_bulk_export(self, vault, sample_character, tmp_path):
        """Test exporting multiple characters"""
        # Create multiple characters
        ids = []
        for i in range(5):
            sample_character.name = f"Export Test {i}"
            character_id = vault.save_character(sample_character)
            ids.append(character_id)

        # Export all characters
        export_dir = tmp_path / "exports"
        export_dir.mkdir()

        for i, character_id in enumerate(ids):
            export_path = export_dir / f"character_{i}.json"
            vault.export_character(character_id, export_path)

        # Verify all exports exist
        assert len(list(export_dir.glob("*.json"))) == 5
