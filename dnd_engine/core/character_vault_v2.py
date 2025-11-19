# ABOUTME: Enhanced character vault with usage tracking for the new save slot system
# ABOUTME: Stores all characters in a single JSON file with usage statistics and metadata

import json
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import asdict

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.systems.inventory import Inventory, InventoryItem, EquipmentSlot
from dnd_engine.systems.currency import Currency
from dnd_engine.systems.resources import ResourcePool


# Current character vault version
VAULT_VERSION = "2.0.0"


class CharacterVaultV2:
    """
    Enhanced character vault with usage tracking.

    Stores all characters in a single character_vault.json file with:
    - Character data (stats, inventory, etc.)
    - Usage statistics (times_used, last_used, save_slots_used)
    - Creation and modification timestamps

    This replaces the old UUID-based individual file system.
    """

    def __init__(self, vault_path: Optional[Path] = None):
        """
        Initialize character vault.

        Args:
            vault_path: Path to character_vault.json (defaults to ~/.dnd_game/character_vault.json)
        """
        if vault_path is None:
            vault_path = Path.home() / ".dnd_game" / "character_vault.json"

        self.vault_path = Path(vault_path)
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize vault file if it doesn't exist
        if not self.vault_path.exists():
            self._initialize_vault()

    def _initialize_vault(self) -> None:
        """Create empty vault file with proper structure."""
        vault_data = {
            "version": VAULT_VERSION,
            "created_at": datetime.now().isoformat(),
            "characters": {}
        }

        with open(self.vault_path, 'w', encoding='utf-8') as f:
            json.dump(vault_data, f, indent=2, ensure_ascii=False)

    def _load_vault(self) -> Dict[str, Any]:
        """
        Load vault data from disk.

        Returns:
            Vault data dictionary

        Raises:
            ValueError: If vault file is corrupted
        """
        try:
            with open(self.vault_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupted vault file: {e}")

    def _save_vault(self, vault_data: Dict[str, Any]) -> None:
        """
        Save vault data to disk.

        Args:
            vault_data: Vault data dictionary
        """
        with open(self.vault_path, 'w', encoding='utf-8') as f:
            json.dump(vault_data, f, indent=2, ensure_ascii=False)

    def add_character(
        self,
        character: Character,
        character_id: Optional[str] = None
    ) -> str:
        """
        Add a character to the vault.

        Args:
            character: Character to add
            character_id: Optional UUID (generates new one if not provided)

        Returns:
            Character UUID

        Raises:
            ValueError: If character_id is invalid or already exists
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

        # Load vault
        vault_data = self._load_vault()

        # Check if character already exists
        if character_id in vault_data["characters"]:
            raise ValueError(f"Character ID already exists: {character_id}")

        # Create character entry
        now = datetime.now().isoformat()
        character_entry = {
            "id": character_id,
            "created_at": now,
            "last_modified": now,
            "last_used": None,
            "times_used": 0,
            "save_slots_used": [],
            "character": self._serialize_character(character)
        }

        # Add to vault
        vault_data["characters"][character_id] = character_entry

        # Save vault
        self._save_vault(vault_data)

        return character_id

    def get_character(self, character_id: str) -> Character:
        """
        Get a character from the vault.

        Args:
            character_id: UUID of the character

        Returns:
            Character instance

        Raises:
            FileNotFoundError: If character doesn't exist
            ValueError: If character data is corrupted
        """
        vault_data = self._load_vault()

        if character_id not in vault_data["characters"]:
            raise FileNotFoundError(f"Character not found: {character_id}")

        character_entry = vault_data["characters"][character_id]
        return self._deserialize_character(character_entry["character"])

    def update_character(self, character_id: str, character: Character) -> None:
        """
        Update a character in the vault (preserves usage stats).

        Args:
            character_id: UUID of the character to update
            character: Updated character data

        Raises:
            FileNotFoundError: If character doesn't exist
        """
        vault_data = self._load_vault()

        if character_id not in vault_data["characters"]:
            raise FileNotFoundError(f"Character not found: {character_id}")

        # Update character data (preserve metadata and stats)
        character_entry = vault_data["characters"][character_id]
        character_entry["character"] = self._serialize_character(character)
        character_entry["last_modified"] = datetime.now().isoformat()

        # Save vault
        self._save_vault(vault_data)

    def record_usage(self, character_id: str, slot_number: int) -> None:
        """
        Record that a character was used in a save slot.

        Updates times_used, last_used, and save_slots_used.

        Args:
            character_id: UUID of the character
            slot_number: Save slot number (1-10)

        Raises:
            FileNotFoundError: If character doesn't exist
        """
        vault_data = self._load_vault()

        if character_id not in vault_data["characters"]:
            raise FileNotFoundError(f"Character not found: {character_id}")

        character_entry = vault_data["characters"][character_id]

        # Update usage statistics
        character_entry["times_used"] = character_entry.get("times_used", 0) + 1
        character_entry["last_used"] = datetime.now().isoformat()

        # Track which save slots used this character
        save_slots_used = character_entry.get("save_slots_used", [])
        if slot_number not in save_slots_used:
            save_slots_used.append(slot_number)
        character_entry["save_slots_used"] = save_slots_used

        # Save vault
        self._save_vault(vault_data)

    def list_characters(self) -> List[Dict[str, Any]]:
        """
        List all characters in the vault with metadata.

        Returns:
            List of dictionaries containing character info and usage stats
        """
        vault_data = self._load_vault()
        characters = []

        for character_id, entry in vault_data["characters"].items():
            char_data = entry["character"]

            characters.append({
                "id": character_id,
                "name": char_data.get("name", "Unknown"),
                "class": char_data.get("character_class", "Unknown"),
                "level": char_data.get("level", 1),
                "race": char_data.get("race", "Unknown"),
                "created_at": entry.get("created_at"),
                "last_modified": entry.get("last_modified"),
                "last_used": entry.get("last_used"),
                "times_used": entry.get("times_used", 0),
                "save_slots_used": entry.get("save_slots_used", [])
            })

        # Sort by last_used (most recent first), then by last_modified
        def sort_key(char):
            last_used = char["last_used"]
            if last_used:
                # Convert to datetime for proper comparison, negate to get newest first
                dt = datetime.fromisoformat(last_used)
                return (0, -dt.timestamp())
            else:
                # No usage, sort by last_modified (newest first)
                dt = datetime.fromisoformat(char["last_modified"])
                return (1, -dt.timestamp())

        characters.sort(key=sort_key)

        return characters

    def delete_character(self, character_id: str) -> bool:
        """
        Delete a character from the vault.

        Args:
            character_id: UUID of the character to delete

        Returns:
            True if character was deleted, False if not found
        """
        vault_data = self._load_vault()

        if character_id in vault_data["characters"]:
            del vault_data["characters"][character_id]
            self._save_vault(vault_data)
            return True

        return False

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
        character = self.get_character(character_id)

        # Update name if provided
        if new_name:
            character.name = new_name
        else:
            character.name = f"Copy of {character.name}"

        # Add with new ID
        new_id = self.add_character(character)

        return new_id

    def import_characters_bulk(
        self,
        characters: List[Character],
        existing_ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Import multiple characters at once.

        Args:
            characters: List of characters to import
            existing_ids: Optional list of existing IDs to use (must match length)

        Returns:
            List of character UUIDs

        Raises:
            ValueError: If existing_ids length doesn't match characters length
        """
        if existing_ids and len(existing_ids) != len(characters):
            raise ValueError("existing_ids length must match characters length")

        character_ids = []
        for i, character in enumerate(characters):
            char_id = existing_ids[i] if existing_ids else None
            character_ids.append(self.add_character(character, char_id))

        return character_ids

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get overall usage statistics for the vault.

        Returns:
            Dictionary with vault statistics
        """
        vault_data = self._load_vault()
        characters = vault_data["characters"]

        total_characters = len(characters)
        total_uses = sum(entry.get("times_used", 0) for entry in characters.values())

        most_used = None
        most_used_count = 0
        for entry in characters.values():
            times_used = entry.get("times_used", 0)
            if times_used > most_used_count:
                most_used_count = times_used
                most_used = entry["character"].get("name", "Unknown")

        return {
            "total_characters": total_characters,
            "total_uses": total_uses,
            "most_used_character": most_used,
            "most_used_count": most_used_count,
            "vault_created": vault_data.get("created_at"),
            "vault_version": vault_data.get("version")
        }

    def _serialize_character(self, character: Character) -> Dict[str, Any]:
        """
        Serialize a character to a dictionary.

        Args:
            character: Character to serialize

        Returns:
            Dictionary representation of character
        """
        return {
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

    def _serialize_inventory(self, inventory: Inventory) -> Dict[str, Any]:
        """Serialize inventory to a dictionary."""
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
        """Serialize character resource pools to a list of dictionaries."""
        return [
            {
                "name": pool.name,
                "current": pool.current,
                "maximum": pool.maximum,
                "recovery_type": pool.recovery_type
            }
            for pool in character.resource_pools.values()
        ]

    def _deserialize_character(self, char_data: Dict[str, Any]) -> Character:
        """
        Deserialize character from data.

        Args:
            char_data: Character data dictionary

        Returns:
            Reconstructed Character
        """
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
