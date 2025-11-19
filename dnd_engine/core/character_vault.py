# ABOUTME: Character vault for managing characters outside of active campaigns
# ABOUTME: Handles character storage, import/export, cloning, and state tracking

import json
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import asdict
from enum import Enum

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.systems.inventory import Inventory, InventoryItem, EquipmentSlot
from dnd_engine.systems.currency import Currency
from dnd_engine.systems.resources import ResourcePool


class CharacterState(Enum):
    """Character state in the vault"""
    AVAILABLE = "available"  # In vault, can join campaigns
    ACTIVE = "active"  # Currently in a campaign
    RETIRED = "retired"  # Marked as retired


# Current character vault version
VAULT_VERSION = "1.0.0"


class CharacterVault:
    """
    Manages character storage and operations outside of campaigns.

    Handles:
    - Character storage in vault directory
    - Listing characters with state information
    - Import/export character files
    - Character cloning
    - State tracking (active/available/retired)
    """

    def __init__(self, vault_dir: Optional[Path] = None):
        """
        Initialize character vault.

        Args:
            vault_dir: Directory for vault storage (defaults to ~/.dnd_terminal/characters/vault)
        """
        if vault_dir is None:
            vault_dir = Path.home() / ".dnd_terminal" / "characters" / "vault"

        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(parents=True, exist_ok=True)

    def save_character(
        self,
        character: Character,
        character_id: Optional[str] = None,
        state: CharacterState = CharacterState.AVAILABLE,
        campaign_name: Optional[str] = None
    ) -> str:
        """
        Save a character to the vault.

        Args:
            character: Character to save
            character_id: Optional UUID (generates new one if not provided)
            state: Character state (active/available/retired)
            campaign_name: Name of campaign if character is active

        Returns:
            Character UUID

        Raises:
            ValueError: If character_id is invalid or state is inconsistent
        """
        # Generate or validate UUID
        if character_id is None:
            character_id = str(uuid.uuid4())
        else:
            # Validate UUID format
            try:
                uuid.UUID(character_id)
            except ValueError:
                raise ValueError(f"Invalid character ID: {character_id}")

        # Validate state consistency
        if state == CharacterState.ACTIVE and campaign_name is None:
            raise ValueError("Active characters must have a campaign_name")
        if state != CharacterState.ACTIVE and campaign_name is not None:
            raise ValueError("Only active characters can have a campaign_name")

        # Create character data
        character_data = self._serialize_character(
            character,
            character_id,
            state,
            campaign_name
        )

        # Write to file
        character_path = self.vault_dir / f"{character_id}.json"
        with open(character_path, 'w', encoding='utf-8') as f:
            json.dump(character_data, f, indent=2, ensure_ascii=False)

        return character_id

    def load_character(self, character_id: str) -> Character:
        """
        Load a character from the vault.

        Args:
            character_id: UUID of the character

        Returns:
            Loaded Character

        Raises:
            FileNotFoundError: If character doesn't exist
            ValueError: If character file is invalid or corrupted
        """
        character_path = self.vault_dir / f"{character_id}.json"

        if not character_path.exists():
            raise FileNotFoundError(f"Character not found: {character_id}")

        # Read character file
        try:
            with open(character_path, 'r', encoding='utf-8') as f:
                character_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupted character file: {e}")

        # Validate character data
        self._validate_character_data(character_data)

        # Deserialize character
        character = self._deserialize_character(character_data)

        return character

    def list_characters(
        self,
        include_retired: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List all characters in the vault.

        Args:
            include_retired: Whether to include retired characters

        Returns:
            List of dictionaries containing character metadata
        """
        characters = []

        for character_file in self.vault_dir.glob("*.json"):
            try:
                with open(character_file, 'r', encoding='utf-8') as f:
                    character_data = json.load(f)

                metadata = character_data.get("metadata", {})
                state = CharacterState(metadata.get("state", "available"))

                # Skip retired characters unless requested
                if state == CharacterState.RETIRED and not include_retired:
                    continue

                char_info = character_data.get("character", {})

                characters.append({
                    "id": metadata.get("character_id"),
                    "name": char_info.get("name", "Unknown"),
                    "class": char_info.get("character_class", "Unknown"),
                    "level": char_info.get("level", 1),
                    "race": char_info.get("race", "Unknown"),
                    "state": state.value,
                    "campaign": metadata.get("campaign_name"),
                    "created": metadata.get("created", "Unknown"),
                    "last_modified": metadata.get("last_modified", "Unknown")
                })
            except (json.JSONDecodeError, KeyError, ValueError):
                # Skip corrupted character files
                continue

        # Sort by last modified (most recent first)
        characters.sort(key=lambda c: c["last_modified"], reverse=True)

        return characters

    def export_character(
        self,
        character_id: str,
        export_path: Path,
        strip_metadata: bool = True
    ) -> Path:
        """
        Export a character to a file for sharing.

        Args:
            character_id: UUID of the character to export
            export_path: Path to export to
            strip_metadata: Whether to strip internal IDs and metadata

        Returns:
            Path to the exported file

        Raises:
            FileNotFoundError: If character doesn't exist
        """
        character_path = self.vault_dir / f"{character_id}.json"

        if not character_path.exists():
            raise FileNotFoundError(f"Character not found: {character_id}")

        with open(character_path, 'r', encoding='utf-8') as f:
            character_data = json.load(f)

        if strip_metadata:
            # Create clean export without internal IDs
            export_data = {
                "version": character_data["version"],
                "character": character_data["character"],
                "exported": datetime.now().isoformat()
            }
        else:
            export_data = character_data

        # Write to export path
        export_path = Path(export_path)
        export_path.parent.mkdir(parents=True, exist_ok=True)

        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        return export_path

    def import_character(
        self,
        import_path: Path,
        character_id: Optional[str] = None
    ) -> str:
        """
        Import a character from a file.

        Args:
            import_path: Path to the character file
            character_id: Optional UUID (generates new one if not provided)

        Returns:
            Character UUID

        Raises:
            FileNotFoundError: If import file doesn't exist
            ValueError: If import file is invalid
        """
        import_path = Path(import_path)

        if not import_path.exists():
            raise FileNotFoundError(f"Import file not found: {import_path}")

        # Read import file
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid import file: {e}")

        # Validate import data
        if "character" not in import_data:
            raise ValueError("Invalid import file: missing 'character' data")

        # Load character
        character = self._deserialize_character(import_data)

        # Save to vault with new ID
        new_id = self.save_character(character, character_id=character_id)

        return new_id

    def clone_character(
        self,
        character_id: str,
        new_name: Optional[str] = None
    ) -> str:
        """
        Clone a character with a new UUID.

        Args:
            character_id: UUID of the character to clone
            new_name: Optional new name (defaults to "Copy of [original name]")

        Returns:
            New character UUID

        Raises:
            FileNotFoundError: If character doesn't exist
        """
        # Load the original character
        character = self.load_character(character_id)

        # Update name if provided
        if new_name:
            character.name = new_name
        else:
            character.name = f"Copy of {character.name}"

        # Save with new ID (always available state for clones)
        new_id = self.save_character(
            character,
            character_id=None,  # Generate new UUID
            state=CharacterState.AVAILABLE
        )

        return new_id

    def delete_character(self, character_id: str) -> bool:
        """
        Delete a character from the vault.

        Args:
            character_id: UUID of the character to delete

        Returns:
            True if character was deleted, False if not found
        """
        character_path = self.vault_dir / f"{character_id}.json"

        if character_path.exists():
            character_path.unlink()
            return True

        return False

    def update_character_state(
        self,
        character_id: str,
        state: CharacterState,
        campaign_name: Optional[str] = None
    ) -> None:
        """
        Update the state of a character.

        Args:
            character_id: UUID of the character
            state: New state
            campaign_name: Campaign name if state is ACTIVE

        Raises:
            FileNotFoundError: If character doesn't exist
            ValueError: If state is inconsistent
        """
        # Load character data
        character_path = self.vault_dir / f"{character_id}.json"

        if not character_path.exists():
            raise FileNotFoundError(f"Character not found: {character_id}")

        with open(character_path, 'r', encoding='utf-8') as f:
            character_data = json.load(f)

        # Validate state consistency
        if state == CharacterState.ACTIVE and campaign_name is None:
            raise ValueError("Active characters must have a campaign_name")
        if state != CharacterState.ACTIVE and campaign_name is not None:
            raise ValueError("Only active characters can have a campaign_name")

        # Update metadata
        character_data["metadata"]["state"] = state.value
        character_data["metadata"]["campaign_name"] = campaign_name
        character_data["metadata"]["last_modified"] = datetime.now().isoformat()

        # Write back
        with open(character_path, 'w', encoding='utf-8') as f:
            json.dump(character_data, f, indent=2, ensure_ascii=False)

    def _serialize_character(
        self,
        character: Character,
        character_id: str,
        state: CharacterState,
        campaign_name: Optional[str]
    ) -> Dict[str, Any]:
        """
        Serialize a character to a dictionary with metadata.

        Args:
            character: Character to serialize
            character_id: Character UUID
            state: Character state
            campaign_name: Campaign name if active

        Returns:
            Dictionary representation of character with metadata
        """
        now = datetime.now().isoformat()

        return {
            "version": VAULT_VERSION,
            "metadata": {
                "character_id": character_id,
                "state": state.value,
                "campaign_name": campaign_name,
                "created": now,
                "last_modified": now
            },
            "character": {
                "name": character.name,
                "character_class": character.character_class.value,
                "level": character.level,
                "race": character.race,
                "subclass": character.subclass,
                "xp": character.xp,
                "max_hp": character.max_hp,
                "current_hp": character.current_hp,
                "ac": character.ac,
                "abilities": asdict(character.abilities),
                "inventory": self._serialize_inventory(character.inventory),
                "conditions": list(character.conditions),
                "resource_pools": self._serialize_resource_pools(character),
                "saving_throw_proficiencies": character.saving_throw_proficiencies,
                "skill_proficiencies": character.skill_proficiencies,
                "expertise_skills": character.expertise_skills,
                "weapon_proficiencies": character.weapon_proficiencies,
                "armor_proficiencies": character.armor_proficiencies,
                "spellcasting_ability": character.spellcasting_ability,
                "known_spells": character.known_spells,
                "prepared_spells": character.prepared_spells
            }
        }

    def _serialize_inventory(self, inventory: Inventory) -> Dict[str, Any]:
        """
        Serialize inventory to a dictionary.

        Args:
            inventory: Inventory to serialize

        Returns:
            Dictionary representation of inventory
        """
        return {
            "items": [
                {
                    "item_id": item.item_id,
                    "category": item.category,
                    "quantity": item.quantity
                }
                for item in inventory.items.values()
            ],
            "equipped": {
                "weapon": inventory.equipped[EquipmentSlot.WEAPON],
                "armor": inventory.equipped[EquipmentSlot.ARMOR]
            },
            "currency": asdict(inventory.currency)
        }

    def _serialize_resource_pools(self, character: Character) -> List[Dict[str, Any]]:
        """
        Serialize character resource pools to a list of dictionaries.

        Args:
            character: Character to serialize resource pools from

        Returns:
            List of dictionaries representing each resource pool
        """
        return [
            {
                "name": pool.name,
                "current": pool.current,
                "maximum": pool.maximum,
                "recovery_type": pool.recovery_type
            }
            for pool in character.resource_pools.values()
        ]

    def _deserialize_character(self, data: Dict[str, Any]) -> Character:
        """
        Deserialize character from data.

        Args:
            data: Character data dictionary (can be full vault format or export format)

        Returns:
            Reconstructed Character
        """
        # Handle both full vault format and export format
        char_data = data.get("character", data)

        abilities = Abilities(**char_data["abilities"])
        inventory = self._deserialize_inventory(char_data["inventory"])

        character = Character(
            name=char_data["name"],
            character_class=CharacterClass(char_data["character_class"]),
            level=char_data["level"],
            abilities=abilities,
            max_hp=char_data["max_hp"],
            ac=char_data["ac"],
            current_hp=char_data["current_hp"],
            xp=char_data["xp"],
            inventory=inventory,
            race=char_data["race"],
            subclass=char_data.get("subclass"),
            saving_throw_proficiencies=char_data.get("saving_throw_proficiencies"),
            skill_proficiencies=char_data.get("skill_proficiencies"),
            expertise_skills=char_data.get("expertise_skills"),
            weapon_proficiencies=char_data.get("weapon_proficiencies"),
            armor_proficiencies=char_data.get("armor_proficiencies"),
            spellcasting_ability=char_data.get("spellcasting_ability"),
            known_spells=char_data.get("known_spells"),
            prepared_spells=char_data.get("prepared_spells")
        )

        # Restore conditions
        for condition in char_data.get("conditions", []):
            character.add_condition(condition)

        # Restore resource pools
        for pool_data in char_data.get("resource_pools", []):
            pool = ResourcePool(**pool_data)
            character.add_resource_pool(pool)

        return character

    def _deserialize_inventory(self, inv_data: Dict[str, Any]) -> Inventory:
        """
        Deserialize inventory from data.

        Args:
            inv_data: Inventory data dictionary

        Returns:
            Reconstructed Inventory
        """
        inventory = Inventory()

        # Restore items
        for item_data in inv_data.get("items", []):
            inventory.add_item(
                item_id=item_data["item_id"],
                category=item_data["category"],
                quantity=item_data["quantity"]
            )

        # Restore equipped items
        equipped_data = inv_data.get("equipped", {})
        if equipped_data.get("weapon"):
            inventory.equip_item(equipped_data["weapon"], EquipmentSlot.WEAPON)
        if equipped_data.get("armor"):
            inventory.equip_item(equipped_data["armor"], EquipmentSlot.ARMOR)

        # Restore currency
        currency_data = inv_data.get("currency", {})
        inventory.currency = Currency(**currency_data)

        return inventory

    def _validate_character_data(self, data: Dict[str, Any]) -> None:
        """
        Validate character file structure.

        Args:
            data: Character data to validate

        Raises:
            ValueError: If character data is invalid
        """
        # Check for either full vault format or export format
        if "character" in data:
            # Full vault format
            required_keys = ["version", "metadata", "character"]
            for key in required_keys:
                if key not in data:
                    raise ValueError(f"Invalid character file: missing '{key}'")
        elif "name" in data:
            # Export format (just character data)
            pass
        else:
            raise ValueError("Invalid character file: missing required data")
