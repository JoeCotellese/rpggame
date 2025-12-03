# ABOUTME: Save slot manager for the new 10-slot save system
# ABOUTME: Handles save/load operations, slot management, and game state persistence

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dnd_engine.core.character_vault_v2 import CharacterVaultV2

from dnd_engine.core.campaign_progress import CampaignProgress
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.save_slot import SaveSlot
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.currency import Currency
from dnd_engine.systems.inventory import EquipmentSlot, Inventory
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.utils.events import Event, EventBus, EventType

# Current save file version
SAVE_VERSION = "2.0.0"


class SaveSlotManager:
    """
    Manages the 10-slot save system.

    Responsibilities:
    - Initialize 10 save slots (slot_01.json through slot_10.json)
    - Save game state to a specific slot
    - Load game state from a specific slot
    - List all slots with metadata
    - Update slot metadata (names, playtime, etc.)
    - Handle auto-save integration
    """

    def __init__(self, saves_dir: Path | None = None):
        """
        Initialize save slot manager.

        Args:
            saves_dir: Directory for save files (defaults to ~/.dnd_game/saves/)
        """
        if saves_dir is None:
            saves_dir = Path.home() / ".dnd_game" / "saves"

        self.saves_dir = Path(saves_dir)
        self.saves_dir.mkdir(parents=True, exist_ok=True)

        # Ensure all 10 slots exist
        self._initialize_slots()

    def _initialize_slots(self) -> None:
        """Create empty slot files for any missing slots."""
        for slot_num in range(1, 11):
            slot_path = self.saves_dir / f"slot_{slot_num:02d}.json"

            if not slot_path.exists():
                # Create empty slot
                empty_slot = SaveSlot.create_empty(slot_num)
                self._save_slot_file(slot_num, empty_slot, game_state=None)

    def _get_slot_path(self, slot_number: int) -> Path:
        """
        Get the file path for a slot number.

        Args:
            slot_number: Slot number (1-10)

        Returns:
            Path to the slot file

        Raises:
            ValueError: If slot number is out of range
        """
        if not 1 <= slot_number <= 10:
            raise ValueError(f"Slot number must be between 1 and 10, got {slot_number}")

        return self.saves_dir / f"slot_{slot_number:02d}.json"

    def list_slots(self) -> list[SaveSlot]:
        """
        List all save slots with metadata.

        Returns:
            List of SaveSlot instances (slots 1-10)
        """
        slots = []

        for slot_num in range(1, 11):
            try:
                slot_path = self._get_slot_path(slot_num)

                if not slot_path.exists():
                    # Create empty slot if missing
                    empty_slot = SaveSlot.create_empty(slot_num)
                    slots.append(empty_slot)
                    continue

                with open(slot_path, encoding="utf-8") as f:
                    slot_data = json.load(f)

                # Extract metadata
                metadata = slot_data.get("metadata", {})
                slot = SaveSlot.from_dict(metadata)
                slots.append(slot)

            except (json.JSONDecodeError, KeyError, ValueError):
                # Corrupted slot - treat as empty
                empty_slot = SaveSlot.create_empty(slot_num)
                slots.append(empty_slot)

        return slots

    def get_slot(self, slot_number: int) -> SaveSlot:
        """
        Get metadata for a specific slot.

        Args:
            slot_number: Slot number (1-10)

        Returns:
            SaveSlot instance with metadata

        Raises:
            ValueError: If slot number is out of range
        """
        slot_path = self._get_slot_path(slot_number)

        if not slot_path.exists():
            return SaveSlot.create_empty(slot_number)

        try:
            with open(slot_path, encoding="utf-8") as f:
                slot_data = json.load(f)

            metadata = slot_data.get("metadata", {})
            return SaveSlot.from_dict(metadata)

        except (json.JSONDecodeError, KeyError, ValueError):
            # Corrupted slot - treat as empty
            return SaveSlot.create_empty(slot_number)

    def save_game(
        self,
        slot_number: int,
        game_state: GameState,
        playtime_delta: int = 0,
        campaign_progress: CampaignProgress | None = None,
        character_vault: CharacterVaultV2 | None = None,
    ) -> Path:
        """
        Save game state to a specific slot.

        Args:
            slot_number: Slot number (1-10)
            game_state: Current game state to save
            playtime_delta: Seconds to add to playtime (for this session)
            campaign_progress: Optional campaign progress for multi-dungeon campaigns
            character_vault: Optional vault to sync character progression to

        Returns:
            Path to the saved file

        Raises:
            ValueError: If slot number is out of range
        """
        # Load existing slot metadata (or create new)
        slot = self.get_slot(slot_number)

        # Update slot metadata
        now = datetime.now()

        if slot.is_empty():
            # First time saving to this slot
            slot.created_at = now
            slot.playtime_seconds = playtime_delta
        else:
            # Update existing slot
            slot.playtime_seconds += playtime_delta

        slot.last_played = now

        # Extract adventure info from game state
        slot.adventure_name = self._get_adventure_display_name(game_state.dungeon_name)
        slot.adventure_progress = self._get_progress_description(game_state)

        # Extract party info
        slot.party_composition = [char.name for char in game_state.party.characters]
        slot.party_levels = [char.level for char in game_state.party.characters]

        # Sync character progression to vault if provided
        if character_vault:
            self._sync_characters_to_vault(game_state, character_vault)

        # Save to file
        return self._save_slot_file(slot_number, slot, game_state, campaign_progress)

    def load_game(
        self,
        slot_number: int,
        event_bus: EventBus | None = None,
        data_loader: DataLoader | None = None,
        dice_roller: DiceRoller | None = None,
    ) -> tuple[GameState, CampaignProgress | None]:
        """
        Load game state from a specific slot.

        Args:
            slot_number: Slot number (1-10)
            event_bus: Event bus for the game (creates new if not provided)
            data_loader: Data loader for content (creates new if not provided)
            dice_roller: Dice roller (creates new if not provided)

        Returns:
            Tuple of (GameState, CampaignProgress or None)

        Raises:
            ValueError: If slot number is out of range or slot is empty
            FileNotFoundError: If slot file doesn't exist
        """
        slot_path = self._get_slot_path(slot_number)

        if not slot_path.exists():
            raise FileNotFoundError(f"Slot {slot_number} not found")

        # Read slot file
        try:
            with open(slot_path, encoding="utf-8") as f:
                slot_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupted slot file: {e}")

        # Check if slot is empty
        metadata = slot_data.get("metadata", {})
        if not metadata.get("adventure_name"):
            raise ValueError(f"Slot {slot_number} is empty")

        # Validate save file
        self._validate_slot_data(slot_data)

        # Check version compatibility
        save_version = slot_data.get("version", "1.0.0")
        if not self._is_compatible_version(save_version):
            raise ValueError(
                f"Incompatible save version: {save_version} (current version: {SAVE_VERSION})"
            )

        # Deserialize game state
        game_state = self._deserialize_game_state(slot_data, event_bus, data_loader, dice_roller)

        # Deserialize campaign progress if present
        campaign_progress = None
        if "campaign_progress" in slot_data:
            campaign_progress = CampaignProgress.from_dict(slot_data["campaign_progress"])

        # Update last_played timestamp
        slot_data["metadata"]["last_played"] = datetime.now().isoformat()
        with open(slot_path, "w", encoding="utf-8") as f:
            json.dump(slot_data, f, indent=2, ensure_ascii=False)

        return game_state, campaign_progress

    def clear_slot(self, slot_number: int) -> None:
        """
        Clear a slot (reset to empty).

        Args:
            slot_number: Slot number (1-10)

        Raises:
            ValueError: If slot number is out of range
        """
        empty_slot = SaveSlot.create_empty(slot_number)
        self._save_slot_file(slot_number, empty_slot, game_state=None)

    def rename_slot(self, slot_number: int, custom_name: str) -> None:
        """
        Set a custom name for a slot.

        Args:
            slot_number: Slot number (1-10)
            custom_name: Custom display name (use empty string to clear)

        Raises:
            ValueError: If slot number is out of range
        """
        slot = self.get_slot(slot_number)
        slot.custom_name = custom_name if custom_name.strip() else None

        # Load full slot data and update metadata
        slot_path = self._get_slot_path(slot_number)

        with open(slot_path, encoding="utf-8") as f:
            slot_data = json.load(f)

        slot_data["metadata"]["custom_name"] = slot.custom_name

        with open(slot_path, "w", encoding="utf-8") as f:
            json.dump(slot_data, f, indent=2, ensure_ascii=False)

    def _save_slot_file(
        self,
        slot_number: int,
        slot: SaveSlot,
        game_state: GameState | None,
        campaign_progress: CampaignProgress | None = None,
    ) -> Path:
        """
        Save slot data and game state to disk.

        Args:
            slot_number: Slot number (1-10)
            slot: SaveSlot metadata
            game_state: Optional game state (None for empty slots)
            campaign_progress: Optional campaign progress for multi-dungeon campaigns

        Returns:
            Path to the saved file
        """
        slot_path = self._get_slot_path(slot_number)

        # Build slot file structure
        slot_data = {
            "version": SAVE_VERSION,
            "metadata": slot.to_dict(),
        }

        if game_state:
            # Include full game state
            slot_data["party"] = [
                self._serialize_character(char) for char in game_state.party.characters
            ]
            slot_data["game_state"] = {
                "dungeon_name": game_state.dungeon_name,
                "campaign_id": game_state.campaign_id,
                "current_room_id": game_state.current_room_id,
                "dungeon_state": self._serialize_dungeon_state(game_state.dungeon),
                "all_dungeon_states": self._serialize_all_dungeon_states(game_state),
                "in_combat": game_state.in_combat,
                "action_history": game_state.action_history,
                "last_entry_direction": game_state.last_entry_direction,
            }
            # Include campaign progress if present
            if campaign_progress:
                slot_data["campaign_progress"] = campaign_progress.to_dict()

            # Include quest states if quest manager is active
            if game_state.quest_manager:
                slot_data["quest_states"] = game_state.quest_manager.serialize_states()
                slot_data["quest_objective_states"] = (
                    game_state.quest_manager.serialize_objective_states()
                )
        else:
            # Empty slot
            slot_data["party"] = []
            slot_data["game_state"] = {}

        # Write to disk
        with open(slot_path, "w", encoding="utf-8") as f:
            json.dump(slot_data, f, indent=2, ensure_ascii=False)

        return slot_path

    def _get_adventure_display_name(self, dungeon_filename: str) -> str:
        """
        Get display name for an adventure/dungeon.

        Args:
            dungeon_filename: Dungeon filename (e.g., 'tomb_of_horrors')

        Returns:
            Human-readable name (e.g., 'Tomb of Horrors')
        """
        if not dungeon_filename:
            return "Unknown Adventure"

        # Convert snake_case to Title Case
        return dungeon_filename.replace("_", " ").title()

    def _get_progress_description(self, game_state: GameState) -> str:
        """
        Get progress description for a game state.

        Args:
            game_state: Current game state

        Returns:
            Progress description (e.g., 'Room 12', 'Entrance Hall')
        """
        if game_state.current_room_id:
            # Try to get room name from dungeon data
            room_data = game_state.dungeon.get("rooms", {}).get(game_state.current_room_id, {})
            room_name = room_data.get("name")

            if room_name:
                return room_name
            else:
                return f"Room {game_state.current_room_id}"

        return "Just Started"

    def _serialize_character(self, character: Character) -> dict[str, Any]:
        """Serialize a character to a dictionary."""
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
            "tool_proficiencies": character.tool_proficiencies,
            "spellcasting_ability": character.spellcasting_ability,
            "known_spells": character.known_spells,
            "prepared_spells": character.prepared_spells,
            "vault_id": character.vault_id,
            "darkvision_range": character.darkvision_range,
        }

    def _serialize_inventory(self, inventory: Inventory) -> dict[str, Any]:
        """Serialize inventory to a dictionary."""
        return {
            "items": [
                {
                    "item_id": item.item_id,
                    "category": item.category,
                    "quantity": item.quantity,
                    "quest_item": item.quest_item,
                }
                for item in inventory.items.values()
            ],
            "equipped": {
                "weapon": inventory.equipped[EquipmentSlot.WEAPON],
                "armor": inventory.equipped[EquipmentSlot.ARMOR],
            },
            "currency": asdict(inventory.currency),
        }

    def _serialize_resource_pools(self, character: Character) -> list[dict[str, Any]]:
        """Serialize character resource pools to a list of dictionaries."""
        return [
            {
                "name": pool.name,
                "current": pool.current,
                "maximum": pool.maximum,
                "recovery_type": pool.recovery_type,
            }
            for pool in character.resource_pools.values()
        ]

    def _serialize_dungeon_state(self, dungeon: dict[str, Any]) -> dict[str, Any]:
        """Serialize dungeon state (room modifications)."""
        room_states = {}

        for room_id, room_data in dungeon.get("rooms", {}).items():
            room_states[room_id] = {
                "searched": room_data.get("searched", False),
                "enemies": room_data.get("enemies", []),
                "items": room_data.get("items", []),
            }

        return room_states

    def _serialize_all_dungeon_states(self, game_state: GameState) -> dict[str, dict[str, Any]]:
        """
        Serialize room states for ALL loaded dungeons.

        This ensures that when traveling between dungeons, cleared rooms
        and collected items are preserved across save/load cycles.

        Args:
            game_state: Current game state with room_registry

        Returns:
            Dictionary mapping dungeon names to their room states
        """
        all_states: dict[str, dict[str, Any]] = {}

        # Always include current dungeon
        all_states[game_state.dungeon_name] = self._serialize_dungeon_state(game_state.dungeon)

        # Include all other loaded dungeons from registry
        if game_state.room_registry:
            for dungeon_name, dungeon_data in game_state.room_registry._loaded_dungeons.items():
                if dungeon_name != game_state.dungeon_name:
                    all_states[dungeon_name] = self._serialize_dungeon_state(dungeon_data)

        return all_states

    def _restore_all_dungeon_states(
        self, game_state: GameState, all_dungeon_states: dict[str, dict[str, Any]]
    ) -> None:
        """
        Restore room states for all dungeons to the room registry.

        This pre-populates the room registry cache with modified dungeon states
        so that when the player travels to a previously visited dungeon,
        cleared rooms and collected items are preserved.

        Args:
            game_state: Game state with room_registry to populate
            all_dungeon_states: Saved states for all dungeons
        """
        if not game_state.room_registry:
            return

        for dungeon_name, room_states in all_dungeon_states.items():
            # Skip current dungeon - already handled
            if dungeon_name == game_state.dungeon_name:
                continue

            # Load the dungeon into registry cache
            dungeon_data = game_state.room_registry.load_dungeon(dungeon_name)
            if not dungeon_data:
                continue

            # Apply saved room states
            for room_id, room_state in room_states.items():
                if room_id in dungeon_data.get("rooms", {}):
                    dungeon_data["rooms"][room_id]["searched"] = room_state.get("searched", False)
                    dungeon_data["rooms"][room_id]["enemies"] = room_state.get("enemies", [])
                    dungeon_data["rooms"][room_id]["items"] = room_state.get("items", [])

    def _deserialize_game_state(
        self,
        slot_data: dict[str, Any],
        event_bus: EventBus | None,
        data_loader: DataLoader | None,
        dice_roller: DiceRoller | None,
    ) -> GameState:
        """Deserialize game state from slot data."""
        # Create party from saved characters
        characters = [self._deserialize_character(char_data) for char_data in slot_data["party"]]
        party = Party(characters)

        # Get game state data
        gs_data = slot_data["game_state"]

        # Create game state (this loads fresh dungeon)
        # Skip initial ROOM_ENTER - we'll fire it after restoring quest states
        game_state = GameState(
            party=party,
            dungeon_name=gs_data["dungeon_name"],
            campaign_id=gs_data.get("campaign_id"),
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller,
            skip_initial_room_enter=True,
        )

        # Restore room-specific state for current dungeon
        room_states = gs_data.get("dungeon_state", {})
        for room_id, room_state in room_states.items():
            if room_id in game_state.dungeon["rooms"]:
                game_state.dungeon["rooms"][room_id]["searched"] = room_state.get("searched", False)
                game_state.dungeon["rooms"][room_id]["enemies"] = room_state.get("enemies", [])
                game_state.dungeon["rooms"][room_id]["items"] = room_state.get("items", [])

        # Restore room states for ALL other dungeons visited during session
        # This ensures cleared rooms stay cleared after save/load
        all_dungeon_states = gs_data.get("all_dungeon_states", {})
        self._restore_all_dungeon_states(game_state, all_dungeon_states)

        # Restore current position
        game_state.current_room_id = gs_data["current_room_id"]

        # Restore action history
        game_state.action_history = gs_data.get("action_history", [])

        # Restore navigation tracking
        game_state.last_entry_direction = gs_data.get("last_entry_direction")

        # Restore quest states if present
        if game_state.quest_manager and "quest_states" in slot_data:
            game_state.quest_manager.deserialize_states(slot_data["quest_states"])

        # Restore quest objective states if present
        if game_state.quest_manager and "quest_objective_states" in slot_data:
            game_state.quest_manager.deserialize_objective_states(
                slot_data["quest_objective_states"]
            )

        # Fire ROOM_ENTER event for the loaded position
        # This ensures discover objectives trigger for the restored room
        game_state.event_bus.emit(
            Event(
                type=EventType.ROOM_ENTER,
                data={
                    "room_id": game_state.current_room_id,
                    "room_name": game_state.get_current_room().get("name", ""),
                    "dungeon_id": game_state.dungeon_name,
                },
            )
        )

        return game_state

    def _deserialize_character(self, char_data: dict[str, Any]) -> Character:
        """Deserialize character from save data."""
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
            saving_throw_proficiencies=char_data.get("saving_throw_proficiencies", []),
            skill_proficiencies=char_data.get("skill_proficiencies", []),
            expertise_skills=char_data.get("expertise_skills", []),
            weapon_proficiencies=char_data.get("weapon_proficiencies", []),
            armor_proficiencies=char_data.get("armor_proficiencies", []),
            tool_proficiencies=char_data.get("tool_proficiencies", []),
            spellcasting_ability=char_data.get("spellcasting_ability"),
            known_spells=char_data.get("known_spells"),
            prepared_spells=char_data.get("prepared_spells"),
            vault_id=char_data.get("vault_id"),
        )

        # Restore darkvision range
        character.darkvision_range = char_data.get("darkvision_range", 0)

        # Restore conditions
        for condition in char_data.get("conditions", []):
            character.add_condition(condition)

        # Restore resource pools
        for pool_data in char_data.get("resource_pools", []):
            pool = ResourcePool(**pool_data)
            character.add_resource_pool(pool)

        return character

    def _deserialize_inventory(self, inv_data: dict[str, Any]) -> Inventory:
        """Deserialize inventory from save data."""
        inventory = Inventory()

        # Restore items
        for item_data in inv_data.get("items", []):
            inventory.add_item(
                item_id=item_data["item_id"],
                category=item_data["category"],
                quantity=item_data["quantity"],
                quest_item=item_data.get("quest_item", False),
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

    def _sync_characters_to_vault(
        self, game_state: GameState, character_vault: CharacterVaultV2
    ) -> None:
        """
        Sync character progression to the vault.

        Updates vault entries for characters that have vault_ids with their
        current XP, level, gold, and permanent items.

        Args:
            game_state: Current game state with party
            character_vault: Vault to sync to
        """
        for character in game_state.party.characters:
            if character.vault_id:
                try:
                    character_vault.update_character(character.vault_id, character)
                except FileNotFoundError:
                    # Character was deleted from vault, skip sync
                    pass

    def _validate_slot_data(self, slot_data: dict[str, Any]) -> None:
        """
        Validate slot file structure.

        Args:
            slot_data: Slot data to validate

        Raises:
            ValueError: If slot data is invalid
        """
        required_keys = ["version", "metadata", "party", "game_state"]

        for key in required_keys:
            if key not in slot_data:
                raise ValueError(f"Invalid slot file: missing '{key}'")

        if not isinstance(slot_data["party"], list):
            raise ValueError("Invalid slot file: 'party' must be a list")

    def _is_compatible_version(self, save_version: str) -> bool:
        """
        Check if save version is compatible with current version.

        Args:
            save_version: Version string from save file

        Returns:
            True if compatible
        """
        # For now, we support both v1.0.0 (old) and v2.0.0 (new)
        # Migration will convert v1.0.0 to v2.0.0
        return save_version in ["1.0.0", "2.0.0"]
