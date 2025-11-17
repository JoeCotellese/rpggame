# ABOUTME: Save and load game state to/from JSON files
# ABOUTME: Handles serialization, validation, versioning, and save file management

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import asdict

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party
from dnd_engine.core.game_state import GameState
from dnd_engine.systems.inventory import Inventory, InventoryItem, EquipmentSlot
from dnd_engine.systems.currency import Currency
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.utils.events import EventBus
from dnd_engine.rules.loader import DataLoader
from dnd_engine.core.dice import DiceRoller


# Current save file version
SAVE_VERSION = "1.0.0"


class SaveManager:
    """
    Manages game save files.

    Handles:
    - Saving game state to JSON
    - Loading game state from JSON
    - Listing available saves with metadata
    - Validating save files
    - Version compatibility
    """

    def __init__(self, saves_dir: Optional[Path] = None):
        """
        Initialize save manager.

        Args:
            saves_dir: Directory for save files (defaults to ./saves)
        """
        if saves_dir is None:
            saves_dir = Path.cwd() / "saves"

        self.saves_dir = Path(saves_dir)
        self.saves_dir.mkdir(exist_ok=True)

    def save_game(
        self,
        game_state: GameState,
        save_name: str,
        auto_save: bool = False
    ) -> Path:
        """
        Save current game state to a JSON file.

        Args:
            game_state: Current game state to save
            save_name: Name for the save file (without extension)
            auto_save: Whether this is an auto-save

        Returns:
            Path to the saved file

        Raises:
            ValueError: If save_name is invalid
        """
        if not save_name or not save_name.strip():
            raise ValueError("Save name cannot be empty")

        # Sanitize save name (remove invalid filename characters)
        save_name = self._sanitize_filename(save_name)

        # Create save data
        save_data = self._serialize_game_state(game_state, auto_save)

        # Write to file
        save_path = self.saves_dir / f"{save_name}.json"
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

        return save_path

    def load_game(
        self,
        save_name: str,
        event_bus: Optional[EventBus] = None,
        data_loader: Optional[DataLoader] = None,
        dice_roller: Optional[DiceRoller] = None
    ) -> GameState:
        """
        Load game state from a save file.

        Args:
            save_name: Name of the save file (without extension)
            event_bus: Event bus for the game (creates new if not provided)
            data_loader: Data loader for content (creates new if not provided)
            dice_roller: Dice roller (creates new if not provided)

        Returns:
            Loaded GameState

        Raises:
            FileNotFoundError: If save file doesn't exist
            ValueError: If save file is invalid or corrupted
        """
        save_path = self.saves_dir / f"{save_name}.json"

        if not save_path.exists():
            raise FileNotFoundError(f"Save file not found: {save_name}")

        # Read save file
        try:
            with open(save_path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupted save file: {e}")

        # Validate save file
        self._validate_save_data(save_data)

        # Check version compatibility
        save_version = save_data.get("version", "0.0.0")
        if not self._is_compatible_version(save_version):
            raise ValueError(
                f"Incompatible save version: {save_version} "
                f"(current version: {SAVE_VERSION})"
            )

        # Deserialize game state
        game_state = self._deserialize_game_state(
            save_data,
            event_bus,
            data_loader,
            dice_roller
        )

        # Update last_played timestamp
        save_data["metadata"]["last_played"] = datetime.now().isoformat()
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

        return game_state

    def list_saves(self) -> List[Dict[str, Any]]:
        """
        List all available save files with metadata.

        Returns:
            List of dictionaries containing save metadata
        """
        saves = []

        for save_file in self.saves_dir.glob("*.json"):
            try:
                with open(save_file, 'r', encoding='utf-8') as f:
                    save_data = json.load(f)

                metadata = save_data.get("metadata", {})
                party_data = save_data.get("party", [])

                # Extract useful information
                saves.append({
                    "name": save_file.stem,
                    "created": metadata.get("created", "Unknown"),
                    "last_played": metadata.get("last_played", metadata.get("created", "Unknown")),
                    "version": save_data.get("version", "Unknown"),
                    "party_size": len(party_data),
                    "party_names": [char.get("name", "Unknown") for char in party_data],
                    "average_level": sum(char.get("level", 1) for char in party_data) / len(party_data) if party_data else 0,
                    "dungeon": save_data.get("game_state", {}).get("dungeon_name", "Unknown"),
                    "auto_save": metadata.get("auto_save", False)
                })
            except (json.JSONDecodeError, KeyError, ValueError):
                # Skip corrupted save files
                continue

        # Sort by last played (most recent first)
        saves.sort(key=lambda s: s["last_played"], reverse=True)

        return saves

    def delete_save(self, save_name: str) -> bool:
        """
        Delete a save file.

        Args:
            save_name: Name of the save file (without extension)

        Returns:
            True if file was deleted, False if file didn't exist
        """
        save_path = self.saves_dir / f"{save_name}.json"

        if save_path.exists():
            save_path.unlink()
            return True

        return False

    def _serialize_game_state(
        self,
        game_state: GameState,
        auto_save: bool
    ) -> Dict[str, Any]:
        """
        Serialize game state to a dictionary.

        Args:
            game_state: Game state to serialize
            auto_save: Whether this is an auto-save

        Returns:
            Dictionary representation of game state
        """
        now = datetime.now().isoformat()

        return {
            "version": SAVE_VERSION,
            "metadata": {
                "created": now,
                "last_played": now,
                "auto_save": auto_save
            },
            "party": [self._serialize_character(char) for char in game_state.party.characters],
            "game_state": {
                "dungeon_name": game_state.dungeon_name,  # Save filename, not display name
                "current_room_id": game_state.current_room_id,
                "dungeon_state": self._serialize_dungeon_state(game_state.dungeon),
                "in_combat": game_state.in_combat,
                "action_history": game_state.action_history,
                "last_entry_direction": game_state.last_entry_direction
            }
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
            "xp": character.xp,
            "max_hp": character.max_hp,
            "current_hp": character.current_hp,
            "ac": character.ac,
            "abilities": asdict(character.abilities),
            "inventory": self._serialize_inventory(character.inventory),
            "conditions": list(character.conditions),
            "resource_pools": self._serialize_resource_pools(character)
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

    def _serialize_dungeon_state(self, dungeon: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize dungeon state (room modifications).

        Args:
            dungeon: Dungeon data

        Returns:
            Dictionary with room states
        """
        room_states = {}

        for room_id, room_data in dungeon.get("rooms", {}).items():
            room_states[room_id] = {
                "searched": room_data.get("searched", False),
                "enemies": room_data.get("enemies", [])
            }

        return room_states

    def _deserialize_game_state(
        self,
        save_data: Dict[str, Any],
        event_bus: Optional[EventBus],
        data_loader: Optional[DataLoader],
        dice_roller: Optional[DiceRoller]
    ) -> GameState:
        """
        Deserialize game state from save data.

        Args:
            save_data: Save data dictionary
            event_bus: Event bus for the game
            data_loader: Data loader for content
            dice_roller: Dice roller

        Returns:
            Reconstructed GameState
        """
        # Create party from saved characters
        characters = [
            self._deserialize_character(char_data)
            for char_data in save_data["party"]
        ]
        party = Party(characters)

        # Get game state data
        gs_data = save_data["game_state"]

        # Create game state (this loads fresh dungeon)
        game_state = GameState(
            party=party,
            dungeon_name=gs_data["dungeon_name"],
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller
        )

        # Restore room-specific state
        room_states = gs_data.get("dungeon_state", {})
        for room_id, room_state in room_states.items():
            if room_id in game_state.dungeon["rooms"]:
                game_state.dungeon["rooms"][room_id]["searched"] = room_state.get("searched", False)
                game_state.dungeon["rooms"][room_id]["enemies"] = room_state.get("enemies", [])

        # Restore current position
        game_state.current_room_id = gs_data["current_room_id"]

        # Restore action history
        game_state.action_history = gs_data.get("action_history", [])

        # Restore navigation tracking
        game_state.last_entry_direction = gs_data.get("last_entry_direction")

        # Note: We don't restore combat state - if saved during combat, it will
        # restart when entering the room
        # This is a simplification for MVP

        return game_state

    def _deserialize_character(self, char_data: Dict[str, Any]) -> Character:
        """
        Deserialize character from save data.

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
            race=char_data["race"]
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
        Deserialize inventory from save data.

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

    def _validate_save_data(self, save_data: Dict[str, Any]) -> None:
        """
        Validate save file structure.

        Args:
            save_data: Save data to validate

        Raises:
            ValueError: If save data is invalid
        """
        required_keys = ["version", "metadata", "party", "game_state"]

        for key in required_keys:
            if key not in save_data:
                raise ValueError(f"Invalid save file: missing '{key}'")

        if not isinstance(save_data["party"], list):
            raise ValueError("Invalid save file: 'party' must be a list")

        if len(save_data["party"]) == 0:
            raise ValueError("Invalid save file: party cannot be empty")

    def _is_compatible_version(self, save_version: str) -> bool:
        """
        Check if save version is compatible with current version.

        Args:
            save_version: Version string from save file

        Returns:
            True if compatible
        """
        # For now, we only support exact version match
        # In the future, this could support migration between versions
        return save_version == SAVE_VERSION

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to remove invalid characters.

        Args:
            filename: Proposed filename

        Returns:
            Sanitized filename
        """
        # Remove invalid filename characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        # Remove leading/trailing spaces and dots
        filename = filename.strip('. ')

        # Ensure it's not empty after sanitization
        if not filename:
            filename = "save"

        return filename
